#!/usr/bin/env bash
# Check: zizmor is invoked in CI.
# Tier coverage: product, canonical.
#
# A .github/zizmor.yaml config file is no longer required — the pinning
# policy has no allowlist exceptions, so zizmor's default unpinned-uses
# rule is sufficient. If a config file exists it is not flagged, but
# it's redundant.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="zizmor-config"
APPLIES="product,canonical"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

workflow_hits=""
if [ -d .github/workflows ]; then
    # Accept any of: the official woodruffw/zizmor-action; `uvx zizmor`;
    # `uv run [args] zizmor` (the dominant Charm Tech pattern — operator,
    # hyrum, charmhub-listing-review all invoke via the project's lint
    # dependency-group rather than uvx); or a bare `zizmor` exec line.
    workflow_hits=$(grep -lE \
        'woodruffw/zizmor|zizmor-action|uvx[[:space:]]+zizmor|uv[[:space:]]+run[[:space:]].*zizmor|(^|[^a-zA-Z0-9_./-])zizmor[[:space:]]' \
        .github/workflows/*.y*ml 2>/dev/null || true)
fi

if [ -n "$workflow_hits" ]; then
    first=$(printf '%s' "$workflow_hits" | head -1)
    emit_check "$CHECK_ID" "pass" \
        "zizmor invoked in CI ($first)." \
        "{\"workflow\":\"$first\"}"
    exit 0
fi

emit_check "$CHECK_ID" "fail" \
    "No workflow invokes zizmor." \
    '{}' \
    '{"kind":"judgement","human_review":"Add a CI step that runs zizmor against .github/workflows/ (uvx zizmor, or via the project'\''s lint dependency-group). No .github/zizmor.yaml config file is required — the default unpinned-uses rule enforces SHA-pinning without an allowlist."}'
exit 1
