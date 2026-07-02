#!/usr/bin/env bash
# Check: workflow secret-handling hygiene.
#
# Follows the Canonical Security "Repository security" page (Secrets section)
# — a repo-level secret-handling audit that flags patterns known to leak
# secrets or over-scope them. Fleet audit 2026-07-02 (recorded in
# roadmap/26.10/repo-setup/security-docs-gap.md rows #32-#36) turned up one
# real hit across all 9 Charm Tech in-scope repos; this check turns that
# audit into a reusable per-repo verification.
#
# Detects, in .github/workflows/*.y*ml:
#   * workflow-level `env:` blocks that reference `${{ secrets.* }}`
#     (over-scoped: every job/step in the workflow sees the secret)
#   * job-level `env:` blocks that reference `${{ secrets.* }}`
#     (over-scoped: every step in the job sees the secret; use step-level
#     env: instead)
#   * `run:` lines that `echo` / `printf` / `cat` a secret expression
#     (log-masking is not guaranteed for every transformation — the
#     reference page warns against this explicitly)
#   * `secrets: inherit` in reusable workflow calls (pass named secrets
#     instead so the callee's secret surface is auditable)
#
# Tier coverage: product, canonical. (Personal-tier: advisory — secret
# handling still matters, but personal repos may lack even a workflow to
# scan.)

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="workflow-secrets"
APPLIES="product,canonical,personal"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

if [ ! -d .github/workflows ]; then
    emit_check "$CHECK_ID" "na" "No .github/workflows/ directory."
    exit 2
fi

