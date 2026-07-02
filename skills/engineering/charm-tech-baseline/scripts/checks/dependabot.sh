#!/usr/bin/env bash
# Check: .github/dependabot.yml exists, declares package ecosystems, and each
# ecosystem has a cooldown of at least 7 days (Charm Tech baseline — see
# charmlibs#499). The cooldown delays raising a PR for a freshly published
# release so a malicious upload caught and yanked inside the window never
# reaches CI.
#
# Tier coverage: product, canonical. (Personal-tier sees this as best-practice
# advisory rather than mandatory.)
#
# Mandate: SEC0025 (Vulnerability Discovery & Identification) — cross-cutting
# requirement for every Canonical repo.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="dependabot"
APPLIES="product,canonical,personal"
MIN_COOLDOWN_DAYS=7

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

found_path=""
for path in .github/dependabot.yml .github/dependabot.yaml; do
    if [ -f "$path" ]; then
        found_path="$path"
        break
    fi
done

if [ -z "$found_path" ]; then
    if [ "$tier" = "personal" ]; then
        emit_check "$CHECK_ID" "fail" \
            "No Dependabot config (personal tier — recommended, not mandated)." \
            '{}' \
            '{"kind":"mechanical","script":"scripts/fixes/add-dependabot.sh","human_review":"Confirm the default ecosystem set matches the repo."}'
        exit 1
    fi
    emit_check "$CHECK_ID" "fail" \
        "No .github/dependabot.yml found (required cross-cutting per SEC0025)." \
        '{}' \
        '{"kind":"mechanical","script":"scripts/fixes/add-dependabot.sh","human_review":"Confirm the default ecosystem set matches the repo (pip/uv, gomod, github-actions, docker)."}'
    exit 1
fi

ecos=$(grep -cE '^[[:space:]]*-[[:space:]]+package-ecosystem:' "$found_path" || true)
if [ "$ecos" -eq 0 ]; then
    emit_check "$CHECK_ID" "fail" \
        "$found_path exists but declares no package-ecosystem entries." \
        "{\"path\":\"$found_path\"}" \
        '{"kind":"judgement","human_review":"Add package-ecosystem blocks for each language/runtime the repo uses (pip/uv, gomod, github-actions, docker)."}'
    exit 1
fi

# Cooldown validation. Needs python3 + PyYAML for a reliable per-ecosystem
# answer; if either is missing, fall back to a presence-only verdict with a
# note in the summary so the agent knows the cooldown was not validated.
have_parser=false
if command -v python3 >/dev/null 2>&1 && python3 -c 'import yaml' 2>/dev/null; then
    have_parser=true
fi

if [ "$have_parser" = "false" ]; then
    # Cheap fallback: at least flag the case where `cooldown:` is entirely absent.
    if ! grep -qE '^[[:space:]]*cooldown:' "$found_path"; then
        emit_check "$CHECK_ID" "fail" \
            "Dependabot configured with $ecos ecosystem(s), but no cooldown: block found (Charm Tech baseline: ≥${MIN_COOLDOWN_DAYS} days)." \
            "{\"path\":\"$found_path\",\"ecosystems\":$ecos,\"cooldown_validated\":false}" \
            '{"kind":"judgement","human_review":"Add a cooldown block to every package-ecosystem entry with default-days/semver-*-days ≥7. See assets/dependabot.yaml.template."}'
        exit 1
    fi
    emit_check "$CHECK_ID" "pass" \
        "Dependabot configured with $ecos ecosystem(s); cooldown present but not validated (python3+PyYAML unavailable)." \
        "{\"path\":\"$found_path\",\"ecosystems\":$ecos,\"cooldown_validated\":false}"
    exit 0
fi

