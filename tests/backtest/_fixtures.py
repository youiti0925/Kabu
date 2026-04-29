"""Shared fixtures for the backtest engine tests.

Provides:
- ``make_bars``: a simple uptrending OHLCV series.
- ``make_run_metadata``: a fully-populated RunMetadata.
- ``DEFAULT_COST``: a CostAssumptions with non-trivial fee + slippage so
  PnL effects are visible.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from kabu.data.source import OHLCBar
from kabu.decision_trace import RunMetadata, SCHEMA_VERSION
from kabu.decision_trace_build import CostAssumptions

JST = timezone(timedelta(hours=9))


DEFAULT_COST = CostAssumptions(slippage_bps=10.0, fee_bps=10.0, fee_fixed_jpy=None)


def make_bars(
    n: int = 30,
    *,
    symbol: str = "7203",
    start_close: float = 1000.0,
    daily_step: float = 1.0,
    volume: int = 1_000_000,
) -> list[OHLCBar]:
    """Return ``n`` daily uptrending bars with non-zero volume / turnover."""
    base = datetime(2024, 4, 1, 15, 0, tzinfo=JST)
    out: list[OHLCBar] = []
    for i in range(n):
        bar_ts = base + timedelta(days=i)
        close = start_close + i * daily_step
        open_ = close - 0.5
        high = close + 1.0
        low = close - 1.0
        prev_close = out[-1].close if out else None
        out.append(
            OHLCBar(
                symbol=symbol,
                interval="1d",
                bar_ts=bar_ts,
                bar_ts_close=bar_ts,
                bar_ts_available=bar_ts + timedelta(minutes=30),
                open=open_,
                high=high,
                low=low,
                close=close,
                adj_close=close,
                volume=volume,
                turnover=close * volume,
                prev_close=prev_close,
            )
        )
    return out


def replace_bar(bar: OHLCBar, **changes) -> OHLCBar:
    """Re-construct an OHLCBar with overrides (frozen dataclass workaround)."""
    base = dict(
        symbol=bar.symbol,
        interval=bar.interval,
        bar_ts=bar.bar_ts,
        bar_ts_close=bar.bar_ts_close,
        bar_ts_available=bar.bar_ts_available,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        adj_close=bar.adj_close,
        volume=bar.volume,
        turnover=bar.turnover,
        prev_close=bar.prev_close,
    )
    base.update(changes)
    return OHLCBar(**base)


def make_run_metadata(**overrides) -> RunMetadata:
    base = dict(
        run_id="run_test_0001",
        commit_sha="abcdef0123456789",
        created_at=datetime(2024, 4, 26, 16, 0, tzinfo=JST),
        trace_schema_version=SCHEMA_VERSION,
        interval="1d",
        universe_snapshot_id="manual_v1",
        data_snapshot_hash="deadbeef" * 4,
        survivorship_policy="static_current_listing",
        survivorship_warning=True,
        currency="JPY",
        report_currency="JPY",
        tax_basis="pretax",
        libraries=(),
        warnings=(),
    )
    base.update(overrides)
    return RunMetadata(**base)
