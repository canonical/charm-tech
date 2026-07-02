#!/usr/bin/env bash
# Check: CONTRIBUTING.md (or equivalent) present AND documents the PR
# workflow with a "Pull requests" anchor.
# Tier coverage: product, canonical.
#
# Why the anchor matters: .github/check-conventional-pr-title.py (the
# validate-pr-title workflow's helper) prints an error message ending in
# "Read more: https://github.com/<owner>/<repo>/blob/<branch>/CONTRIBUTING.md#pull-requests".
# If the destination file has no `# Pull requests` heading the link
# silently lands at the top of the document — the audited Charm Tech
# pattern (10 of 14 repos) is to have the heading.
#
# Accepted variants for the file itself: CONTRIBUTING.md, HACKING.md,
# docs/contributing.md, docs/how-to/contribute.md, .github/CONTRIBUTING.md
# (pebble uses HACKING.md).

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="contributing"
APPLIES="product,canonical"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

found_path=""
for path in CONTRIBUTING.md HACKING.md docs/contributing.md docs/how-to/contribute.md .github/CONTRIBUTING.md; do
    if [ -f "$path" ]; then
        found_path="$path"
        break
    fi
done

if [ -z "$found_path" ]; then
    emit_check "$CHECK_ID" "fail" \
        "No CONTRIBUTING.md / HACKING.md / docs/contributing found." \
        '{}' \
        '{"kind":"mechanical","script":"scripts/fixes/add-contributing.sh","human_review":"Customise the dev-setup pointer / project description for the repo (Python / Go / docs)."}'
    exit 1
fi

# A `# Pull requests` (or `## Pull requests`) heading — anchor the validate-
# pr-title.py "Read more" URL lands on. Case-insensitive; allow trailing
# whitespace.
if grep -qiE '^#{1,3}[[:space:]]+pull[[:space:]]+requests?[[:space:]]*$' "$found_path"; then
    emit_check "$CHECK_ID" "pass" \
        "Contributing guidance present at $found_path with a Pull requests section." \
        "{\"path\":\"$found_path\",\"pull_requests_heading\":true}"
    exit 0
fi

emit_check "$CHECK_ID" "fail" \
    "$found_path present but has no 'Pull requests' heading — the validate-pr-title.py \"Read more\" URL (#pull-requests) will not anchor." \
    "{\"path\":\"$found_path\",\"pull_requests_heading\":false}" \
    '{"kind":"judgement","human_review":"Add a `# Pull requests` (or `## Pull requests`) section listing the allowed Conventional-Commits types (chore, ci, docs, feat, fix, perf, refactor, revert, test) and the no-scopes rule. See assets/CONTRIBUTING.md.template for the canonical shape; for pebble-style HACKING.md the anchor can live there instead."}'
exit 1
