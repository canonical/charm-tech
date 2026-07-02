#!/usr/bin/env python3
"""Fix: install the operator-style Conventional Commits PR-title check.

Two-file pattern (source: canonical/operator):
  - .github/workflows/validate-pr-title.yaml — runs on pull_request
    [opened, edited, synchronize], permissions: {}, no PR-title fetch from
    the API; reads it from the event payload via the PR_TITLE env var.
  - .github/check-conventional-pr-title.py — self-contained Python (stdlib
    only). Allowed types: chore, ci, docs, feat, fix, perf, refactor, revert,
    test. Scopes disallowed.

Both files are staged from the asset templates. The Python script's _HELP_URL
placeholder is rewritten to point at this repo's CONTRIBUTING.md so the error
message links to the right place. The agent should still check the
CONTRIBUTING.md exists and documents these types.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import origin_url, repo_root, run

SCRIPT_DIR = Path(__file__).resolve().parent


def main() -> int:
    try:
        os.chdir(repo_root())
    except OSError:
        return 3

    workflow = ".github/workflows/validate-pr-title.yaml"
    script = ".github/check-conventional-pr-title.py"

    if Path(workflow).exists() or Path(".github/workflows/validate-pr-title.yml").exists():
        sys.stderr.write(f"{workflow} (or .yml variant) already exists; refusing to overwrite.\n")
        return 1
    if Path(script).exists():
        sys.stderr.write(f"{script} already exists; refusing to overwrite.\n")
        return 1

    wf_template = SCRIPT_DIR.parent.parent / "assets" / "validate-pr-title.yaml.template"
    py_template = SCRIPT_DIR.parent.parent / "assets" / "check-conventional-pr-title.py.template"
    if not wf_template.is_file():
        sys.stderr.write(f"Workflow template missing: {wf_template}\n")
        return 3
    if not py_template.is_file():
        sys.stderr.write(f"Python template missing: {py_template}\n")
        return 3

    Path(".github/workflows").mkdir(parents=True, exist_ok=True)
    shutil.copy(wf_template, workflow)
    shutil.copy(py_template, script)

    # Rewrite the help-URL placeholder to point at THIS repo.
    url = origin_url()
    prefix = "https://github.com/"
    if url.startswith(prefix) and len(url) > len(prefix):
        slug = url[len(prefix):]
        owner = slug.split("/", 1)[0]
        name = slug.rsplit("/", 1)[-1]

        r = run(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"])
        default_branch = r.stdout.strip() if r.returncode == 0 else ""
        if default_branch.startswith("origin/"):
            default_branch = default_branch[len("origin/"):]
        if not default_branch:
            r2 = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
            default_branch = r2.stdout.strip() if r2.returncode == 0 else "main"
        if not default_branch:
            default_branch = "main"

        text = Path(script).read_text()
        text = text.replace("REPLACE_WITH_OWNER", owner)
        text = text.replace("REPLACE_WITH_REPO", name)
        text = text.replace("/blob/main/", f"/blob/{default_branch}/")
        Path(script).write_text(text)
        sys.stdout.write(
            f"Rewrote help-URL to https://github.com/{owner}/{name}/blob/{default_branch}/CONTRIBUTING.md#pull-requests\n"
        )
    else:
        sys.stderr.write(
            f"Could not determine origin slug; left REPLACE_WITH_OWNER/REPO placeholders in {script} — fix before committing.\n"
        )

    sys.stdout.write(f"Wrote {workflow} and {script}.\n")
    sys.stdout.write(
        "Confirm CONTRIBUTING.md (or HACKING.md, etc.) exists in this repo and documents the allowed Conventional-Commits types; if not, add a \"Pull requests\" section listing chore/ci/docs/feat/fix/perf/refactor/revert/test before merging.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
