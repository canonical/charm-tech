#!/usr/bin/env bash
# Check: SEC0030 V1.3 Security Documentation coverage.
# Tier coverage: product only.
#
# Looks for either docs/explanation/security.md (Sphinx-stack convention)
# or an expanded SECURITY.md that covers the seven V1.3 sections.
# The check is heuristic — it looks for headings, not deep content.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="sec0030-coverage"
APPLIES="product"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

target=""
for path in docs/explanation/security.md docs/security.md SECURITY.md; do
    [ -f "$path" ] && target="$path" && break
done

if [ -z "$target" ]; then
    emit_check "$CHECK_ID" "fail" \
        "No security documentation found (docs/explanation/security.md or expanded SECURITY.md)." \
        '{}' \
        '{"kind":"judgement","human_review":"Either author docs/explanation/security.md (preferred) or expand SECURITY.md to cover the seven SEC0030 V1.3 sections."}'
    exit 1
fi

# Each requirement is (label-for-report, regex-fragment-that-matches-the-heading).
# Regex is a single ERE alternation; case-insensitive matching is forced
# by grep -i below. Wider variants exist because the cycle's reference
# PRs picked slightly different wording (e.g. "Cryptographic technology"
# on pebble; "Decommissioning" vs "Secure decommissioning").
required_labels=(
    "Product architecture"
    "Secure by design"
    "Cryptography"
    "Hardening"
    "Logging and monitoring"
    "Decommissioning"
    "Security lifecycle"
)
required_patterns=(
    "Product architecture"
    "Secure by design"
    "Crypt"
    "Hardening"
    "Logging|Monitoring"
    "Decommissioning"
    "Security lifecycle|Security updates"
)
missing=""
for i in "${!required_labels[@]}"; do
    if ! grep -qiE "^#{1,4} .*(${required_patterns[$i]})" "$target"; then
        missing="${missing}${required_labels[$i]}; "
    fi
done

if [ -z "$missing" ]; then
    emit_check "$CHECK_ID" "pass" \
        "SEC0030 V1.3 coverage looks complete in $target." \
        "{\"path\":\"$target\"}"
    exit 0
fi

trimmed=${missing%; }
emit_check "$CHECK_ID" "fail" \
    "SEC0030 V1.3 missing section(s) in $target: $trimmed" \
    "{\"path\":\"$target\",\"missing\":\"$trimmed\"}" \
    '{"kind":"judgement","human_review":"Add the missing section(s). See operator#2571, pebble#893, jubilant#332, charm-ubuntu#87 for reference patterns (sentence-case headers, Mermaid diagrams, bulleted hardening with To-harden intro, channels-bullet-list at end of Reporting)."}'
exit 1
