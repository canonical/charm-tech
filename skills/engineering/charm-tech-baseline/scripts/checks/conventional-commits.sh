#!/usr/bin/env bash
# Check: Conventional-commits PR-title enforcement workflow present.
# Tier coverage: product, canonical.
#
# Cycle reference: 7 of 8 merged; see references/sweep-history.md.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="conventional-commits"
APPLIES="product,canonical"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

if ! [ -d .github/workflows ]; then
    emit_check "$CHECK_ID" "fail" \
        "No .github/workflows directory." \
        '{}' \
        '{"kind":"mechanical","script":"scripts/fixes/add-validate-pr-title.sh","human_review":"Installs operator-style validate-pr-title.yaml + check-conventional-pr-title.py. Confirm CONTRIBUTING.md documents the allowed types."}'
    exit 1
fi

hit=$(grep -lE 'amannn/action-semantic-pull-request|conventional-commit|check-conventional-pr-title' .github/workflows/*.y*ml 2>/dev/null | head -1 || true)
if [ -n "$hit" ]; then
    emit_check "$CHECK_ID" "pass" \
        "PR-title Conventional-Commits enforcement wired up." \
        "{\"workflow\":\"$hit\"}"
    exit 0
fi

emit_check "$CHECK_ID" "fail" \
    "No Conventional-Commits PR-title workflow found." \
    '{}' \
    '{"kind":"mechanical","script":"scripts/fixes/add-validate-pr-title.sh","human_review":"Installs operator-style validate-pr-title.yaml + check-conventional-pr-title.py (source: canonical/operator). Confirm CONTRIBUTING.md documents the allowed type list (chore/ci/docs/feat/fix/perf/refactor/revert/test) and disallows scopes."}'
exit 1
