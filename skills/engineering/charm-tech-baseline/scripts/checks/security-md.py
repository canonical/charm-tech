#!/usr/bin/env python3
"""Check: SECURITY.md exists and references the Ubuntu disclosure policy.
Tier coverage: all (product, canonical, personal).

Mandate: SEC0025 §General Requirements + SEC0026 (Canonical-internal);
best practice for personal-tier.

Pass:    SECURITY.md present AND links to ubuntu.com/security/disclosure-policy
         OR to security@ubuntu.com / security@canonical.com
Fail:    SECURITY.md missing, OR present but no disclosure-policy link/contact
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

CHECK_ID = "security-md"
APPLIES = "product,canonical,personal"

PATTERN = re.compile(r"ubuntu\.com/security/disclosure-policy|security@(ubuntu|canonical)\.com|security/advisories", re.IGNORECASE)


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    cd_repo_root()

    p = Path("SECURITY.md")
    if not p.is_file():
        emit_check(
            CHECK_ID, "fail",
            "SECURITY.md is missing.",
            {},
            {"kind": "mechanical", "script": "scripts/fixes/add-security-md.py", "human_review": "Customise the disclosure contact and supported-versions table."},
        )
        return EXIT_FAIL

    text = p.read_text(errors="replace")
    if PATTERN.search(text):
        lines = text.count("\n")
        emit_check(
            CHECK_ID, "pass",
            "SECURITY.md present and references the Ubuntu disclosure policy.",
            {"path": "SECURITY.md", "lines": lines},
        )
        return EXIT_PASS

    emit_check(
        CHECK_ID, "fail",
        "SECURITY.md present but does not reference the Ubuntu disclosure policy or a security contact.",
        {"path": "SECURITY.md"},
        {"kind": "judgement", "human_review": "Add a Reporting section linking https://ubuntu.com/security/disclosure-policy and the project security contact."},
    )
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
