#!/usr/bin/env bash
# Check: pyproject.toml sets `[tool.uv].exclude-newer` to a rolling
# quarantine of at least 7 days.
#
# Rationale (Canonical Security "How-To: Secure a repo" — Minimum
# release age section): a package-manager-level cooldown protects
# every dep-resolution path (manual `uv add`, `uv lock` regens, uvx
# bootstraps, CI re-resolves) that Dependabot cooldown alone doesn't
# cover — Dependabot cooldown only affects PRs Dependabot itself opens.
#
# uv's `exclude-newer` accepts three formats per the docs:
#   - RFC 3339 timestamps (absolute snapshot; e.g. 2026-01-01T00:00:00Z)
#   - Friendly durations (rolling window; e.g. "7 days", "1 week")
#   - ISO 8601 durations (rolling window; e.g. "P7D", "P30D")
#
# Prefer a rolling window ("7 days" / "P7D"). Absolute timestamps also
# accepted but flagged in evidence: they freeze resolution to a moment
# and drift silently as they age.
#
# Tier coverage: all tiers.
# `na` when there's no `pyproject.toml`, no `[tool.uv]`, or (for tiers
# where uv isn't in use) no `uv.lock`.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="uv-exclude-newer"
APPLIES="product,canonical,personal"
MIN_DAYS=7

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

if [ ! -f pyproject.toml ]; then
    emit_check "$CHECK_ID" "na" "No pyproject.toml — not a uv project."
    exit 2
fi

# Parse [tool.uv] and inspect exclude-newer. Needs python3+tomllib
# (stdlib in 3.11+) — fall back to a text-only presence check when the
# parser isn't available.
have_parser=false
if command -v python3 >/dev/null 2>&1 && \
   python3 -c 'import tomllib' 2>/dev/null; then
    have_parser=true
fi

if [ "$have_parser" = "false" ]; then
    # Fallback: presence check on `exclude-newer` inside `[tool.uv]`.
    # This is intentionally cheap; agents on hosts without Python 3.11+
    # can still get a signal.
    if grep -qE '^\s*exclude-newer\s*=' pyproject.toml && \
       grep -qE '^\[tool\.uv\]' pyproject.toml; then
        emit_check "$CHECK_ID" "pass" \
            "exclude-newer present in pyproject.toml (value not validated — python3+tomllib unavailable)." \
            '{"parser":false,"exclude_newer_present":true}'
        exit 0
    fi
    emit_check "$CHECK_ID" "fail" \
        "No exclude-newer found under [tool.uv] in pyproject.toml (unvalidated fallback)." \
        '{"parser":false,"exclude_newer_present":false}' \
        '{"kind":"judgement","human_review":"Add `exclude-newer = \"7 days\"` under [tool.uv] in pyproject.toml. Prefer a friendly-duration string (rolling window) over an RFC 3339 timestamp (absolute snapshot). See Canonical Security \"How-To: Secure a repo\" — Minimum release age."}'
    exit 1
fi

result=$(MIN_DAYS="$MIN_DAYS" python3 - <<'PY' 2>/dev/null
import json, os, re, sys
try:
    import tomllib
except Exception:
    print("PARSE_ERROR import tomllib failed")
    sys.exit(0)

MIN_DAYS = int(os.environ["MIN_DAYS"])

try:
    with open("pyproject.toml", "rb") as f:
        doc = tomllib.load(f)
except Exception as e:
    print(f"PARSE_ERROR {e}")
    sys.exit(0)

tool_uv = (doc.get("tool") or {}).get("uv")
if tool_uv is None:
    print("NO_TOOL_UV")
    sys.exit(0)
if "exclude-newer" not in tool_uv:
    print("MISSING")
    sys.exit(0)

value = tool_uv["exclude-newer"]
if not isinstance(value, str):
    print(f"UNKNOWN_TYPE {type(value).__name__} {value!r}")
    sys.exit(0)

# Classify the value:
#   RFC3339 timestamp: contains 'T' and ends with 'Z' or timezone offset.
#   ISO 8601 duration: matches /^P(?:\d+[YMWD])+(?:T(?:\d+[HMS])+)?$/ or PT...
#   Friendly duration: matches a number + unit word (hours/days/weeks/etc.)
def parse_days(v: str):
    v = v.strip()
    # RFC 3339 timestamp
    if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', v):
        return ("snapshot", None)
    # ISO 8601 duration
    m = re.match(r'^P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$', v)
    if m:
        y, mo, w, d, h, mi, s = (int(x) if x else 0 for x in m.groups())
        # Approx: month=30d, year=365d.
        days = y*365 + mo*30 + w*7 + d + h/24 + mi/1440 + s/86400
        return ("iso8601", days)
    # Friendly duration: parse "N unit" tokens; sum in days.
    unit_days = {
        "second": 1/86400, "seconds": 1/86400, "sec": 1/86400, "s": 1/86400,
        "minute": 1/1440, "minutes": 1/1440, "min": 1/1440, "m": 1/1440,
        "hour": 1/24, "hours": 1/24, "hr": 1/24, "hrs": 1/24, "h": 1/24,
        "day": 1, "days": 1, "d": 1,
        "week": 7, "weeks": 7, "w": 7,
        "month": 30, "months": 30, "mon": 30, "mo": 30,
        "year": 365, "years": 365, "yr": 365, "y": 365,
    }
    total = 0
    matched = False
    for num, unit in re.findall(r'(\d+(?:\.\d+)?)\s*([A-Za-z]+)', v):
        u = unit.lower().rstrip('.')
        if u not in unit_days:
            return ("unknown", None)
        total += float(num) * unit_days[u]
        matched = True
    if matched:
        return ("friendly", total)
    return ("unknown", None)

kind, days = parse_days(value)
print(f"FOUND kind={kind} days={days if days is not None else 'None'} value={value!r}")
PY
)

