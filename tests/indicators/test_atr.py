"""Unit tests for kabu.indicators.atr."""

from __future__ import annotations

import pytest

from kabu.indicators.atr import atr


def test_atr_returns_none_until_seed_filled():
    out = atr([1.0, 2.0, 3.0], [0.5, 1.5, 2.5], [1.0, 2.0, 3.0], window=14)
    assert all(v is None for v in out)


def test_atr_constant_range_returns_constant_value():
    n = 30
    high = [10.0] * n
    low = [9.0] * n
    close = [9.5] * n
    out = atr(high, low, close, window=14)
    last = out[-1]
    assert last is not None
    assert last == pytest.approx(1.0)


def test_atr_input_length_mismatch_raises():
    with pytest.raises(ValueError):
        atr([1.0, 2.0], [0.0, 1.0, 2.0], [1.0, 2.0], window=2)


def test_atr_rejects_non_positive_window():
    with pytest.raises(TypeError):
        atr([1.0, 2.0], [0.0, 1.0], [0.5, 1.5], window=0)


def test_atr_does_not_mutate_inputs():
    high = [10.0, 11.0, 12.0, 13.0, 14.0]
    low = [9.0, 10.0, 11.0, 12.0, 13.0]
    close = [9.5, 10.5, 11.5, 12.5, 13.5]
    snap_h = list(high)
    snap_l = list(low)
    snap_c = list(close)
    atr(high, low, close, window=2)
    assert high == snap_h
    assert low == snap_l
    assert close == snap_c
