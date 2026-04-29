"""Simple Moving Average."""

from __future__ import annotations

from collections.abc import Sequence

from kabu.indicators._utils import require_floats, require_window


def sma(values: Sequence[float], window: int) -> list[float | None]:
    """Return the simple moving average over ``window`` bars.

    Output length equals input length. Indices ``[0, window-2]`` are
    ``None`` because the window is not yet full.
    """
    require_window(window)
    require_floats(values)
    n = len(values)
    out: list[float | None] = [None] * n
    if n < window:
        return out
    running = sum(values[:window])
    out[window - 1] = running / window
    for i in range(window, n):
        running += values[i] - values[i - window]
        out[i] = running / window
    return out
