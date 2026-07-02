#!/usr/bin/env bash
# Fix: copy the AGENTS.md template into the repo root.
# Agent must fill in {{...}} placeholders before committing — the
# template is intentionally a skeleton, not a working file.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

cd "$(repo_root)" || exit 3

if [ -e AGENTS.md ]; then
    printf 'AGENTS.md already exists; refusing to overwrite.\n' >&2
    exit 1
fi

template="$script_dir/../../assets/AGENTS.md.template"
[ -f "$template" ] || { printf 'Template missing.\n' >&2; exit 3; }

cp -- "$template" AGENTS.md
printf 'Copied AGENTS.md template. Replace {{REPO_DESCRIPTION_ONE_SENTENCE}}, {{SETUP_COMMANDS}}, {{TEST_COMMANDS}}, {{LINT_COMMANDS}}, {{DEPTH_LINK_TITLE}}, {{DEPTH_LINK}} before committing.\n'
