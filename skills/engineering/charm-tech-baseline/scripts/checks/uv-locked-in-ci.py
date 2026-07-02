#!/usr/bin/env python3
"""Check: CI invocations of `uv run` and `uv sync` pass `--locked` so a
stale `uv.lock` fails the build rather than silently re-resolving.

Rationale (Canonical Security "How-To: Secure a repo" — Lockfile(s)
section): commit the lockfile and use the frozen-install command in
CI, so drift between `pyproject.toml` and `uv.lock` comes back as a
reviewable commit instead of a silent CI-side re-resolve. Without
`--locked`, a PR that widens a version range in `pyproject.toml`
without regenerating `uv.lock` silently re-resolves in the CI runner
and the transitive-dep delta never appears in the diff.

Preference: `--locked` (fails on stale lockfile) over `--frozen`
(skips freshness check entirely — masks drift instead of surfacing
it). This check accepts either but reports how many use each.

Tier coverage: product, canonical, personal (advisory).

Scope: reads `.github/workflows/*.y*ml` and the top-level `Makefile`
(some repos, e.g. api_demo_server, put `uv run` inside `make lint` /
`make integration` targets that CI shells out to).

Skipped patterns (don't touch the project lockfile — reporting them
would be noise):
  - `uv run --no-project --script ...`
  - `uv run --no-project --with-requirements ...`
  - `uvx <tool>` / `uvx <tool>@vX.Y.Z ...`
  - `uv tool install` / `uv tool run`

Non-uv repos (Go, or Python repos with no `pyproject.toml`) are
reported as `na`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import (
    EXIT_FAIL, EXIT_NA, EXIT_PASS, EXIT_UNKNOWN,
    cd_repo_root, emit_check, parse_tier, tier_applies,
)

CHECK_ID = "uv-locked-in-ci"
APPLIES = "product,canonical,personal"

# Match `uv run` or `uv sync`, at any indent, in a YAML `run:` block or
# Makefile recipe. Group 1 is the invocation slice (everything from
# `uv` to end-of-line — enough to inspect flags).
INVOKE_RE = re.compile(r'(uv\s+(?:run|sync)\b[^\r\n]*)')


def classify(inv: str) -> str:
    """Return one of: locked, frozen, bare, skipped-<reason>."""
    # Skip patterns first.
    if re.search(r'\buv\s+run\s+--no-project\b.*(?:--script|--with-requirements)\b', inv):
        return "skipped-no-project"
    if re.search(r'\buv\s+tool\s+(?:install|run)\b', inv):
        return "skipped-uv-tool"
    # Note: `uvx` is a separate binary; the regex above only matches
    # `uv run|sync`, so uvx invocations never reach this classifier.
    if '--locked' in inv:
        return "locked"
    if '--frozen' in inv:
        return "frozen"
    return "bare"


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    cd_repo_root()

    if not Path("pyproject.toml").is_file() and not Path("uv.lock").is_file():
        emit_check(CHECK_ID, "na", "No pyproject.toml or uv.lock — not a uv project.")
        return EXIT_NA

    # Gather candidate files: workflows + Makefile at the top level.
    files: list[str] = []
    wf_dir = Path(".github/workflows")
    if wf_dir.is_dir():
        for p in wf_dir.iterdir():
            if p.is_file() and p.suffix in (".yml", ".yaml"):
                files.append(str(p))
    for mk in ("Makefile", "makefile", "GNUmakefile"):
        if Path(mk).is_file():
            files.append(mk)
    files = sorted(set(files))

    if not files:
        emit_check(CHECK_ID, "na", "No workflows or Makefile to audit.")
        return EXIT_NA

    totals = {"locked": 0, "frozen": 0, "bare": 0, "skipped-no-project": 0, "skipped-uv-tool": 0}
    bare_hits: list[str] = []

    for path in files:
        try:
            with open(path) as f:
                for lineno, line in enumerate(f, 1):
                    for m in INVOKE_RE.finditer(line):
                        inv = m.group(1)
                        cat = classify(inv)
                        totals[cat] = totals.get(cat, 0) + 1
                        if cat == "bare":
                            bare_hits.append(f"{path}:{lineno}: {inv.strip()}")
        except (OSError, UnicodeDecodeError):
            continue

    n_locked = totals["locked"]
    n_frozen = totals["frozen"]
    n_bare = totals["bare"]
    n_skipped_no_project = totals["skipped-no-project"]
    n_skipped_uv_tool = totals["skipped-uv-tool"]

    total_project = n_locked + n_frozen + n_bare

    evidence = {
        "files_scanned": len(files),
        "invocations": {
            "locked": n_locked,
            "frozen": n_frozen,
            "bare": n_bare,
            "skipped_no_project": n_skipped_no_project,
            "skipped_uv_tool": n_skipped_uv_tool,
        },
    }

    if total_project == 0:
        emit_check(
            CHECK_ID, "na",
            f"No project-scoped uv run / uv sync invocations found in workflows or Makefile (skipped: {n_skipped_no_project} no-project, {n_skipped_uv_tool} uv-tool).",
            evidence,
        )
        return EXIT_NA

    if n_bare == 0:
        if n_frozen > 0 and n_locked == 0:
            emit_check(
                CHECK_ID, "pass",
                f"All {total_project} project-scoped uv invocations use --frozen or --locked ({n_frozen} frozen, 0 bare). Prefer --locked over --frozen — --locked fails on a stale lockfile, --frozen skips the freshness check entirely.",
                evidence,
            )
        else:
            emit_check(
                CHECK_ID, "pass",
                f"All {total_project} project-scoped uv invocations use --locked or --frozen ({n_locked} locked, {n_frozen} frozen).",
                evidence,
            )
        return EXIT_PASS

    remediation = {
        "kind": "judgement",
        "human_review": "Add --locked (preferred) or --frozen to each bare `uv run` / `uv sync` invocation. --locked fails the build if uv.lock is stale vs pyproject.toml, forcing the PR author to commit a fresh lockfile — surfacing the resolution delta as a reviewable diff. --frozen skips the freshness check entirely and masks drift, so prefer --locked.",
    }

    emit_check(
        CHECK_ID, "fail",
        f"{n_bare} of {total_project} project-scoped uv invocation(s) missing --locked/--frozen ({n_locked} locked, {n_frozen} frozen, {n_bare} bare).",
        evidence,
        remediation,
    )
    if bare_hits:
        sys.stderr.write("\n# uv-locked-in-ci detail (bare invocations):\n")
        sys.stderr.write("\n".join(bare_hits) + "\n")
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
