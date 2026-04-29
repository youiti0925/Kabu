#!/usr/bin/env python3
"""Fail if any file > 1 MB is staged or tracked.

Policy: docs/RISKS.md (5-3) and docs/ROADMAP.md (5).

CLI:
    python scripts/check_no_large_files.py             # walk repo (CI mode)
    python scripts/check_no_large_files.py FILE [...]  # check given files (pre-commit)

Exit codes:
    0 = clean
    1 = at least one file exceeds the size limit
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 1 * 1024 * 1024  # 1 MB

# Always ignore .git internals and known build artifacts. We rely on
# .gitignore for runtime outputs (runs/, libs/, data/raw/, data/cache/),
# but we still need to skip them when walking the working tree directly.
SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
    "runs",
    "libs",
}

# Skip these paths under data/ but keep .gitkeep visible.
SKIP_REL_PREFIXES = {
    "data/raw/",
    "data/cache/",
}


def iter_repo_files() -> list[Path]:
    """Use `git ls-files` so we only consider tracked files when run in CI."""
    try:
        out = subprocess.check_output(
            ["git", "ls-files", "-z"],
            cwd=REPO_ROOT,
        ).decode("utf-8", errors="replace")
        files = [REPO_ROOT / p for p in out.split("\x00") if p]
        return files
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: walk the working tree.
        out_paths: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                p = Path(dirpath) / fn
                rel = str(p.relative_to(REPO_ROOT)).replace("\\", "/")
                if any(rel.startswith(pfx) for pfx in SKIP_REL_PREFIXES):
                    continue
                out_paths.append(p)
        return out_paths


def main(argv: list[str]) -> int:
    if argv:
        targets = [Path(a) for a in argv]
    else:
        targets = iter_repo_files()

    violations = 0
    for path in targets:
        if not path.exists() or not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > MAX_BYTES:
            try:
                rel = str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
            except ValueError:
                rel = str(path)
            print(f"{rel}: {size:,} bytes (limit {MAX_BYTES:,})")
            violations += 1

    if violations:
        print(
            f"\nFAIL: {violations} file(s) exceed {MAX_BYTES} bytes.",
            file=sys.stderr,
        )
        print("Policy: docs/RISKS.md / docs/ROADMAP.md.", file=sys.stderr)
        return 1
    print("OK: no oversized files.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
