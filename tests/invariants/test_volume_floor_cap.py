"""Invariant: volume / turnover floors block the fill in MVP.

Policy: BACKTEST_CONTRACT.md S0 D-11 / S4-3 / S4-4.

PR-S3: ``volume_floor`` and ``turnover_floor`` cause the fill to be
SKIPPED (not split). Splitting is a later PR.
"""

from __future__ import annotations

import pytest

from kabu.backtest import ScriptedDecision, run_backtest

from tests.backtest._fixtures import DEFAULT_COST, make_bars, replace_bar


def test_zero_volume_blocks_fill(tmp_path):
    bars = make_bars(5)
    bars[2] = replace_bar(bars[2], volume=0, turnover=0.0)
    decisions = [ScriptedDecision(bar_ts=bars[1].bar_ts, action="enter_long")]
    result = run_backtest(
        bars=bars,
        decisions=decisions,
        cost=DEFAULT_COST,
        run_id="r1",
        trace_jsonl_path=tmp_path / "trace_raw.jsonl",
    )
    assert result.trades == ()
    assert any(s.reason == "volume_zero" for s in result.skipped)


def test_volume_floor_blocks_fill(tmp_path):
    bars = make_bars(5)
    bars[2] = replace_bar(bars[2], volume=10, turnover=10.0 * bars[2].close)
    decisions = [ScriptedDecision(bar_ts=bars[1].bar_ts, action="enter_long")]
    result = run_backtest(
        bars=bars,
        decisions=decisions,
        cost=DEFAULT_COST,
        run_id="r1",
        trace_jsonl_path=tmp_path / "trace_raw.jsonl",
        min_volume=10_000,
    )
    assert result.trades == ()
    assert any(s.reason == "volume_floor" for s in result.skipped)


def test_turnover_floor_blocks_fill(tmp_path):
    bars = make_bars(5)
    bars[2] = replace_bar(bars[2], turnover=100.0)  # very small JPY
    decisions = [ScriptedDecision(bar_ts=bars[1].bar_ts, action="enter_long")]
    result = run_backtest(
        bars=bars,
        decisions=decisions,
        cost=DEFAULT_COST,
        run_id="r1",
        trace_jsonl_path=tmp_path / "trace_raw.jsonl",
        min_turnover_jpy=1_000_000.0,
    )
    assert result.trades == ()
    assert any(s.reason == "turnover_floor" for s in result.skipped)


def test_below_lot_size_blocks_fill(tmp_path):
    """If target_jpy_per_trade rounds to 0 lots, the fill is skipped."""
    bars = make_bars(5)
    decisions = [ScriptedDecision(bar_ts=bars[1].bar_ts, action="enter_long")]
    # Tiny budget vs raw open ~1000 yen => 0 shares at lot_size=100.
    result = run_backtest(
        bars=bars,
        decisions=decisions,
        cost=DEFAULT_COST,
        run_id="r1",
        trace_jsonl_path=tmp_path / "trace_raw.jsonl",
        target_jpy_per_trade=10.0,
        lot_size=100,
    )
    assert result.trades == ()
    assert any(s.reason == "below_lot_size" for s in result.skipped)
