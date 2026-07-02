#!/usr/bin/env python3
"""Check: canonical-secscan-client (or equivalent) workflow present, with the
SSDLC identification details wired up so results land in the long-term scan
registry.
Tier coverage: product only.

Mandate: SEC0025. Run at least once per cycle per product with SSDLC
identification.

Two flavours are accepted:

1. **sbomber-driven** (Charm Tech default): the workflow checks out or
   invokes `canonical/sbomber`, and the repo carries one or more
   `.sbomber-manifest*.yaml` files (root or under .github/). SSDLC
   identification lives in `ssdlc_params:` blocks per artifact inside the
   manifest; the secscan client is enabled via `clients.secscan` in the
   manifest. Pass requires: workflow + at least one manifest with both
   `clients.secscan` and per-artifact `ssdlc_params`.

2. **Direct canonical-secscan-client**: the workflow runs the client
   directly (or via cs-github-actions / starflow). Pass requires the
   --ssdlc-product-name / --ssdlc-cycle CLI parameters.
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

CHECK_ID = "secscan-workflow"
APPLIES = "product"

SBOMBER_RE = re.compile(r"canonical/sbomber|\./sbomber|sbomber/sbomber", re.IGNORECASE)
DIRECT_RE = re.compile(r"canonical-secscan-client|run-secscan|sbom-secscan|scan-python", re.IGNORECASE)
SECSCAN_KEY_RE = re.compile(r"^\s*secscan\s*:", re.MULTILINE)
SSDLC_KEY_RE = re.compile(r"^\s*ssdlc_params\s*:", re.MULTILINE)
SSDLC_CLI_RE = re.compile(r"ssdlc-product-name|ssdlc-cycle")


def find_first(pattern: re.Pattern[str], files: list[Path]) -> str:
    for p in files:
        try:
            if pattern.search(p.read_text(errors="replace")):
                return str(p)
        except OSError:
            continue
    return ""


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    cd_repo_root()

    wf_dir = Path(".github/workflows")
    if not wf_dir.is_dir():
        emit_check(
            CHECK_ID, "fail",
            "No .github/workflows directory.",
            {},
            {"kind": "judgement", "human_review": "Set up workflows and wire secscan."},
        )
        return EXIT_FAIL

    workflows = sorted(list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml")))

    sbomber_workflow = find_first(SBOMBER_RE, workflows)
    direct_workflow = find_first(DIRECT_RE, workflows)

    if not sbomber_workflow and not direct_workflow:
        emit_check(
            CHECK_ID, "fail",
            "No secscan workflow found.",
            {},
            {"kind": "judgement", "human_review": "Reference: canonical/sbomber composite action (Charm Tech default), canonical/cs-github-actions run-secscan, or canonical/starflow scan-python. Use the --batch instance; GitHub private runners are allow-listed."},
        )
        return EXIT_FAIL

    if sbomber_workflow:
        workflow_hit = sbomber_workflow
        # Find manifests up to 3 levels deep, excluding .git
        manifests: list[str] = []
        for pattern in (".sbomber-manifest*.yaml", ".sbomber-manifest*.yml"):
            for p in Path(".").rglob(pattern):
                # Depth check: <=3 components from root
                parts = p.parts
                if len(parts) > 3:
                    continue
                if any(part == ".git" for part in parts):
                    continue
                manifests.append(str(p))

        if not manifests:
            emit_check(
                CHECK_ID, "fail",
                "sbomber workflow present but no .sbomber-manifest*.yaml found at repo root or under .github/.",
                {"workflow": workflow_hit},
                {"kind": "judgement", "human_review": "Add a .sbomber-manifest-<flavour>.yaml describing artifacts, with clients.secscan enabled and ssdlc_params per artifact. See canonical/sbomber/examples/all/manifest.yaml."},
            )
            return EXIT_FAIL

        problems: list[str] = []
        has_secscan = False
        has_ssdlc = False
        for m in manifests:
            try:
                text = Path(m).read_text(errors="replace")
            except OSError:
                continue
            if SECSCAN_KEY_RE.search(text):
                has_secscan = True
            if SSDLC_KEY_RE.search(text):
                has_ssdlc = True

        if not has_secscan:
            problems.append("no manifest declares clients.secscan")
        if not has_ssdlc:
            problems.append("no manifest carries per-artifact ssdlc_params")

        evidence = {
            "workflow": workflow_hit,
            "driver": "sbomber",
            "manifests": manifests,
        }

        if not problems:
            emit_check(
                CHECK_ID, "pass",
                "sbomber workflow present; manifest enables secscan client and carries ssdlc_params.",
                evidence,
            )
            return EXIT_PASS

        joined = "; ".join(problems)
        emit_check(
            CHECK_ID, "fail",
            f"sbomber workflow present but manifest incomplete: {joined}.",
            evidence,
            {"kind": "judgement", "human_review": "In the .sbomber-manifest*.yaml, ensure clients.secscan is enabled and every artifact declares ssdlc_params (name/version/channel) — these are what the SSDLC scan registry indexes."},
        )
        return EXIT_FAIL

    # Direct client path.
    workflow_hit = direct_workflow
    try:
        text = Path(workflow_hit).read_text(errors="replace")
    except OSError:
        text = ""
    if SSDLC_CLI_RE.search(text):
        emit_check(
            CHECK_ID, "pass",
            "secscan workflow present with SSDLC identification parameters.",
            {"workflow": workflow_hit, "driver": "canonical-secscan-client"},
        )
        return EXIT_PASS

    emit_check(
        CHECK_ID, "fail",
        "secscan workflow present but --ssdlc-* identification parameters missing.",
        {"workflow": workflow_hit, "driver": "canonical-secscan-client"},
        {"kind": "judgement", "human_review": "Pass --ssdlc-product-name, --ssdlc-cycle, --ssdlc-product-channel, --ssdlc-product-version so results land in the long-term SSDLC scan registry. (Or migrate to canonical/sbomber and move identification into the manifest ssdlc_params blocks.)"},
    )
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
