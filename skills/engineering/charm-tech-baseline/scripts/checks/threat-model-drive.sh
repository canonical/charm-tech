#!/usr/bin/env bash
# Check: Threat model — informational only.
# Tier coverage: product only.
#
# Threat models live in the central SSDLC Artifacts Drive. This check
# emits an informational note prompting the agent to confirm the
# Drive sheet is current for the cycle.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="threat-model-drive"
APPLIES="product"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

emit_check "$CHECK_ID" "unknown" \
    "Cannot verify from the repo — threat models live in the SSDLC Artifacts Drive. Confirm a refreshed model exists for this cycle." \
    '{}' \
    '{"kind":"judgement","human_review":"SEC0028: refresh every release cycle; demonstrate no unacceptable residual risk; any accepted risk needs a Risk Acceptance Form. Charm SDK consolidated sheet covers ops/ops-scenario/ops-tracing/jubilant/concierge; pebble has its own sheet."}'
exit 0
