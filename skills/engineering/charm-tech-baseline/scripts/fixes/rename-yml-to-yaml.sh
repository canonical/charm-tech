#!/usr/bin/env bash
# Fix: rename every *.yml under .github/ to *.yaml, using `git mv` so
# history follows. Skips files where the .yaml twin already exists (left
# for manual reconciliation — likely intentional or a stale leftover).
#
# Does NOT update references: `workflow_call uses:` paths, README links,
# downstream consumers of a composite action.yml, etc. The human-review
# note on the matching check flags this; rerun the audit + grep after.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

cd "$(repo_root)" || exit 3

if ! [ -d .github ]; then
    printf 'No .github/ directory; nothing to do.\n'
    exit 0
fi

mapfile -t offenders < <(find .github -type f -name '*.yml' 2>/dev/null | sort)

if [ ${#offenders[@]} -eq 0 ]; then
    printf 'No .yml files under .github/; nothing to do.\n'
    exit 0
fi

in_git_repo=0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 && in_git_repo=1

renamed=0
skipped=0
for src in "${offenders[@]}"; do
    dst=${src%.yml}.yaml
    if [ -e "$dst" ]; then
        printf 'SKIP: %s — %s already exists.\n' "$src" "$dst" >&2
        skipped=$((skipped + 1))
        continue
    fi
    if [ "$in_git_repo" -eq 1 ] && git ls-files --error-unmatch -- "$src" >/dev/null 2>&1; then
        git mv -- "$src" "$dst"
    else
        mv -- "$src" "$dst"
    fi
    printf 'Renamed: %s -> %s\n' "$src" "$dst"
    renamed=$((renamed + 1))
done

printf '\nDone: %d renamed, %d skipped.\n' "$renamed" "$skipped"
printf 'Reminder: grep the repo (and downstream consumers) for the old .yml paths in case any workflow_call / README / action ref points at them.\n'
