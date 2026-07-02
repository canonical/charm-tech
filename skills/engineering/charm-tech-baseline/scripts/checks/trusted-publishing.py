#!/usr/bin/env python3
"""Check: every PyPI publish path uses Trusted Publishing (OIDC), not a long-lived
API token. Detects:
  - `pypa/gh-action-pypi-publish` invocations — pass requires NO `password:`
    or `username:` input, and the surrounding job (or workflow) must declare
    `id-token: write`.
  - `twine upload` invocations — fail; twine is the long-lived-token path.

Emits `na` when no PyPI publish path is present (Python project that doesn't
publish, or non-Python repo). Tier coverage: all tiers — anyone publishing
to PyPI from GitHub Actions should use Trusted Publishing.

Reference: BASELINE.md "All Python-publishing repos already use Trusted
Publishing (OIDC id-token: write + pypa/gh-action-pypi-publish)".
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

CHECK_ID = "trusted-publishing"
APPLIES = "product,canonical,personal"

TOKEN_INPUT_RE = re.compile(r"^[ \t]*(password|username):", re.MULTILINE)
ID_TOKEN_WRITE_RE = re.compile(r"^[ \t]*id-token:[ \t]*write\b", re.MULTILINE)
TWINE_RE = re.compile(r"(^|[ \t])twine[ \t]+upload\b", re.MULTILINE)


def main() -> int:
    tier = parse_tier()
    if not tier_applies(APPLIES, tier):
        emit_check(CHECK_ID, "na", f"Not applicable for tier {tier}.")
        return EXIT_NA

    cd_repo_root()

    wf_dir = Path(".github/workflows")
    if not wf_dir.is_dir():
        emit_check(CHECK_ID, "na", "No .github/workflows directory; no publish workflow to audit.")
        return EXIT_NA

    workflows = sorted(
        [str(p) for p in wf_dir.iterdir() if p.is_file() and p.suffix in (".yml", ".yaml")]
    )
    if not workflows:
        emit_check(CHECK_ID, "na", "No workflows under .github/workflows.")
        return EXIT_NA

    publish_files: list[str] = []
    twine_files: list[str] = []
    bad_token_files: list[str] = []
    missing_id_token_files: list[str] = []

    for wf in workflows:
        try:
            text = Path(wf).read_text(errors="replace")
        except OSError:
            continue
        if "pypa/gh-action-pypi-publish" in text:
            publish_files.append(wf)
            if TOKEN_INPUT_RE.search(text):
                bad_token_files.append(wf)
            if not ID_TOKEN_WRITE_RE.search(text):
                missing_id_token_files.append(wf)
        if TWINE_RE.search(text):
            twine_files.append(wf)

    if not publish_files and not twine_files:
        emit_check(CHECK_ID, "na", "No PyPI publish workflow detected (no pypa/gh-action-pypi-publish or twine upload).")
        return EXIT_NA

    evidence = {
        "publish_workflows": publish_files,
        "twine_workflows": twine_files,
        "missing_id_token": missing_id_token_files,
        "token_inputs": bad_token_files,
    }

    problems: list[str] = []
    if twine_files:
        problems.append("twine upload detected (long-lived API token path)")
    if bad_token_files:
        problems.append("pypa/gh-action-pypi-publish invoked with password/username input")
    if missing_id_token_files:
        problems.append("publish workflow missing id-token: write permission")

    if not problems:
        emit_check(
            CHECK_ID, "pass",
            "PyPI publishing uses Trusted Publishing (OIDC; id-token: write + pypa/gh-action-pypi-publish, no token input).",
            evidence,
        )
        return EXIT_PASS

    joined = "; ".join(problems)
    emit_check(
        CHECK_ID, "fail",
        f"PyPI publishing is not fully on Trusted Publishing: {joined}.",
        evidence,
        {"kind": "judgement", "human_review": (
            "Convert the publish workflow to Trusted Publishing: drop "
            "password/username inputs, add permissions: { id-token: write } "
            "at the job level, configure the PyPI project/environment as a "
            "Trusted Publisher, and revoke any leftover API tokens. "
            "Templates (fill in REPLACE_WITH_* markers before use): "
            "personal|canonical → assets/trusted-publishing.yml.template "
            "(inline CycloneDX SBOM + dual attestation); "
            "product → assets/trusted-publishing-product.yml.template + "
            "assets/sbom-secscan.yaml.template + "
            "assets/sbomber-manifest-{sdist,wheel}.yaml.template. "
            "Before committing, modernise pinned action versions: for every "
            "third-party action, look up the latest release on GitHub, pin "
            "it by commit SHA, and update the `# vX.Y.Z` comment. Environment "
            "name is `publish-pypi` (fleet convention). The result must pass "
            "zizmor with no findings."
        )},
    )
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
