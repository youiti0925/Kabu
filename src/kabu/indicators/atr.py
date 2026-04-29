"""Average True Range (Wilder)."""

from __future__ import annotations

from collections.abc import Sequence

from kabu.indicators._utils import require_window


def atr(
    high: Sequence[float],
    low: Sequence[float],
    close: Sequence[float],
    window: int = 14,
) -> list[float | None]:
    """Return Wilder's ATR over ``window`` bars.

    Inputs must have equal length. Output length matches the inputs.
    Indices ``[0, window-1]`` are ``None`` because the seed average needs
    ``window`` true-range values.
    """
    require_window(window)
    if not (len(high) == len(low) == len(close)):
        raise ValueError("high / low / close must have equal length")
    n = len(high)
    out: list[float | None] = [None] * n
    if n <= window:
        return out

    tr: list[float] = [0.0] * n
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )

    seed = sum(tr[1 : window + 1]) / window
    out[window] = seed
    prev = seed
    for i in range(window + 1, n):
        prev = (prev * (window - 1) + tr[i]) / window
        out[i] = prev
    return out
