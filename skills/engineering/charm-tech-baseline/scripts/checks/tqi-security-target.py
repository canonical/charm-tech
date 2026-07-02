#!/usr/bin/env python3
"""Check: TQI security target — informational only.
Tier coverage: product only.

The TQI target lives in the central *TiCS Targets 26.10* spreadsheet,
not the repo. This check just emits an informational note prompting
the agent to verify the target is recorded for the cycle.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import (
    EXIT_NA, EXIT_PASS,
    emit_check, parse_tier, tier_applies,
)

CHECK_ID = "tqi-security-target"
APPLIES = "product"


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    emit_check(
        CHECK_ID, "unknown",
        "Cannot verify from the repo — the TQI security target lives in the *TiCS Targets 26.10* spreadsheet. Confirm a target is recorded for this product.",
        {},
        {"kind": "judgement", "human_review": "Set/verify the per-repo Security metric (TQI) target in *TiCS Targets 26.10* by 30 June."},
    )
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
