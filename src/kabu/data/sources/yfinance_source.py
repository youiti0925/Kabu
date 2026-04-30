"""yfinance-backed Source adapter (P4.7).

This module is the ONLY place in ``src/kabu/`` that may import the
``yfinance`` package, and it does so LAZILY (inside
``_default_yfinance_history``). This keeps the rest of the codebase
free of vendor coupling and lets CI run without the real package
installed.

Usage:

    from kabu.data.sources import YFinanceSource
    src = YFinanceSource()                # real network use (manual / local)
    src = YFinanceSource(history_fn=fake) # tests; never touches yfinance

Contract references:
- DATA_SOURCES.md S0 D-3 (vendor isolation)
- DATA_SOURCES.md S0 D-4 (as_of required)
- DATA_SOURCES.md S0 D-5 (data_source / data_source_version in run_metadata)
- POINT_IN_TIME.md 3-1 / 5 (bar_ts_available <= as_of)
- CALENDAR.md S0 D-2 / D-6 / D-7 (tz-aware datetimes; bar_ts == bar_ts_available)

PIT note: yfinance is NOT a point-in-time data source. P4.7 uses it for
OHLCV smoke testing only. fundamentals / earnings / news from yfinance
are explicitly disallowed (DATA_SOURCES.md S0 D-6).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Any, Optional

from kabu.data.source import OHLCBar


JST = timezone(timedelta(hours=9))

# Public constant: how this source identifies itself in run_metadata.
DATA_SOURCE_NAME = "yfinance"


HistoryFn = Callable[[str, datetime, datetime], Sequence[Mapping[str, Any]]]


def _require_aware(name: str, ts: datetime) -> None:
    if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
        raise ValueError(f"{name} must be timezone-aware (CALENDAR.md S0 D-2)")


def yfinance_row_to_ohlcbar(
    row: Mapping[str, Any],
    *,
    symbol: str,
    interval: str,
    bar_close_tz: timezone = JST,
    bar_close_hour: int = 15,
    bar_close_minute: int = 0,
    fill_lag: timedelta = timedelta(minutes=30),
    prev_close: Optional[float] = None,
) -> OHLCBar:
    """Convert one yfinance-style row into an ``OHLCBar``.

    The row must carry: ``date`` (a ``date`` or ``datetime``), ``open``,
    ``high``, ``low``, ``close``, ``adj_close``, ``volume``. ``turnover``
    is computed as ``close * volume`` if not supplied.

    bar_ts_close is computed as the requested close time on the bar's
    date (in ``bar_close_tz``). bar_ts_available = bar_ts_close + fill_lag.
    bar_ts = bar_ts_available (CALENDAR.md S0 D-7).
    """
    raw_date = row["date"]
    if isinstance(raw_date, datetime):
        bar_date = raw_date.date()
    else:
        bar_date = raw_date  # assumed datetime.date
    bar_ts_close = datetime.combine(
        bar_date,
        time(hour=bar_close_hour, minute=bar_close_minute),
        tzinfo=bar_close_tz,
    )
    bar_ts_available = bar_ts_close + fill_lag

    open_ = float(row["open"])
    high = float(row["high"])
    low = float(row["low"])
    close = float(row["close"])
    adj_close = float(row.get("adj_close", close))
    volume = int(row["volume"])
    turnover = float(row.get("turnover", close * volume))

    return OHLCBar(
        symbol=symbol,
        interval=interval,
        bar_ts=bar_ts_available,
        bar_ts_close=bar_ts_close,
        bar_ts_available=bar_ts_available,
        open=open_,
        high=high,
        low=low,
        close=close,
        adj_close=adj_close,
        volume=volume,
        turnover=turnover,
        prev_close=prev_close,
    )


def _default_yfinance_history(
    symbol: str, start: datetime, end: datetime
) -> Sequence[Mapping[str, Any]]:
    """Default history function. Imports yfinance lazily.

    This function is the ONE place that imports the real yfinance
    package. It is reached only when the caller leaves ``history_fn``
    unset and actually requests data. Tests inject a fake ``history_fn``
    so this code path is never triggered under pytest.
    """
    import yfinance  # noqa: PLC0415  (lazy on purpose)

    df = yfinance.Ticker(symbol).history(
        start=start.date(),
        end=end.date(),
        auto_adjust=False,
    )
    rows: list[dict[str, Any]] = []
    for ts, row in df.iterrows():
        try:
            bar_date = ts.to_pydatetime().date()
        except AttributeError:
            bar_date = ts.date() if hasattr(ts, "date") else ts
        rows.append(
            {
                "date": bar_date,
                "open": float(row.get("Open", 0.0)),
                "high": float(row.get("High", 0.0)),
                "low": float(row.get("Low", 0.0)),
                "close": float(row.get("Close", 0.0)),
                "adj_close": float(row.get("Adj Close", row.get("Close", 0.0))),
                "volume": int(row.get("Volume", 0)),
            }
        )
    return rows


@dataclass
class YFinanceSource:
    """Adapter implementing the ``kabu.data.Source`` Protocol via yfinance.

    P4.7 keeps this MVP-only:
    - 1d bars on the OHLCV path
    - bar timestamps are placed in JST (configurable)
    - PIT cutoff is enforced (``bar_ts_available <= as_of``)
    - fundamentals / earnings / news are NOT exposed here
    """

    history_fn: Optional[HistoryFn] = None
    default_tz: timezone = JST
    bar_close_hour: int = 15
    bar_close_minute: int = 0
    fill_lag_minutes: int = 30

    def get_ohlcv(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        *,
        as_of: datetime,
    ) -> list[OHLCBar]:
        if not isinstance(symbol, str) or not symbol:
            raise ValueError("symbol must be a non-empty string")
        for ts, name in ((start, "start"), (end, "end"), (as_of, "as_of")):
            _require_aware(name, ts)
        if start > end:
            raise ValueError("start must be <= end")

        history_fn = self.history_fn or _default_yfinance_history
        rows = history_fn(symbol, start, end)

        fill_lag = timedelta(minutes=self.fill_lag_minutes)
        out: list[OHLCBar] = []
        prev_close: Optional[float] = None
        for raw in rows:
            bar = yfinance_row_to_ohlcbar(
                raw,
                symbol=symbol,
                interval="1d",
                bar_close_tz=self.default_tz,
                bar_close_hour=self.bar_close_hour,
                bar_close_minute=self.bar_close_minute,
                fill_lag=fill_lag,
                prev_close=prev_close,
            )
            prev_close = bar.close
            if bar.bar_ts < start or bar.bar_ts > end:
                continue
            if bar.bar_ts_available > as_of:
                continue
            out.append(bar)
        out.sort(key=lambda b: b.bar_ts)
        return out


__all__ = [
    "DATA_SOURCE_NAME",
    "HistoryFn",
    "YFinanceSource",
    "yfinance_row_to_ohlcbar",
]