# Collect workflow files.
mapfile -t workflows < <(find .github/workflows -maxdepth 1 -type f \( -name '*.yml' -o -name '*.yaml' \) | sort)
if [ ${#workflows[@]} -eq 0 ]; then
    emit_check "$CHECK_ID" "na" "No workflow files under .github/workflows/."
    exit 2
fi

# Structural checks need a YAML parser to distinguish workflow/job/step
# `env:` scope reliably. If python3+PyYAML isn't available, fall back to
# textual checks (echo-secrets and secrets: inherit only) with a note.
have_parser=false
if command -v python3 >/dev/null 2>&1 && python3 -c 'import yaml' 2>/dev/null; then
    have_parser=true
fi

# Textual quick-scan hits — reliable without YAML parsing.
echo_hits=""
inherit_hits=""
for wf in "${workflows[@]}"; do
    # `run:` line that starts with echo/printf/cat AND interpolates ${{ secrets.* }}
    # (Both single-line `run: echo ...` and, best-effort, first-line of `run: |` block).
    while IFS= read -r hit; do
        [ -n "$hit" ] && echo_hits+="${wf}:${hit}"$'\n'
    done < <(grep -nE '^[[:space:]]*(-[[:space:]]+)?run:[[:space:]]*(echo|printf|cat)\b.*\$\{\{[[:space:]]*secrets\.' "$wf" 2>/dev/null)
    # `secrets: inherit`
    while IFS= read -r hit; do
        [ -n "$hit" ] && inherit_hits+="${wf}:${hit}"$'\n'
    done < <(grep -nE '^[[:space:]]*secrets:[[:space:]]*inherit\b' "$wf" 2>/dev/null)
done

# Structural env-scope hits — need the parser.
env_hits=""
parse_errors=""
if [ "$have_parser" = "true" ]; then
    env_hits=$(WORKFLOWS="$(printf '%s\n' "${workflows[@]}")" python3 - <<'PY' 2>/dev/null
import os, re, sys
try:
    import yaml
except Exception:
    sys.exit(0)
sec = re.compile(r'\$\{\{\s*secrets\.')

def walk_env(env, path_parts, scope, findings):
    """Recursively record secrets found in env: mapping values."""
    if not isinstance(env, dict):
        return
    for k, v in env.items():
        if isinstance(v, str) and sec.search(v):
            findings.append((scope, ".".join(path_parts + [str(k)])))

for wf in os.environ["WORKFLOWS"].splitlines():
    try:
        with open(wf) as f:
            doc = yaml.safe_load(f)
    except Exception as e:
        print(f"PARSE_ERROR\t{wf}\t{e}")
        continue
    if not isinstance(doc, dict):
        continue
    findings = []  # (scope_label, key_path)
    wf_env = doc.get("env")
    walk_env(wf_env, [], "workflow", findings)
    jobs = doc.get("jobs") or {}
    if isinstance(jobs, dict):
        for jname, job in jobs.items():
            if not isinstance(job, dict):
                continue
            walk_env(job.get("env"), [f"jobs.{jname}"], "job", findings)
            # steps: step-level env: is fine — we deliberately don't walk.
    for scope, key in findings:
        print(f"HIT\t{wf}\t{scope}\t{key}")
PY
)
    # Separate parse errors from hits.
    parse_errors=$(printf '%s' "$env_hits" | awk -F'\t' '$1=="PARSE_ERROR"{print}')
    env_hits=$(printf '%s' "$env_hits" | awk -F'\t' '$1=="HIT"{print}')
fi

# Count and format.
n_workflow=$(printf '%s' "$env_hits" | awk -F'\t' '$3=="workflow"{c++} END{print c+0}')
n_job=$(printf '%s' "$env_hits" | awk -F'\t' '$3=="job"{c++} END{print c+0}')
n_echo=$(printf '%s' "$echo_hits" | grep -c . || true)
n_inherit=$(printf '%s' "$inherit_hits" | grep -c . || true)
total=$(( n_workflow + n_job + n_echo + n_inherit ))

# Build a compact evidence blob.
esc() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e ':a;N;$!ba;s/\n/\\n/g'; }
evidence=$(printf '{"workflows_scanned":%d,"parser":%s,"hits":{"workflow_env":%d,"job_env":%d,"echo_secret":%d,"secrets_inherit":%d}}' \
    "${#workflows[@]}" "$have_parser" "$n_workflow" "$n_job" "$n_echo" "$n_inherit")

if [ "$total" -eq 0 ]; then
    if [ "$have_parser" = "false" ]; then
        emit_check "$CHECK_ID" "pass" \
            "No echo-secret or secrets: inherit hits across ${#workflows[@]} workflow(s); env-scope check skipped (python3+PyYAML unavailable)." \
            "$evidence"
    else
        emit_check "$CHECK_ID" "pass" \
            "No workflow-/job-level env: secrets, echo-secret, or secrets: inherit hits across ${#workflows[@]} workflow(s)." \
            "$evidence"
    fi
    exit 0
fi

# Failure path — build a human summary.
summary="Secret-handling hits: ${n_workflow} workflow-level env, ${n_job} job-level env, ${n_echo} echo-secret, ${n_inherit} secrets: inherit."
details=""
[ -n "$env_hits" ] && details+=$'env: scope hits:\n'"$env_hits"$'\n'
[ -n "$echo_hits" ] && details+=$'echo/printf/cat hits (file:line:content):\n'"$echo_hits"$'\n'
[ -n "$inherit_hits" ] && details+=$'secrets: inherit hits:\n'"$inherit_hits"$'\n'
details_esc=$(esc "$details")

remediation='{"kind":"judgement","human_review":"Move secrets to step-level env: (never workflow- or job-level). Never echo/printf/cat a secret expression — pass via env: and reference $VAR instead. In reusable-workflow calls, pass named secrets rather than secrets: inherit."}'

emit_check "$CHECK_ID" "fail" \
    "$summary" \
    "$evidence" \
    "$remediation"
# Emit the per-hit detail as a second line for the agent (not JSON — the
# runner concatenates lines and the agent reads both).
if [ -n "$details" ]; then
    printf '\n# workflow-secrets detail:\n%s' "$details" >&2
fi
exit 1
