"""Invariant: indicators must not use future bars.

Policy: POINT_IN_TIME.md 3-2 / SCHEMA.md S0 D-9.

Test strategy: take a base series, compute indicator outputs, then EXTEND
the series with arbitrary future values and recompute. The original prefix
of outputs must be unchanged. If an indicator peeks ahead, the prefix would
shift.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

import pytest

from kabu.indicators.atr import atr
from kabu.indicators.bollinger import bollinger_bands
from kabu.indicators.macd import macd
from kabu.indicators.rsi import rsi
from kabu.indicators.sma import sma


BASE = [
    100.0, 101.0, 99.5, 102.0, 103.0, 104.5, 103.0, 105.0,
    106.5, 105.0, 107.0, 108.0, 109.5, 110.0, 109.0, 111.0,
    112.5, 113.0, 112.0, 114.0, 115.5, 117.0, 116.0, 118.0,
    119.5, 121.0, 120.0, 122.0, 123.5, 125.0, 124.0, 126.0,
    127.5, 129.0, 128.0, 130.0, 131.5, 133.0, 132.0, 134.0,
]
FUTURE_TAILS = [
    [1.0, 1.0, 1.0],
    [200.0, 199.0, 198.0],
    [50.0, 60.0, 70.0],
]


def _equal_prefix(a: Sequence[object], b: Sequence[object], n: int) -> None:
    assert n <= len(a)
    assert n <= len(b)
    for i in range(n):
        x, y = a[i], b[i]
        if x is None or y is None:
            assert x is y, f"index {i}: {x!r} vs {y!r}"
            continue
        if isinstance(x, float) and isinstance(y, float):
            assert math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-12), (
                f"index {i}: {x} vs {y}"
            )
            continue
        # Composite types (MACDPoint / BollingerPoint).
        assert x == y, f"index {i}: {x!r} vs {y!r}"


@pytest.mark.parametrize("future", FUTURE_TAILS)
def test_sma_no_lookahead(future: list[float]) -> None:
    out_base = sma(BASE, window=5)
    out_extended = sma(BASE + future, window=5)
    _equal_prefix(out_base, out_extended, len(BASE))


@pytest.mark.parametrize("future", FUTURE_TAILS)
def test_rsi_no_lookahead(future: list[float]) -> None:
    out_base = rsi(BASE, window=14)
    out_extended = rsi(BASE + future, window=14)
    _equal_prefix(out_base, out_extended, len(BASE))


@pytest.mark.parametrize("future", FUTURE_TAILS)
def test_macd_no_lookahead(future: list[float]) -> None:
    out_base = macd(BASE)
    out_extended = macd(BASE + future)
    _equal_prefix(out_base, out_extended, len(BASE))


@pytest.mark.parametrize("future", FUTURE_TAILS)
def test_bollinger_no_lookahead(future: list[float]) -> None:
    out_base = bollinger_bands(BASE, window=20)
    out_extended = bollinger_bands(BASE + future, window=20)
    _equal_prefix(out_base, out_extended, len(BASE))


@pytest.mark.parametrize("future", FUTURE_TAILS)
def test_atr_no_lookahead(future: list[float]) -> None:
    high = [v + 0.5 for v in BASE]
    low = [v - 0.5 for v in BASE]
    close = list(BASE)
    h2 = high + [v + 0.5 for v in future]
    l2 = low + [v - 0.5 for v in future]
    c2 = close + future
    out_base = atr(high, low, close, window=14)
    out_extended = atr(h2, l2, c2, window=14)
    _equal_prefix(out_base, out_extended, len(BASE))


def test_rolling_window_emits_none_until_filled() -> None:
    """Rolling indicators must NOT bfill / use future to fill the warmup."""
    out = sma([1.0, 2.0, 3.0, 4.0, 5.0], window=3)
    # Indices 0 and 1 cannot have a value -- they would require either a
    # past value we don't have or a future one.
    assert out[0] is None
    assert out[1] is None
    assert out[2] is not None
