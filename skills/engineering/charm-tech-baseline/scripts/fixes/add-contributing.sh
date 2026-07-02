#!/usr/bin/env bash
# Fix: copy the CONTRIBUTING.md template into the repo root and rewrite the
# owner/repo placeholders to match origin. The template mirrors the
# dominant Charm Tech pattern (substantive standalone doc with a
# `# Pull requests` section).

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

cd "$(repo_root)" || exit 3

if [ -e CONTRIBUTING.md ]; then
    printf 'CONTRIBUTING.md already exists; refusing to overwrite.\n' >&2
    exit 1
fi

template="$script_dir/../../assets/CONTRIBUTING.md.template"
[ -f "$template" ] || { printf 'Template missing.\n' >&2; exit 3; }

cp -- "$template" CONTRIBUTING.md

url=$(origin_url)
slug=${url#https://github.com/}
if [ -n "$slug" ] && [ "$slug" != "$url" ]; then
    owner=${slug%%/*}
    name=${slug##*/}
    sed -i \
        -e "s|REPLACE_WITH_OWNER|$owner|g" \
        -e "s|REPLACE_WITH_REPO|$name|g" \
        CONTRIBUTING.md
    printf 'Rewrote owner/repo placeholders to %s/%s.\n' "$owner" "$name"
else
    printf 'Could not determine origin slug; left REPLACE_WITH_OWNER/REPO placeholders in CONTRIBUTING.md — fix before committing.\n' >&2
fi

printf 'Wrote CONTRIBUTING.md. Confirm: the `# Pull requests` type list matches .github/check-conventional-pr-title.py (chore, ci, docs, feat, fix, perf, refactor, revert, test).\n'
