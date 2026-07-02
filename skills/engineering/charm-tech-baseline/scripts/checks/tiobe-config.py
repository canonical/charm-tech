#!/usr/bin/env python3
"""Check: TIOBE TICS workflow present, wired with the auth token, and the
language-specific linters TICS needs are declared as project dependencies.
Tier coverage: product only.

Mandate: SEC0024 (Static Code Analysis). TIOBE TICS is the required
SCA tool for SSDLC satisfaction; additional scanners are encouraged
but do not substitute.

Pass:    A workflow under .github/workflows/ invokes tiobe/tics-github-action,
         references `secrets.TICSAUTHTOKEN`, and the per-language linters
         (Python: flake8 + pylint; Go: staticcheck) are visible somewhere
         in the repo (workflow install step, pyproject.toml dep group,
         Makefile, or go.mod tooling).
Fail:    Any of the above missing.

Notes: This script does NOT verify the TQI target spreadsheet entry, the
Coverage XML artefact path, or the actual TICS dashboard score (all live
outside the repo). The `tqi-security-target` check covers the spreadsheet
entry; coverage-XML is left as a per-repo judgement.
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

CHECK_ID = "tiobe-config"
APPLIES = "product"


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    cd_repo_root()

    wf_dir = Path(".github/workflows")
    if not wf_dir.is_dir():
        emit_check(
            CHECK_ID, "fail",
            "No .github/workflows/ directory; cannot host TIOBE TICS workflow.",
            {},
            {"kind": "judgement", "human_review": "Add a tiobe.yaml workflow per https://canonical-tiobe-docs.canonical.com/ — needs the self-hosted tiobe runner and viewer config selection."},
        )
        return EXIT_FAIL

    hits: list[str] = []
    for p in sorted(list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml"))):
        try:
            if "tiobe/tics-github-action" in p.read_text(errors="replace"):
                hits.append(str(p))
        except OSError:
            continue

    if not hits:
        emit_check(
            CHECK_ID, "fail",
            "No TIOBE TICS workflow found under .github/workflows/.",
            {},
            {"kind": "judgement", "human_review": "Add a tiobe.yaml workflow using the self-hosted tiobe runner and the appropriate viewer config (GoProjects for Go; default for Python)."},
        )
        return EXIT_FAIL

    workflow = hits[0]
    problems: list[str] = []

    workflow_text = Path(workflow).read_text(errors="replace")
    if not re.search(r"secrets\.TICSAUTHTOKEN", workflow_text):
        problems.append("workflow does not reference secrets.TICSAUTHTOKEN")

    # Determine language.
    language = "unknown"
    if Path("pyproject.toml").is_file() or any(Path(".").glob("*.py")) or Path("requirements.txt").is_file() or Path("setup.cfg").is_file():
        language = "python"
    elif Path("go.mod").is_file():
        language = "go"

    # Aggregate content from candidate files.
    def gather() -> str:
        parts = [workflow_text]
        for f in ("pyproject.toml", "requirements.txt", "requirements-dev.txt", "setup.cfg", "Makefile", "go.mod", "tools.go"):
            p = Path(f)
            if p.is_file():
                try:
                    parts.append(p.read_text(errors="replace"))
                except OSError:
                    pass
        return "\n".join(parts)

    haystack = gather()

    def linter_hit(pattern: str) -> bool:
        return re.search(pattern, haystack, re.IGNORECASE) is not None

    if language == "python":
        if not linter_hit(r"(^|[^a-z])flake8([^a-z]|$)"):
            problems.append("flake8 not declared in workflow/pyproject/requirements/Makefile")
        if not linter_hit(r"(^|[^a-z])pylint([^a-z]|$)"):
            problems.append("pylint not declared in workflow/pyproject/requirements/Makefile")
    elif language == "go":
        if not linter_hit(r"staticcheck"):
            problems.append("staticcheck not declared in workflow/Makefile/go.mod/tools.go")

    evidence = {"workflow": workflow, "language": language}

    if not problems:
        emit_check(
            CHECK_ID, "pass",
            "TIOBE TICS workflow present, TICSAUTHTOKEN wired, and language linters declared.",
            evidence,
        )
        return EXIT_PASS

    joined = "; ".join(problems)
    emit_check(
        CHECK_ID, "fail",
        f"TIOBE TICS workflow present but incomplete: {joined}.",
        evidence,
        {"kind": "judgement", "human_review": "Add secrets.TICSAUTHTOKEN to the workflow env (TICS publishes nothing without it). For Python repos, declare flake8 and pylint in a [dependency-groups] block (or install them in the workflow). For Go repos, add staticcheck via a tools.go entry, Makefile target, or workflow install step. Also confirm a Cobertura coverage artefact is produced before the TICS step runs — that is repo-specific and not auto-verified here."},
    )
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
