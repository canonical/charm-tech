#!/usr/bin/env python3
"""Check: GitHub releases are immutable (latest release's `immutable: true`).
Tier coverage: product, canonical.

Implementation: uses `gh api repos/<owner>/<repo>/releases` if `gh` is
available; falls back to a 'unknown' note if it isn't.

Known blockers (do not flag as fail):
  - pebble: snap build (pebble#856)
  - concierge: goreleaser monolith (concierge#172 / #142)
Heuristically: if the repo origin is canonical/{pebble,concierge,charmlibs},
emit a note explaining the blocker.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import (
    EXIT_FAIL, EXIT_NA, EXIT_PASS, EXIT_UNKNOWN,
    emit_check, origin_url, parse_tier, run, tier_applies,
)

CHECK_ID = "immutable-releases"
APPLIES = "product,canonical"


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    url = origin_url()
    slug = url[len("https://github.com/"):] if url.startswith("https://github.com/") else url

    if slug == "canonical/pebble":
        emit_check(CHECK_ID, "na", "pebble immutable-releases blocked on snap-build process update (pebble#856).")
        return EXIT_NA
    if slug == "canonical/concierge":
        emit_check(CHECK_ID, "na", "concierge immutable-releases blocked on goreleaser build/publish split (concierge#172 / #142).")
        return EXIT_NA

    if not shutil.which("gh"):
        emit_check(CHECK_ID, "unknown", "gh CLI not installed; cannot query release immutability flag.")
        return EXIT_UNKNOWN

    r = run(["gh", "api", f"repos/{slug}/releases?per_page=1", "--jq", ".[0].immutable // empty"])
    flag = r.stdout.strip() if r.returncode == 0 else ""
    if not flag:
        emit_check(CHECK_ID, "na", f"No releases on {slug} yet — toggle the setting before the first release.")
        return EXIT_NA

    if flag == "true":
        emit_check(
            CHECK_ID, "pass",
            "Latest release is immutable.",
            {"slug": slug},
        )
        return EXIT_PASS

    emit_check(
        CHECK_ID, "fail",
        "Latest release is NOT immutable. Setting needs to be flipped, or an active blocker tracked.",
        {"slug": slug},
        {"kind": "judgement", "human_review": "Flip the per-repo Make-published-releases-immutable toggle in GitHub Settings. If blocked on tooling (goreleaser, snap-build), record the blocker upstream and revisit when the upstream lands."},
    )
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
