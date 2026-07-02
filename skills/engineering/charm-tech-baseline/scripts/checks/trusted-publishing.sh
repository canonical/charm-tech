#!/usr/bin/env bash
# Check: every PyPI publish path uses Trusted Publishing (OIDC), not a long-lived
# API token. Detects:
#   - `pypa/gh-action-pypi-publish` invocations — pass requires NO `password:`
#     or `username:` input, and the surrounding job (or workflow) must declare
#     `id-token: write`.
#   - `twine upload` invocations — fail; twine is the long-lived-token path.
#
# Emits `na` when no PyPI publish path is present (Python project that doesn't
# publish, or non-Python repo). Tier coverage: all tiers — anyone publishing
# to PyPI from GitHub Actions should use Trusted Publishing.
#
# Reference: BASELINE.md "All Python-publishing repos already use Trusted
# Publishing (OIDC id-token: write + pypa/gh-action-pypi-publish)".

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="trusted-publishing"
APPLIES="product,canonical,personal"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

workflows_dir=".github/workflows"
if [ ! -d "$workflows_dir" ]; then
    emit_check "$CHECK_ID" "na" "No .github/workflows directory; no publish workflow to audit."
    exit 2
fi

# Collect candidate workflow files (yaml + yml).
mapfile -t workflows < <(find "$workflows_dir" -maxdepth 1 -type f \( -name '*.yml' -o -name '*.yaml' \) 2>/dev/null)
if [ ${#workflows[@]} -eq 0 ]; then
    emit_check "$CHECK_ID" "na" "No workflows under .github/workflows."
    exit 2
fi

publish_files=()
twine_files=()
bad_token_files=()
missing_id_token_files=()

for wf in "${workflows[@]}"; do
    if grep -qE 'pypa/gh-action-pypi-publish' "$wf"; then
        publish_files+=("$wf")
        # Token-based use: any `password:` or `username:` input under the action.
        if grep -qE '^[[:space:]]*(password|username):' "$wf"; then
            bad_token_files+=("$wf")
        fi
        # `id-token: write` must be present somewhere in the file (workflow- or
        # job-level). Bare `id-token:` without `write` does not satisfy.
        if ! grep -qE '^[[:space:]]*id-token:[[:space:]]*write\b' "$wf"; then
            missing_id_token_files+=("$wf")
        fi
    fi
    if grep -qE '(^|[[:space:]])twine[[:space:]]+upload\b' "$wf"; then
        twine_files+=("$wf")
    fi
done

if [ ${#publish_files[@]} -eq 0 ] && [ ${#twine_files[@]} -eq 0 ]; then
    emit_check "$CHECK_ID" "na" "No PyPI publish workflow detected (no pypa/gh-action-pypi-publish or twine upload)."
    exit 2
fi

json_list() {
    # Emit a JSON array from a bash array passed as positional args.
    if [ "$#" -eq 0 ]; then printf '[]'; return; fi
    printf '['
    sep=""
    for f in "$@"; do
        esc=$(printf '%s' "$f" | sed 's/"/\\"/g')
        printf '%s"%s"' "$sep" "$esc"
        sep=","
    done
    printf ']'
}

evidence=$(printf '{"publish_workflows":%s,"twine_workflows":%s,"missing_id_token":%s,"token_inputs":%s}' \
    "$(json_list "${publish_files[@]:-}")" \
    "$(json_list "${twine_files[@]:-}")" \
    "$(json_list "${missing_id_token_files[@]:-}")" \
    "$(json_list "${bad_token_files[@]:-}")")

problems=()
if [ ${#twine_files[@]} -gt 0 ]; then
    problems+=("twine upload detected (long-lived API token path)")
fi
if [ ${#bad_token_files[@]} -gt 0 ]; then
    problems+=("pypa/gh-action-pypi-publish invoked with password/username input")
fi
if [ ${#missing_id_token_files[@]} -gt 0 ]; then
    problems+=("publish workflow missing id-token: write permission")
fi

if [ ${#problems[@]} -eq 0 ]; then
    emit_check "$CHECK_ID" "pass" \
        "PyPI publishing uses Trusted Publishing (OIDC; id-token: write + pypa/gh-action-pypi-publish, no token input)." \
        "$evidence"
    exit 0
fi

joined=$(IFS='; '; printf '%s' "${problems[*]}")
emit_check "$CHECK_ID" "fail" \
    "PyPI publishing is not fully on Trusted Publishing: $joined." \
    "$evidence" \
    '{"kind":"judgement","human_review":"Convert the publish workflow to Trusted Publishing: drop password/username inputs, add permissions: { id-token: write } at the job (or workflow) level, configure the PyPI project/environment as a Trusted Publisher, and revoke any leftover API tokens. See assets/trusted-publishing.yml.template for the canonical shape."}'
exit 1
