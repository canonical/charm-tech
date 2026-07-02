#!/usr/bin/env python3
"""Fix: copy the SECURITY.md template into the repo root.
Caller is the agent, which must then:
  1. Replace placeholder fields ({{REPO}}, {{CONTACT}}, etc.).
  2. Stage and commit; do not push without user direction.

This script never overwrites an existing SECURITY.md.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import repo_root

SCRIPT_DIR = Path(__file__).resolve().parent


def main() -> int:
    try:
        os.chdir(repo_root())
    except OSError:
        return 3

    if Path("SECURITY.md").exists():
        sys.stderr.write("SECURITY.md already exists; refusing to overwrite. Remove it first if the intent is to replace.\n")
        return 1

    template = SCRIPT_DIR.parent.parent / "assets" / "SECURITY.md.template"
    if not template.is_file():
        sys.stderr.write(f"Template missing at {template}\n")
        return 3

    shutil.copy(template, "SECURITY.md")
    sys.stdout.write("Copied SECURITY.md template. Replace placeholders ({{REPO}}, {{CONTACT}}) before committing.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
