"""Synthetic run fixture for stats tests.

Builds a complete `runs/<run_id>/` directory under ``tmp_path``:
- run_metadata.json
- trace_raw.jsonl (= trace_joined for tests; we fold a future_outcome in)
- outcome_backfill.jsonl
- trace_joined.jsonl (with future_outcome populated)
- trades.jsonl
- skipped_fills.jsonl
- backtest_result.json

Tests use this to exercise the loader + aggregator + writer end to end.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from kabu.backtest.engine import SkippedFill
from kabu.backtest.io import (
    summarize_backtest_result,
    write_backtest_result_json,
    write_skipped_fills_jsonl,
    write_trades_jsonl,
)
from kabu.backtest.trade import Trade
from kabu.decision_trace import (
    BollingerPoint,
    DecisionSlice,
    ExecutionAssumptionSlice,
    FutureOutcomeSlice,
    LongTermTrendSlice,
    MACDPoint,
    MarketSlice,
    RiskCtxSlice,
    SCHEMA_VERSION,
    TechnicalSlice,
    Trace,
    TraceSlices,
)
from kabu.run_metadata_io import write_run_metadata_json
from kabu.run_paths import build_run_paths
from kabu.trace_io import write_traces_jsonl

from tests.backtest._fixtures import make_run_metadata


JST = timezone(timedelta(hours=9))


def _make_trace(
    *,
    run_id: str,
    symbol: str,
    bar_index: int,
    rsi: float,
    close_vs_sma200: float,
    macd_hist: float,
    final_action: str = "observe_only",
    forward_return_5d: float | None = 0.01,
    outcome_label_static: str | None = None,
    rule_id: str = "trace_mvp_observe_only",
    rule_version: str = "0.1.0",
    rule_params_hash: str = "0123456789abcdef",
) -> Trace:
    bar_ts = datetime(2024, 4, 1, 15, 0, tzinfo=JST) + timedelta(days=bar_index)
    bar_ts_close = bar_ts
    bar_ts_available = bar_ts + timedelta(minutes=30)
    market = MarketSlice(
        open=1000.0, high=1010.0, low=999.0, close=1005.0,
        adj_close=1005.0, volume=1_000_000, turnover=1_005_000_000.0,
        prev_close=1002.0, gap_pct=(1000.0 - 1002.0) / 1002.0,
    )
    technical = TechnicalSlice(
        adjustment_basis="split_dividend_back_adjusted",
        sma20=1004.0, sma60=1003.0, sma200=1001.0,
        rsi14=rsi,
        macd=MACDPoint(line=0.5, signal=0.4, hist=macd_hist),
        bb=BollingerPoint(middle=1004.0, upper=1010.0, lower=998.0),
        atr14=1.5,
    )
    if close_vs_sma200 > 0:
        trend = "above_sma200"
    elif close_vs_sma200 < 0:
        trend = "below_sma200"
    else:
        trend = "unknown"
    long_term = LongTermTrendSlice(
        close_vs_sma200=close_vs_sma200,
        trend_label=trend,  # type: ignore[arg-type]
    )
    risk = RiskCtxSlice()
    decision = DecisionSlice(
        final_action=final_action,  # type: ignore[arg-type]
        technical_only_action="not_evaluated",
        rule_id=rule_id,
        rule_version=rule_version,
        rule_params_hash=rule_params_hash,
    )
    execution = ExecutionAssumptionSlice(
        assumed_fill_bar="next_open",
        latency_bars=1,
        slippage_bps=5.0,
        fee_bps=5.0,
    )
    fo = FutureOutcomeSlice(
        forward_return_basis="close_to_close",
        forward_return_5d=forward_return_5d,
        outcome_label_static=outcome_label_static,  # type: ignore[arg-type]
        forward_return_horizon_bars=(1, 5, 20),
        forward_return_end_ts=bar_ts_available + timedelta(days=5),
    )
    return Trace(
        schema_version=SCHEMA_VERSION,
        trace_schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit_sha="abcdef0123456789",
        created_at=datetime(2024, 4, 30, 16, 0, tzinfo=JST),
        symbol=symbol,
        market="TSE_PRIME",
        sector="輸送用機器",
        interval="1d",
        bar_ts=bar_ts,
        bar_ts_close=bar_ts_close,
        bar_ts_available=bar_ts_available,
        universe_snapshot_id="manual_v1",
        data_snapshot_hash="deadbeef" * 4,
        slices=TraceSlices(
            market=market,
            technical=technical,
            long_term_trend=long_term,
            risk_ctx=risk,
            decision=decision,
            execution_assumption=execution,
            future_outcome=fo,
        ),
        unavailable_reason=None,
    )


def make_traces(run_id: str = "r_test", n: int = 35) -> list[Trace]:
    """35 traces so the default minimum_n=30 has at least one bucket pass."""
    traces: list[Trace] = []
    for i in range(n):
        # Vary RSI / SMA distance / MACD hist to spread across buckets.
        rsi = 25.0 + (i * 1.5)  # 25 .. 76
        close_vs_sma200 = -0.15 + i * 0.01  # -0.15 .. 0.19
        macd_hist = -0.5 + (i * 0.04)
        # Outcome label spread.
        if i % 5 == 0:
            label = "win"
            ret = 0.05
        elif i % 5 == 1:
            label = "loss"
            ret = -0.04
        elif i % 5 == 2:
            label = "flat"
            ret = 0.0
        elif i % 5 == 3:
            label = "big_win"
            ret = 0.10
        else:
            label = "big_loss"
            ret = -0.10
        traces.append(
            _make_trace(
                run_id=run_id,
                symbol="7203" if i % 2 == 0 else "6758",
                bar_index=i,
                rsi=rsi,
                close_vs_sma200=close_vs_sma200,
                macd_hist=macd_hist,
                forward_return_5d=ret,
                outcome_label_static=label,
            )
        )
    return traces


def make_trades(run_id: str = "r_test", trace_jsonl_path: str = "/tmp/x.jsonl") -> list[Trade]:
    base = datetime(2024, 4, 1, 15, 0, tzinfo=JST)
    return [
        Trade(
            trade_id=f"{run_id}-00000",
            run_id=run_id,
            symbol="7203",
            side="long",
            quantity=100,
            entry_decision_ts=base,
            entry_fill_ts=base + timedelta(days=1),
            entry_price=1000.0,
            entry_trace_key=f"7203@{base.isoformat()}",
            trace_jsonl_path=trace_jsonl_path,
            fee_jpy=500.0,
            slippage_jpy=100.0,
            exit_decision_ts=base + timedelta(days=5),
            exit_fill_ts=base + timedelta(days=6),
            exit_price=1010.0,
            exit_trace_key=f"7203@{(base + timedelta(days=5)).isoformat()}",
            exit_reason="scripted_exit",
            gross_pnl_jpy=1000.0,
            net_pnl_jpy=400.0,
        ),
    ]


def make_skipped(run_id: str = "r_test") -> list[SkippedFill]:
    base = datetime(2024, 4, 1, 15, 0, tzinfo=JST)
    return [
        SkippedFill(
            run_id=run_id,
            symbol="7203",
            decision_ts=base + timedelta(days=10),
            attempted_fill_ts=base + timedelta(days=11),
            intended_action="enter_long",
            reason="halted",
        ),
        SkippedFill(
            run_id=run_id,
            symbol="6758",
            decision_ts=base + timedelta(days=12),
            attempted_fill_ts=base + timedelta(days=13),
            intended_action="exit_long",
            reason="not_long",
        ),
        SkippedFill(
            run_id=run_id,
            symbol="6758",
            decision_ts=base + timedelta(days=14),
            attempted_fill_ts=base + timedelta(days=15),
            intended_action="enter_long",
            reason="halted",
        ),
    ]


def build_run(tmp_path: Path, run_id: str = "r_test"):
    """Materialize a complete run directory under ``tmp_path``.

    Returns the ``RunPaths`` object pointing at it.
    """
    paths = build_run_paths(tmp_path, run_id=run_id)
    paths.ensure_run_dir()

    metadata = make_run_metadata(run_id=run_id)
    write_run_metadata_json(paths.run_metadata_json, metadata)

    traces = make_traces(run_id=run_id, n=35)
    # trace_raw is what build_trace would have produced; trace_joined has fo.
    write_traces_jsonl(paths.trace_raw_jsonl, traces)
    write_traces_jsonl(paths.trace_joined_jsonl, traces)

    trades = make_trades(run_id=run_id, trace_jsonl_path=str(paths.trace_raw_jsonl))
    write_trades_jsonl(paths.trades_jsonl, trades)

    skipped = make_skipped(run_id=run_id)
    write_skipped_fills_jsonl(paths.skipped_fills_jsonl, skipped)

    # Build a fake BacktestResult-shaped summary for round trip.
    from kabu.backtest.engine import BacktestResult
    result = BacktestResult(
        run_id=run_id,
        trades=tuple(trades),
        closing_positions=(),
        skipped=tuple(skipped),
        initial_cash_jpy=10_000_000.0,
        final_cash_jpy=10_001_000.0,
        trace_jsonl_path=str(paths.trace_raw_jsonl),
    )
    summary = summarize_backtest_result(
        result,
        created_at=datetime(2024, 4, 30, 16, 0, tzinfo=JST),
        trades_jsonl_path=str(paths.trades_jsonl),
        skipped_fills_jsonl_path=str(paths.skipped_fills_jsonl),
    )
    write_backtest_result_json(paths.backtest_result_json, summary)
    return paths
