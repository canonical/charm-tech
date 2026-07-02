#!/usr/bin/env bash
# Check: TQI security target — informational only.
# Tier coverage: product only.
#
# The TQI target lives in the central *TiCS Targets 26.10* spreadsheet,
# not the repo. This check just emits an informational note prompting
# the agent to verify the target is recorded for the cycle.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="tqi-security-target"
APPLIES="product"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

emit_check "$CHECK_ID" "unknown" \
    "Cannot verify from the repo — the TQI security target lives in the *TiCS Targets 26.10* spreadsheet. Confirm a target is recorded for this product." \
    '{}' \
    '{"kind":"judgement","human_review":"Set/verify the per-repo Security metric (TQI) target in *TiCS Targets 26.10* by 30 June."}'
exit 0
