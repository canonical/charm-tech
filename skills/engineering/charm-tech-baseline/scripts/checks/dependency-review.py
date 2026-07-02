#!/usr/bin/env python3
"""Check: actions/dependency-review-action workflow present on PRs.
Tier coverage: product, canonical.

Cycle reference: sweep landed 2026-06-27 (4 PRs open across operator,
pebble, jubilant, charmlibs); see references/sweep-history.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import (
    EXIT_FAIL, EXIT_NA, EXIT_PASS,
    cd_repo_root, emit_check, parse_tier, tier_applies,
)

CHECK_ID = "dependency-review"
APPLIES = "product,canonical"


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
            "No .github/workflows/ directory.",
            {},
            {"kind": "judgement", "human_review": "Set up workflows; then add dependency-review."},
        )
        return EXIT_FAIL

    hit = ""
    for path in sorted(list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml"))):
        try:
            if "actions/dependency-review-action" in path.read_text(errors="replace"):
                hit = str(path)
                break
        except OSError:
            continue

    if hit:
        emit_check(
            CHECK_ID, "pass",
            "dependency-review-action wired up.",
            {"workflow": hit},
        )
        return EXIT_PASS

    emit_check(
        CHECK_ID, "fail",
        "No actions/dependency-review-action workflow.",
        {},
        {"kind": "judgement", "human_review": "Add a dependency-review.yaml workflow on pull_request, ~10 lines. Reference: canonical/operator#2587 (open as of 2026-06-27)."},
    )
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
