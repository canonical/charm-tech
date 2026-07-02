#!/usr/bin/env bash
# Check: actions/dependency-review-action workflow present on PRs.
# Tier coverage: product, canonical.
#
# Cycle reference: sweep landed 2026-06-27 (4 PRs open across operator,
# pebble, jubilant, charmlibs); see references/sweep-history.md.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="dependency-review"
APPLIES="product,canonical"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

if ! [ -d .github/workflows ]; then
    emit_check "$CHECK_ID" "fail" \
        "No .github/workflows/ directory." \
        '{}' \
        '{"kind":"judgement","human_review":"Set up workflows; then add dependency-review."}'
    exit 1
fi

hit=$(grep -lE 'actions/dependency-review-action' .github/workflows/*.y*ml 2>/dev/null | head -1 || true)
if [ -n "$hit" ]; then
    emit_check "$CHECK_ID" "pass" \
        "dependency-review-action wired up." \
        "{\"workflow\":\"$hit\"}"
    exit 0
fi

emit_check "$CHECK_ID" "fail" \
    "No actions/dependency-review-action workflow." \
    '{}' \
    '{"kind":"judgement","human_review":"Add a dependency-review.yaml workflow on pull_request, ~10 lines. Reference: canonical/operator#2587 (open as of 2026-06-27)."}'
exit 1
