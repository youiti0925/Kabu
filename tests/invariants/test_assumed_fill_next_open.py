"""Invariant: T close decision -> T+1 open fill.

Policy: BACKTEST_CONTRACT.md S0 D-3..D-6 / S2-2 / CALENDAR.md S0 D-3..D-5.
"""

from __future__ import annotations

import pytest

from kabu.backtest import ScriptedDecision, run_backtest
from kabu.backtest.fill import compute_long_entry_fill_price

from tests.backtest._fixtures import DEFAULT_COST, make_bars


def test_entry_fill_ts_is_next_bar(tmp_path):
    bars = make_bars(10)
    decisions = [ScriptedDecision(bar_ts=bars[3].bar_ts, action="enter_long")]
    result = run_backtest(
        bars=bars,
        decisions=decisions,
        cost=DEFAULT_COST,
        run_id="r1",
        trace_jsonl_path=tmp_path / "trace_raw.jsonl",
    )
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_decision_ts == bars[3].bar_ts
    assert trade.entry_fill_ts == bars[4].bar_ts
    assert trade.entry_fill_ts != trade.entry_decision_ts  # NOT same close


def test_entry_price_uses_next_bars_raw_open_with_slippage(tmp_path):
    bars = make_bars(10)
    decisions = [ScriptedDecision(bar_ts=bars[3].bar_ts, action="enter_long")]
    result = run_backtest(
        bars=bars,
        decisions=decisions,
        cost=DEFAULT_COST,
        run_id="r1",
        trace_jsonl_path=tmp_path / "trace_raw.jsonl",
    )
    trade = result.trades[0]
    expected = compute_long_entry_fill_price(
        bars[4].open, DEFAULT_COST.slippage_bps
    )
    assert trade.entry_price == pytest.approx(expected)


def test_decision_at_T_does_not_use_T_open_or_T_close(tmp_path):
    """Defensive: ensure the engine never tags the same-day open / close."""
    bars = make_bars(10)
    decisions = [ScriptedDecision(bar_ts=bars[3].bar_ts, action="enter_long")]
    result = run_backtest(
        bars=bars,
        decisions=decisions,
        cost=DEFAULT_COST,
        run_id="r1",
        trace_jsonl_path=tmp_path / "trace_raw.jsonl",
    )
    trade = result.trades[0]
    # The fill price must differ from same-day open/close (with slippage,
    # next-day open is strictly different in our uptrending fixture).
    assert trade.entry_price != pytest.approx(bars[3].open)
    assert trade.entry_price != pytest.approx(bars[3].close)
