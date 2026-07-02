#!/usr/bin/env python3
"""Check: OpenSSF Scorecard workflow + README badge.
Tier coverage: product, canonical. (Operator pilots; rest gated behind
its adoption — see references/open-investigations.md.)

Pass     — workflow uses ossf/scorecard-action; README has the badge.
Partial  — workflow OR badge present but not both — emitted as fail with
           human_review noting which half is missing.
Fail     — neither present.
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

CHECK_ID = "openssf-scorecard"
APPLIES = "product,canonical"

BADGE_RE = re.compile(r"securityscorecards\.dev/projects/github\.com|scorecard\.dev/projects")


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    cd_repo_root()

    workflow = ""
    wf_dir = Path(".github/workflows")
    if wf_dir.is_dir():
        for p in sorted(list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml"))):
            try:
                if "ossf/scorecard-action" in p.read_text(errors="replace"):
                    workflow = str(p)
                    break
            except OSError:
                continue

    badge = ""
    for readme in ("README.md", "README.rst", "README.txt", "readme.md"):
        p = Path(readme)
        if not p.is_file():
            continue
        try:
            if BADGE_RE.search(p.read_text(errors="replace")):
                badge = readme
                break
        except OSError:
            continue

    if workflow and badge:
        emit_check(
            CHECK_ID, "pass",
            f"OpenSSF Scorecard workflow ({workflow}) and README badge ({badge}) present.",
            {"workflow": workflow, "badge_in": badge},
        )
        return EXIT_PASS

    if not workflow and not badge:
        emit_check(
            CHECK_ID, "fail",
            "No OpenSSF Scorecard workflow or badge. (Note: 26.10-cycle rollout is gated behind operator's adoption — see references/open-investigations.md.)",
            {},
            {"kind": "judgement", "human_review": "Wait for operator adoption to settle and propagate its workflow + branch-protection wiring; do not invent conventions ahead of it."},
        )
        return EXIT_FAIL

    missing = "workflow"
    if not badge:
        missing = "README badge"
    if not workflow:
        missing = "workflow"
    emit_check(
        CHECK_ID, "fail",
        f"Partial OpenSSF Scorecard setup — {missing} missing.",
        {"workflow": workflow, "badge_in": badge},
        {"kind": "judgement", "human_review": "Add the missing half (workflow or badge) to match the operator-led convention."},
    )
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
