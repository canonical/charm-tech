#!/usr/bin/env python3
"""Fix: rename every *.yml under .github/ to *.yaml, using `git mv` so
history follows. Skips files where the .yaml twin already exists (left
for manual reconciliation — likely intentional or a stale leftover).

Does NOT update references: `workflow_call uses:` paths, README links,
downstream consumers of a composite action.yml, etc. The human-review
note on the matching check flags this; rerun the audit + grep after.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.common import repo_root, run


def main() -> int:
    try:
        os.chdir(repo_root())
    except OSError:
        return 3

    if not Path(".github").is_dir():
        sys.stdout.write("No .github/ directory; nothing to do.\n")
        return 0

    offenders = sorted(str(p) for p in Path(".github").rglob("*.yml") if p.is_file())

    if not offenders:
        sys.stdout.write("No .yml files under .github/; nothing to do.\n")
        return 0

    in_git_repo = run(["git", "rev-parse", "--is-inside-work-tree"]).returncode == 0

    renamed = 0
    skipped = 0
    for src in offenders:
        dst = src[:-len(".yml")] + ".yaml"
        if Path(dst).exists():
            sys.stderr.write(f"SKIP: {src} — {dst} already exists.\n")
            skipped += 1
            continue
        tracked = False
        if in_git_repo:
            tracked = run(["git", "ls-files", "--error-unmatch", "--", src]).returncode == 0
        if tracked:
            subprocess.run(["git", "mv", "--", src, dst])
        else:
            shutil.move(src, dst)
        sys.stdout.write(f"Renamed: {src} -> {dst}\n")
        renamed += 1

    sys.stdout.write(f"\nDone: {renamed} renamed, {skipped} skipped.\n")
    sys.stdout.write("Reminder: grep the repo (and downstream consumers) for the old .yml paths in case any workflow_call / README / action ref points at them.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
