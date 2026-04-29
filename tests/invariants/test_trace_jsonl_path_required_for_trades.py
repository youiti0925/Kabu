"""Invariant: every Trade carries a non-empty trace_jsonl_path.

Policy: BACKTEST_CONTRACT.md S7 / SCHEMA.md S6.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from kabu.backtest import ScriptedDecision, Trade, run_backtest

from tests.backtest._fixtures import DEFAULT_COST, make_bars


def _trade_kwargs(**overrides):
    bars = make_bars(2)
    base = dict(
        trade_id="t1",
        run_id="r1",
        symbol="7203",
        side="long",
        quantity=100,
        entry_decision_ts=bars[0].bar_ts,
        entry_fill_ts=bars[1].bar_ts,
        entry_price=1000.0,
        entry_trace_key="7203@T",
        trace_jsonl_path="/tmp/trace_raw.jsonl",
    )
    base.update(overrides)
    return base


def test_dataclass_rejects_empty_trace_jsonl_path():
    with pytest.raises(ValueError):
        Trade(**_trade_kwargs(trace_jsonl_path=""))


def test_dataclass_accepts_valid_trace_jsonl_path():
    trade = Trade(**_trade_kwargs())
    assert trade.trace_jsonl_path == "/tmp/trace_raw.jsonl"


def test_engine_stamps_trace_jsonl_path_on_every_trade(tmp_path):
    bars = make_bars(10)
    path = tmp_path / "trace_raw.jsonl"
    decisions = [
        ScriptedDecision(bar_ts=bars[1].bar_ts, action="enter_long"),
        ScriptedDecision(bar_ts=bars[5].bar_ts, action="exit_long"),
    ]
    result = run_backtest(
        bars=bars,
        decisions=decisions,
        cost=DEFAULT_COST,
        run_id="r1",
        trace_jsonl_path=path,
    )
    assert len(result.trades) == 1
    for t in result.trades:
        assert t.trace_jsonl_path == str(path)
        assert t.trace_jsonl_path  # non-empty


def test_engine_rejects_empty_trace_jsonl_path():
    bars = make_bars(5)
    with pytest.raises(ValueError):
        run_backtest(
            bars=bars,
            decisions=[],
            cost=DEFAULT_COST,
            run_id="r1",
            trace_jsonl_path="",
        )
