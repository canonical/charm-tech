#!/usr/bin/env bash
# Check: SBOM workflow / manifest present and triggered per cycle.
# Tier coverage: product only.
#
# Mandate: SEC0027 (every release type). Generated via sbom-request.canonical.com.
# Some repos carry an in-repo manifest (.sbomber-manifest-*.yaml); some
# integrate the SBOM request as a CI workflow step.
#
# A `workflow_dispatch:`-only workflow satisfies presence but not cadence —
# SBOM must be regenerated every release / cycle. Pass requires at least one
# of the cadence triggers: `release`, `schedule`, or tag-pushes
# (`push: tags:` or `push: branches:` + `tags:` filter). Manifests-only repos
# are accepted unconditionally — the manifest is consumed by an external
# sbom-request pipeline that owns its own cadence.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="sbom-workflow"
APPLIES="product"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

manifests=$(find .github -maxdepth 2 \( -name '*sbomber-manifest*.y*ml' -o -name 'sbom*.y*ml' \) 2>/dev/null | head -3 || true)
workflow=""
if [ -d .github/workflows ]; then
    workflow=$(grep -lEi 'sbom-request|sbomber|sbom-secscan' .github/workflows/*.y*ml 2>/dev/null | head -1 || true)
fi

if [ -z "$manifests" ] && [ -z "$workflow" ]; then
    emit_check "$CHECK_ID" "fail" \
        "No SBOM workflow or manifest found." \
        '{}' \
        '{"kind":"judgement","human_review":"Request SBOM via sbom-request.canonical.com Web UI or REST API; store in the SSDLC Artifacts directory and request review in ~SSDLC. Add a CI step that triggers SBOM generation per release if useful."}'
    exit 1
fi

# Cadence validation only when a workflow is present (manifests are
# externally orchestrated).
cadence_ok=true
cadence_reason=""
if [ -n "$workflow" ]; then
    # Parse the `on:` block. Accept either:
    #   - release: types: [published|created|released] (or just `release:`)
    #   - schedule:
    #   - push: tags: ['v*'] (or any tag pattern)
    # `workflow_dispatch` alone does NOT satisfy cadence.
    if command -v python3 >/dev/null 2>&1 && python3 -c 'import yaml' 2>/dev/null; then
        cadence_check=$(WF="$workflow" python3 - <<'PY' 2>/dev/null
import os, sys
import yaml
path = os.environ["WF"]
try:
    with open(path) as f:
        doc = yaml.safe_load(f)
except Exception as e:
    print(f"PARSE_ERROR {e}")
    sys.exit(0)
# GitHub Actions parses `on:` as boolean True (the yaml token `on`), so
# PyYAML maps the key to the boolean True, not the string "on".
on = doc.get(True) if isinstance(doc, dict) else None
if on is None and isinstance(doc, dict):
    on = doc.get("on")
if on is None:
    print("MISSING_ON")
    sys.exit(0)
if isinstance(on, str):
    on = {on: None}
elif isinstance(on, list):
    on = {k: None for k in on}
if not isinstance(on, dict):
    print("UNKNOWN_ON_SHAPE")
    sys.exit(0)
triggers = set(on.keys())
if "release" in triggers or "schedule" in triggers:
    print("OK")
    sys.exit(0)
push = on.get("push")
if isinstance(push, dict) and ("tags" in push or "tags-ignore" in push):
    print("OK")
    sys.exit(0)
# Anything else (workflow_dispatch only, pull_request, push without tags)
# does not satisfy cadence.
print("NO_CADENCE " + ",".join(sorted(triggers)))
PY
)
        case "$cadence_check" in
            OK)
                : ;;
            NO_CADENCE*)
                cadence_ok=false
                cadence_reason="workflow triggers (${cadence_check#NO_CADENCE }) include no cadence trigger (release / schedule / push: tags)" ;;
            MISSING_ON|UNKNOWN_ON_SHAPE|PARSE_ERROR*)
                cadence_ok=false
                cadence_reason="could not parse workflow triggers ($cadence_check)" ;;
        esac
    else
        # Fallback grep — be lenient since we can't parse properly.
        if ! grep -qE '^[[:space:]]*(release|schedule):' "$workflow" \
           && ! grep -qzoE 'push:[[:space:]]*\n[[:space:]]+tags:' "$workflow"; then
            cadence_ok=false
            cadence_reason="no release/schedule/push-tags trigger found (grep fallback; install python3+PyYAML for accurate check)"
        fi
    fi
fi

found=$(printf '%s' "${manifests} ${workflow}" | tr '\n' ',' | sed 's/,$//' | sed 's/^ //; s/ $//')

if [ "$cadence_ok" = "true" ]; then
    emit_check "$CHECK_ID" "pass" \
        "SBOM workflow / manifest present with per-cycle cadence." \
        "{\"found\":\"$found\"}"
    exit 0
fi

emit_check "$CHECK_ID" "fail" \
    "SBOM workflow present but cadence not guaranteed: $cadence_reason." \
    "{\"found\":\"$found\",\"workflow\":\"$workflow\"}" \
    '{"kind":"judgement","human_review":"SBOM must regenerate per release/cycle. Add `on: release: types: [published]` (preferred for release-cut workflows) or `on: schedule:` (for unreleased products) or `on: push: tags: [v*]`. workflow_dispatch alone is not sufficient."}'
exit 1
