#!/usr/bin/env bash
# Check: AGENTS.md present (best-of-class; agent-onboarding entry point).
# Tier coverage: product, canonical. Personal-tier: informational only.
#
# Convention: keep it minimal — a short pointer file, not an encyclopaedia.
# See references/sweep-history.md for the deferred AGENTS.md sweep.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="agents-md"
APPLIES="product,canonical,personal"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

if [ -f AGENTS.md ]; then
    lines=$(wc -l < AGENTS.md)
    if [ "$lines" -gt 200 ]; then
        emit_check "$CHECK_ID" "fail" \
            "AGENTS.md present but at $lines lines is well past the 'keep it minimal' convention." \
            "{\"path\":\"AGENTS.md\",\"lines\":$lines}" \
            '{"kind":"judgement","human_review":"Trim AGENTS.md down — point at HACKING/CONTRIBUTING for depth; keep AGENTS.md to setup commands and conventions only."}'
        exit 1
    fi
    emit_check "$CHECK_ID" "pass" \
        "AGENTS.md present ($lines lines)." \
        "{\"path\":\"AGENTS.md\",\"lines\":$lines}"
    exit 0
fi

emit_check "$CHECK_ID" "fail" \
    "No AGENTS.md found." \
    '{}' \
    '{"kind":"mechanical","script":"scripts/fixes/add-agents-md.sh","human_review":"Customise the dev-setup commands for this repo (uv / go / make / just)."}'
exit 1
