"""Invariant: forbidden run-output paths are never committed.

Policy: RISKS.md 5-3 / .gitignore / scripts/check_no_forbidden_paths.py.

This test runs the same logic as the CI guard from inside pytest, so that
a developer who deletes the GitHub Actions workflow still gets an early
warning when running ``pytest`` locally.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_no_forbidden_paths.py"

FORBIDDEN_PREFIXES = ("runs", "libs", "data/raw", "data/cache")


def test_forbidden_dirs_are_absent_or_empty():
    """The repo root must not have any tracked content under the forbidden
    paths. Walking the working tree is sufficient because .gitignore keeps
    ``runs/`` etc. untracked anyway.
    """
    for prefix in FORBIDDEN_PREFIXES:
        target = REPO_ROOT / prefix
        if not target.exists():
            continue
        # Existence is OK only if ``git ls-files`` reports nothing under it.
        out = subprocess.check_output(
            ["git", "ls-files", "--", prefix],
            cwd=REPO_ROOT,
        ).decode("utf-8")
        listed = [line for line in out.splitlines() if line.strip()]
        assert not listed, (
            f"forbidden path {prefix!r} contains tracked files: {listed!r}"
        )


def test_check_no_forbidden_paths_script_passes():
    """Running the CI guard script directly must succeed (exit code 0)."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"check_no_forbidden_paths.py failed:\nstdout={proc.stdout}\nstderr={proc.stderr}"
    )
