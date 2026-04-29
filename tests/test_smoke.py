"""Smoke test: ensure the package imports and exposes a version string.

This test exists so pytest has at least one test to collect at the
P0.9 guardrail stage. Replace / extend in PR-S1+.
"""

from __future__ import annotations


def test_kabu_imports_and_has_version() -> None:
    import kabu

    assert hasattr(kabu, "__version__")
    assert isinstance(kabu.__version__, str)
    assert kabu.__version__ != ""
