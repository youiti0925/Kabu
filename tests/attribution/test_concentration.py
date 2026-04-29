"""Concentration warning tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from kabu.attribution import (
    AttributionConfig,
    build_attribution_report,
    build_axes,
    build_overall_totals,
    detect_concentration_warnings,
)
from kabu.backtest.io import write_trades_jsonl
from kabu.backtest.trade import Trade
from kabu.stats.loaders import load_run_inputs

from tests.attribution.test_aggregate import _make_trade
from tests.stats._fixtures import build_run


def test_concentration_warning_for_single_symbol(tmp_path):
    """One symbol carrying > 50% of trades AND of net_pnl triggers two warnings."""
    run_id = "r_attr_conc"
    paths = build_run(tmp_path, run_id=run_id)
    # Three trades: two on 7203 (large positive PnL), one on 6758 (small).
    trades = [
        _make_trade(
            run_id=run_id, trade_id="t1", symbol="7203",
            entry_offset_days=1, net_pnl_jpy=900.0,
            trace_jsonl_path=str(paths.trace_raw_jsonl),
        ),
        _make_trade(
            run_id=run_id, trade_id="t2", symbol="7203",
            entry_offset_days=2, net_pnl_jpy=900.0,
            trace_jsonl_path=str(paths.trace_raw_jsonl),
        ),
        _make_trade(
            run_id=run_id, trade_id="t3", symbol="6758",
            entry_offset_days=3, net_pnl_jpy=100.0,
            trace_jsonl_path=str(paths.trace_raw_jsonl),
        ),
    ]
    write_trades_jsonl(paths.trades_jsonl, trades)
    inp = load_run_inputs(paths)
    overall = build_overall_totals(inp)
    axes = build_axes(inp, AttributionConfig(minimum_n=30), overall)
    warnings = detect_concentration_warnings(axes, overall, high_concentration_pct=50.0)

    severities = {(w.axis, w.bucket_key, w.severity) for w in warnings}
    assert ("symbol", "7203", "high_pnl_concentration") in severities
    assert ("symbol", "7203", "high_trade_count_concentration") in severities


def test_concentration_no_warning_when_balanced(tmp_path):
    run_id = "r_attr_balanced"
    paths = build_run(tmp_path, run_id=run_id)
    # Four roughly-equal trades, none above 50%.
    trades = [
        _make_trade(
            run_id=run_id, trade_id=f"t{i}", symbol="7203" if i % 2 == 0 else "6758",
            entry_offset_days=i, net_pnl_jpy=200.0,
            trace_jsonl_path=str(paths.trace_raw_jsonl),
        )
        for i in range(4)
    ]
    write_trades_jsonl(paths.trades_jsonl, trades)
    inp = load_run_inputs(paths)
    overall = build_overall_totals(inp)
    axes = build_axes(inp, AttributionConfig(minimum_n=30), overall)
    warnings = detect_concentration_warnings(axes, overall, high_concentration_pct=50.0)
    severities = {(w.axis, w.bucket_key, w.severity) for w in warnings}
    # Symbol-level pnl is 50/50; > 50% is required, so no warning.
    assert ("symbol", "7203", "high_pnl_concentration") not in severities
    assert ("symbol", "6758", "high_pnl_concentration") not in severities


def test_no_closed_trades_warning(tmp_path):
    """When there is a Trade record but exit_price is None on all of them."""
    run_id = "r_attr_open"
    paths = build_run(tmp_path, run_id=run_id)
    base = datetime(2024, 4, 1, 15, 0, tzinfo=timezone(timedelta(hours=9)))
    open_trade = Trade(
        trade_id="t_open",
        run_id=run_id,
        symbol="7203",
        side="long",
        quantity=100,
        entry_decision_ts=base,
        entry_fill_ts=base + timedelta(days=1),
        entry_price=1000.0,
        entry_trace_key="7203@T",
        trace_jsonl_path=str(paths.trace_raw_jsonl),
        fee_jpy=100.0,
        slippage_jpy=50.0,
    )
    write_trades_jsonl(paths.trades_jsonl, [open_trade])
    inp = load_run_inputs(paths)
    overall = build_overall_totals(inp)
    axes = build_axes(inp, AttributionConfig(minimum_n=30), overall)
    warnings = detect_concentration_warnings(axes, overall, high_concentration_pct=50.0)
    severities = {w.severity for w in warnings}
    assert "no_closed_trades" in severities


def test_low_sample_warning_attached_to_row(tmp_path):
    """Default minimum_n is 30; symbol bucket with fewer entries gets low_sample."""
    paths = build_run(tmp_path, run_id="r_attr_low")
    inp = load_run_inputs(paths)
    overall = build_overall_totals(inp)
    axes = build_axes(inp, AttributionConfig(minimum_n=30), overall)
    sym_axis = next(a for a in axes if a.axis == "symbol")
    # 35 traces split 18/17 between two symbols; both buckets are < 30.
    for row in sym_axis.rows:
        assert row.low_sample is True
        assert "low_sample" in row.warnings
