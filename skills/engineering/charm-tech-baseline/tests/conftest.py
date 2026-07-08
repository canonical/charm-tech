"""Shared helpers for the charm-tech-baseline check tests.

The tests are functional: each writes a small tree into a tmp dir and runs
the real check script as a subprocess via ``uv run --script``, matching how
``check.py`` itself invokes each check in production. No mocking.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


@pytest.fixture
def run_check(tmp_path, monkeypatch):
    """Return ``run(check_name, tier, files)`` -> parsed JSON dict.

    ``files`` is a mapping of repo-relative path -> file contents. Parent
    directories are created as needed. The check runs with cwd = tmp_path.
    """
    def _run(name: str, tier: str, files: dict[str, str]) -> dict:
        for rel, body in files.items():
            dest = tmp_path / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(body)
        monkeypatch.chdir(tmp_path)
        proc = subprocess.run(
            ["uv", "run", "--script", str(SCRIPTS / "checks" / f"{name}.py"), f"--tier={tier}"],
            capture_output=True, text=True, check=False,
        )
        assert proc.stdout, f"{name} produced no stdout (stderr: {proc.stderr!r})"
        return json.loads(proc.stdout)

    return _run
