#!/usr/bin/env python3
"""Check: zizmor is invoked in CI.
Tier coverage: product, canonical.

A .github/zizmor.yaml config file is no longer required — the pinning
policy has no allowlist exceptions, so zizmor's default unpinned-uses
rule is sufficient. If a config file exists it is not flagged, but
it's redundant.
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

CHECK_ID = "zizmor-config"
APPLIES = "product,canonical"

PATTERN = re.compile(
    r"woodruffw/zizmor|zizmor-action|uvx[ \t]+zizmor|uv[ \t]+run[ \t].*zizmor|(^|[^a-zA-Z0-9_./-])zizmor[ \t]"
)


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    cd_repo_root()

    hits: list[str] = []
    wf_dir = Path(".github/workflows")
    if wf_dir.is_dir():
        for p in sorted(list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml"))):
            try:
                text = p.read_text(errors="replace")
            except OSError:
                continue
            for line in text.splitlines():
                if PATTERN.search(line):
                    hits.append(str(p))
                    break

    if hits:
        first = hits[0]
        emit_check(
            CHECK_ID, "pass",
            f"zizmor invoked in CI ({first}).",
            {"workflow": first},
        )
        return EXIT_PASS

    emit_check(
        CHECK_ID, "fail",
        "No workflow invokes zizmor.",
        {},
        {"kind": "judgement", "human_review": "Add a CI step that runs zizmor against .github/workflows/ (uvx zizmor, or via the project's lint dependency-group). No .github/zizmor.yaml config file is required — the default unpinned-uses rule enforces SHA-pinning without an allowlist."},
    )
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
