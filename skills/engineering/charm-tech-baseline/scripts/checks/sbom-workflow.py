#!/usr/bin/env python3
"""Check: SBOM workflow / manifest present and triggered per cycle.
Tier coverage: product only.

Mandate: SEC0027 (every release type). Generated via sbom-request.canonical.com.
Some repos carry an in-repo manifest (.sbomber-manifest-*.yaml); some
integrate the SBOM request as a CI workflow step.

A `workflow_dispatch:`-only workflow satisfies presence but not cadence —
SBOM must be regenerated every release / cycle. Pass requires at least one
of the cadence triggers: `release`, `schedule`, or tag-pushes
(`push: tags:` or `push: branches:` + `tags:` filter). Manifests-only repos
are accepted unconditionally — the manifest is consumed by an external
sbom-request pipeline that owns its own cadence.
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

CHECK_ID = "sbom-workflow"
APPLIES = "product"

WORKFLOW_KEY_RE = re.compile(r"sbom-request|sbomber|sbom-secscan", re.IGNORECASE)


def find_manifests() -> list[str]:
    hits: list[str] = []
    gh = Path(".github")
    root_candidates: list[Path] = []
    # maxdepth 2: .github + .github/<subdir>
    if gh.is_dir():
        for p in gh.iterdir():
            if p.is_file() and (
                re.search(r"sbomber-manifest.*\.ya?ml$", p.name)
                or re.search(r"^sbom.*\.ya?ml$", p.name)
            ):
                root_candidates.append(p)
            if p.is_dir():
                for p2 in p.iterdir():
                    if p2.is_file() and (
                        re.search(r"sbomber-manifest.*\.ya?ml$", p2.name)
                        or re.search(r"^sbom.*\.ya?ml$", p2.name)
                    ):
                        root_candidates.append(p2)
    for p in root_candidates[:3]:
        hits.append(str(p))
    return hits


def find_workflow() -> str:
    wf_dir = Path(".github/workflows")
    if not wf_dir.is_dir():
        return ""
    for p in sorted(list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml"))):
        try:
            if WORKFLOW_KEY_RE.search(p.read_text(errors="replace")):
                return str(p)
        except OSError:
            continue
    return ""


def cadence_check_yaml(workflow: str) -> tuple[bool, str]:
    """Return (ok, reason). reason is empty on ok."""
    try:
        import yaml  # type: ignore
    except Exception:
        return cadence_check_grep(workflow)
    try:
        with open(workflow) as f:
            doc = yaml.safe_load(f)
    except Exception as e:
        return False, f"could not parse workflow triggers (PARSE_ERROR {e})"
    if not isinstance(doc, dict):
        return False, "could not parse workflow triggers (UNKNOWN_ON_SHAPE)"
    on = doc.get(True)
    if on is None:
        on = doc.get("on")
    if on is None:
        return False, "could not parse workflow triggers (MISSING_ON)"
    if isinstance(on, str):
        on = {on: None}
    elif isinstance(on, list):
        on = {k: None for k in on}
    if not isinstance(on, dict):
        return False, "could not parse workflow triggers (UNKNOWN_ON_SHAPE)"
    triggers = set(on.keys())
    if "release" in triggers or "schedule" in triggers:
        return True, ""
    push = on.get("push")
    if isinstance(push, dict) and ("tags" in push or "tags-ignore" in push):
        return True, ""
    joined = ",".join(sorted(str(t) for t in triggers))
    return False, f"workflow triggers ({joined}) include no cadence trigger (release / schedule / push: tags)"


def cadence_check_grep(workflow: str) -> tuple[bool, str]:
    try:
        text = Path(workflow).read_text(errors="replace")
    except OSError:
        return False, "no release/schedule/push-tags trigger found (grep fallback; install python3+PyYAML for accurate check)"
    if re.search(r"^[ \t]*(release|schedule):", text, re.MULTILINE):
        return True, ""
    if re.search(r"push:[ \t]*\n[ \t]+tags:", text):
        return True, ""
    return False, "no release/schedule/push-tags trigger found (grep fallback; install python3+PyYAML for accurate check)"


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    cd_repo_root()

    manifests = find_manifests()
    workflow = find_workflow()

    if not manifests and not workflow:
        emit_check(
            CHECK_ID, "fail",
            "No SBOM workflow or manifest found.",
            {},
            {"kind": "judgement", "human_review": "Request SBOM via sbom-request.canonical.com Web UI or REST API; store in the SSDLC Artifacts directory and request review in ~SSDLC. Add a CI step that triggers SBOM generation per release if useful."},
        )
        return EXIT_FAIL

    cadence_ok = True
    cadence_reason = ""
    if workflow:
        cadence_ok, cadence_reason = cadence_check_yaml(workflow)

    parts = list(manifests) + ([workflow] if workflow else [])
    found = ",".join(parts).strip().strip(",")

    if cadence_ok:
        emit_check(
            CHECK_ID, "pass",
            "SBOM workflow / manifest present with per-cycle cadence.",
            {"found": found},
        )
        return EXIT_PASS

    emit_check(
        CHECK_ID, "fail",
        f"SBOM workflow present but cadence not guaranteed: {cadence_reason}.",
        {"found": found, "workflow": workflow},
        {"kind": "judgement", "human_review": "SBOM must regenerate per release/cycle. Add `on: release: types: [published]` (preferred for release-cut workflows) or `on: schedule:` (for unreleased products) or `on: push: tags: [v*]`. workflow_dispatch alone is not sufficient."},
    )
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
