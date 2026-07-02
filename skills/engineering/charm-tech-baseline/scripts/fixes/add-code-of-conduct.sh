#!/usr/bin/env bash
# Fix: copy the Code-of-Conduct template (link-only Ubuntu CoC) into the repo root.
# Refuses to overwrite an existing file.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

cd "$(repo_root)" || exit 3

if [ -e CODE_OF_CONDUCT.md ]; then
    printf 'CODE_OF_CONDUCT.md already exists; refusing to overwrite.\n' >&2
    exit 1
fi

template="$script_dir/../../assets/CODE_OF_CONDUCT.md"
[ -f "$template" ] || { printf 'Template missing.\n' >&2; exit 3; }

cp -- "$template" CODE_OF_CONDUCT.md
printf 'Copied CODE_OF_CONDUCT.md. No placeholders to fill in — the link-only form is complete as-is.\n'
