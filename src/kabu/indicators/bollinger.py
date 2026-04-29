"""Bollinger Bands."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from kabu.indicators._utils import require_floats, require_window


@dataclass(frozen=True)
class BollingerPoint:
    middle: float
    upper: float
    lower: float


def bollinger_bands(
    values: Sequence[float],
    window: int = 20,
    num_std: float = 2.0,
) -> list[BollingerPoint | None]:
    """Return middle / upper / lower band for each index.

    Middle is the simple moving average. Upper / lower use the population
    standard deviation over the same window (matching most charting tools).
    """
    require_window(window)
    require_floats(values)
    if num_std <= 0:
        raise ValueError("num_std must be positive")
    n = len(values)
    out: list[BollingerPoint | None] = [None] * n
    if n < window:
        return out
    for i in range(window - 1, n):
        chunk = values[i - window + 1 : i + 1]
        mean = sum(chunk) / window
        variance = sum((x - mean) ** 2 for x in chunk) / window
        sd = math.sqrt(variance)
        out[i] = BollingerPoint(
            middle=mean,
            upper=mean + num_std * sd,
            lower=mean - num_std * sd,
        )
    return out
