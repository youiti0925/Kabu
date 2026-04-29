"""Unit tests for kabu.indicators.rsi."""

from __future__ import annotations

import pytest

from kabu.indicators.rsi import rsi


def test_rsi_returns_none_before_seed_filled():
    out = rsi([1.0, 2.0, 3.0], window=14)
    assert out == [None, None, None]


def test_rsi_pure_uptrend_is_100():
    series = [float(i) for i in range(1, 30)]
    out = rsi(series, window=14)
    # First filled index = window. Subsequent values for a pure uptrend == 100.
    assert out[14] == pytest.approx(100.0)
    assert all(v == pytest.approx(100.0) for v in out[14:])


def test_rsi_pure_downtrend_is_zero():
    series = [float(30 - i) for i in range(30)]
    out = rsi(series, window=14)
    assert out[14] == pytest.approx(0.0)
    assert all(v == pytest.approx(0.0) for v in out[14:])


def test_rsi_rejects_non_positive_window():
    with pytest.raises(TypeError):
        rsi([1.0, 2.0], window=0)


def test_rsi_does_not_mutate_input():
    src = [1.0, 2.0, 1.5, 2.5, 2.0, 3.0, 2.5, 3.5, 3.0, 4.0,
           3.5, 4.5, 4.0, 5.0, 4.5, 5.5]
    snapshot = list(src)
    rsi(src, window=14)
    assert src == snapshot
