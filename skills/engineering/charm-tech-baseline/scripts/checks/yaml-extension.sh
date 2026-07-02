#!/usr/bin/env bash
# Check: YAML files under .github/ use the .yaml extension, not .yml.
# Tier coverage: product, canonical, personal.
#
# Convention: Charm Tech (and the broader Canonical convention) prefers
# the explicit `.yaml` spelling — matching the official YAML spec and the
# pattern already used by almost every Charm Tech-authored workflow this cycle.
# Mixed extensions inside one repo also defeat tooling globs that only
# match one form.
#
# Scope: anything under .github/ — workflows, dependabot, zizmor,
# issue templates, etc. Anything outside .github/ (Snapcraft snapcraft.yaml,
# Rockcraft rockcraft.yaml, etc.) is out of scope; those names are fixed
# by upstream tooling.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="yaml-extension"
APPLIES="product,canonical,personal"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

if ! [ -d .github ]; then
    emit_check "$CHECK_ID" "na" "No .github/ directory; nothing to check."
    exit 2
fi

mapfile -t offenders < <(find .github -type f -name '*.yml' 2>/dev/null | sort)

if [ ${#offenders[@]} -eq 0 ]; then
    emit_check "$CHECK_ID" "pass" \
        "All YAML files under .github/ use the .yaml extension." \
        '{}'
    exit 0
fi

offenders_json=$(printf '%s\n' "${offenders[@]}" | jq -R . | jq -sc .)
count=${#offenders[@]}
joined=$(IFS=', '; printf '%s' "${offenders[*]}")

emit_check "$CHECK_ID" "fail" \
    "$count file(s) under .github/ use .yml instead of .yaml: $joined." \
    "{\"offenders\":$offenders_json}" \
    '{"kind":"mechanical","script":"scripts/fixes/rename-yml-to-yaml.sh","human_review":"git mv each .yml -> .yaml under .github/. Confirm no external reference uses the old path (workflow_call uses:, docs links, downstream consumers of action.yml)."}'
exit 1
