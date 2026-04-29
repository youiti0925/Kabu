"""Invariant: stop-high / stop-low / special-quote / halted bars do not fill.

Policy: BACKTEST_CONTRACT.md S0 D-12 / S4-5 / S4-6.

PR-S3 uses bar-level flags (is_halted / is_special_quote /
is_circuit_breaker) as a conservative proxy. Precise stop-high/low tables
are deferred to a later PR.
"""

from __future__ import annotations

import pytest

from kabu.backtest import ScriptedDecision, run_backtest
from kabu.backtest.checks import is_unfillable

from tests.backtest._fixtures import DEFAULT_COST, make_bars, replace_bar


def _engine_skip_reason(bars, decision_idx, tmp_path):
    decisions = [
        ScriptedDecision(bar_ts=bars[decision_idx].bar_ts, action="enter_long")
    ]
    result = run_backtest(
        bars=bars,
        decisions=decisions,
        cost=DEFAULT_COST,
        run_id="r1",
        trace_jsonl_path=tmp_path / "trace_raw.jsonl",
    )
    assert result.trades == ()
    assert len(result.skipped) == 1
    return result.skipped[0].reason


def test_halted_next_bar_blocks_fill(tmp_path):
    bars = make_bars(5)
    bars[2] = replace_bar(bars[2], is_halted=True)
    reason = _engine_skip_reason(bars, decision_idx=1, tmp_path=tmp_path)
    assert reason == "halted"


def test_special_quote_next_bar_blocks_fill(tmp_path):
    bars = make_bars(5)
    bars[2] = replace_bar(bars[2], is_special_quote=True)
    reason = _engine_skip_reason(bars, decision_idx=1, tmp_path=tmp_path)
    assert reason == "special_quote"


def test_circuit_breaker_next_bar_blocks_fill(tmp_path):
    bars = make_bars(5)
    bars[2] = replace_bar(bars[2], is_circuit_breaker=True)
    reason = _engine_skip_reason(bars, decision_idx=1, tmp_path=tmp_path)
    assert reason == "circuit_breaker"


def test_is_unfillable_returns_none_for_normal_bar():
    bars = make_bars(3)
    assert is_unfillable(bars[0]) is None


def test_is_unfillable_priority_order():
    """When multiple flags are set, the first matched reason wins."""
    bars = make_bars(1)
    b = replace_bar(bars[0], is_halted=True, is_special_quote=True)
    assert is_unfillable(b) == "halted"
