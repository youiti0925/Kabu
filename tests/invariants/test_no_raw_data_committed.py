"""Invariant: no real OHLCV / cache / runs files are committed to git.

Policy: BACKTEST_CONTRACT.md S6-A / DATA_SOURCES.md S0 / RISKS.md 5-3.
``data/raw/`` and ``data/cache/`` are vendor-output / cache directories;
``runs/`` is per-run output. None should ever appear under ``git ls-files``.

Distinct from ``test_no_committed_run_outputs`` which already covers
``runs/``: this test focuses on data-cache leakage and is an extra safety
net specifically for P4.7 vendor work.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

_FORBIDDEN_PREFIXES = (
    "data/raw/",
    "data/cache/",
    "runs/",
    "libs/",
)
_FORBIDDEN_EXTS = {
    ".parquet",
    ".duckdb",
    ".sqlite",
    ".sqlite3",
    ".csv",
    ".pkl",
    ".feather",
    ".h5",
    ".hdf5",
}
_ALLOWED_EXACT = {
    "data/.gitkeep",
    ".env.example",
}


def _list_tracked_files() -> list[str]:
    out = subprocess.check_output(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
    ).decode("utf-8", errors="replace")
    return [p for p in out.split("\x00") if p]


def test_no_raw_data_committed():
    """No tracked file lives under data/raw, data/cache, runs/, libs/."""
    bad: list[str] = []
    for rel in _list_tracked_files():
        if rel in _ALLOWED_EXACT:
            continue
        for prefix in _FORBIDDEN_PREFIXES:
            if rel.startswith(prefix):
                bad.append(rel)
                break
    assert not bad, f"forbidden tracked paths: {bad}"


def test_no_data_extension_committed():
    """No tracked file with a data extension (parquet, duckdb, csv, ...)."""
    bad: list[str] = []
    for rel in _list_tracked_files():
        if rel in _ALLOWED_EXACT:
            continue
        suffix = Path(rel).suffix.lower()
        if suffix in _FORBIDDEN_EXTS:
            bad.append(rel)
    assert not bad, f"forbidden data-extension files committed: {bad}"
