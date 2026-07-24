"""detect-tier.py: override arg is pure; git-driven paths use a real init."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "detect-tier.py"


def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, check=False, cwd=cwd,
    )


def test_override_product():
    assert _run("product").stdout.strip() == "product"


def test_override_rejects_garbage():
    proc = _run("something-else")
    assert proc.returncode != 0
    assert proc.stderr.strip() == "unknown"


def test_canonical_product_repo_from_origin(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/canonical/operator"],
        cwd=tmp_path, check=True,
    )
    assert _run(cwd=tmp_path).stdout.strip() == "product"


def test_canonical_non_product_repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/canonical/lxd"],
        cwd=tmp_path, check=True,
    )
    assert _run(cwd=tmp_path).stdout.strip() == "canonical"
