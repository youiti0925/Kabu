"""Unit tests for kabu.indicators.macd."""

from __future__ import annotations

import pytest

from kabu.indicators.macd import macd


def test_macd_returns_none_until_signal_seed_filled():
    out = macd([float(i) for i in range(20)])
    # Default 12 / 26 / 9: needs 26 + 9 - 1 = 34 bars before first signal.
    assert all(v is None for v in out)


def test_macd_short_input_all_none():
    out = macd([1.0, 2.0, 3.0])
    assert all(v is None for v in out)


def test_macd_pure_uptrend_hist_eventually_positive():
    series = [float(i) for i in range(1, 100)]
    out = macd(series)
    last = out[-1]
    assert last is not None
    # In a pure uptrend, MACD line > 0 and signal trails it, so hist > 0.
    assert last.line > 0
    assert last.signal > 0


def test_macd_rejects_fast_ge_slow():
    with pytest.raises(ValueError):
        macd([1.0, 2.0, 3.0], fast=12, slow=12)


def test_macd_does_not_mutate_input():
    src = [float(i) for i in range(50)]
    snapshot = list(src)
    macd(src)
    assert src == snapshot
