#!/usr/bin/env bash
# Fix: copy the SECURITY.md template into the repo root.
# Caller is the agent, which must then:
#   1. Replace placeholder fields ({{REPO}}, {{CONTACT}}, etc.).
#   2. Stage and commit; do not push without user direction.
#
# This script never overwrites an existing SECURITY.md.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

cd "$(repo_root)" || exit 3

if [ -e SECURITY.md ]; then
    printf 'SECURITY.md already exists; refusing to overwrite. Remove it first if the intent is to replace.\n' >&2
    exit 1
fi

template="$script_dir/../../assets/SECURITY.md.template"
if [ ! -f "$template" ]; then
    printf 'Template missing at %s\n' "$template" >&2
    exit 3
fi

cp -- "$template" SECURITY.md
printf 'Copied SECURITY.md template. Replace placeholders ({{REPO}}, {{CONTACT}}) before committing.\n'
