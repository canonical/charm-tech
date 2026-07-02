#!/usr/bin/env bash
# Check: .pre-commit-config.yaml present (informational).
# Tier coverage: product, canonical, personal.
#
# Cycle convention (see references/decisions.md): tool versions live in
# pyproject.toml [dependency-groups], not in the pre-commit config's
# rev: fields. The hooks invoke tools via `language: system` against
# the lockfile. A config that pins versions in rev: fields is flagged
# as a soft fail because it duplicates the source of truth.
#
# Carve-out: hooks from pre-commit/pre-commit-hooks (end-of-file-fixer,
# trailing-whitespace, check-yaml, check-added-large-files, …) are
# generic file-hygiene checks with no Python-tool counterpart in
# pyproject.toml dependency-groups. Pinning their rev: is the standard
# way to use them and does not duplicate any other source of truth, so
# they are exempted from the count.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="pre-commit-config"
APPLIES="product,canonical,personal"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

if [ ! -f .pre-commit-config.yaml ] && [ ! -f .pre-commit-config.yml ]; then
    emit_check "$CHECK_ID" "fail" \
        "No .pre-commit-config.yaml found." \
        '{}' \
        '{"kind":"judgement","human_review":"Add a minimal config for the languages in use; hooks should use language: system to invoke tools from the uv-locked dependency-groups."}'
    exit 1
fi

config=".pre-commit-config.yaml"
[ -f .pre-commit-config.yml ] && config=".pre-commit-config.yml"

# Count rev: pins on a per-block basis so we can exempt repos that only
# ship generic file-hygiene hooks. Repos in EXEMPT_REPOS are skipped.
EXEMPT_REPOS='https://github.com/pre-commit/pre-commit-hooks'
versioned_revs=$(awk -v exempt="$EXEMPT_REPOS" '
    BEGIN {
        n = split(exempt, parts, " ")
        for (i = 1; i <= n; i++) ex[parts[i]] = 1
        count = 0
        cur = ""
    }
    /^[[:space:]]*-[[:space:]]*repo:[[:space:]]*/ {
        sub(/^[[:space:]]*-[[:space:]]*repo:[[:space:]]*/, "")
        gsub(/["\x27]/, "")
        sub(/[[:space:]]+$/, "")
        cur = $0
        next
    }
    /^[[:space:]]*rev:[[:space:]]+["\x27]?[a-zA-Z0-9._-]+["\x27]?[[:space:]]*$/ {
        if (!(cur in ex)) count++
    }
    END { print count }
' "$config" 2>/dev/null || printf '0')

if [ "$versioned_revs" -gt 0 ]; then
    emit_check "$CHECK_ID" "fail" \
        "Pre-commit config pins $versioned_revs rev: version(s). Cycle convention is to invoke tools via language: system from pyproject.toml [dependency-groups]." \
        "{\"config\":\"$config\",\"versioned_revs\":$versioned_revs}" \
        '{"kind":"judgement","human_review":"Move tool versions to pyproject.toml [dependency-groups]; replace each pinned hook with a language: system equivalent. Reference: pytest-jubilant#86."}'
    exit 1
fi

emit_check "$CHECK_ID" "pass" \
    "Pre-commit config present and tool versions not duplicated in rev: fields." \
    "{\"config\":\"$config\"}"
exit 0
