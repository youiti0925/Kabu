#!/usr/bin/env python3
"""Fail if .gitignore is missing required entries.

Required entries are derived from docs/RISKS.md (5-3) and docs/ROADMAP.md (5).

Exit codes:
    0 = all required entries present
    1 = missing entries
    2 = .gitignore not found
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GITIGNORE = REPO_ROOT / ".gitignore"

REQUIRED_ENTRIES = [
    "runs/",
    "libs/",
    "data/raw/",
    "data/cache/",
    "*.parquet",
    "*.duckdb",
    "*.sqlite",
    "*.csv",
    "*.pkl",
    "*.feather",
    ".env",
    ".venv/",
    "__pycache__/",
    ".pytest_cache/",
]


def parse_gitignore(text: str) -> set[str]:
    entries: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Strip inline comments only when leading `#` is escaped; else trust line.
        entries.add(line.lstrip("/"))
    return entries


def main() -> int:
    if not GITIGNORE.exists():
        print(".gitignore not found at repo root.", file=sys.stderr)
        return 2

    text = GITIGNORE.read_text(encoding="utf-8")
    entries = parse_gitignore(text)

    missing = [e for e in REQUIRED_ENTRIES if e.lstrip("/") not in entries]
    if missing:
        print("FAIL: .gitignore is missing required entries:")
        for m in missing:
            print(f"  - {m}")
        print("Policy: docs/RISKS.md (5-3), docs/ROADMAP.md (5).", file=sys.stderr)
        return 1
    print("OK: .gitignore contains all required entries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
