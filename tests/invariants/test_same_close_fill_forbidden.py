"""Invariant: same-close fill is forbidden in MVP.

Policy: BACKTEST_CONTRACT.md S0 D-4 / S2-2 / CALENDAR.md S0 D-5.
"""

from __future__ import annotations

import pytest

from kabu.backtest import run_backtest

from tests.backtest._fixtures import DEFAULT_COST, make_bars


def test_assumed_fill_bar_must_be_next_open(tmp_path):
    bars = make_bars(5)
    with pytest.raises(ValueError):
        run_backtest(
            bars=bars,
            decisions=[],
            cost=DEFAULT_COST,
            run_id="r1",
            trace_jsonl_path=tmp_path / "trace_raw.jsonl",
            assumed_fill_bar="same_close",
        )


def test_assumed_fill_bar_other_value_rejected(tmp_path):
    bars = make_bars(5)
    for bad in ("close", "T_close", "intraday", ""):
        with pytest.raises(ValueError):
            run_backtest(
                bars=bars,
                decisions=[],
                cost=DEFAULT_COST,
                run_id="r1",
                trace_jsonl_path=tmp_path / "trace_raw.jsonl",
                assumed_fill_bar=bad,
            )


def test_latency_bars_must_be_one(tmp_path):
    bars = make_bars(5)
    with pytest.raises(ValueError):
        run_backtest(
            bars=bars,
            decisions=[],
            cost=DEFAULT_COST,
            run_id="r1",
            trace_jsonl_path=tmp_path / "trace_raw.jsonl",
            latency_bars=0,
        )
    with pytest.raises(ValueError):
        run_backtest(
            bars=bars,
            decisions=[],
            cost=DEFAULT_COST,
            run_id="r1",
            trace_jsonl_path=tmp_path / "trace_raw.jsonl",
            latency_bars=2,
        )