cooldown_result=$(MIN="$MIN_COOLDOWN_DAYS" CFG="$found_path" python3 - <<'PY' 2>/dev/null
import json, os, sys
try:
    import yaml
except Exception:
    print("PARSE_ERROR import yaml failed")
    sys.exit(0)

min_days = int(os.environ["MIN"])
path = os.environ["CFG"]
try:
    with open(path) as f:
        doc = yaml.safe_load(f)
except Exception as e:
    print(f"PARSE_ERROR {e}")
    sys.exit(0)

if not isinstance(doc, dict):
    print("PARSE_ERROR top-level not a mapping")
    sys.exit(0)

updates = doc.get("updates") or []
problems = []  # list of "<ecosystem>@<directory>: <issue>"
for entry in updates:
    if not isinstance(entry, dict):
        continue
    eco = entry.get("package-ecosystem", "?")
    direc = entry.get("directory", entry.get("directories", "?"))
    label = f"{eco}@{direc}"
    cd = entry.get("cooldown")
    if not isinstance(cd, dict):
        problems.append(f"{label}: no cooldown block")
        continue
    # Validate each days key that is present; require at least default-days.
    keys = ("default-days", "semver-major-days", "semver-minor-days", "semver-patch-days")
    if "default-days" not in cd and not any(k in cd for k in keys):
        problems.append(f"{label}: cooldown block present but no *-days field set")
        continue
    for k in keys:
        if k in cd:
            try:
                v = int(cd[k])
            except (TypeError, ValueError):
                problems.append(f"{label}: cooldown.{k} not an integer ({cd[k]!r})")
                continue
            if v < min_days:
                problems.append(f"{label}: cooldown.{k}={v} < {min_days}")

print("OK " + json.dumps({"problems": problems, "ecosystems": len(updates)}))
PY
)

case "$cooldown_result" in
    "PARSE_ERROR "*)
        # Fall through to presence check rather than failing on parse error.
        if ! grep -qE '^[[:space:]]*cooldown:' "$found_path"; then
            emit_check "$CHECK_ID" "fail" \
                "Dependabot configured with $ecos ecosystem(s), but no cooldown: block found and YAML parser errored — could not auto-validate." \
                "{\"path\":\"$found_path\",\"ecosystems\":$ecos,\"cooldown_validated\":false}" \
                '{"kind":"judgement","human_review":"Add a cooldown block to every package-ecosystem entry with default-days/semver-*-days ≥7."}'
            exit 1
        fi
        emit_check "$CHECK_ID" "unknown" \
            "Dependabot present with cooldown block, but YAML parser errored — cooldown values not validated." \
            "{\"path\":\"$found_path\",\"ecosystems\":$ecos,\"cooldown_validated\":false}"
        exit 3 ;;
    "OK "*)
        payload=${cooldown_result#OK }
        # Cheap "is the problems array empty?" check without piping into jq.
        if printf '%s' "$payload" | grep -q '"problems": *\[\]'; then
            emit_check "$CHECK_ID" "pass" \
                "Dependabot configured with $ecos ecosystem(s); cooldown ≥${MIN_COOLDOWN_DAYS} days on every entry." \
                "{\"path\":\"$found_path\",\"ecosystems\":$ecos,\"cooldown_validated\":true}"
            exit 0
        fi
        evidence="{\"path\":\"$found_path\",\"ecosystems\":$ecos,\"cooldown_validated\":true,\"detail\":$payload}"
        emit_check "$CHECK_ID" "fail" \
            "Dependabot present but cooldown below Charm Tech baseline (≥${MIN_COOLDOWN_DAYS} days) on one or more ecosystems." \
            "$evidence" \
            '{"kind":"judgement","human_review":"Set cooldown.default-days (and any per-semver-tier overrides) to at least 7 on every package-ecosystem entry. See assets/dependabot.yaml.template."}'
        exit 1 ;;
    *)
        emit_check "$CHECK_ID" "unknown" \
            "Cooldown parser produced no output." \
            "{\"path\":\"$found_path\",\"ecosystems\":$ecos}"
        exit 3 ;;
esac
