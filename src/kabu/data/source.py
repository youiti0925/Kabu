"""Source Protocol and OHLCBar value type.

Contract references:
- DATA_SOURCES.md S0 D-3 (Source Protocol comes first; vendors hidden)
- DATA_SOURCES.md S0 D-4 (as_of required, no default)
- CALENDAR.md S0 D-2 / D-6 / D-7 (tz-aware datetimes; bar_ts == bar_ts_available by default)
- SCHEMA.md S0 D-1..D-3 (interval / bar_ts_close / bar_ts_available required)
- BACKTEST_CONTRACT.md S0 D-9 (raw + adj_close coexist)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class OHLCBar:
    """A single OHLCV bar in raw + adjusted form.

    All datetimes must be timezone-aware (CALENDAR.md S0 D-2). bar_ts is by
    default `bar_ts_available` (CALENDAR.md S0 D-7) -- callers that need the
    other timestamps should read them explicitly.
    """

    symbol: str
    interval: str
    bar_ts: datetime
    bar_ts_close: datetime
    bar_ts_available: datetime
    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: int
    turnover: float
    prev_close: float | None = None
    # Halt / circuit-breaker flags. PR-S3 backtest engine uses these as a
    # conservative proxy for fillability (BACKTEST_CONTRACT.md S0 D-12).
    is_halted: bool = False
    is_special_quote: bool = False
    is_circuit_breaker: bool = False

    def __post_init__(self) -> None:
        for name in ("bar_ts", "bar_ts_close", "bar_ts_available"):
            ts = getattr(self, name)
            if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
                raise ValueError(
                    f"OHLCBar.{name} must be timezone-aware "
                    f"(CALENDAR.md S0 D-2); got naive {ts!r}"
                )
        if self.bar_ts_close > self.bar_ts_available:
            raise ValueError(
                "bar_ts_close must be <= bar_ts_available "
                "(CALENDAR.md S0 D-6)"
            )
        if self.high < self.low:
            raise ValueError("high must be >= low")
        if self.volume < 0:
            raise ValueError("volume must be >= 0")


@runtime_checkable
class Source(Protocol):
    """Vendor-agnostic OHLCV accessor.

    Implementations must:
    - take ``as_of`` as a required keyword-only argument with no default
      (DATA_SOURCES.md S0 D-4); callers that fail to pass it should hit a
      ``TypeError`` from Python's argument resolver.
    - never return bars whose ``bar_ts_available > as_of`` (point-in-time
      invariant; POINT_IN_TIME.md 3-1 / 5).
    - return bars sorted by ``bar_ts`` ascending.
    - never mutate inputs.

    The Protocol is intentionally narrow at PR-S1. ``get_fundamentals``,
    ``get_earnings``, etc. are deliberately omitted -- they are blocked
    until a point-in-time source is adopted (DATA_SOURCES.md S0 D-6 / D-7).
    """

    def get_ohlcv(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        *,
        as_of: datetime,
    ) -> list[OHLCBar]:
        ...
