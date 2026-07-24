#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Check: workflow secret-handling hygiene.

Follows the Canonical Security "Repository security" page (Secrets section)
— a repo-level secret-handling audit that flags patterns known to leak
secrets or over-scope them. Fleet audit 2026-07-02 (recorded in
roadmap/26.10/repo-setup/security-docs-gap.md rows #32-#36) turned up one
real hit across all 9 Charm Tech in-scope repos; this check turns that
audit into a reusable per-repo verification.

Detects, in .github/workflows/*.y*ml:
  * workflow-level `env:` blocks that reference `${{ secrets.* }}`
    (over-scoped: every job/step in the workflow sees the secret)
  * job-level `env:` blocks that reference `${{ secrets.* }}`
    (over-scoped: every step in the job sees the secret; use step-level
    env: instead)
  * `run:` lines that `echo` / `printf` / `cat` a secret expression
    (log-masking is not guaranteed for every transformation — the
    reference page warns against this explicitly)
  * `secrets: inherit` in reusable workflow calls (pass named secrets
    instead so the callee's secret surface is auditable)

Tier coverage: product, canonical. (Personal-tier: advisory — secret
handling still matters, but personal repos may lack even a workflow to
scan.)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import (
    EXIT_FAIL, EXIT_NA, EXIT_PASS,
    cd_repo_root, emit_check, parse_tier, tier_applies,
)

import yaml

CHECK_ID = "workflow-secrets"
APPLIES = "product,canonical,personal"

SECRET_RE = re.compile(r"\$\{\{\s*secrets\.")
ECHO_RE = re.compile(r"^[ \t]*(-[ \t]+)?run:[ \t]*(echo|printf|cat)\b.*\$\{\{[ \t]*secrets\.")
INHERIT_RE = re.compile(r"^[ \t]*secrets:[ \t]*inherit\b")


def walk_env(env, scope: str, findings: list[tuple[str, str]], path_parts: list[str]) -> None:
    if not isinstance(env, dict):
        return
    for k, v in env.items():
        if isinstance(v, str) and SECRET_RE.search(v):
            findings.append((scope, ".".join(path_parts + [str(k)])))


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    cd_repo_root()

    wf_dir = Path(".github/workflows")
    if not wf_dir.is_dir():
        emit_check(CHECK_ID, "na", "No .github/workflows/ directory.")
        return EXIT_NA

    workflows = sorted(
        [p for p in wf_dir.iterdir() if p.is_file() and p.suffix in (".yml", ".yaml")]
    )
    if not workflows:
        emit_check(CHECK_ID, "na", "No workflow files under .github/workflows/.")
        return EXIT_NA

    have_parser = True  # PyYAML available via PEP 723

    echo_hits: list[str] = []
    inherit_hits: list[str] = []
    for wf in workflows:
        try:
            text = wf.read_text(errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if ECHO_RE.match(line):
                echo_hits.append(f"{wf}:{i}:{line}")
            if INHERIT_RE.match(line):
                inherit_hits.append(f"{wf}:{i}:{line}")

    env_hits: list[tuple[str, str, str]] = []
    for wf in workflows:
        try:
            with open(wf) as f:
                doc = yaml.safe_load(f)
        except Exception:
            continue
        if not isinstance(doc, dict):
            continue
        findings: list[tuple[str, str]] = []
        walk_env(doc.get("env"), "workflow", findings, [])
        jobs = doc.get("jobs") or {}
        if isinstance(jobs, dict):
            for jname, job in jobs.items():
                if not isinstance(job, dict):
                    continue
                walk_env(job.get("env"), "job", findings, [f"jobs.{jname}"])
        for scope, key in findings:
            env_hits.append((str(wf), scope, key))

    n_workflow = sum(1 for _, s, _ in env_hits if s == "workflow")
    n_job = sum(1 for _, s, _ in env_hits if s == "job")
    n_echo = len(echo_hits)
    n_inherit = len(inherit_hits)
    total = n_workflow + n_job + n_echo + n_inherit

    evidence = {
        "workflows_scanned": len(workflows),
        "parser": have_parser,
        "hits": {
            "workflow_env": n_workflow,
            "job_env": n_job,
            "echo_secret": n_echo,
            "secrets_inherit": n_inherit,
        },
    }

    if total == 0:
        emit_check(
            CHECK_ID, "pass",
            f"No workflow-/job-level env: secrets, echo-secret, or secrets: inherit hits across {len(workflows)} workflow(s).",
            evidence,
        )
        return EXIT_PASS

    summary = (
        f"Secret-handling hits: {n_workflow} workflow-level env, {n_job} job-level env, "
        f"{n_echo} echo-secret, {n_inherit} secrets: inherit."
    )
    details = ""
    if env_hits:
        details += "env: scope hits:\n" + "\n".join(f"{w}\t{s}\t{k}" for w, s, k in env_hits) + "\n"
    if echo_hits:
        details += "echo/printf/cat hits (file:line:content):\n" + "\n".join(echo_hits) + "\n"
    if inherit_hits:
        details += "secrets: inherit hits:\n" + "\n".join(inherit_hits) + "\n"

    remediation = {
        "kind": "judgement",
        "human_review": "Move secrets to step-level env: (never workflow- or job-level). Never echo/printf/cat a secret expression — pass via env: and reference $VAR instead. In reusable-workflow calls, pass named secrets rather than secrets: inherit.",
    }

    emit_check(CHECK_ID, "fail", summary, evidence, remediation)
    if details:
        sys.stderr.write(f"\n# workflow-secrets detail:\n{details}")
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
