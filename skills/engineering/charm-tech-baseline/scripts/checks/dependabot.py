#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Check: .github/dependabot.yml exists, declares package ecosystems, and each
ecosystem has a cooldown of at least 7 days (Charm Tech baseline — see
charmlibs#499). The cooldown delays raising a PR for a freshly published
release so a malicious upload caught and yanked inside the window never
reaches CI.

Tier coverage: product, canonical. (Personal-tier sees this as best-practice
advisory rather than mandatory.)

Mandate: SEC0025 (Vulnerability Discovery & Identification) — cross-cutting
requirement for every Canonical repo.
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

import yaml

CHECK_ID = "dependabot"
APPLIES = "product,canonical,personal"
MIN_COOLDOWN_DAYS = 7

ECOSYSTEM_LINE_RE = re.compile(r"^[ \t]*-[ \t]+package-ecosystem:", re.MULTILINE)
PRECOMMIT_ECO_RE = re.compile(
    r"""^[ \t]*-[ \t]+package-ecosystem:[ \t]*["']?pre-commit["']?[ \t]*$""",
    re.MULTILINE,
)
PRECOMMIT_REV_RE = re.compile(r"^[ \t]*rev:[ \t]+", re.MULTILINE)


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    cd_repo_root()

    found_path = ""
    for path in (".github/dependabot.yml", ".github/dependabot.yaml"):
        if Path(path).is_file():
            found_path = path
            break

    if not found_path:
        if tier == "personal":
            emit_check(
                CHECK_ID, "fail",
                "No Dependabot config (personal tier — recommended, not mandated).",
                {},
                {"kind": "mechanical", "script": "scripts/fixes/add-dependabot.py", "human_review": "Confirm the default ecosystem set matches the repo."},
            )
            return EXIT_FAIL
        emit_check(
            CHECK_ID, "fail",
            "No .github/dependabot.yml found (required cross-cutting per SEC0025).",
            {},
            {"kind": "mechanical", "script": "scripts/fixes/add-dependabot.py", "human_review": "Confirm the default ecosystem set matches the repo (pip/uv, gomod, github-actions, docker)."},
        )
        return EXIT_FAIL

    text = Path(found_path).read_text(errors="replace")
    ecos = len(ECOSYSTEM_LINE_RE.findall(text))
    if ecos == 0:
        emit_check(
            CHECK_ID, "fail",
            f"{found_path} exists but declares no package-ecosystem entries.",
            {"path": found_path},
            {"kind": "judgement", "human_review": "Add package-ecosystem blocks for each language/runtime the repo uses (pip/uv, gomod, github-actions, docker)."},
        )
        return EXIT_FAIL

    # Cross-check: if .pre-commit-config.yaml carries any rev: entries,
    # dependabot must declare the pre-commit ecosystem to bump the SHAs.
    # See references/decisions.md § "Remote pre-commit hooks — SHA-pin".
    pc_config = ""
    for path in (".pre-commit-config.yaml", ".pre-commit-config.yml"):
        if Path(path).is_file():
            pc_config = path
            break
    if pc_config:
        try:
            pc_text = Path(pc_config).read_text(errors="replace")
        except OSError:
            pc_text = ""
        if PRECOMMIT_REV_RE.search(pc_text) and not PRECOMMIT_ECO_RE.search(text):
            emit_check(
                CHECK_ID, "fail",
                f"{found_path} is missing a pre-commit package-ecosystem entry — required because {pc_config} carries rev: entries whose SHAs need Dependabot bumps (Charm Tech baseline).",
                {"path": found_path, "ecosystems": ecos, "pre_commit_config": pc_config},
                {"kind": "judgement", "human_review": "Add a pre-commit package-ecosystem block to dependabot.yaml (same shape as github-actions, cooldown ≥7 days). See assets/dependabot.yaml.template."},
            )
            return EXIT_FAIL

    # Parse and validate cooldown.
    try:
        doc = yaml.safe_load(text)
    except Exception:
        # Fall through to presence check.
        if not re.search(r"^[ \t]*cooldown:", text, re.MULTILINE):
            emit_check(
                CHECK_ID, "fail",
                f"Dependabot configured with {ecos} ecosystem(s), but no cooldown: block found and YAML parser errored — could not auto-validate.",
                {"path": found_path, "ecosystems": ecos, "cooldown_validated": False},
                {"kind": "judgement", "human_review": "Add a cooldown block to every package-ecosystem entry with default-days/semver-*-days ≥7."},
            )
            return EXIT_FAIL
        emit_check(
            CHECK_ID, "unknown",
            "Dependabot present with cooldown block, but YAML parser errored — cooldown values not validated.",
            {"path": found_path, "ecosystems": ecos, "cooldown_validated": False},
        )
        return EXIT_UNKNOWN

    if not isinstance(doc, dict):
        # Match parse-error behaviour.
        if not re.search(r"^[ \t]*cooldown:", text, re.MULTILINE):
            emit_check(
                CHECK_ID, "fail",
                f"Dependabot configured with {ecos} ecosystem(s), but no cooldown: block found and YAML parser errored — could not auto-validate.",
                {"path": found_path, "ecosystems": ecos, "cooldown_validated": False},
                {"kind": "judgement", "human_review": "Add a cooldown block to every package-ecosystem entry with default-days/semver-*-days ≥7."},
            )
            return EXIT_FAIL
        emit_check(
            CHECK_ID, "unknown",
            "Dependabot present with cooldown block, but YAML parser errored — cooldown values not validated.",
            {"path": found_path, "ecosystems": ecos, "cooldown_validated": False},
        )
        return EXIT_UNKNOWN

    updates = doc.get("updates") or []
    problems: list[str] = []
    for entry in updates:
        if not isinstance(entry, dict):
            continue
        eco = entry.get("package-ecosystem", "?")
        direc = entry.get("directory", entry.get("directories", "?"))
        label = f"{eco}@{direc}"
        cd = entry.get("cooldown")
        if not isinstance(cd, dict):
            problems.append(f"{label}: no cooldown block")
            continue
        keys = ("default-days", "semver-major-days", "semver-minor-days", "semver-patch-days")
        if "default-days" not in cd and not any(k in cd for k in keys):
            problems.append(f"{label}: cooldown block present but no *-days field set")
            continue
        for k in keys:
            if k in cd:
                try:
                    v = int(cd[k])
                except (TypeError, ValueError):
                    problems.append(f"{label}: cooldown.{k} not an integer ({cd[k]!r})")
                    continue
                if v < MIN_COOLDOWN_DAYS:
                    problems.append(f"{label}: cooldown.{k}={v} < {MIN_COOLDOWN_DAYS}")

    if not problems:
        emit_check(
            CHECK_ID, "pass",
            f"Dependabot configured with {ecos} ecosystem(s); cooldown ≥{MIN_COOLDOWN_DAYS} days on every entry.",
            {"path": found_path, "ecosystems": ecos, "cooldown_validated": True},
        )
        return EXIT_PASS

    evidence = {
        "path": found_path,
        "ecosystems": ecos,
        "cooldown_validated": True,
        "detail": {"problems": problems, "ecosystems": len(updates)},
    }
    emit_check(
        CHECK_ID, "fail",
        f"Dependabot present but cooldown below Charm Tech baseline (≥{MIN_COOLDOWN_DAYS} days) on one or more ecosystems.",
        evidence,
        {"kind": "judgement", "human_review": "Set cooldown.default-days (and any per-semver-tier overrides) to at least 7 on every package-ecosystem entry. See assets/dependabot.yaml.template."},
    )
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
