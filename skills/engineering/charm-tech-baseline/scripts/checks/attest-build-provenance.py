#!/usr/bin/env python3
"""Check: actions/attest-build-provenance present in release / publish workflows,
with a `subject-path:` input, AND ordered to run *before* the publish step.
Tier coverage: product, canonical.

Cycle reference: sweep complete 2026-06-27 (jubilant#352, pebble#885,
pytest-jubilant#82+#83 merged); concierge skipped pending goreleaser
split. See references/sweep-history.md.

Ordering rules:
  - Same job: attest step index must be < publish step index.
  - Cross-job: attest job must transitively appear in the publish job's
    `needs:` chain (e.g. build-and-attest -> publish via uploaded artefacts).

Uses python3 + PyYAML for parsing. Falls back to `unknown` if either is
unavailable, rather than emitting a brittle grep-based verdict.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import (
    EXIT_FAIL, EXIT_NA, EXIT_PASS, EXIT_UNKNOWN,
    cd_repo_root, emit_check, parse_tier, tier_applies,
)

CHECK_ID = "attest-build-provenance"
APPLIES = "product,canonical"

ATTEST = "actions/attest-build-provenance"
PUBLISH_ACTIONS = (
    "pypa/gh-action-pypi-publish",
    "snapcore/action-publish",
    "goreleaser/goreleaser-action",
    "softprops/action-gh-release",
)
TEST_PYPI_HOSTS = ("test.pypi.org", "testpypi.org")


def _targets_test_pypi(step: dict) -> bool:
    with_block = step.get("with") or {}
    url = (with_block.get("repository-url") or with_block.get("repository_url") or "")
    if any(h in url for h in TEST_PYPI_HOSTS):
        return True
    run_str = step.get("run") or ""
    if any(h in run_str for h in TEST_PYPI_HOSTS):
        return True
    env = step.get("env") or {}
    url2 = (env.get("TWINE_REPOSITORY_URL") or env.get("TWINE_REPOSITORY") or "")
    return any(h in url2 for h in TEST_PYPI_HOSTS)


def is_publish_step(step) -> bool:
    if not isinstance(step, dict):
        return False
    uses = step.get("uses") or ""
    run_str = step.get("run") or ""
    is_action_publish = any(p in uses for p in PUBLISH_ACTIONS)
    is_twine_publish = "twine upload" in run_str
    if not (is_action_publish or is_twine_publish):
        return False
    if _targets_test_pypi(step):
        return False
    return True


def is_attest_step(step) -> bool:
    if not isinstance(step, dict):
        return False
    uses = step.get("uses") or ""
    return ATTEST in uses


def needs_of(job) -> list[str]:
    needs = job.get("needs") if isinstance(job, dict) else None
    if needs is None:
        return []
    if isinstance(needs, str):
        return [needs]
    return list(needs)


def transitive_needs(jobs: dict, start: str) -> set[str]:
    seen: set[str] = set()
    stack = [start]
    while stack:
        n = stack.pop()
        if n in seen or n not in jobs:
            continue
        seen.add(n)
        stack.extend(needs_of(jobs[n]))
    seen.discard(start)
    return seen


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    cd_repo_root()

    if not Path(".github/workflows").is_dir():
        emit_check(CHECK_ID, "na", "No .github/workflows directory; nothing to attest.")
        return EXIT_NA

    try:
        import yaml  # type: ignore
    except Exception:
        emit_check(
            CHECK_ID, "unknown",
            "PyYAML not installed (python3 -c 'import yaml' fails); cannot parse workflow YAML.",
        )
        return EXIT_UNKNOWN

    failures: list[str] = []
    publish_workflows: list[str] = []
    attested_workflows: list[str] = []

    wf_dir = Path(".github/workflows")
    workflow_paths = sorted(list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml")))

    for path in workflow_paths:
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

        job_steps: dict[str, dict] = {}
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
                    subj = (
                        with_block.get("subject-path")
                        or with_block.get("subject-checksums")
                        or with_block.get("subject-digest")
                    )
                    rec["attests"].append({"index": i, "has_subject": bool(subj)})
                if is_publish_step(step):
                    rec["publishes"].append({"index": i})
            job_steps[jname] = rec

        publish_jobs = [j for j, r in job_steps.items() if r["publishes"]]
        if not publish_jobs:
            continue
        publish_workflows.append(str(path))

        workflow_ok = True
        for pjob in publish_jobs:
            prec = job_steps[pjob]
            first_publish_idx = min(p["index"] for p in prec["publishes"])

            same_job_attests = [a for a in prec["attests"] if a["index"] < first_publish_idx]
            same_job_attest_no_order = [a for a in prec["attests"] if a["index"] >= first_publish_idx]
            if same_job_attests:
                if not any(a["has_subject"] for a in same_job_attests):
                    failures.append(f"{path}:{pjob}: attest step has no subject-path/subject-digest/subject-checksums")
                    workflow_ok = False
                continue
            if same_job_attest_no_order:
                failures.append(f"{path}:{pjob}: attest step runs AFTER the publish step (must be before)")
                workflow_ok = False
                continue

            upstream = transitive_needs(jobs, pjob)
            upstream_attests: list[tuple[str, dict]] = []
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
            attested_workflows.append(str(path))

    evidence = {
        "publish_workflows": publish_workflows,
        "attested_workflows": attested_workflows,
        "failures": failures,
    }

    if not publish_workflows:
        emit_check(CHECK_ID, "na", "No publish/release workflow found; attestation not applicable.")
        return EXIT_NA

    if not failures:
        emit_check(
            CHECK_ID, "pass",
            "Build provenance attestation present, with subject-path, ordered before publish.",
            evidence,
        )
        return EXIT_PASS

    top = failures[0] if len(failures) == 1 else f"{failures[0]} (and {len(failures)-1} more)"
    reason_q = top.replace('"', '\\"')
    emit_check(
        CHECK_ID, "fail",
        f"Publish workflow(s) missing or misordered attestation: {reason_q}",
        evidence,
        {"kind": "judgement", "human_review": "Wire actions/attest-build-provenance@<sha> BEFORE the publish step in the same job, or in an upstream job in the publish jobs `needs:` chain. Set `with.subject-path` to the published artefact glob (e.g. dist/*). Concierge skip applies until goreleaser build/publish split lands."},
    )
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
