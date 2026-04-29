#!/usr/bin/env python3
"""Fail if FX-specific tokens leak into Kabu source / tests / docs.

Policy: docs/ANTI_FX_LEAK.md
Scope: src/kabu/, tests/, docs/ (extensible via SCAN_DIRS).
Allowlist: files that legitimately discuss the forbidden tokens
(e.g. ANTI_FX_LEAK.md, RISKS.md, README.md).

CLI:
    python scripts/check_no_fx_leak.py             # full repo scan
    python scripts/check_no_fx_leak.py FILE [...]  # scan only given files (pre-commit)

Exit codes:
    0 = clean
    1 = forbidden tokens found
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SCAN_DIRS = ["src/kabu", "tests", "docs"]
SCAN_EXTS = {".py", ".md", ".toml", ".yaml", ".yml", ".json", ".txt", ".ini", ".cfg"}

# Files that may legitimately mention forbidden tokens for documentation.
ALLOWLIST = {
    "docs/ANTI_FX_LEAK.md",
    "docs/RISKS.md",
    "README.md",
}

# Forbidden tokens. (regex_pattern, human_label).
# `pip` regex excludes `pip install/config/freeze/show/list/uninstall/search`
# and `pip3` so it does not collide with the package installer.
FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    (r"\bfrom\s+fx\b", "from fx"),
    (r"\bfrom\s+src\.fx\b", "from src.fx"),
    (r"\bimport\s+fx\b", "import fx"),
    (r"\bimport\s+oanda\b", "import oanda"),
    (r"\bOANDA\b", "OANDA"),
    (r"\boanda\b", "oanda"),
    (r"\bDXY\b", "DXY"),
    (r"\bUSD_exposure\b", "USD_exposure"),
    (r"\bUSDJPY_exposure\b", "USDJPY_exposure"),
    (r"\bcurrency_pair\b", "currency_pair"),
    (r"\bpip\b(?!\s*(?:install|config|freeze|show|list|uninstall|search|3))", "pip"),
    (r"\bpip_value\b", "pip_value"),
    (r"\bevent_high\b", "event_high"),
    (r"\bspread_abnormal\b", "spread_abnormal"),
    (r"\brisk_gate\.event_high\b", "risk_gate.event_high"),
    (r"\bsession_asia\b", "session_asia"),
    (r"\bsession_europe\b", "session_europe"),
    (r"\bsession_us\b", "session_us"),
]
COMPILED = [(re.compile(p), label) for p, label in FORBIDDEN_PATTERNS]


def iter_default_targets() -> list[Path]:
    out: list[Path] = []
    for d in SCAN_DIRS:
        base = REPO_ROOT / d
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in SCAN_EXTS:
                out.append(path)
    return out


def normalize(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def is_allowlisted(rel: str) -> bool:
    return rel in ALLOWLIST


def is_in_scan_scope(rel: str) -> bool:
    if rel in ALLOWLIST:
        return True  # allowlisted files are still "in scope" but skipped
    return any(rel.startswith(d + "/") or rel == d for d in SCAN_DIRS)


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    findings: list[tuple[int, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return findings
    for lineno, line in enumerate(text.splitlines(), start=1):
        for regex, label in COMPILED:
            if regex.search(line):
                findings.append((lineno, label, line.rstrip()))
    return findings


def main(argv: list[str]) -> int:
    if argv:
        targets = [Path(a) for a in argv]
    else:
        targets = iter_default_targets()

    violations = 0
    for path in targets:
        rel = normalize(path)
        if argv:
            # In pre-commit / explicit-args mode, only consider files that fall
            # inside our scan scope. Other files (e.g. .github/, scripts/) are
            # ignored so the script is safe to wire up broadly.
            if not is_in_scan_scope(rel):
                continue
        if is_allowlisted(rel):
            continue
        if not path.exists() or not path.is_file():
            continue
        if path.suffix not in SCAN_EXTS:
            continue
        for lineno, label, line in scan_file(path):
            print(f"{rel}:{lineno}: forbidden token [{label}] -> {line}")
            violations += 1

    if violations:
        print(f"\nFAIL: {violations} forbidden FX-leak token(s) found.", file=sys.stderr)
        print("Policy: docs/ANTI_FX_LEAK.md", file=sys.stderr)
        return 1
    print("OK: no FX-leak tokens in scope.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
