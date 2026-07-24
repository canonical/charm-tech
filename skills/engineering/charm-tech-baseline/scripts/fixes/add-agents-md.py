#!/usr/bin/env python3
"""Fix: copy the AGENTS.md template into the repo root.
Agent must fill in {{...}} placeholders before committing — the
template is intentionally a skeleton, not a working file.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import repo_root

SCRIPT_DIR = Path(__file__).resolve().parent


def main() -> int:
    try:
        import os
        os.chdir(repo_root())
    except OSError:
        return 3

    if Path("AGENTS.md").exists():
        sys.stderr.write("AGENTS.md already exists; refusing to overwrite.\n")
        return 1

    template = SCRIPT_DIR.parent.parent / "assets" / "AGENTS.md.template"
    if not template.is_file():
        sys.stderr.write("Template missing.\n")
        return 3

    shutil.copy(template, "AGENTS.md")
    sys.stdout.write("Copied AGENTS.md template. Replace {{REPO_DESCRIPTION_ONE_SENTENCE}}, {{SETUP_COMMANDS}}, {{TEST_COMMANDS}}, {{LINT_COMMANDS}}, {{DEPTH_LINK_TITLE}}, {{DEPTH_LINK}} before committing.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
