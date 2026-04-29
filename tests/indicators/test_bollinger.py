"""Unit tests for kabu.indicators.bollinger."""

from __future__ import annotations

import pytest

from kabu.indicators.bollinger import bollinger_bands


def test_bb_constant_series_zero_width():
    out = bollinger_bands([5.0] * 25, window=20)
    last = out[-1]
    assert last is not None
    assert last.middle == pytest.approx(5.0)
    assert last.upper == pytest.approx(5.0)
    assert last.lower == pytest.approx(5.0)


def test_bb_returns_none_until_window_filled():
    out = bollinger_bands([float(i) for i in range(10)], window=20)
    assert all(v is None for v in out)


def test_bb_upper_above_middle_above_lower():
    out = bollinger_bands([1.0, 2.0, 3.0, 4.0, 5.0], window=3)
    last = out[-1]
    assert last is not None
    assert last.upper > last.middle > last.lower


def test_bb_rejects_non_positive_num_std():
    with pytest.raises(ValueError):
        bollinger_bands([1.0, 2.0, 3.0], window=3, num_std=0)


def test_bb_does_not_mutate_input():
    src = [1.0, 2.0, 3.0, 4.0, 5.0]
    snapshot = list(src)
    bollinger_bands(src, window=3)
    assert src == snapshot
