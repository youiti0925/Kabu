"""Unit tests for kabu.indicators.sma."""

from __future__ import annotations

import math

import pytest

from kabu.indicators.sma import sma


def test_sma_basic_window_3():
    out = sma([1.0, 2.0, 3.0, 4.0, 5.0], window=3)
    assert out[0] is None
    assert out[1] is None
    assert math.isclose(out[2], 2.0)
    assert math.isclose(out[3], 3.0)
    assert math.isclose(out[4], 4.0)


def test_sma_too_short_returns_all_none():
    out = sma([1.0, 2.0], window=5)
    assert out == [None, None]


def test_sma_window_1_is_identity():
    out = sma([1.5, 2.5, 3.5], window=1)
    assert [round(v, 6) for v in out] == [1.5, 2.5, 3.5]


def test_sma_rejects_non_positive_window():
    with pytest.raises(TypeError):
        sma([1.0, 2.0], window=0)
    with pytest.raises(TypeError):
        sma([1.0, 2.0], window=-3)


def test_sma_rejects_none_in_input():
    with pytest.raises(ValueError):
        sma([1.0, None, 3.0], window=2)  # type: ignore[list-item]


def test_sma_does_not_mutate_input():
    src = [1.0, 2.0, 3.0, 4.0]
    snapshot = list(src)
    sma(src, window=2)
    assert src == snapshot
