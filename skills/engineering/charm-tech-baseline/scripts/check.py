#!/usr/bin/env python3
"""Umbrella check runner. Dispatches every script in checks/ that
applies to the resolved tier and emits a single JSON report.

Usage:
    check.py [--tier=product|canonical|personal]
             [--only=<check>[,<check>...]]
             [--format=json|markdown]
"""

from __future__ import annotations

import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
from lib.common import origin_url  # noqa: E402


def usage() -> None:
    sys.stderr.write((__doc__ or "").strip() + "\n")


def main() -> int:
    tier_override = ""
    only_filter = ""
    fmt = "json"

    for arg in sys.argv[1:]:
        if arg.startswith("--tier="):
            tier_override = arg[len("--tier="):]
        elif arg.startswith("--only="):
            only_filter = arg[len("--only="):]
        elif arg.startswith("--format="):
            fmt = arg[len("--format="):]
        elif arg in ("-h", "--help"):
            print((__doc__ or "").strip())
            return 0
        else:
            print(f"Unknown argument: {arg}", file=sys.stderr)
            return 2

    if tier_override:
        tier = tier_override
        tier_source = "override"
    else:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "detect-tier.py")],
            capture_output=True, text=True,
        )
        tier = result.stdout.strip()
        tier_source = "detected"

    if tier == "unknown":
        print(
            "Could not detect tier; pass --tier=product|canonical|personal",
            file=sys.stderr,
        )
        return 2

    repo = origin_url()
    generated_at = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    checks_dir = SCRIPT_DIR / "checks"
    if only_filter:
        selected = []
        for check_id in only_filter.split(","):
            path = checks_dir / f"{check_id}.py"
            if path.is_file():
                selected.append(path)
            else:
                print(f"Unknown check: {check_id}", file=sys.stderr)
                return 2
    else:
        selected = sorted(checks_dir.glob("*.py")) if checks_dir.is_dir() else []

    results: list[dict] = []
    notes: list[str] = []
    for path in selected:
        proc = subprocess.run(
            [str(path), f"--tier={tier}"],
            capture_output=True, text=True,
        )
        out = proc.stdout.strip()
        if not out:
            notes.append(
                f"check {path.name} produced no output (exit {proc.returncode})"
            )
            continue
        try:
            results.append(json.loads(out))
        except json.JSONDecodeError:
            notes.append(f"check {path.name} produced unparseable output")

    if fmt == "json":
        report = {
            "schema_version": 1,
            "repo": repo,
            "tier": tier,
            "tier_source": tier_source,
            "generated_at": generated_at,
            "checks": results,
            "notes": notes,
        }
        print(json.dumps(report))
        return 0

    # Markdown summary path — human spot-checks; agents should prefer JSON.
    print("# Repo-setup audit\n")
    print(f"- Repo: `{repo}`")
    print(f"- Tier: **{tier}** ({tier_source})")
    print(f"- Generated: {generated_at}\n")
    print("## Findings\n")
    for r in results:
        print(f"- **{r.get('status')}** (`{r.get('id')}`) — {r.get('summary')}")
    if notes:
        print("\n## Notes\n")
        for n in notes:
            print(f"- {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
