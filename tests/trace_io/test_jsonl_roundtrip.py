"""JSONL writer / reader roundtrip tests for kabu.trace.v1.

Policy: SCHEMA.md S6.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from kabu.decision_trace import (
    FutureOutcomeSlice,
    SCHEMA_VERSION,
    TraceSlices,
)
from kabu.trace_io import (
    read_traces_jsonl,
    trace_from_dict,
    trace_to_dict,
    write_traces_jsonl,
)

from tests.decision_trace._fixtures import make_trace


def test_single_trace_roundtrip(tmp_path):
    path = tmp_path / "trace.jsonl"
    original = make_trace()
    written = write_traces_jsonl(path, [original])
    assert written == 1
    loaded = list(read_traces_jsonl(path))
    assert len(loaded) == 1
    rt = loaded[0]
    assert rt.schema_version == SCHEMA_VERSION
    assert rt.symbol == original.symbol
    assert rt.bar_ts == original.bar_ts
    assert rt.bar_ts_close == original.bar_ts_close
    assert rt.bar_ts_available == original.bar_ts_available
    assert rt.slices.decision.rule_id == original.slices.decision.rule_id
    assert rt.slices.decision.rule_version == original.slices.decision.rule_version
    assert rt.slices.decision.rule_params_hash == original.slices.decision.rule_params_hash
    assert rt.slices.technical.adjustment_basis == original.slices.technical.adjustment_basis
    assert rt.slices.execution_assumption.assumed_fill_bar == "next_open"
    assert rt.slices.execution_assumption.latency_bars == 1
    assert rt.slices.future_outcome is None


def test_multiple_traces_roundtrip(tmp_path):
    path = tmp_path / "many.jsonl"
    JST = timezone(timedelta(hours=9))
    traces = []
    for i in range(3):
        bar_ts = datetime(2024, 4, 26 + i, 15, 0, tzinfo=JST)
        traces.append(
            make_trace(
                run_id=f"r{i}",
                bar_ts=bar_ts,
                bar_ts_close=bar_ts,
                bar_ts_available=bar_ts + timedelta(minutes=30),
            )
        )
    written = write_traces_jsonl(path, traces)
    assert written == 3
    loaded = list(read_traces_jsonl(path))
    assert [t.run_id for t in loaded] == ["r0", "r1", "r2"]


def test_blank_lines_are_skipped(tmp_path):
    path = tmp_path / "with_blanks.jsonl"
    write_traces_jsonl(path, [make_trace()])
    # Inject empty lines.
    text = path.read_text(encoding="utf-8")
    path.write_text(f"\n\n{text}\n\n", encoding="utf-8")
    assert len(list(read_traces_jsonl(path))) == 1


def test_future_outcome_round_trips_when_present(tmp_path):
    path = tmp_path / "with_outcome.jsonl"
    base = make_trace()
    end = base.bar_ts_available + timedelta(days=5)
    fo = FutureOutcomeSlice(
        forward_return_basis="close_to_close",
        forward_return_5d=0.0123,
        forward_return_horizon_bars=(1, 5),
        forward_return_end_ts=end,
    )
    enriched = make_trace()
    enriched_slices = TraceSlices(
        market=enriched.slices.market,
        technical=enriched.slices.technical,
        long_term_trend=enriched.slices.long_term_trend,
        risk_ctx=enriched.slices.risk_ctx,
        decision=enriched.slices.decision,
        execution_assumption=enriched.slices.execution_assumption,
        future_outcome=fo,
    )
    enriched = make_trace(slices=enriched_slices)
    write_traces_jsonl(path, [enriched])
    loaded = list(read_traces_jsonl(path))
    assert len(loaded) == 1
    rt_fo = loaded[0].slices.future_outcome
    assert rt_fo is not None
    assert rt_fo.forward_return_basis == "close_to_close"
    assert rt_fo.forward_return_5d == pytest.approx(0.0123)
    assert rt_fo.forward_return_horizon_bars == (1, 5)
    assert rt_fo.forward_return_end_ts == end


def test_writer_handles_iterators(tmp_path):
    path = tmp_path / "from_gen.jsonl"
    def gen():
        for _ in range(2):
            yield make_trace()
    n = write_traces_jsonl(path, gen())
    assert n == 2


def test_dict_roundtrip_independent_of_io(tmp_path):
    """Even without disk, dict <-> dataclass round trip must be lossless
    for the fields we care about."""
    original = make_trace()
    d = trace_to_dict(original)
    rt = trace_from_dict(d)
    assert rt.schema_version == original.schema_version
    assert rt.symbol == original.symbol
    assert rt.slices.decision.rule_id == original.slices.decision.rule_id
    assert rt.slices.market.close == pytest.approx(original.slices.market.close)
    assert rt.slices.technical.atr14 == pytest.approx(original.slices.technical.atr14)
