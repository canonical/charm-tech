#!/usr/bin/env python3
"""Check: AGENTS.md present (best-of-class; agent-onboarding entry point).
Tier coverage: product, canonical. Personal-tier: informational only.

Convention: keep it minimal — a short pointer file, not an encyclopaedia.
See references/sweep-history.md for the deferred AGENTS.md sweep.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import (
    EXIT_FAIL, EXIT_NA, EXIT_PASS, EXIT_UNKNOWN,
    cd_repo_root, emit_check, parse_tier, tier_applies,
)

CHECK_ID = "agents-md"
APPLIES = "product,canonical,personal"


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    cd_repo_root()

    p = Path("AGENTS.md")
    if p.is_file():
        lines = p.read_text().count("\n")
        if lines > 200:
            emit_check(
                CHECK_ID, "fail",
                f"AGENTS.md present but at {lines} lines is well past the 'keep it minimal' convention.",
                {"path": "AGENTS.md", "lines": lines},
                {"kind": "judgement", "human_review": "Trim AGENTS.md down — point at HACKING/CONTRIBUTING for depth; keep AGENTS.md to setup commands and conventions only."},
            )
            return EXIT_FAIL
        emit_check(
            CHECK_ID, "pass",
            f"AGENTS.md present ({lines} lines).",
            {"path": "AGENTS.md", "lines": lines},
        )
        return EXIT_PASS

    emit_check(
        CHECK_ID, "fail",
        "No AGENTS.md found.",
        {},
        {"kind": "mechanical", "script": "scripts/fixes/add-agents-md.py", "human_review": "Customise the dev-setup commands for this repo (uv / go / make / just)."},
    )
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
