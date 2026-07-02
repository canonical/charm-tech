#!/usr/bin/env bash
# Check: CODE_OF_CONDUCT.md present.
# Tier coverage: product, canonical. (Best-practice for personal too;
# emitted as a softer fail.)
#
# Decision: link-only form pointing at the Ubuntu Code of Conduct, not a
# full Contributor Covenant template. See references/decisions.md and
# references/sweep-history.md (Community-health sweep).

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="code-of-conduct"
APPLIES="product,canonical,personal"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

for path in CODE_OF_CONDUCT.md docs/CODE_OF_CONDUCT.md .github/CODE_OF_CONDUCT.md; do
    if [ -f "$path" ]; then
        if grep -qiE 'ubuntu\.com/community/ethos/code-of-conduct' "$path"; then
            emit_check "$CHECK_ID" "pass" \
                "CODE_OF_CONDUCT.md present and links to the Ubuntu Code of Conduct." \
                "{\"path\":\"$path\"}"
            exit 0
        fi
        emit_check "$CHECK_ID" "fail" \
            "CODE_OF_CONDUCT.md present but does not link to the Ubuntu Code of Conduct (cycle convention: link-only form)." \
            "{\"path\":\"$path\"}" \
            '{"kind":"judgement","human_review":"Replace with link-only form pointing at https://ubuntu.com/community/ethos/code-of-conduct (Ubuntu CoC has its own reporting/enforcement path via Community Council)."}'
        exit 1
    fi
done

emit_check "$CHECK_ID" "fail" \
    "No CODE_OF_CONDUCT.md found." \
    '{}' \
    '{"kind":"mechanical","script":"scripts/fixes/add-code-of-conduct.sh","human_review":"None — template is fixed link-only form."}'
exit 1
