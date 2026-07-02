#!/usr/bin/env python3
"""Fix: copy the CONTRIBUTING.md template into the repo root and rewrite the
owner/repo placeholders to match origin. The template mirrors the
dominant Charm Tech pattern (substantive standalone doc with a
`# Pull requests` section).
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import origin_url, repo_root

SCRIPT_DIR = Path(__file__).resolve().parent


def main() -> int:
    try:
        os.chdir(repo_root())
    except OSError:
        return 3

    if Path("CONTRIBUTING.md").exists():
        sys.stderr.write("CONTRIBUTING.md already exists; refusing to overwrite.\n")
        return 1

    template = SCRIPT_DIR.parent.parent / "assets" / "CONTRIBUTING.md.template"
    if not template.is_file():
        sys.stderr.write("Template missing.\n")
        return 3

    shutil.copy(template, "CONTRIBUTING.md")

    url = origin_url()
    prefix = "https://github.com/"
    if url.startswith(prefix) and len(url) > len(prefix):
        slug = url[len(prefix):]
        # Match shell: owner=${slug%%/*}, name=${slug##*/}.
        owner = slug.split("/", 1)[0]
        name = slug.rsplit("/", 1)[-1]
        text = Path("CONTRIBUTING.md").read_text()
        text = text.replace("REPLACE_WITH_OWNER", owner).replace("REPLACE_WITH_REPO", name)
        Path("CONTRIBUTING.md").write_text(text)
        sys.stdout.write(f"Rewrote owner/repo placeholders to {owner}/{name}.\n")
    else:
        sys.stderr.write("Could not determine origin slug; left REPLACE_WITH_OWNER/REPO placeholders in CONTRIBUTING.md — fix before committing.\n")

    sys.stdout.write("Wrote CONTRIBUTING.md. Confirm: the `# Pull requests` type list matches .github/check-conventional-pr-title.py (chore, ci, docs, feat, fix, perf, refactor, revert, test).\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
