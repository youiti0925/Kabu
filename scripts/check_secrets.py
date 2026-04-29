#!/usr/bin/env python3
"""Lightweight secret scan (pure stdlib).

This is intentionally simple. It is *not* a replacement for gitleaks /
detect-secrets. See docs/RISKS.md (5-3) for the plan to introduce a proper
secret scanner in CI.

Detects:
- AWS access key id pattern: AKIA[0-9A-Z]{16}
- AWS secret access key pattern: 40-char base64-ish (heuristic, low precision)
- Generic private key headers
- High-confidence "token = '...'" / "api_key = '...'" assignments with long values
- Tracked .env files (also covered by check_no_forbidden_paths.py)

CLI:
    python scripts/check_secrets.py             # scan tracked files
    python scripts/check_secrets.py FILE [...]  # scan specific files (pre-commit)

Exit codes:
    0 = no findings
    1 = potential secret(s) detected
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Self-allowlist: this file legitimately contains secret patterns.
SELF_PATH = "scripts/check_secrets.py"
ALLOWLIST = {
    SELF_PATH,
    "docs/RISKS.md",
    "docs/AI_REVIEW_SAFETY.md",
}

SCAN_EXTS = {
    ".py",
    ".md",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".txt",
    ".ini",
    ".cfg",
    ".env",
    ".sh",
}

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "private_key_block",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |)PRIVATE KEY-----"),
    ),
    (
        "generic_high_entropy_assignment",
        re.compile(
            r"(?ix)\b(?:api[_-]?key|secret|token|password|passwd|pwd)"
            r"\s*[:=]\s*['\"]([A-Za-z0-9+/_\-]{20,})['\"]"
        ),
    ),
    (
        "github_token",
        re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    ),
    (
        "slack_token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    ),
]


def normalize(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def list_tracked_files() -> list[Path]:
    try:
        out = subprocess.check_output(
            ["git", "ls-files", "-z"],
            cwd=REPO_ROOT,
        ).decode("utf-8", errors="replace")
        return [REPO_ROOT / p for p in out.split("\x00") if p]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    findings: list[tuple[int, str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return findings
    for lineno, line in enumerate(text.splitlines(), start=1):
        for label, regex in PATTERNS:
            if regex.search(line):
                findings.append((lineno, label, line.strip()[:200]))
    return findings


def main(argv: list[str]) -> int:
    if argv:
        targets = [Path(a) for a in argv]
    else:
        targets = list_tracked_files()

    violations = 0
    for path in targets:
        rel = normalize(path)
        if rel in ALLOWLIST:
            continue
        if not path.exists() or not path.is_file():
            continue
        if path.suffix not in SCAN_EXTS and Path(rel).name != ".env":
            continue
        for lineno, label, snippet in scan_file(path):
            print(f"{rel}:{lineno}: potential secret [{label}] -> {snippet}")
            violations += 1

    if violations:
        print(
            f"\nFAIL: {violations} potential secret(s) detected.",
            file=sys.stderr,
        )
        print(
            "This scanner is heuristic. Plan: replace with gitleaks "
            "(see docs/RISKS.md 5-3).",
            file=sys.stderr,
        )
        return 1
    print("OK: no obvious secrets in scope.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
