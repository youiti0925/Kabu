"""Pure-function technical indicators.

Every function in this package:
- consumes only past data (no future bars; POINT_IN_TIME.md 3-2)
- returns ``None`` for indices where the rolling window is not yet filled
- never mutates its inputs

These are computed on adjusted series (BACKTEST_CONTRACT.md S0 D-9 /
SCHEMA.md S0 D-9). The caller is responsible for passing adjusted close
values; the indicator does not adjust on its own.
"""

from kabu.indicators.atr import atr
from kabu.indicators.bollinger import bollinger_bands
from kabu.indicators.macd import macd
from kabu.indicators.rsi import rsi
from kabu.indicators.sma import sma

__all__ = ["sma", "rsi", "macd", "bollinger_bands", "atr"]
