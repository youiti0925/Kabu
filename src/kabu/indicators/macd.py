"""MACD (12 / 26 / 9 default)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from kabu.indicators._utils import require_floats, require_window


@dataclass(frozen=True)
class MACDPoint:
    line: float
    signal: float
    hist: float


def _ema(values: Sequence[float], window: int) -> list[float | None]:
    require_window(window)
    n = len(values)
    out: list[float | None] = [None] * n
    if n < window:
        return out
    seed = sum(values[:window]) / window
    out[window - 1] = seed
    alpha = 2.0 / (window + 1)
    prev = seed
    for i in range(window, n):
        prev = alpha * values[i] + (1 - alpha) * prev
        out[i] = prev
    return out


def macd(
    values: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> list[MACDPoint | None]:
    """Return MACD line / signal / histogram for each index.

    None until both EMAs and the signal EMA over the MACD line are filled.
    """
    require_window(fast)
    require_window(slow)
    require_window(signal)
    require_floats(values)
    if fast >= slow:
        raise ValueError("fast must be < slow")

    n = len(values)
    fast_ema = _ema(values, fast)
    slow_ema = _ema(values, slow)
    macd_line: list[float | None] = [None] * n
    for i in range(n):
        f = fast_ema[i]
        s = slow_ema[i]
        if f is None or s is None:
            continue
        macd_line[i] = f - s

    # signal EMA seeds at the first index where ``signal`` consecutive
    # MACD-line values are available.
    out: list[MACDPoint | None] = [None] * n
    first = next((i for i, v in enumerate(macd_line) if v is not None), None)
    if first is None or first + signal > n:
        return out
    seed_idx = first + signal - 1
    seed = sum(macd_line[first : first + signal]) / signal  # type: ignore[arg-type]
    sig_prev = seed
    line_at_seed = macd_line[seed_idx]
    assert line_at_seed is not None
    out[seed_idx] = MACDPoint(line=line_at_seed, signal=seed, hist=line_at_seed - seed)
    alpha = 2.0 / (signal + 1)
    for i in range(seed_idx + 1, n):
        v = macd_line[i]
        if v is None:
            continue
        sig_prev = alpha * v + (1 - alpha) * sig_prev
        out[i] = MACDPoint(line=v, signal=sig_prev, hist=v - sig_prev)
    return out
