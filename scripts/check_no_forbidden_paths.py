#!/usr/bin/env python3
"""Fail if forbidden paths or extensions are tracked / staged.

Forbidden paths (entire subtree):
    runs/
    libs/
    data/raw/
    data/cache/

Forbidden extensions (anywhere in repo):
    *.parquet, *.duckdb, *.sqlite, *.sqlite3,
    *.csv, *.pkl, *.feather, *.h5, *.hdf5,
    .env (and .env.* except .env.example)

Allowed exceptions:
    data/.gitkeep
    .env.example

Policy: docs/RISKS.md (5-3), docs/ROADMAP.md (5), .gitignore.

CLI:
    python scripts/check_no_forbidden_paths.py             # walk tracked files (CI)
    python scripts/check_no_forbidden_paths.py FILE [...]  # check given files (pre-commit)

Exit codes:
    0 = clean
    1 = forbidden paths / files detected
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_PREFIXES = (
    "runs/",
    "libs/",
    "data/raw/",
    "data/cache/",
)

FORBIDDEN_EXTS = {
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

ALLOWED_EXACT = {
    "data/.gitkeep",
    ".env.example",
}


def normalize(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def list_tracked_files() -> list[str]:
    try:
        out = subprocess.check_output(
            ["git", "ls-files", "-z"],
            cwd=REPO_ROOT,
        ).decode("utf-8", errors="replace")
        return [p for p in out.split("\x00") if p]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def is_env_file(name: str) -> bool:
    """Match `.env` or `.env.<suffix>` but not `.env.example`."""
    base = Path(name).name
    if base == ".env":
        return True
    if base.startswith(".env.") and base != ".env.example":
        return True
    return False


def violates(rel: str) -> str | None:
    """Return reason string if rel violates a rule, else None."""
    # Strip a leading "./" only. Do NOT use .lstrip("./") -- that would also
    # eat the leading dot in filenames like ".env".
    if rel.startswith("./"):
        rel = rel[2:]
    if rel in ALLOWED_EXACT:
        return None
    for pfx in FORBIDDEN_PREFIXES:
        if rel.startswith(pfx):
            return f"forbidden path prefix: {pfx}"
    suffix = Path(rel).suffix.lower()
    if suffix in FORBIDDEN_EXTS:
        return f"forbidden extension: {suffix}"
    if is_env_file(rel):
        return "forbidden secret file (.env)"
    return None


def main(argv: list[str]) -> int:
    if argv:
        candidates = [normalize(Path(a)) for a in argv]
    else:
        candidates = list_tracked_files()

    violations = 0
    for rel in candidates:
        reason = violates(rel)
        if reason is not None:
            print(f"{rel}: {reason}")
            violations += 1

    if violations:
        print(
            f"\nFAIL: {violations} forbidden path/file detected.",
            file=sys.stderr,
        )
        print(
            "Policy: docs/RISKS.md (5-3), docs/ROADMAP.md (5), .gitignore.",
            file=sys.stderr,
        )
        return 1
    print("OK: no forbidden paths / files.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
