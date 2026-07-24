"""check.py: one smoke test that --only dispatches and shapes a report."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RUNNER = Path(__file__).resolve().parent.parent / "scripts" / "check.py"


def test_only_dispatches_selected_check(tmp_path):
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "dependabot.yaml").write_text(
        "version: 2\nupdates:\n  - package-ecosystem: pip\n    directory: /\n"
        "    schedule: {interval: weekly}\n    cooldown: {default-days: 7}\n"
    )
    proc = subprocess.run(
        [sys.executable, str(RUNNER), "--tier=canonical", "--only=dependabot"],
        capture_output=True, text=True, check=True, cwd=tmp_path,
    )
    report = json.loads(proc.stdout)
    assert report["tier"] == "canonical"
    assert report["tier_source"] == "override"
    assert [c["id"] for c in report["checks"]] == ["dependabot"]
    assert report["checks"][0]["status"] == "pass"
