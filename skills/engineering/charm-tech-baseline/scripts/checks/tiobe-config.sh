#!/usr/bin/env bash
# Check: TIOBE TICS workflow present, wired with the auth token, and the
# language-specific linters TICS needs are declared as project dependencies.
# Tier coverage: product only.
#
# Mandate: SEC0024 (Static Code Analysis). TIOBE TICS is the required
# SCA tool for SSDLC satisfaction; additional scanners are encouraged
# but do not substitute.
#
# Pass:    A workflow under .github/workflows/ invokes tiobe/tics-github-action,
#          references `secrets.TICSAUTHTOKEN`, and the per-language linters
#          (Python: flake8 + pylint; Go: staticcheck) are visible somewhere
#          in the repo (workflow install step, pyproject.toml dep group,
#          Makefile, or go.mod tooling).
# Fail:    Any of the above missing.
#
# Notes: This script does NOT verify the TQI target spreadsheet entry, the
# Coverage XML artefact path, or the actual TICS dashboard score (all live
# outside the repo). The `tqi-security-target` check covers the spreadsheet
# entry; coverage-XML is left as a per-repo judgement.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="tiobe-config"
APPLIES="product"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

if ! [ -d .github/workflows ]; then
    emit_check "$CHECK_ID" "fail" \
        "No .github/workflows/ directory; cannot host TIOBE TICS workflow." \
        '{}' \
        '{"kind":"judgement","human_review":"Add a tiobe.yaml workflow per https://canonical-tiobe-docs.canonical.com/ — needs the self-hosted tiobe runner and viewer config selection."}'
    exit 1
fi

hits=$(grep -lE 'tiobe/tics-github-action' .github/workflows/*.y*ml 2>/dev/null || true)
if [ -z "$hits" ]; then
    emit_check "$CHECK_ID" "fail" \
        "No TIOBE TICS workflow found under .github/workflows/." \
        '{}' \
        '{"kind":"judgement","human_review":"Add a tiobe.yaml workflow using the self-hosted tiobe runner and the appropriate viewer config (GoProjects for Go; default for Python)."}'
    exit 1
fi

workflow=$(printf '%s' "$hits" | head -1)
problems=()

# TICSAUTHTOKEN secret — without it the action runs but reports nothing.
if ! grep -qE 'secrets\.TICSAUTHTOKEN' "$workflow"; then
    problems+=("workflow does not reference secrets.TICSAUTHTOKEN")
fi

# Per-language linter deps. Be permissive about *where* they appear — TICS
# only needs them findable on PATH, so any of: workflow install step,
# pyproject.toml dep group, requirements file, Makefile, or go.mod tools
# block counts as a hit.
language="unknown"
if [ -f pyproject.toml ] || compgen -G '*.py' >/dev/null 2>&1 || [ -f requirements.txt ] || [ -f setup.cfg ]; then
    language="python"
elif [ -f go.mod ]; then
    language="go"
fi

linter_hit() {
    pat=$1
    # Look in workflow, all pyproject/requirements, and the Makefile if present.
    # Each `[ -f X ] && cat X` returns 1 when X is missing; with `set -o pipefail`,
    # a missing final file would propagate to the pipeline and falsely suppress a
    # real grep match. Force each line to succeed.
    {
        cat "$workflow" 2>/dev/null
        [ -f pyproject.toml ] && cat pyproject.toml || true
        [ -f requirements.txt ] && cat requirements.txt || true
        [ -f requirements-dev.txt ] && cat requirements-dev.txt || true
        [ -f setup.cfg ] && cat setup.cfg || true
        [ -f Makefile ] && cat Makefile || true
        [ -f go.mod ] && cat go.mod || true
        [ -f tools.go ] && cat tools.go || true
    } 2>/dev/null | grep -qiE "$pat"
}

case "$language" in
    python)
        linter_hit '(^|[^a-z])flake8([^a-z]|$)' || problems+=("flake8 not declared in workflow/pyproject/requirements/Makefile")
        linter_hit '(^|[^a-z])pylint([^a-z]|$)'  || problems+=("pylint not declared in workflow/pyproject/requirements/Makefile")
        ;;
    go)
        linter_hit 'staticcheck' || problems+=("staticcheck not declared in workflow/Makefile/go.mod/tools.go")
        ;;
    *)
        # Couldn't classify the project — note it without failing on linter deps.
        :
        ;;
esac

evidence="{\"workflow\":\"$workflow\",\"language\":\"$language\"}"

if [ ${#problems[@]} -eq 0 ]; then
    emit_check "$CHECK_ID" "pass" \
        "TIOBE TICS workflow present, TICSAUTHTOKEN wired, and language linters declared." \
        "$evidence"
    exit 0
fi

joined=$(IFS='; '; printf '%s' "${problems[*]}")
emit_check "$CHECK_ID" "fail" \
    "TIOBE TICS workflow present but incomplete: $joined." \
    "$evidence" \
    '{"kind":"judgement","human_review":"Add secrets.TICSAUTHTOKEN to the workflow env (TICS publishes nothing without it). For Python repos, declare flake8 and pylint in a [dependency-groups] block (or install them in the workflow). For Go repos, add staticcheck via a tools.go entry, Makefile target, or workflow install step. Also confirm a Cobertura coverage artefact is produced before the TICS step runs — that is repo-specific and not auto-verified here."}'
exit 1
