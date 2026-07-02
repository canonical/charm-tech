#!/usr/bin/env bash
# Fix: install the operator-style Conventional Commits PR-title check.
#
# Two-file pattern (source: canonical/operator):
#   - .github/workflows/validate-pr-title.yaml — runs on pull_request
#     [opened, edited, synchronize], permissions: {}, no PR-title fetch from
#     the API; reads it from the event payload via the PR_TITLE env var.
#   - .github/check-conventional-pr-title.py — self-contained Python (stdlib
#     only). Allowed types: chore, ci, docs, feat, fix, perf, refactor, revert,
#     test. Scopes disallowed.
#
# Both files are staged from the asset templates. The Python script's _HELP_URL
# placeholder is rewritten to point at this repo's CONTRIBUTING.md so the error
# message links to the right place. The agent should still check the
# CONTRIBUTING.md exists and documents these types; sweep-validate-pr-title.md
# in the roadmap tree records which Charm Tech repos had to add or extend it.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

cd "$(repo_root)" || exit 3

workflow=".github/workflows/validate-pr-title.yaml"
script=".github/check-conventional-pr-title.py"

if [ -e "$workflow" ] || [ -e ".github/workflows/validate-pr-title.yml" ]; then
    printf '%s (or .yml variant) already exists; refusing to overwrite.\n' "$workflow" >&2
    exit 1
fi
if [ -e "$script" ]; then
    printf '%s already exists; refusing to overwrite.\n' "$script" >&2
    exit 1
fi

wf_template="$script_dir/../../assets/validate-pr-title.yaml.template"
py_template="$script_dir/../../assets/check-conventional-pr-title.py.template"
[ -f "$wf_template" ] || { printf 'Workflow template missing: %s\n' "$wf_template" >&2; exit 3; }
[ -f "$py_template" ] || { printf 'Python template missing: %s\n' "$py_template" >&2; exit 3; }

mkdir -p .github/workflows
cp -- "$wf_template" "$workflow"
cp -- "$py_template" "$script"

# Rewrite the help-URL placeholder to point at THIS repo.
url=$(origin_url)
slug=${url#https://github.com/}
if [ -n "$slug" ] && [ "$slug" != "$url" ]; then
    owner=${slug%%/*}
    name=${slug##*/}
    default_branch=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's@^origin/@@')
    [ -n "$default_branch" ] || default_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || printf 'main')
    sed -i \
        -e "s|REPLACE_WITH_OWNER|$owner|g" \
        -e "s|REPLACE_WITH_REPO|$name|g" \
        -e "s|/blob/main/|/blob/$default_branch/|g" \
        "$script"
    printf 'Rewrote help-URL to https://github.com/%s/%s/blob/%s/CONTRIBUTING.md#pull-requests\n' \
        "$owner" "$name" "$default_branch"
else
    printf 'Could not determine origin slug; left REPLACE_WITH_OWNER/REPO placeholders in %s — fix before committing.\n' "$script" >&2
fi

printf 'Wrote %s and %s.\n' "$workflow" "$script"
printf 'Confirm CONTRIBUTING.md (or HACKING.md, etc.) exists in this repo and documents the allowed Conventional-Commits types; if not, add a "Pull requests" section listing chore/ci/docs/feat/fix/perf/refactor/revert/test before merging.\n'
