#!/usr/bin/env bash
# Fix: copy the Dependabot template into .github/.
# Agent must edit the package-ecosystem set to match the repo
# (drop unused ecosystems, uncomment gomod / docker if applicable).

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

cd "$(repo_root)" || exit 3

if [ -e .github/dependabot.yml ] || [ -e .github/dependabot.yaml ]; then
    printf '.github/dependabot.{yml,yaml} already exists; refusing to overwrite.\n' >&2
    exit 1
fi

mkdir -p .github
template="$script_dir/../../assets/dependabot.yml.template"
[ -f "$template" ] || { printf 'Template missing.\n' >&2; exit 3; }

cp -- "$template" .github/dependabot.yaml
printf 'Wrote .github/dependabot.yaml. Confirm the ecosystem set matches the repo (pip, github-actions by default; uncomment gomod as needed), and that all dev tooling in use by the repo is in the dev tooling group.\n'
