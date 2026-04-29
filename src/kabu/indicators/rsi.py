"""Relative Strength Index (Wilder's smoothing)."""

from __future__ import annotations

from collections.abc import Sequence

from kabu.indicators._utils import require_floats, require_window


def rsi(values: Sequence[float], window: int = 14) -> list[float | None]:
    """Return Wilder's RSI over ``window`` bars.

    Output length equals input length. Indices ``[0, window-1]`` are
    ``None`` because the seed average needs ``window`` price changes.
    """
    require_window(window)
    require_floats(values)
    n = len(values)
    out: list[float | None] = [None] * n
    if n <= window:
        return out

    gain_sum = 0.0
    loss_sum = 0.0
    for i in range(1, window + 1):
        diff = values[i] - values[i - 1]
        if diff >= 0:
            gain_sum += diff
        else:
            loss_sum -= diff
    avg_gain = gain_sum / window
    avg_loss = loss_sum / window
    out[window] = _rsi_from(avg_gain, avg_loss)

    for i in range(window + 1, n):
        diff = values[i] - values[i - 1]
        gain = diff if diff > 0 else 0.0
        loss = -diff if diff < 0 else 0.0
        avg_gain = (avg_gain * (window - 1) + gain) / window
        avg_loss = (avg_loss * (window - 1) + loss) / window
        out[i] = _rsi_from(avg_gain, avg_loss)
    return out


def _rsi_from(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))
