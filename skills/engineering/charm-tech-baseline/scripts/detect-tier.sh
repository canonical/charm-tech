#!/usr/bin/env bash
# Inspect the current repo's origin remote and emit one of:
#   product | canonical | personal | unknown
#
# Detection rules (in order):
#   1. URL matches https://github.com/canonical/<repo>      -> canonical or product
#   2. URL matches https://github.com/<other-org>/<repo>:
#      a. If the repo is a fork of canonical/<repo> (detected via
#         `gh repo view --json isFork,parent`, or an `upstream` remote
#         pointing at canonical/<repo>)                     -> canonical or product
#      b. Otherwise                                          -> personal
#   3. No remote / no clear org                              -> unknown
#
# The fork lookup matters because Charm Tech engineers routinely work
# from a personal fork of a canonical/* repo; the baseline that applies
# is the upstream repo's, not the fork owner's.
#
# Product-tier classification within canonical/ is driven by a small
# allowlist below (Charm Tech products as of 2026-06 — operator, pebble,
# jubilant, concierge, charmlibs). All other canonical/* repos are
# 'canonical' tier (cross-cutting requirements only).
#
# Override: pass an argument to force a tier (useful when auditing a
# repo before transfer to the canonical org).
#
# Exit 0 always; the tier name is printed on stdout.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=lib/common.sh
. "$script_dir/lib/common.sh"

if [ $# -ge 1 ]; then
    case "$1" in
        product|canonical|personal) printf '%s\n' "$1"; exit 0 ;;
        *) printf 'unknown\n' >&2; exit 1 ;;
    esac
fi

url=$(origin_url)
if [ -z "$url" ]; then
    printf 'unknown\n'
    exit 0
fi

# Strip https://github.com/ prefix; left with <org>/<repo>.
path=${url#https://github.com/}
# Tolerate other forwarding hosts; if we still have a URL-looking
# string, fall back to unknown rather than guess.
if [[ $path == http*://* ]]; then
    printf 'unknown\n'
    exit 0
fi
org=${path%%/*}
repo=${path#*/}

# If origin is not under canonical/, the repo may still be a fork of a
# canonical/* repo — in which case the upstream's baseline applies.
# Resolve the effective owner/repo before tier classification.
if [ "$org" != "canonical" ]; then
    parent_slug=""
    # Preferred: ask GitHub directly.
    if command -v gh >/dev/null 2>&1; then
        parent_slug=$(gh repo view "$org/$repo" \
            --json isFork,parent \
            --jq 'select(.isFork) | .parent | select(.owner.login == "canonical") | "\(.owner.login)/\(.name)"' \
            2>/dev/null || printf '')
    fi
    # Fallback: an `upstream` remote pointing at canonical/<repo>.
    if [ -z "$parent_slug" ]; then
        upstream_url=$(git config --get remote.upstream.url 2>/dev/null || printf '')
        upstream_url=${upstream_url/git@github.com:/https://github.com/}
        upstream_url=${upstream_url%.git}
        upstream_path=${upstream_url#https://github.com/}
        case "$upstream_path" in
            canonical/*) parent_slug=$upstream_path ;;
        esac
    fi
    if [ -n "$parent_slug" ]; then
        org="canonical"
        repo=${parent_slug#canonical/}
    fi
fi

case "$org" in
    canonical)
        # Product-tier allowlist (Charm Tech products this cycle).
        case "$repo" in
            operator|pebble|jubilant|concierge|charmlibs)
                printf 'product\n' ;;
            *)
                printf 'canonical\n' ;;
        esac
        ;;
    *)
        printf 'personal\n'
        ;;
esac
