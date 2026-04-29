"""Invariants: outcome backfill is separate from raw trace; the decision
builder does not import outcome enrichment.

Policy:
- POINT_IN_TIME.md 3-4 / 3-7
- SCHEMA.md S6 / S7-2
- PR-S3 brief: ``trace_raw`` and ``outcome_backfill`` MUST live in
  different files.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import kabu.decision_trace_build as build_mod
from kabu.outcome import (
    enrich_future_outcomes,
    join_traces_with_outcomes,
    read_outcome_backfill_jsonl,
    write_outcome_backfill_jsonl,
)
from kabu.trace_io import read_traces_jsonl, write_traces_jsonl

from tests.backtest._fixtures import make_bars
from tests.decision_trace._fixtures import make_trace


def test_decision_trace_build_does_not_import_outcome():
    """Source-level structural separation."""
    src = inspect.getsource(build_mod)
    assert "from kabu.outcome" not in src, (
        "decision_trace_build must not import from kabu.outcome"
    )
    assert "import kabu.outcome" not in src, (
        "decision_trace_build must not import from kabu.outcome"
    )
    # Also: build_trace must not have any future_outcome-related parameter.
    sig = inspect.signature(build_mod.build_trace)
    forbidden = {"future_outcome", "outcome", "forward_return"}
    assert not any(name.lower() in forbidden for name in sig.parameters)


def test_backfill_jsonl_path_must_differ_from_trace_raw(tmp_path):
    bars = make_bars(20)
    bars_by_symbol = {bars[0].symbol: bars}
    # Build a trace whose bar_ts matches one of the simulated bars.
    trace = make_trace(
        bar_ts=bars[2].bar_ts,
        bar_ts_close=bars[2].bar_ts,
        bar_ts_available=bars[2].bar_ts_available,
        symbol=bars[0].symbol,
    )
    raw_path = tmp_path / "trace_raw.jsonl"
    backfill_path = tmp_path / "outcome_backfill.jsonl"
    assert raw_path != backfill_path

    write_traces_jsonl(raw_path, [trace])
    records = enrich_future_outcomes([trace], bars_by_symbol, horizon_bars=(1, 5))
    assert len(records) == 1
    write_outcome_backfill_jsonl(backfill_path, records)

    assert raw_path.exists()
    assert backfill_path.exists()
    assert raw_path.read_text() != backfill_path.read_text()
    # The raw trace file must not contain any outcome data.
    assert "forward_return_basis" not in raw_path.read_text() or (
        # The raw trace serializes future_outcome=null; that's fine.
        '"future_outcome": null' in raw_path.read_text()
    )


def test_join_populates_future_outcome_without_mutating_originals(tmp_path):
    bars = make_bars(20)
    bars_by_symbol = {bars[0].symbol: bars}
    trace = make_trace(
        bar_ts=bars[2].bar_ts,
        bar_ts_close=bars[2].bar_ts,
        bar_ts_available=bars[2].bar_ts_available,
        symbol=bars[0].symbol,
    )
    assert trace.slices.future_outcome is None
    records = enrich_future_outcomes([trace], bars_by_symbol, horizon_bars=(1, 5))
    joined = join_traces_with_outcomes([trace], records)
    assert joined[0] is not trace  # new instance
    assert trace.slices.future_outcome is None  # original untouched
    assert joined[0].slices.future_outcome is not None
    assert joined[0].slices.future_outcome.forward_return_basis == "close_to_close"


def test_outcome_backfill_jsonl_round_trip(tmp_path):
    bars = make_bars(30)  # need >= 2 + max_horizon (20) + 1 bars
    bars_by_symbol = {bars[0].symbol: bars}
    trace = make_trace(
        bar_ts=bars[2].bar_ts,
        bar_ts_close=bars[2].bar_ts,
        bar_ts_available=bars[2].bar_ts_available,
        symbol=bars[0].symbol,
    )
    path = tmp_path / "outcome_backfill.jsonl"
    records = enrich_future_outcomes(
        [trace], bars_by_symbol, horizon_bars=(1, 5, 20)
    )
    n = write_outcome_backfill_jsonl(path, records)
    assert n == 1
    loaded = list(read_outcome_backfill_jsonl(path))
    assert len(loaded) == 1
    rec = loaded[0]
    assert rec.trace_key.run_id == trace.run_id
    assert rec.trace_key.symbol == trace.symbol
    assert rec.trace_key.bar_ts == trace.bar_ts
    assert rec.outcome.forward_return_basis == "close_to_close"
    assert rec.outcome.forward_return_end_ts is not None


def test_enrich_skips_traces_without_enough_future_bars():
    bars = make_bars(5)
    bars_by_symbol = {bars[0].symbol: bars}
    # Use the LAST bar's bar_ts -- there is no future for max horizon.
    trace = make_trace(
        bar_ts=bars[-1].bar_ts,
        bar_ts_close=bars[-1].bar_ts,
        bar_ts_available=bars[-1].bar_ts_available,
        symbol=bars[0].symbol,
    )
    records = enrich_future_outcomes([trace], bars_by_symbol, horizon_bars=(20,))
    assert records == []
