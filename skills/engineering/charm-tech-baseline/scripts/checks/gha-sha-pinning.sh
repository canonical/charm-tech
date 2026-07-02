#!/usr/bin/env bash
# Check: third-party GHA actions are SHA-pinned, with the documented
# exception for GitHub-owned and PyPA-owned actions (see
# references/decisions.md).
#
# Tier coverage: product, canonical, personal.
#
# Implementation: greps `uses:` lines under .github/workflows/. A ref is
# SHA-pinned iff it matches a 40-char hex string. Refs of the form
# `actions/*`, `github/*`, `pypa/*` are allowed to use tags or branches.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="gha-sha-pinning"
APPLIES="product,canonical,personal"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

if ! [ -d .github/workflows ]; then
    emit_check "$CHECK_ID" "na" "No .github/workflows directory."
    exit 2
fi

violations=0
violators=""
total=0
while IFS= read -r line; do
    ref=${line#*uses: }
    ref=${ref%% *}
    ref=${ref%\"}
    ref=${ref#\"}
    [ -z "$ref" ] && continue
    [ "${ref:0:2}" = "./" ] && continue   # local action
    [ "${ref:0:1}" = "." ] && continue
    total=$((total + 1))
    repo_part=${ref%@*}
    after_at=${ref#*@}
    # Allow GitHub-owned, PyPA-owned, and the org-owned canonical/* actions.
    case "$repo_part" in
        actions/*|github/*|pypa/*|canonical/*) continue ;;
    esac
    # SHA-pinned iff after_at is 40 hex chars.
    if ! printf '%s' "$after_at" | grep -qE '^[0-9a-fA-F]{40}$'; then
        violations=$((violations + 1))
        violators="$violators $ref"
    fi
done < <(grep -hE '^[[:space:]]*-?[[:space:]]*uses:[[:space:]]+' .github/workflows/*.y*ml 2>/dev/null | sed 's/.*uses:[[:space:]]*//')

if [ "$violations" -eq 0 ]; then
    emit_check "$CHECK_ID" "pass" \
        "All third-party GHA actions SHA-pinned (allowed exceptions: actions/, github/, pypa/, canonical/)." \
        "{\"actions_inspected\":$total}"
    exit 0
fi

trimmed=$(printf '%s' "$violators" | sed 's/^ //' | tr ' ' ',' )
emit_check "$CHECK_ID" "fail" \
    "$violations third-party action ref(s) not SHA-pinned." \
    "{\"actions_inspected\":$total,\"non_pinned\":\"$trimmed\"}" \
    '{"kind":"judgement","human_review":"Replace each non-pinned ref with the upstream commit SHA + a # vX.Y.Z comment. Confirm zizmor.yml allows the appropriate ref-pin exceptions."}'
exit 1
