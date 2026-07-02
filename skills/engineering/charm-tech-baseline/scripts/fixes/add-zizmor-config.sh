#!/usr/bin/env bash
# Fix: copy the zizmor config template into .github/.
# Allowlist matches the cycle's settled decision: SHA-pin third-party
# actions; ref-pin allowed for actions/, github/, pypa/, canonical/.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

cd "$(repo_root)" || exit 3

if [ -e .github/zizmor.yml ] || [ -e .github/zizmor.yaml ]; then
    printf '.github/zizmor.{yml,yaml} already exists; refusing to overwrite.\n' >&2
    exit 1
fi

mkdir -p .github
template="$script_dir/../../assets/zizmor.yml.template"
[ -f "$template" ] || { printf 'Template missing.\n' >&2; exit 3; }

cp -- "$template" .github/zizmor.yml
printf 'Wrote .github/zizmor.yml. Adjust the allowlist if the repo uses an action that needs a non-standard ref-pin exception.\n'
