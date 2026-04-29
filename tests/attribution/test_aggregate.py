"""Aggregation tests for kabu.attribution."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from kabu.attribution import (
    AttributionConfig,
    build_attribution_report,
    build_axes,
    build_overall_totals,
)
from kabu.backtest.engine import SkippedFill
from kabu.backtest.io import (
    summarize_backtest_result,
    write_backtest_result_json,
    write_skipped_fills_jsonl,
    write_trades_jsonl,
)
from kabu.backtest.trade import Trade
from kabu.run_metadata_io import write_run_metadata_json
from kabu.run_paths import build_run_paths
from kabu.stats.loaders import load_run_inputs
from kabu.trace_io import write_traces_jsonl

from tests.backtest._fixtures import make_run_metadata
from tests.stats._fixtures import build_run, make_traces


JST = timezone(timedelta(hours=9))


def _make_trade(
    *,
    run_id: str,
    trade_id: str,
    symbol: str,
    entry_offset_days: int,
    net_pnl_jpy: float,
    trace_jsonl_path: str,
    fee_jpy: float = 100.0,
    slippage_jpy: float = 50.0,
) -> Trade:
    base = datetime(2024, 4, 1, 15, 0, tzinfo=JST)
    entry = base + timedelta(days=entry_offset_days)
    exit_ = entry + timedelta(days=4)
    return Trade(
        trade_id=trade_id,
        run_id=run_id,
        symbol=symbol,
        side="long",
        quantity=100,
        entry_decision_ts=entry,
        entry_fill_ts=entry + timedelta(days=1),
        entry_price=1000.0,
        entry_trace_key=f"{symbol}@{entry.isoformat()}",
        trace_jsonl_path=trace_jsonl_path,
        fee_jpy=fee_jpy,
        slippage_jpy=slippage_jpy,
        exit_decision_ts=exit_,
        exit_fill_ts=exit_ + timedelta(days=1),
        exit_price=1000.0 + (net_pnl_jpy + fee_jpy) / 100,
        exit_trace_key=f"{symbol}@{exit_.isoformat()}",
        exit_reason="scripted_exit",
        gross_pnl_jpy=net_pnl_jpy + fee_jpy,
        net_pnl_jpy=net_pnl_jpy,
    )


def _build_run_with_trades(
    tmp_path: Path,
    *,
    run_id: str,
    trades: list[Trade],
    skipped: list[SkippedFill] | None = None,
    n_traces: int = 35,
):
    paths = build_run_paths(tmp_path, run_id=run_id)
    paths.ensure_run_dir()

    metadata = make_run_metadata(run_id=run_id)
    write_run_metadata_json(paths.run_metadata_json, metadata)

    traces = make_traces(run_id=run_id, n=n_traces)
    write_traces_jsonl(paths.trace_raw_jsonl, traces)
    write_traces_jsonl(paths.trace_joined_jsonl, traces)

    write_trades_jsonl(paths.trades_jsonl, trades)
    write_skipped_fills_jsonl(paths.skipped_fills_jsonl, skipped or [])

    from kabu.backtest.engine import BacktestResult
    result = BacktestResult(
        run_id=run_id,
        trades=tuple(trades),
        closing_positions=(),
        skipped=tuple(skipped or []),
        initial_cash_jpy=10_000_000.0,
        final_cash_jpy=10_000_000.0
        + sum(t.net_pnl_jpy or 0 for t in trades),
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


# --- Required tests ---------------------------------------------------------


def test_attribution_symbol_pnl(tmp_path):
    run_id = "r_attr_sym"
    paths = build_run(tmp_path, run_id=run_id)
    # The fixture's traces include symbols 7203 and 6758. We add one trade
    # per symbol with distinct PnL.
    trades = [
        _make_trade(
            run_id=run_id,
            trade_id="t1",
            symbol="7203",
            entry_offset_days=1,
            net_pnl_jpy=500.0,
            trace_jsonl_path=str(paths.trace_raw_jsonl),
        ),
        _make_trade(
            run_id=run_id,
            trade_id="t2",
            symbol="6758",
            entry_offset_days=2,
            net_pnl_jpy=300.0,
            trace_jsonl_path=str(paths.trace_raw_jsonl),
        ),
    ]
    write_trades_jsonl(paths.trades_jsonl, trades)
    inp = load_run_inputs(paths)
    overall = build_overall_totals(inp)
    axes = build_axes(inp, AttributionConfig(minimum_n=30), overall)
    sym_axis = next(a for a in axes if a.axis == "symbol")
    rows_by_key = {r.bucket_key: r for r in sym_axis.rows}
    assert rows_by_key["7203"].total_net_pnl_jpy == pytest.approx(500.0)
    assert rows_by_key["6758"].total_net_pnl_jpy == pytest.approx(300.0)
    assert rows_by_key["7203"].contribution_pct == pytest.approx(500 / 800 * 100)
    assert rows_by_key["6758"].contribution_pct == pytest.approx(300 / 800 * 100)


def test_attribution_period_year_month(tmp_path):
    run_id = "r_attr_period"
    # Make trades spanning April + May + June 2024.
    paths = build_run(tmp_path, run_id=run_id)
    trades = [
        _make_trade(
            run_id=run_id,
            trade_id=f"t{i}",
            symbol="7203" if i % 2 == 0 else "6758",
            entry_offset_days=offset,
            net_pnl_jpy=net,
            trace_jsonl_path=str(paths.trace_raw_jsonl),
        )
        for i, (offset, net) in enumerate([(1, 200), (35, -100), (65, 400)])
    ]
    write_trades_jsonl(paths.trades_jsonl, trades)
    inp = load_run_inputs(paths)
    overall = build_overall_totals(inp)
    axes = build_axes(inp, AttributionConfig(minimum_n=30), overall)

    year_axis = next(a for a in axes if a.axis == "year")
    quarter_axis = next(a for a in axes if a.axis == "quarter")
    month_axis = next(a for a in axes if a.axis == "month")

    year_keys = {r.bucket_key for r in year_axis.rows}
    quarter_keys = {r.bucket_key for r in quarter_axis.rows}
    month_keys = {r.bucket_key for r in month_axis.rows}
    assert "2024" in year_keys
    assert any(k.startswith("2024-Q") for k in quarter_keys)
    assert "2024-04" in month_keys or "2024-05" in month_keys or "2024-06" in month_keys


def test_attribution_sector_unknown_when_missing(tmp_path):
    run_id = "r_attr_sec"
    paths = build_run(tmp_path, run_id=run_id)
    # Add a trade for a symbol that doesn't appear in the trace fixture.
    trades = [
        _make_trade(
            run_id=run_id,
            trade_id="t_unknown",
            symbol="9999",  # not in the trace fixture
            entry_offset_days=3,
            net_pnl_jpy=100.0,
            trace_jsonl_path=str(paths.trace_raw_jsonl),
        ),
    ]
    write_trades_jsonl(paths.trades_jsonl, trades)
    inp = load_run_inputs(paths)
    overall = build_overall_totals(inp)
    axes = build_axes(inp, AttributionConfig(minimum_n=30), overall)
    sec_axis = next(a for a in axes if a.axis == "sector")
    rows_by_key = {r.bucket_key: r for r in sec_axis.rows}
    assert "unknown" in rows_by_key
    assert rows_by_key["unknown"].trade_count >= 1
    assert "unknown_sector" in rows_by_key["unknown"].warnings


def test_attribution_rule_id(tmp_path):
    paths = build_run(tmp_path, run_id="r_attr_rule")
    inp = load_run_inputs(paths)
    overall = build_overall_totals(inp)
    axes = build_axes(inp, AttributionConfig(minimum_n=30), overall)
    rule_id_axis = next(a for a in axes if a.axis == "rule_id")
    assert rule_id_axis.rows
    # Fixture uses "trace_mvp_observe_only" everywhere.
    assert any(r.bucket_key == "trace_mvp_observe_only" for r in rule_id_axis.rows)
    rule_version_axis = next(a for a in axes if a.axis == "rule_version")
    assert any(r.bucket_key == "0.1.0" for r in rule_version_axis.rows)


def test_attribution_skip_reason(tmp_path):
    paths = build_run(tmp_path, run_id="r_attr_skip")
    inp = load_run_inputs(paths)
    overall = build_overall_totals(inp)
    axes = build_axes(inp, AttributionConfig(minimum_n=30), overall)
    skip_axis = next(a for a in axes if a.axis == "skip_reason")
    rows_by_key = {r.bucket_key: r for r in skip_axis.rows}
    # Fixture has 2 halted + 1 not_long.
    assert rows_by_key["halted"].skipped_count == 2
    assert rows_by_key["not_long"].skipped_count == 1


def test_contribution_pct_handles_zero_total(tmp_path):
    """If total_net_pnl_jpy sums to 0, contribution_pct is None."""
    run_id = "r_attr_zero"
    paths = build_run(tmp_path, run_id=run_id)
    # Two trades summing exactly to 0.
    trades = [
        _make_trade(
            run_id=run_id,
            trade_id="t1",
            symbol="7203",
            entry_offset_days=1,
            net_pnl_jpy=500.0,
            trace_jsonl_path=str(paths.trace_raw_jsonl),
        ),
        _make_trade(
            run_id=run_id,
            trade_id="t2",
            symbol="6758",
            entry_offset_days=2,
            net_pnl_jpy=-500.0,
            trace_jsonl_path=str(paths.trace_raw_jsonl),
        ),
    ]
    write_trades_jsonl(paths.trades_jsonl, trades)
    inp = load_run_inputs(paths)
    overall = build_overall_totals(inp)
    assert overall.total_net_pnl_jpy == pytest.approx(0.0)
    axes = build_axes(inp, AttributionConfig(minimum_n=30), overall)
    sym_axis = next(a for a in axes if a.axis == "symbol")
    for row in sym_axis.rows:
        assert row.contribution_pct is None
