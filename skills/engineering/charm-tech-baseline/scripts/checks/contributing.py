#!/usr/bin/env python3
"""Check: CONTRIBUTING.md (or equivalent) present AND documents the PR
workflow with a "Pull requests" anchor.
Tier coverage: product, canonical.

Why the anchor matters: .github/check-conventional-pr-title.py (the
validate-pr-title workflow's helper) prints an error message ending in
"Read more: https://github.com/<owner>/<repo>/blob/<branch>/CONTRIBUTING.md#pull-requests".
If the destination file has no `# Pull requests` heading the link
silently lands at the top of the document — the audited Charm Tech
pattern (10 of 14 repos) is to have the heading.

Accepted variants for the file itself: CONTRIBUTING.md, HACKING.md,
docs/contributing.md, docs/how-to/contribute.md, .github/CONTRIBUTING.md
(pebble uses HACKING.md).
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

CHECK_ID = "contributing"
APPLIES = "product,canonical"


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    cd_repo_root()

    found = ""
    for path in ("CONTRIBUTING.md", "HACKING.md", "docs/contributing.md", "docs/how-to/contribute.md", ".github/CONTRIBUTING.md"):
        if Path(path).is_file():
            found = path
            break

    if not found:
        emit_check(
            CHECK_ID, "fail",
            "No CONTRIBUTING.md / HACKING.md / docs/contributing found.",
            {},
            {"kind": "mechanical", "script": "scripts/fixes/add-contributing.py", "human_review": "Customise the dev-setup pointer / project description for the repo (Python / Go / docs)."},
        )
        return EXIT_FAIL

    text = Path(found).read_text(errors="replace")
    # ^#{1,3}\s+pull\s+requests?\s*$ (multiline, case-insensitive)
    if re.search(r"^#{1,3}[ \t]+pull[ \t]+requests?[ \t]*$", text, re.IGNORECASE | re.MULTILINE):
        emit_check(
            CHECK_ID, "pass",
            f"Contributing guidance present at {found} with a Pull requests section.",
            {"path": found, "pull_requests_heading": True},
        )
        return EXIT_PASS

    emit_check(
        CHECK_ID, "fail",
        f"{found} present but has no 'Pull requests' heading — the validate-pr-title.py \"Read more\" URL (#pull-requests) will not anchor.",
        {"path": found, "pull_requests_heading": False},
        {"kind": "judgement", "human_review": "Add a `# Pull requests` (or `## Pull requests`) section listing the allowed Conventional-Commits types (chore, ci, docs, feat, fix, perf, refactor, revert, test) and the no-scopes rule. See assets/CONTRIBUTING.md.template for the canonical shape; for pebble-style HACKING.md the anchor can live there instead."},
    )
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
