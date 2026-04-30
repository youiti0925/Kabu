"""Invariant: vendor SDK imports must NOT leak outside src/kabu/data/sources/.

Policy: DATA_SOURCES.md S0 D-3 / VENDOR_SETUP.md.

The intent: aplication code (backtest, decision_trace_build, stats,
attribution, ...) must call into the ``kabu.data.Source`` Protocol, NOT
directly into a vendor SDK. P4.7 enforces this for ``yfinance``. Future
vendors should be added to ``_FORBIDDEN_VENDOR_TOKENS``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src" / "kabu"
ALLOWED_PARENT = SRC_DIR / "data" / "sources"

_FORBIDDEN_VENDOR_TOKENS = (
    "yfinance",
    # Add new vendors here as they are introduced.
    # "stooq", "jquants",
)


def _is_under(path: Path, ancestor: Path) -> bool:
    try:
        path.relative_to(ancestor)
        return True
    except ValueError:
        return False


def _scan_files() -> list[Path]:
    return [p for p in SRC_DIR.rglob("*.py")]


@pytest.mark.parametrize("token", _FORBIDDEN_VENDOR_TOKENS)
def test_vendor_import_not_outside_data_sources(token: str):
    pattern = re.compile(
        r"^\s*(?:from\s+" + re.escape(token) + r"(?:\.|\s)|import\s+" + re.escape(token) + r"\b)",
        re.MULTILINE,
    )
    leaks: list[str] = []
    for path in _scan_files():
        if _is_under(path, ALLOWED_PARENT):
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            leaks.append(str(path.relative_to(REPO_ROOT)))
    assert not leaks, (
        f"vendor token {token!r} leaked into non-data-sources files: {leaks}"
    )


def test_data_sources_init_only_imports_local_modules():
    """The package init re-exports our adapter, not the vendor SDK directly."""
    init_text = (ALLOWED_PARENT / "__init__.py").read_text(encoding="utf-8")
    # The init file may re-export YFinanceSource (our wrapper) but must NOT
    # have a top-level `import yfinance` — that would pull yfinance at
    # package import time, which we explicitly avoid.
    assert "import yfinance" not in init_text
    assert "from yfinance" not in init_text


def test_yfinance_module_imports_lazily():
    """``yfinance`` must only be imported inside a function body, not at module top."""
    p = ALLOWED_PARENT / "yfinance_source.py"
    text = p.read_text(encoding="utf-8")
    # Find any non-indented `import yfinance` (top-level): there must be none.
    top_level_pattern = re.compile(r"^(?:from\s+yfinance\b|import\s+yfinance\b)", re.MULTILINE)
    matches = top_level_pattern.findall(text)
    assert not matches, (
        f"yfinance must be imported lazily (inside a function), found {matches!r} "
        f"at module top level"
    )
