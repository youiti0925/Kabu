"""Engine-level happy paths and basic integration."""

from __future__ import annotations

import pytest

from kabu.backtest import (
    BacktestResult,
    ScriptedDecision,
    run_backtest,
)
from kabu.backtest.engine import decisions_from_traces

from tests.backtest._fixtures import DEFAULT_COST, make_bars
from tests.decision_trace._fixtures import make_trace


def test_smoke_no_decisions_returns_no_trades(tmp_path):
    bars = make_bars(20)
    result = run_backtest(
        bars=bars,
        decisions=[],
        cost=DEFAULT_COST,
        run_id="r1",
        trace_jsonl_path=tmp_path / "trace_raw.jsonl",
    )
    assert isinstance(result, BacktestResult)
    assert result.trades == ()
    assert result.skipped == ()
    assert result.closing_positions == ()


def test_enter_long_then_exit_long_round_trip(tmp_path):
    bars = make_bars(10)
    decisions = [
        ScriptedDecision(bar_ts=bars[2].bar_ts, action="enter_long"),
        ScriptedDecision(bar_ts=bars[5].bar_ts, action="exit_long"),
    ]
    result = run_backtest(
        bars=bars,
        decisions=decisions,
        cost=DEFAULT_COST,
        run_id="r2",
        trace_jsonl_path=tmp_path / "trace_raw.jsonl",
    )
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_decision_ts == bars[2].bar_ts
    assert trade.entry_fill_ts == bars[3].bar_ts
    assert trade.exit_decision_ts == bars[5].bar_ts
    assert trade.exit_fill_ts == bars[6].bar_ts
    assert trade.gross_pnl_jpy is not None
    assert trade.net_pnl_jpy is not None
    assert result.closing_positions == ()


def test_redundant_enter_is_skipped(tmp_path):
    bars = make_bars(10)
    decisions = [
        ScriptedDecision(bar_ts=bars[1].bar_ts, action="enter_long"),
        ScriptedDecision(bar_ts=bars[3].bar_ts, action="enter_long"),
    ]
    result = run_backtest(
        bars=bars,
        decisions=decisions,
        cost=DEFAULT_COST,
        run_id="r3",
        trace_jsonl_path=tmp_path / "trace_raw.jsonl",
    )
    assert len(result.trades) == 1
    assert any(s.reason == "already_long" for s in result.skipped)


def test_exit_without_position_is_skipped(tmp_path):
    bars = make_bars(10)
    decisions = [
        ScriptedDecision(bar_ts=bars[1].bar_ts, action="exit_long"),
    ]
    result = run_backtest(
        bars=bars,
        decisions=decisions,
        cost=DEFAULT_COST,
        run_id="r4",
        trace_jsonl_path=tmp_path / "trace_raw.jsonl",
    )
    assert result.trades == ()
    assert any(s.reason == "not_long" for s in result.skipped)


def test_open_position_is_marked_to_market_at_last_close(tmp_path):
    bars = make_bars(10)
    decisions = [
        ScriptedDecision(bar_ts=bars[2].bar_ts, action="enter_long"),
    ]
    result = run_backtest(
        bars=bars,
        decisions=decisions,
        cost=DEFAULT_COST,
        run_id="r5",
        trace_jsonl_path=tmp_path / "trace_raw.jsonl",
    )
    assert len(result.trades) == 1
    assert len(result.closing_positions) == 1
    pos = result.closing_positions[0]
    assert pos.symbol == "7203"
    assert pos.quantity > 0


def test_decision_at_last_bar_has_no_next_bar(tmp_path):
    bars = make_bars(5)
    decisions = [
        ScriptedDecision(bar_ts=bars[-1].bar_ts, action="enter_long"),
    ]
    result = run_backtest(
        bars=bars,
        decisions=decisions,
        cost=DEFAULT_COST,
        run_id="r6",
        trace_jsonl_path=tmp_path / "trace_raw.jsonl",
    )
    assert result.trades == ()
    assert any(s.reason == "no_next_bar" for s in result.skipped)


def test_unknown_action_is_rejected_by_dataclass():
    bars = make_bars(5)
    with pytest.raises(ValueError):
        ScriptedDecision(bar_ts=bars[0].bar_ts, action="rocket_to_the_moon")


def test_decisions_from_traces_with_observe_only_makes_no_trades(tmp_path):
    """PR-S2 traces emit only observe_only -> engine does no trading."""
    bars = make_bars(20)
    traces = [make_trace()]  # default decision is observe_only
    decisions = decisions_from_traces(traces)
    # observe_only is treated as noop, so no trades.
    result = run_backtest(
        bars=bars,
        decisions=decisions,
        cost=DEFAULT_COST,
        run_id="r7",
        trace_jsonl_path=tmp_path / "trace_raw.jsonl",
    )
    assert result.trades == ()


def test_run_id_required(tmp_path):
    bars = make_bars(5)
    with pytest.raises(ValueError):
        run_backtest(
            bars=bars,
            decisions=[],
            cost=DEFAULT_COST,
            run_id="",
            trace_jsonl_path=tmp_path / "trace_raw.jsonl",
        )
