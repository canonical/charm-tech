#!/usr/bin/env bash
# Check: canonical-secscan-client (or equivalent) workflow present, with the
# SSDLC identification details wired up so results land in the long-term scan
# registry.
# Tier coverage: product only.
#
# Mandate: SEC0025. Run at least once per cycle per product with SSDLC
# identification.
#
# Two flavours are accepted:
#
# 1. **sbomber-driven** (Charm Tech default): the workflow checks out or
#    invokes `canonical/sbomber`, and the repo carries one or more
#    `.sbomber-manifest*.yaml` files (root or under .github/). SSDLC
#    identification lives in `ssdlc_params:` blocks per artifact inside the
#    manifest; the secscan client is enabled via `clients.secscan` in the
#    manifest. Pass requires: workflow + at least one manifest with both
#    `clients.secscan` and per-artifact `ssdlc_params`.
#
# 2. **Direct canonical-secscan-client**: the workflow runs the client
#    directly (or via cs-github-actions / starflow). Pass requires the
#    --ssdlc-product-name / --ssdlc-cycle CLI parameters.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="secscan-workflow"
APPLIES="product"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

if ! [ -d .github/workflows ]; then
    emit_check "$CHECK_ID" "fail" \
        "No .github/workflows directory." \
        '{}' \
        '{"kind":"judgement","human_review":"Set up workflows and wire secscan."}'
    exit 1
fi

# Prefer a workflow that *invokes* sbomber (checkout of canonical/sbomber,
# or `./sbomber` / `sbomber/sbomber` exec) over orchestrators that merely
# `uses:` a sub-workflow that does — picking the orchestrator first would
# misclassify the repo as direct-client.
sbomber_workflow=$(grep -lEi \
    'canonical/sbomber|\./sbomber|sbomber/sbomber' \
    .github/workflows/*.y*ml 2>/dev/null | head -1 || true)

direct_workflow=$(grep -lEi \
    'canonical-secscan-client|run-secscan|sbom-secscan|scan-python' \
    .github/workflows/*.y*ml 2>/dev/null | head -1 || true)

if [ -z "$sbomber_workflow" ] && [ -z "$direct_workflow" ]; then
    emit_check "$CHECK_ID" "fail" \
        "No secscan workflow found." \
        '{}' \
        '{"kind":"judgement","human_review":"Reference: canonical/sbomber composite action (Charm Tech default), canonical/cs-github-actions run-secscan, or canonical/starflow scan-python. Use the --batch instance; GitHub private runners are allow-listed."}'
    exit 1
fi

if [ -n "$sbomber_workflow" ]; then
    workflow_hit=$sbomber_workflow
    # Manifests live as .sbomber-manifest*.yaml at the repo root or under
    # .github/ — accept either.
    mapfile -t manifests < <(find . -maxdepth 3 \
        \( -path ./.git -prune \) -o \
        -type f \( -name '.sbomber-manifest*.yaml' -o -name '.sbomber-manifest*.yml' \) -print 2>/dev/null)

    if [ ${#manifests[@]} -eq 0 ]; then
        emit_check "$CHECK_ID" "fail" \
            "sbomber workflow present but no .sbomber-manifest*.yaml found at repo root or under .github/." \
            "{\"workflow\":\"$workflow_hit\"}" \
            '{"kind":"judgement","human_review":"Add a .sbomber-manifest-<flavour>.yaml describing artifacts, with clients.secscan enabled and ssdlc_params per artifact. See canonical/sbomber/examples/all/manifest.yaml."}'
        exit 1
    fi

    problems=()
    has_secscan_client=0
    has_ssdlc_params=0
    for m in "${manifests[@]}"; do
        # Be permissive about indentation; `clients:` block lists `secscan:`
        # as a key (with empty body or args).
        if grep -qE '^\s*secscan\s*:' "$m"; then
            has_secscan_client=1
        fi
        if grep -qE '^\s*ssdlc_params\s*:' "$m"; then
            has_ssdlc_params=1
        fi
    done

    [ $has_secscan_client -eq 0 ] && problems+=("no manifest declares clients.secscan")
    [ $has_ssdlc_params -eq 0 ]   && problems+=("no manifest carries per-artifact ssdlc_params")

    evidence=$(printf '{"workflow":"%s","driver":"sbomber","manifests":%s}' \
        "$workflow_hit" \
        "$(printf '%s\n' "${manifests[@]}" | jq -R . | jq -sc .)")

    if [ ${#problems[@]} -eq 0 ]; then
        emit_check "$CHECK_ID" "pass" \
            "sbomber workflow present; manifest enables secscan client and carries ssdlc_params." \
            "$evidence"
        exit 0
    fi

    joined=$(IFS='; '; printf '%s' "${problems[*]}")
    emit_check "$CHECK_ID" "fail" \
        "sbomber workflow present but manifest incomplete: $joined." \
        "$evidence" \
        '{"kind":"judgement","human_review":"In the .sbomber-manifest*.yaml, ensure clients.secscan is enabled and every artifact declares ssdlc_params (name/version/channel) — these are what the SSDLC scan registry indexes."}'
    exit 1
fi

# Direct canonical-secscan-client path.
workflow_hit=$direct_workflow
if grep -qE 'ssdlc-product-name|ssdlc-cycle' "$workflow_hit"; then
    emit_check "$CHECK_ID" "pass" \
        "secscan workflow present with SSDLC identification parameters." \
        "{\"workflow\":\"$workflow_hit\",\"driver\":\"canonical-secscan-client\"}"
    exit 0
fi

emit_check "$CHECK_ID" "fail" \
    "secscan workflow present but --ssdlc-* identification parameters missing." \
    "{\"workflow\":\"$workflow_hit\",\"driver\":\"canonical-secscan-client\"}" \
    '{"kind":"judgement","human_review":"Pass --ssdlc-product-name, --ssdlc-cycle, --ssdlc-product-channel, --ssdlc-product-version so results land in the long-term SSDLC scan registry. (Or migrate to canonical/sbomber and move identification into the manifest ssdlc_params blocks.)"}'
exit 1
