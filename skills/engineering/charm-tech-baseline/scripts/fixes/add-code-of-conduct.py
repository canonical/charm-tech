#!/usr/bin/env python3
"""Fix: copy the Code-of-Conduct template (link-only Ubuntu CoC) into the repo root.
Refuses to overwrite an existing file.
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

    if Path("CODE_OF_CONDUCT.md").exists():
        sys.stderr.write("CODE_OF_CONDUCT.md already exists; refusing to overwrite.\n")
        return 1

    template = SCRIPT_DIR.parent.parent / "assets" / "CODE_OF_CONDUCT.md"
    if not template.is_file():
        sys.stderr.write("Template missing.\n")
        return 3

    shutil.copy(template, "CODE_OF_CONDUCT.md")
    sys.stdout.write("Copied CODE_OF_CONDUCT.md. No placeholders to fill in — the link-only form is complete as-is.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
