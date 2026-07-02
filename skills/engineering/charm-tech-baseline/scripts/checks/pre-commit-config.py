#!/usr/bin/env python3
"""Check: .pre-commit-config.yaml present (informational).
Tier coverage: product, canonical, personal.

Cycle convention (see references/decisions.md): tool versions live in
pyproject.toml [dependency-groups], not in the pre-commit config's
rev: fields. The hooks invoke tools via `language: system` against
the lockfile. A config that pins versions in rev: fields is flagged
as a soft fail because it duplicates the source of truth.

Carve-out: hooks from pre-commit/pre-commit-hooks (end-of-file-fixer,
trailing-whitespace, check-yaml, check-added-large-files, …) are
generic file-hygiene checks with no Python-tool counterpart in
pyproject.toml dependency-groups. Pinning their rev: is the standard
way to use them and does not duplicate any other source of truth, so
they are exempted from the count.
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

CHECK_ID = "pre-commit-config"
APPLIES = "product,canonical,personal"

EXEMPT_REPOS = {"https://github.com/pre-commit/pre-commit-hooks"}

REPO_RE = re.compile(r"^[ \t]*-[ \t]*repo:[ \t]*(.*)$")
REV_RE = re.compile(r"""^[ \t]*rev:[ \t]+["']?[a-zA-Z0-9._-]+["']?[ \t]*$""")


def count_versioned_revs(text: str) -> int:
    count = 0
    cur = ""
    for line in text.splitlines():
        m = REPO_RE.match(line)
        if m:
            val = m.group(1).strip()
            val = val.replace('"', "").replace("'", "").rstrip()
            cur = val
            continue
        if REV_RE.match(line):
            if cur not in EXEMPT_REPOS:
                count += 1
    return count


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    cd_repo_root()

    if not Path(".pre-commit-config.yaml").is_file() and not Path(".pre-commit-config.yml").is_file():
        emit_check(
            CHECK_ID, "fail",
            "No .pre-commit-config.yaml found.",
            {},
            {"kind": "judgement", "human_review": "Add a minimal config for the languages in use; hooks should use language: system to invoke tools from the uv-locked dependency-groups."},
        )
        return EXIT_FAIL

    config = ".pre-commit-config.yaml"
    if Path(".pre-commit-config.yml").is_file():
        config = ".pre-commit-config.yml"

    try:
        text = Path(config).read_text(errors="replace")
    except OSError:
        text = ""
    versioned_revs = count_versioned_revs(text)

    if versioned_revs > 0:
        emit_check(
            CHECK_ID, "fail",
            f"Pre-commit config pins {versioned_revs} rev: version(s). Cycle convention is to invoke tools via language: system from pyproject.toml [dependency-groups].",
            {"config": config, "versioned_revs": versioned_revs},
            {"kind": "judgement", "human_review": "Move tool versions to pyproject.toml [dependency-groups]; replace each pinned hook with a language: system equivalent. Reference: pytest-jubilant#86."},
        )
        return EXIT_FAIL

    emit_check(
        CHECK_ID, "pass",
        "Pre-commit config present and tool versions not duplicated in rev: fields.",
        {"config": config},
    )
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
