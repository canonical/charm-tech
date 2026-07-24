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
they are exempted from the *tool-version* count.

The carve-out still has to be **SHA-pinned**, not tag-pinned — same
discipline as gha-sha-pinning (see references/decisions.md § "Remote
pre-commit hooks — SHA-pin, don't tag-pin"). A `rev: v5.0.0` on an
exempt repo is a gap; a `rev: <40-char hex>  # frozen: v5.0.0` is
the shape.
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
REV_LINE_RE = re.compile(r"^[ \t]*rev:[ \t]+(.*)$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def scan_revs(text: str) -> tuple[int, int]:
    """Return (tool_revs, tag_pinned_exempt_revs).

    tool_revs counts rev: entries on non-exempt repos (duplicating the
    dependency-group source of truth).

    tag_pinned_exempt_revs counts rev: entries on the exempt carve-out
    that aren't full 40-char SHAs — the carve-out still has to be
    SHA-pinned, same discipline as gha-sha-pinning.
    """
    tool_revs = 0
    tag_pinned = 0
    cur = ""
    for line in text.splitlines():
        m = REPO_RE.match(line)
        if m:
            cur = m.group(1).strip().replace('"', "").replace("'", "").rstrip()
            continue
        rm = REV_LINE_RE.match(line)
        if not rm:
            continue
        val = rm.group(1)
        # Strip trailing comment (e.g. `# frozen: v5.0.0`) before matching.
        val = re.sub(r"[ \t]*#.*$", "", val)
        val = val.replace('"', "").replace("'", "").strip()
        if cur in EXEMPT_REPOS:
            if not SHA_RE.match(val):
                tag_pinned += 1
        else:
            tool_revs += 1
    return tool_revs, tag_pinned


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
    versioned_revs, tag_pinned_revs = scan_revs(text)

    if versioned_revs > 0:
        emit_check(
            CHECK_ID, "fail",
            f"Pre-commit config pins {versioned_revs} rev: version(s). Cycle convention is to invoke tools via language: system from pyproject.toml [dependency-groups].",
            {"config": config, "versioned_revs": versioned_revs},
            {"kind": "judgement", "human_review": "Move tool versions to pyproject.toml [dependency-groups]; replace each pinned hook with a language: system equivalent. Reference: pytest-jubilant#86."},
        )
        return EXIT_FAIL

    if tag_pinned_revs > 0:
        emit_check(
            CHECK_ID, "fail",
            f"Pre-commit config has {tag_pinned_revs} rev: entry(s) pinned by tag rather than full SHA. Cycle convention (see decisions.md § Remote pre-commit hooks): SHA-pin, don't tag-pin — same discipline as gha-sha-pinning.",
            {"config": config, "tag_pinned_revs": tag_pinned_revs},
            {"kind": "judgement", "human_review": "Resolve each tag-pinned rev: to its 40-char commit SHA and add a `# frozen: <tag>` trailing comment. Dependabot pre-commit ecosystem will bump the SHA."},
        )
        return EXIT_FAIL

    emit_check(
        CHECK_ID, "pass",
        "Pre-commit config present, no tool versions duplicated in rev: fields, and any surviving rev: is SHA-pinned.",
        {"config": config},
    )
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
