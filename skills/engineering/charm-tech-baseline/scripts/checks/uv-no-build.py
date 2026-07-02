#!/usr/bin/env python3
"""Check: pyproject.toml sets `[tool.uv].no-build = true` (with optional
per-package escape hatches via `[tool.uv].no-build-package`).

Rationale (Canonical Security "How-To: Secure a repo" — Install scripts
section): `pip install <sdist>` and `uv sync` from an sdist run the
source distribution's setup.py / PEP 517 build hooks — arbitrary code
execution at install time. Wheels don't run install scripts.
`no-build = true` tells uv to refuse any sdist and only accept wheels,
closing the vector.

A fleet-wide scan (2026-07-02) found 0/571 dependencies were sdist-
only, so this is a zero-cost change today for typical Charm Tech
repos. If a specific dep only ships sdist, per-package overrides are
supported: `no-build-package = ["that-one-pkg"]`.

Tier coverage: all tiers.
`na` when there's no pyproject.toml, no [tool.uv], and no uv.lock
(i.e. not a uv project). `fail` if uv.lock is present but [tool.uv]
is absent (same rule as uv-exclude-newer).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import (
    EXIT_FAIL, EXIT_NA, EXIT_PASS, EXIT_UNKNOWN,
    cd_repo_root, emit_check, parse_tier, tier_applies,
)

CHECK_ID = "uv-no-build"
APPLIES = "product,canonical,personal"

REMEDIATION_ADD = {
    "kind": "judgement",
    "human_review": (
        "Add `no-build = true` under [tool.uv] in pyproject.toml. Refuses sdist "
        "installs (closes the setup.py-executes-arbitrary-code vector); wheels-"
        "only. Per-package escape hatch if a specific dep only ships sdist: "
        "`no-build-package = [\"that-one-pkg\"]`. See Canonical Security "
        "\"How-To: Secure a repo\" — Install scripts."
    ),
}


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    cd_repo_root()

    if not Path("pyproject.toml").is_file():
        emit_check(CHECK_ID, "na", "No pyproject.toml — not a uv project.")
        return EXIT_NA

    try:
        import tomllib
        have_parser = True
    except ImportError:
        have_parser = False

    if not have_parser:
        text = Path("pyproject.toml").read_text(errors="replace")
        has_tool_uv = bool(re.search(r'^\[tool\.uv\]', text, re.MULTILINE))
        has_no_build = bool(re.search(r'^\s*no-build\s*=\s*true', text, re.MULTILINE))
        if has_tool_uv and has_no_build:
            emit_check(
                CHECK_ID, "pass",
                "[tool.uv].no-build present (value not validated — python3+tomllib unavailable).",
                {"parser": False},
            )
            return EXIT_PASS
        if Path("uv.lock").is_file():
            emit_check(
                CHECK_ID, "fail",
                "uv.lock present but no [tool.uv].no-build = true found in pyproject.toml (unvalidated fallback).",
                {"parser": False, "uv_lock_present": True},
                REMEDIATION_ADD,
            )
            return EXIT_FAIL
        emit_check(
            CHECK_ID, "na",
            "No [tool.uv].no-build and no uv.lock — not a uv-configured project.",
            {"parser": False, "uv_lock_present": False},
        )
        return EXIT_NA

    try:
        with open("pyproject.toml", "rb") as f:
            doc = tomllib.load(f)
    except Exception as e:
        emit_check(
            CHECK_ID, "unknown",
            f"Could not parse pyproject.toml: {e}",
            {"parser": True},
        )
        return EXIT_UNKNOWN

    tool_uv = (doc.get("tool") or {}).get("uv")
    if tool_uv is None:
        # A uv.lock in the working tree means the project uses uv even
        # though pyproject.toml doesn't declare [tool.uv] yet — that's a
        # fail (add the section), not na.
        if Path("uv.lock").is_file():
            emit_check(
                CHECK_ID, "fail",
                "uv.lock present but pyproject.toml has no [tool.uv] section. Add [tool.uv] with no-build = true.",
                {"parser": True, "tool_uv": False, "uv_lock_present": True},
                REMEDIATION_ADD,
            )
            return EXIT_FAIL
        emit_check(
            CHECK_ID, "na",
            "pyproject.toml has no [tool.uv] and no uv.lock — not a uv-configured project.",
            {"parser": True, "tool_uv": False, "uv_lock_present": False},
        )
        return EXIT_NA

    no_build_package = tool_uv.get("no-build-package") or []

    if "no-build" not in tool_uv:
        emit_check(
            CHECK_ID, "fail",
            f"[tool.uv] present but no-build not set. Add no-build = true. (Any existing no-build-package: {no_build_package}.)",
            {"parser": True, "no_build": None, "no_build_package": no_build_package},
            REMEDIATION_ADD,
        )
        return EXIT_FAIL

    value = tool_uv["no-build"]
    if value is True:
        emit_check(
            CHECK_ID, "pass",
            f"[tool.uv].no-build = true. Per-package overrides: {no_build_package}.",
            {"parser": True, "no_build": True, "no_build_package": no_build_package},
        )
        return EXIT_PASS

    if value is False:
        emit_check(
            CHECK_ID, "fail",
            "[tool.uv].no-build is explicitly false. Set to true to refuse sdist installs.",
            {"parser": True, "no_build": False},
            {
                "kind": "judgement",
                "human_review": (
                    "Set no-build = true under [tool.uv]. If specific packages "
                    "genuinely need sdist builds, allow only those via "
                    "`no-build-package = [\"pkg1\",\"pkg2\"]` instead of turning "
                    "the blanket protection off."
                ),
            },
        )
        return EXIT_FAIL

    emit_check(
        CHECK_ID, "fail",
        f"[tool.uv].no-build is not a boolean: {type(value).__name__} {value!r}",
        {"parser": True},
        {"kind": "judgement", "human_review": "Set no-build to a boolean, e.g. no-build = true."},
    )
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
