#!/usr/bin/env python3
"""Check: no use of the deprecated actions/attest-sbom action.
Tier coverage: all.

actions/attest-sbom is deprecated in favour of actions/attest. Since v4 it
already runs as a thin wrapper over actions/attest, and its inputs
(subject-path, sbom-path) are compatible with the new action — so this is
a straight action swap with no behaviour change.

Ref: https://github.com/actions/attest-sbom (deprecation notice).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import (
    EXIT_FAIL, EXIT_NA, EXIT_PASS,
    cd_repo_root, emit_check, parse_tier, tier_applies,
)

CHECK_ID = "attest-sbom-deprecated"
APPLIES = "all"


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    cd_repo_root()

    wf_dir = Path(".github/workflows")
    if not wf_dir.is_dir():
        emit_check(CHECK_ID, "na", "No .github/workflows/ directory.")
        return EXIT_NA

    hits: list[str] = []
    for path in sorted(list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml"))):
        try:
            if "actions/attest-sbom" in path.read_text(errors="replace"):
                hits.append(str(path))
        except OSError:
            continue

    if not hits:
        emit_check(
            CHECK_ID, "pass",
            "No use of the deprecated actions/attest-sbom action.",
        )
        return EXIT_PASS

    emit_check(
        CHECK_ID, "fail",
        "actions/attest-sbom is deprecated; swap to actions/attest (same inputs).",
        {"workflows": hits},
        {
            "kind": "judgement",
            "human_review": (
                "Replace `uses: actions/attest-sbom@<sha>` with "
                "`uses: actions/attest@<sha>` in the listed workflows; "
                "subject-path and sbom-path inputs are compatible. "
                "Ref: https://github.com/actions/attest-sbom (deprecation notice)."
            ),
        },
    )
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
