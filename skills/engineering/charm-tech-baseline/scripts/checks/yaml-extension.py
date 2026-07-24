#!/usr/bin/env python3
"""Check: YAML files under .github/ use the .yaml extension, not .yml.
Tier coverage: product, canonical, personal.

Convention: Charm Tech (and the broader Canonical convention) prefers
the explicit `.yaml` spelling — matching the official YAML spec and the
pattern already used by almost every Charm Tech-authored workflow this cycle.
Mixed extensions inside one repo also defeat tooling globs that only
match one form.

Scope: anything under .github/ — workflows, dependabot, zizmor,
issue templates, etc. Anything outside .github/ (Snapcraft snapcraft.yaml,
Rockcraft rockcraft.yaml, etc.) is out of scope; those names are fixed
by upstream tooling.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import (
    EXIT_FAIL, EXIT_NA, EXIT_PASS,
    cd_repo_root, emit_check, parse_tier, tier_applies,
)

CHECK_ID = "yaml-extension"
APPLIES = "product,canonical,personal"


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    cd_repo_root()

    gh = Path(".github")
    if not gh.is_dir():
        emit_check(CHECK_ID, "na", "No .github/ directory; nothing to check.")
        return EXIT_NA

    offenders = sorted(str(p) for p in gh.rglob("*.yml") if p.is_file())

    if not offenders:
        emit_check(
            CHECK_ID, "pass",
            "All YAML files under .github/ use the .yaml extension.",
            {},
        )
        return EXIT_PASS

    count = len(offenders)
    joined = ", ".join(offenders)
    emit_check(
        CHECK_ID, "fail",
        f"{count} file(s) under .github/ use .yml instead of .yaml: {joined}.",
        {"offenders": offenders},
        {"kind": "mechanical", "script": "scripts/fixes/rename-yml-to-yaml.py", "human_review": "git mv each .yml -> .yaml under .github/. Confirm no external reference uses the old path (workflow_call uses:, docs links, downstream consumers of action.yml)."},
    )
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
