#!/usr/bin/env python3
"""Check: Threat model — informational only.
Tier coverage: product only.

Threat models live in the central SSDLC Artifacts Drive. This check
emits an informational note prompting the agent to confirm the
Drive sheet is current for the cycle.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import (
    EXIT_NA, EXIT_PASS,
    emit_check, parse_tier, tier_applies,
)

CHECK_ID = "threat-model-drive"
APPLIES = "product"


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    emit_check(
        CHECK_ID, "unknown",
        "Cannot verify from the repo — threat models live in the SSDLC Artifacts Drive. Confirm a refreshed model exists for this cycle.",
        {},
        {"kind": "judgement", "human_review": "SEC0028: refresh every release cycle; demonstrate no unacceptable residual risk; any accepted risk needs a Risk Acceptance Form. Charm SDK consolidated sheet covers ops/ops-scenario/ops-tracing/jubilant/concierge; pebble has its own sheet."},
    )
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
