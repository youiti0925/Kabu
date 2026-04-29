"""Shared test fixtures for kabu.decision_trace.* tests.

Builds a deterministic synthetic OHLCV history long enough to fill all
indicator windows (200 bars) and a default valid Trace for tweak-style
tests.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from kabu.data.source import OHLCBar
from kabu.decision_trace import (
    ASSUMED_FILL_BAR_NEXT_OPEN,
    DEFAULT_ADJUSTMENT_BASIS,
    DEFAULT_LATENCY_BARS,
    OBSERVE_ONLY_RULE_ID,
    OBSERVE_ONLY_RULE_VERSION,
    BollingerPoint,
    DecisionSlice,
    ExecutionAssumptionSlice,
    LongTermTrendSlice,
    MACDPoint,
    MarketSlice,
    RiskCtxSlice,
    SCHEMA_VERSION,
    TechnicalSlice,
    Trace,
    TraceSlices,
)
from kabu.decision_trace_build import CostAssumptions

JST = timezone(timedelta(hours=9))


def make_bars(n: int = 250, symbol: str = "7203") -> list[OHLCBar]:
    """Return ``n`` daily OHLCV bars, gently uptrending."""
    base = datetime(2024, 1, 4, 15, 0, tzinfo=JST)
    out: list[OHLCBar] = []
    for i in range(n):
        bar_ts = base + timedelta(days=i)
        bar_ts_close = bar_ts
        bar_ts_available = bar_ts + timedelta(minutes=30)
        close = 1000.0 + i * 1.5
        open_ = close - 0.5
        high = close + 1.0
        low = close - 1.0
        prev_close = out[-1].close if out else None
        out.append(
            OHLCBar(
                symbol=symbol,
                interval="1d",
                bar_ts=bar_ts,
                bar_ts_close=bar_ts_close,
                bar_ts_available=bar_ts_available,
                open=open_,
                high=high,
                low=low,
                close=close,
                adj_close=close,
                volume=1_000_000,
                turnover=close * 1_000_000,
                prev_close=prev_close,
            )
        )
    return out


def default_cost() -> CostAssumptions:
    return CostAssumptions(slippage_bps=5.0, fee_bps=5.0, fee_fixed_jpy=None)


def make_trace(**overrides) -> Trace:
    """Return a fully-populated, valid Trace. Override any field via kwargs."""
    bar_ts = datetime(2024, 4, 26, 15, 0, tzinfo=JST)
    bar_ts_close = bar_ts
    bar_ts_available = bar_ts + timedelta(minutes=30)
    market = MarketSlice(
        open=1000.0, high=1010.0, low=999.0, close=1005.0,
        adj_close=1005.0, volume=1_000_000, turnover=1_005_000_000.0,
        prev_close=1002.0, gap_pct=(1000.0 - 1002.0) / 1002.0,
    )
    technical = TechnicalSlice(
        adjustment_basis=DEFAULT_ADJUSTMENT_BASIS,
        sma20=1004.0, sma60=1003.0, sma200=1001.0,
        rsi14=55.0,
        macd=MACDPoint(line=0.5, signal=0.4, hist=0.1),
        bb=BollingerPoint(middle=1004.0, upper=1010.0, lower=998.0),
        atr14=1.5,
    )
    long_term_trend = LongTermTrendSlice(
        close_vs_sma200=(1005.0 - 1001.0) / 1001.0,
        trend_label="above_sma200",
    )
    risk_ctx = RiskCtxSlice()
    decision = DecisionSlice(
        final_action="observe_only",
        technical_only_action="not_evaluated",
        rule_id=OBSERVE_ONLY_RULE_ID,
        rule_version=OBSERVE_ONLY_RULE_VERSION,
        rule_params_hash="0123456789abcdef",
    )
    execution = ExecutionAssumptionSlice(
        assumed_fill_bar=ASSUMED_FILL_BAR_NEXT_OPEN,
        latency_bars=DEFAULT_LATENCY_BARS,
        slippage_bps=5.0,
        fee_bps=5.0,
    )
    slices = TraceSlices(
        market=market,
        technical=technical,
        long_term_trend=long_term_trend,
        risk_ctx=risk_ctx,
        decision=decision,
        execution_assumption=execution,
        future_outcome=None,
    )

    base = dict(
        schema_version=SCHEMA_VERSION,
        trace_schema_version=SCHEMA_VERSION,
        run_id="run_test_0001",
        commit_sha="abcdef0123456789",
        created_at=datetime(2024, 4, 26, 16, 0, tzinfo=JST),
        symbol="7203",
        market="TSE_PRIME",
        sector="輸送用機器",
        interval="1d",
        bar_ts=bar_ts,
        bar_ts_close=bar_ts_close,
        bar_ts_available=bar_ts_available,
        universe_snapshot_id="manual_v1",
        data_snapshot_hash="deadbeef" * 4,
        slices=slices,
        unavailable_reason=None,
    )
    base.update(overrides)
    return Trace(**base)
