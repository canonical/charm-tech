#!/usr/bin/env bash
# Check: actions/attest-build-provenance present in release / publish workflows,
# with a `subject-path:` input, AND ordered to run *before* the publish step.
# Tier coverage: product, canonical.
#
# Cycle reference: sweep complete 2026-06-27 (jubilant#352, pebble#885,
# pytest-jubilant#82+#83 merged); concierge skipped pending goreleaser
# split. See references/sweep-history.md.
#
# Ordering rules:
#   - Same job: attest step index must be < publish step index.
#   - Cross-job: attest job must transitively appear in the publish job's
#     `needs:` chain (e.g. build-and-attest → publish via uploaded artefacts).
#
# Uses python3 + PyYAML for parsing. Falls back to `unknown` if either is
# unavailable, rather than emitting a brittle grep-based verdict.

set -uo pipefail
script_dir=$(dirname -- "${BASH_SOURCE[0]}")
# shellcheck source=../lib/common.sh
. "$script_dir/../lib/common.sh"

tier=""
for arg in "$@"; do
    case "$arg" in --tier=*) tier=${arg#--tier=} ;; esac
done

CHECK_ID="attest-build-provenance"
APPLIES="product,canonical"

if ! tier_applies "$APPLIES" "$tier"; then
    emit_check "$CHECK_ID" "na" "Not applicable for tier $tier."
    exit 2
fi

cd "$(repo_root)" || exit 3

if ! [ -d .github/workflows ]; then
    emit_check "$CHECK_ID" "na" "No .github/workflows directory; nothing to attest."
    exit 2
fi

if ! command -v python3 >/dev/null 2>&1; then
    emit_check "$CHECK_ID" "unknown" \
        "python3 not available; cannot parse workflow YAML for attest-step ordering."
    exit 3
fi
if ! python3 -c 'import yaml' 2>/dev/null; then
    emit_check "$CHECK_ID" "unknown" \
        "PyYAML not installed (python3 -c 'import yaml' fails); cannot parse workflow YAML."
    exit 3
fi

# The python helper emits one of:
#   NA <reason>
#   PASS <evidence-json>
#   FAIL <reason> <evidence-json>
result=$(python3 - <<'PY' 2>/dev/null
import glob, json, os, sys

ATTEST = "actions/attest-build-provenance"
PUBLISH_ACTIONS = (
    "pypa/gh-action-pypi-publish",
    "snapcore/action-publish",
    "goreleaser/goreleaser-action",
    "softprops/action-gh-release",
)

try:
    import yaml
except Exception as e:
    print(f"NA could not import yaml: {e}")
    sys.exit(0)

TEST_PYPI_HOSTS = ("test.pypi.org", "testpypi.org")

def _targets_test_pypi(step):
    # pypa/gh-action-pypi-publish: with.repository-url
    with_block = step.get("with") or {}
    url = (with_block.get("repository-url") or with_block.get("repository_url") or "")
    if any(h in url for h in TEST_PYPI_HOSTS):
        return True
    # twine: --repository-url <url>, or TWINE_REPOSITORY_URL env
    run = step.get("run") or ""
    if any(h in run for h in TEST_PYPI_HOSTS):
        return True
    env = step.get("env") or {}
    url2 = (env.get("TWINE_REPOSITORY_URL") or env.get("TWINE_REPOSITORY") or "")
    return any(h in url2 for h in TEST_PYPI_HOSTS)

def is_publish_step(step):
    if not isinstance(step, dict):
        return False
    uses = step.get("uses") or ""
    run = step.get("run") or ""
    is_action_publish = any(p in uses for p in PUBLISH_ACTIONS)
    # `twine upload` is also a publish action even though it isn't a marketplace action.
    is_twine_publish = "twine upload" in run
    if not (is_action_publish or is_twine_publish):
        return False
    # Test-PyPI publishes are staging dry-runs; nobody consumes provenance
    # from test.pypi.org and pypi-attestations doesn't verify it, so don't
    # demand attestation for them.
    if _targets_test_pypi(step):
        return False
    return True

def is_attest_step(step):
    uses = (step.get("uses") or "") if isinstance(step, dict) else ""
    return ATTEST in uses

def needs_of(job):
    needs = job.get("needs") if isinstance(job, dict) else None
    if needs is None:
        return []
    if isinstance(needs, str):
        return [needs]
    return list(needs)

def transitive_needs(jobs, start):
    seen, stack = set(), [start]
    while stack:
        n = stack.pop()
        if n in seen or n not in jobs:
            continue
        seen.add(n)
        stack.extend(needs_of(jobs[n]))
    seen.discard(start)
    return seen

failures = []           # human-readable strings
publish_workflows = []  # files containing any publish step
attested_workflows = [] # files where attestation is correctly wired

for path in sorted(glob.glob(".github/workflows/*.yml") + glob.glob(".github/workflows/*.yaml")):
    try:
        with open(path) as f:
            doc = yaml.safe_load(f)
    except Exception as e:
        failures.append(f"{path}: YAML parse error ({e})")
        continue
    if not isinstance(doc, dict):
        continue
    jobs = doc.get("jobs") or {}
    if not isinstance(jobs, dict):
        continue

    # Index steps per job: list of (kind, index, subject_path_set).
    job_steps = {}
    for jname, job in jobs.items():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps") or []
        rec = {"attests": [], "publishes": []}
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            if is_attest_step(step):
                with_block = step.get("with") or {}
                subj = with_block.get("subject-path") or with_block.get("subject-checksums") or with_block.get("subject-digest")
                rec["attests"].append({"index": i, "has_subject": bool(subj)})
            if is_publish_step(step):
                rec["publishes"].append({"index": i})
        job_steps[jname] = rec

    publish_jobs = [j for j, r in job_steps.items() if r["publishes"]]
    if not publish_jobs:
        continue
    publish_workflows.append(path)

    workflow_ok = True
    for pjob in publish_jobs:
        prec = job_steps[pjob]
        first_publish_idx = min(p["index"] for p in prec["publishes"])

        # 1. Attest in the same job, ordered before publish, with a subject.
        same_job_attests = [a for a in prec["attests"] if a["index"] < first_publish_idx]
        same_job_attest_no_order = [a for a in prec["attests"] if a["index"] >= first_publish_idx]
        if same_job_attests:
            if not any(a["has_subject"] for a in same_job_attests):
                failures.append(f"{path}:{pjob}: attest step has no subject-path/subject-digest/subject-checksums")
                workflow_ok = False
            # ordering OK; skip cross-job check
            continue
        if same_job_attest_no_order:
            failures.append(f"{path}:{pjob}: attest step runs AFTER the publish step (must be before)")
            workflow_ok = False
            continue

        # 2. Attest in a transitive `needs:` job, with a subject.
        upstream = transitive_needs(jobs, pjob)
        upstream_attests = []
        for uj in upstream:
            for a in job_steps.get(uj, {}).get("attests", []):
                upstream_attests.append((uj, a))
        if not upstream_attests:
            failures.append(f"{path}:{pjob}: publish step has no attest step in this job or in any upstream `needs:` job")
            workflow_ok = False
            continue
        if not any(a["has_subject"] for _, a in upstream_attests):
            ujs = ",".join(sorted({uj for uj, _ in upstream_attests}))
            failures.append(f"{path}:{pjob}: upstream attest step(s) in {ujs} have no subject-path")
            workflow_ok = False
            continue
    if workflow_ok:
        attested_workflows.append(path)

evidence = {
    "publish_workflows": publish_workflows,
    "attested_workflows": attested_workflows,
    "failures": failures,
}
if not publish_workflows:
    print("NA No publish/release workflow found; attestation not applicable.")
elif not failures:
    print("PASS " + json.dumps(evidence))
else:
    # Use a short top-line reason; full list in evidence.failures.
    top = failures[0] if len(failures) == 1 else f"{failures[0]} (and {len(failures)-1} more)"
    print("FAIL " + top + " ||| " + json.dumps(evidence))
PY
)

# Convert "||| evidence-json" tail into a separate variable when present.
case "$result" in
    "NA "*)
        reason=${result#NA }
        emit_check "$CHECK_ID" "na" "$reason"
        exit 2 ;;
    "PASS "*)
        evidence=${result#PASS }
        emit_check "$CHECK_ID" "pass" \
            "Build provenance attestation present, with subject-path, ordered before publish." \
            "$evidence"
        exit 0 ;;
    "FAIL "*)
        body=${result#FAIL }
        reason=${body%% ||| *}
        evidence=${body#* ||| }
        # Escape double quotes in the reason for safe JSON embedding.
        reason_q=$(printf '%s' "$reason" | sed 's/"/\\"/g')
        emit_check "$CHECK_ID" "fail" \
            "Publish workflow(s) missing or misordered attestation: $reason_q" \
            "$evidence" \
            '{"kind":"judgement","human_review":"Wire actions/attest-build-provenance@<sha> BEFORE the publish step in the same job, or in an upstream job in the publish jobs `needs:` chain. Set `with.subject-path` to the published artefact glob (e.g. dist/*). Concierge skip applies until goreleaser build/publish split lands."}'
        exit 1 ;;
    *)
        emit_check "$CHECK_ID" "unknown" \
            "Parser produced no output; cannot verify attestation."
        exit 3 ;;
esac
