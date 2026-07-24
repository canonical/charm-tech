#!/usr/bin/env python3
"""Check: SEC0030 V1.3 Security Documentation coverage.
Tier coverage: product only.

Looks for either docs/explanation/security.md (Sphinx-stack convention)
or an expanded SECURITY.md that covers the seven V1.3 sections.
The check is heuristic — it looks for headings, not deep content.
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

CHECK_ID = "sec0030-coverage"
APPLIES = "product"

REQUIRED = [
    ("Product architecture", "Product architecture"),
    ("Secure by design", "Secure by design"),
    ("Cryptography", "Crypt"),
    ("Hardening", "Hardening"),
    ("Logging and monitoring", "Logging|Monitoring"),
    ("Decommissioning", "Decommissioning"),
    ("Security lifecycle", "Security lifecycle|Security updates"),
]


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    cd_repo_root()

    target = ""
    for path in ("docs/explanation/security.md", "docs/security.md", "SECURITY.md"):
        if Path(path).is_file():
            target = path
            break

    if not target:
        emit_check(
            CHECK_ID, "fail",
            "No security documentation found (docs/explanation/security.md or expanded SECURITY.md).",
            {},
            {"kind": "judgement", "human_review": "Either author docs/explanation/security.md (preferred) or expand SECURITY.md to cover the seven SEC0030 V1.3 sections."},
        )
        return EXIT_FAIL

    text = Path(target).read_text(errors="replace")
    missing_parts: list[str] = []
    for label, pattern in REQUIRED:
        rx = re.compile(rf"^#{{1,4}} .*({pattern})", re.IGNORECASE | re.MULTILINE)
        if not rx.search(text):
            missing_parts.append(label)

    if not missing_parts:
        emit_check(
            CHECK_ID, "pass",
            f"SEC0030 V1.3 coverage looks complete in {target}.",
            {"path": target},
        )
        return EXIT_PASS

    trimmed = "; ".join(missing_parts)
    emit_check(
        CHECK_ID, "fail",
        f"SEC0030 V1.3 missing section(s) in {target}: {trimmed}",
        {"path": target, "missing": trimmed},
        {"kind": "judgement", "human_review": "Add the missing section(s). See operator#2571, pebble#893, jubilant#332, charm-ubuntu#87 for reference patterns (sentence-case headers, Mermaid diagrams, bulleted hardening with To-harden intro, channels-bullet-list at end of Reporting)."},
    )
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
