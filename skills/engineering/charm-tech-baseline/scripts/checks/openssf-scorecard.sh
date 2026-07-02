#!/usr/bin/env bash
# Check: OpenSSF Scorecard workflow + README badge.
# Tier coverage: product, canonical. (Operator pilots; rest gated behind
# its adoption — see references/open-investigations.md.)
#
# Pass     — workflow uses ossf/scorecard-action; README has the badge.
# Partial  — workflow OR badge present but not both — emitted as fail with
#            human_review noting which half is missing.
# Fail     — neither present.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="openssf-scorecard"
APPLIES="product,canonical"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

workflow=""
if [ -d .github/workflows ]; then
    workflow=$(grep -lE 'ossf/scorecard-action' .github/workflows/*.y*ml 2>/dev/null | head -1 || true)
fi
badge=""
for readme in README.md README.rst README.txt readme.md; do
    [ -f "$readme" ] || continue
    if grep -qE 'securityscorecards\.dev/projects/github\.com|scorecard\.dev/projects' "$readme"; then
        badge="$readme"
        break
    fi
done

if [ -n "$workflow" ] && [ -n "$badge" ]; then
    emit_check "$CHECK_ID" "pass" \
        "OpenSSF Scorecard workflow ($workflow) and README badge ($badge) present." \
        "{\"workflow\":\"$workflow\",\"badge_in\":\"$badge\"}"
    exit 0
fi

if [ -z "$workflow" ] && [ -z "$badge" ]; then
    emit_check "$CHECK_ID" "fail" \
        "No OpenSSF Scorecard workflow or badge. (Note: 26.10-cycle rollout is gated behind operator's adoption — see references/open-investigations.md.)" \
        '{}' \
        '{"kind":"judgement","human_review":"Wait for operator adoption to settle and propagate its workflow + branch-protection wiring; do not invent conventions ahead of it."}'
    exit 1
fi

missing="workflow"
[ -z "$badge" ] && missing="README badge"
[ -z "$workflow" ] && missing="workflow"
emit_check "$CHECK_ID" "fail" \
    "Partial OpenSSF Scorecard setup — $missing missing." \
    "{\"workflow\":\"$workflow\",\"badge_in\":\"$badge\"}" \
    '{"kind":"judgement","human_review":"Add the missing half (workflow or badge) to match the operator-led convention."}'
exit 1
