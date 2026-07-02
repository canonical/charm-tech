#!/usr/bin/env bash
# Check: GitHub releases are immutable (latest release's `immutable: true`).
# Tier coverage: product, canonical.
#
# Implementation: uses `gh api repos/<owner>/<repo>/releases` if `gh` is
# available; falls back to a 'unknown' note if it isn't.
#
# Known blockers (do not flag as fail):
#   - pebble: snap build (pebble#856)
#   - concierge: goreleaser monolith (concierge#172 / #142)
# Heuristically: if the repo origin is canonical/{pebble,concierge,charmlibs},
# emit a note explaining the blocker.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="immutable-releases"
APPLIES="product,canonical"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

url=$(origin_url)
slug=${url#https://github.com/}

# Known blockers — emit a 'pass' with annotation rather than failing
# the audit on something the cycle has explicitly tracked.
case "$slug" in
    canonical/pebble)
        emit_check "$CHECK_ID" "na" \
            "pebble immutable-releases blocked on snap-build process update (pebble#856)."
        exit 2 ;;
    canonical/concierge)
        emit_check "$CHECK_ID" "na" \
            "concierge immutable-releases blocked on goreleaser build/publish split (concierge#172 / #142)."
        exit 2 ;;
esac

if ! command -v gh >/dev/null 2>&1; then
    emit_check "$CHECK_ID" "unknown" \
        "gh CLI not installed; cannot query release immutability flag."
    exit 3
fi

# Take the most recent release. If none, emit na.
flag=$(gh api "repos/$slug/releases?per_page=1" --jq '.[0].immutable // empty' 2>/dev/null || true)
if [ -z "$flag" ]; then
    emit_check "$CHECK_ID" "na" \
        "No releases on $slug yet — toggle the setting before the first release."
    exit 2
fi

if [ "$flag" = "true" ]; then
    emit_check "$CHECK_ID" "pass" \
        "Latest release is immutable." \
        "{\"slug\":\"$slug\"}"
    exit 0
fi

emit_check "$CHECK_ID" "fail" \
    "Latest release is NOT immutable. Setting needs to be flipped, or an active blocker tracked." \
    "{\"slug\":\"$slug\"}" \
    '{"kind":"judgement","human_review":"Flip the per-repo Make-published-releases-immutable toggle in GitHub Settings. If blocked on tooling (goreleaser, snap-build), record the blocker upstream and revisit when the upstream lands."}'
exit 1
