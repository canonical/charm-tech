#!/usr/bin/env bash
# Check: zizmor is wired up (workflow + config).
# Tier coverage: product, canonical.
#
# Looks for: .github/zizmor.yml (or .yaml) AND a workflow that invokes
# zizmor (either via the action or `uvx zizmor`).

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

config=""
for path in .github/zizmor.yml .github/zizmor.yaml; do
    [ -f "$path" ] && config="$path" && break
done

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

if [ -n "$config" ] && [ -n "$workflow_hits" ]; then
    first=$(printf '%s' "$workflow_hits" | head -1)
    emit_check "$CHECK_ID" "pass" \
        "zizmor configured ($config) and run in CI ($first)." \
        "{\"config\":\"$config\",\"workflow\":\"$first\"}"
    exit 0
fi

if [ -n "$config" ] && [ -z "$workflow_hits" ]; then
    emit_check "$CHECK_ID" "fail" \
        "zizmor config present but no workflow runs it." \
        "{\"config\":\"$config\"}" \
        '{"kind":"judgement","human_review":"Add a CI step running zizmor (the canonical org pins a specific SHA in operator/jubilant)."}'
    exit 1
fi

if [ -z "$config" ] && [ -n "$workflow_hits" ]; then
    emit_check "$CHECK_ID" "fail" \
        "Workflow invokes zizmor but no .github/zizmor.yml config." \
        '{}' \
        '{"kind":"mechanical","script":"scripts/fixes/add-zizmor-config.sh","human_review":"Confirm allowlist matches actually-used actions."}'
    exit 1
fi

emit_check "$CHECK_ID" "fail" \
    "No zizmor config or workflow." \
    '{}' \
    '{"kind":"judgement","human_review":"Add .github/zizmor.yml (allowlist for actions/, github/, pypa/, canonical/ ref-pin) and a CI step (uvx zizmor against .github/workflows/)."}'
exit 1
