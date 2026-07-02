#!/usr/bin/env python3
"""Fix: copy the Dependabot template into .github/.
Agent must edit the package-ecosystem set to match the repo
(drop unused ecosystems, uncomment gomod / docker if applicable).
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

    if Path(".github/dependabot.yml").exists() or Path(".github/dependabot.yaml").exists():
        sys.stderr.write(".github/dependabot.{yml,yaml} already exists; refusing to overwrite.\n")
        return 1

    Path(".github").mkdir(parents=True, exist_ok=True)
    template = SCRIPT_DIR.parent.parent / "assets" / "dependabot.yaml.template"
    if not template.is_file():
        sys.stderr.write("Template missing.\n")
        return 3

    shutil.copy(template, ".github/dependabot.yaml")
    sys.stdout.write("Wrote .github/dependabot.yaml. Confirm the ecosystem set matches the repo (pip, github-actions by default; uncomment gomod as needed), and that all dev tooling in use by the repo is in the dev tooling group.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