first_line=$(printf '%s' "$result" | head -1)

case "$first_line" in
    PARSE_ERROR*)
        emit_check "$CHECK_ID" "unknown" \
            "Could not parse pyproject.toml: ${first_line#PARSE_ERROR }" \
            '{"parser":true}'
        exit 3
        ;;
    NO_TOOL_UV)
        # A uv.lock in the working tree means the project uses uv even
        # though pyproject.toml doesn't declare [tool.uv] yet — that's
        # a fail (add the section), not na.
        if [ -f uv.lock ]; then
            emit_check "$CHECK_ID" "fail" \
                "uv.lock present but pyproject.toml has no [tool.uv] section. Add [tool.uv] with exclude-newer = \"${MIN_DAYS} days\"." \
                '{"parser":true,"tool_uv":false,"uv_lock_present":true}' \
                '{"kind":"judgement","human_review":"Add [tool.uv] to pyproject.toml with `exclude-newer = \"7 days\"`. This gives every uv resolution path (manual uv add, uv lock regens, uvx bootstraps, CI re-resolves) a rolling 7-day quarantine on fresh releases — complementing the Dependabot cooldown that only covers Dependabot-authored PRs. See Canonical Security \"How-To: Secure a repo\" — Minimum release age."}'
            exit 1
        fi
        emit_check "$CHECK_ID" "na" \
            "pyproject.toml has no [tool.uv] section and no uv.lock — not a uv-configured project." \
            '{"parser":true,"tool_uv":false,"uv_lock_present":false}'
        exit 2
        ;;
    MISSING)
        emit_check "$CHECK_ID" "fail" \
            "[tool.uv] present but exclude-newer not set. Add exclude-newer = \"${MIN_DAYS} days\" to give every uv resolution path (manual uv add, uv lock, uvx, CI re-resolves) a rolling ${MIN_DAYS}-day quarantine on fresh releases." \
            '{"parser":true,"tool_uv":true,"exclude_newer_present":false}' \
            '{"kind":"judgement","human_review":"Add `exclude-newer = \"7 days\"` under [tool.uv] in pyproject.toml. Prefer a friendly-duration string (rolling window) over an RFC 3339 timestamp (absolute snapshot). See Canonical Security \"How-To: Secure a repo\" — Minimum release age."}'
        exit 1
        ;;
    UNKNOWN_TYPE*)
        emit_check "$CHECK_ID" "fail" \
            "[tool.uv].exclude-newer is not a string: ${first_line#UNKNOWN_TYPE }" \
            '{"parser":true}' \
            '{"kind":"judgement","human_review":"Set exclude-newer to a string, e.g. \"7 days\"."}'
        exit 1
        ;;
    FOUND*)
        # Extract fields.
        kind=$(printf '%s' "$first_line" | sed -n 's/.*kind=\([A-Za-z0-9]*\).*/\1/p')
        days=$(printf '%s' "$first_line" | sed -n 's/.*days=\([0-9.]*\|None\).*/\1/p')
        value=$(printf '%s' "$first_line" | sed -n "s/.*value=\('.*'\|\".*\"\).*/\1/p")

        evidence=$(printf '{"parser":true,"exclude_newer_kind":"%s","exclude_newer_value":%s,"exclude_newer_days":%s}' \
            "$kind" "$(printf '%s' "$value" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read().strip().strip("\"").strip("\047")))')" \
            "${days:-null}")

        case "$kind" in
            snapshot)
                emit_check "$CHECK_ID" "pass" \
                    "exclude-newer set to an RFC 3339 timestamp (absolute snapshot). Accepted but note: this freezes resolution to a moment and drifts silently as time passes; prefer a rolling friendly-duration like \"${MIN_DAYS} days\"." \
                    "$evidence"
                exit 0
                ;;
            iso8601|friendly)
                days_int=${days%.*}
                if [ "${days_int:-0}" -ge "$MIN_DAYS" ] 2>/dev/null; then
                    emit_check "$CHECK_ID" "pass" \
                        "exclude-newer = ${value} (${kind}, ≈${days} days). Rolling ≥${MIN_DAYS}-day quarantine." \
                        "$evidence"
                    exit 0
                fi
                emit_check "$CHECK_ID" "fail" \
                    "exclude-newer = ${value} (${kind}, ≈${days} days) is below the ${MIN_DAYS}-day baseline." \
                    "$evidence" \
                    '{"kind":"judgement","human_review":"Widen exclude-newer to at least \"7 days\" to match the Charm Tech baseline and the existing Dependabot cooldown."}'
                exit 1
                ;;
            unknown|*)
                emit_check "$CHECK_ID" "fail" \
                    "exclude-newer = ${value} did not parse as an RFC 3339 timestamp, ISO 8601 duration, or friendly duration." \
                    "$evidence" \
                    '{"kind":"judgement","human_review":"Set exclude-newer to a friendly duration like \"7 days\" per the uv docs."}'
                exit 1
                ;;
        esac
        ;;
    *)
        emit_check "$CHECK_ID" "unknown" \
            "Unexpected parser output: $first_line" \
            '{"parser":true}'
        exit 3
        ;;
esac
