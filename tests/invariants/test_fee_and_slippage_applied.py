"""Invariant: fee_bps / fee_fixed_jpy / slippage_bps reflect into PnL.

Policy: BACKTEST_CONTRACT.md S0 D-7 / D-8 / S3.
"""

from __future__ import annotations

import pytest

from kabu.backtest import ScriptedDecision, run_backtest
from kabu.backtest.fill import (
    compute_fee,
    compute_long_entry_fill_price,
    compute_long_exit_fill_price,
)
from kabu.decision_trace_build import CostAssumptions

from tests.backtest._fixtures import make_bars


def _round_trip(cost: CostAssumptions, tmp_path):
    bars = make_bars(10)
    decisions = [
        ScriptedDecision(bar_ts=bars[1].bar_ts, action="enter_long"),
        ScriptedDecision(bar_ts=bars[5].bar_ts, action="exit_long"),
    ]
    result = run_backtest(
        bars=bars,
        decisions=decisions,
        cost=cost,
        run_id="r1",
        trace_jsonl_path=tmp_path / "trace_raw.jsonl",
    )
    return result, bars


def test_higher_slippage_reduces_pnl(tmp_path):
    low = CostAssumptions(slippage_bps=0.0, fee_bps=0.0, fee_fixed_jpy=None)
    high = CostAssumptions(slippage_bps=50.0, fee_bps=0.0, fee_fixed_jpy=None)
    r_low, _ = _round_trip(low, tmp_path / "a")
    r_high, _ = _round_trip(high, tmp_path / "b")
    assert r_low.trades[0].net_pnl_jpy is not None
    assert r_high.trades[0].net_pnl_jpy is not None
    assert r_high.trades[0].net_pnl_jpy < r_low.trades[0].net_pnl_jpy


def test_higher_fee_reduces_pnl(tmp_path):
    no_fee = CostAssumptions(slippage_bps=0.0, fee_bps=0.0, fee_fixed_jpy=None)
    with_fee = CostAssumptions(slippage_bps=0.0, fee_bps=20.0, fee_fixed_jpy=None)
    r_no, _ = _round_trip(no_fee, tmp_path / "a")
    r_yes, _ = _round_trip(with_fee, tmp_path / "b")
    assert r_yes.trades[0].net_pnl_jpy < r_no.trades[0].net_pnl_jpy


def test_fixed_fee_reduces_pnl(tmp_path):
    no_fix = CostAssumptions(slippage_bps=0.0, fee_bps=0.0, fee_fixed_jpy=None)
    with_fix = CostAssumptions(slippage_bps=0.0, fee_bps=0.0, fee_fixed_jpy=500.0)
    r_no, _ = _round_trip(no_fix, tmp_path / "a")
    r_yes, _ = _round_trip(with_fix, tmp_path / "b")
    # Two fills (entry + exit) -> two fixed fees of 500 = -1000 JPY total.
    expected_diff = 2 * 500.0
    assert r_no.trades[0].net_pnl_jpy - r_yes.trades[0].net_pnl_jpy == pytest.approx(expected_diff)


def test_pnl_components_match_fill_helpers(tmp_path):
    cost = CostAssumptions(slippage_bps=10.0, fee_bps=10.0, fee_fixed_jpy=None)
    result, bars = _round_trip(cost, tmp_path)
    trade = result.trades[0]
    expected_entry = compute_long_entry_fill_price(bars[2].open, cost.slippage_bps)
    expected_exit = compute_long_exit_fill_price(bars[6].open, cost.slippage_bps)
    qty = trade.quantity
    expected_gross = (expected_exit - expected_entry) * qty
    expected_entry_fee = compute_fee(expected_entry * qty, cost.fee_bps, cost.fee_fixed_jpy)
    expected_exit_fee = compute_fee(expected_exit * qty, cost.fee_bps, cost.fee_fixed_jpy)
    expected_net = expected_gross - (expected_entry_fee + expected_exit_fee)
    assert trade.gross_pnl_jpy == pytest.approx(expected_gross)
    assert trade.net_pnl_jpy == pytest.approx(expected_net)
