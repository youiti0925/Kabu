"""Invariant: future_outcome.forward_return_basis is required when present.

Policy: SCHEMA.md S0 D-10. PR-S2 contract: future_outcome may be ``None``,
in which case no validation triggers.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from kabu.decision_trace import (
    BollingerPoint,
    DecisionSlice,
    ExecutionAssumptionSlice,
    FutureOutcomeSlice,
    LongTermTrendSlice,
    MACDPoint,
    MarketSlice,
    RiskCtxSlice,
    SCHEMA_VERSION,
    TechnicalSlice,
    TraceSlices,
)
from kabu.trace_io import trace_from_dict, trace_to_dict

from tests.decision_trace._fixtures import make_trace


def test_future_outcome_can_be_none():
    trace = make_trace()
    assert trace.slices.future_outcome is None
    d = trace_to_dict(trace)
    rt = trace_from_dict(d)
    assert rt.slices.future_outcome is None


def test_future_outcome_with_basis_is_accepted():
    fo = FutureOutcomeSlice(forward_return_basis="close_to_close")
    assert fo.forward_return_basis == "close_to_close"


def test_future_outcome_dict_without_basis_is_rejected_on_read():
    base = make_trace()
    d = trace_to_dict(base)
    d["slices"]["future_outcome"] = {"forward_return_5d": 0.01}
    with pytest.raises(ValueError):
        trace_from_dict(d)


def test_future_outcome_dict_with_basis_round_trips_through_reader():
    base = make_trace()
    d = trace_to_dict(base)
    d["slices"]["future_outcome"] = {
        "forward_return_basis": "close_to_close",
        "forward_return_5d": 0.012,
    }
    rt = trace_from_dict(d)
    assert rt.slices.future_outcome is not None
    assert rt.slices.future_outcome.forward_return_basis == "close_to_close"
    assert rt.slices.future_outcome.forward_return_5d == pytest.approx(0.012)


def test_future_outcome_end_ts_round_trips_as_aware():
    base = make_trace()
    end = base.bar_ts_available + timedelta(days=5)
    d = trace_to_dict(base)
    d["slices"]["future_outcome"] = {
        "forward_return_basis": "close_to_close",
        "forward_return_end_ts": end.isoformat(),
    }
    rt = trace_from_dict(d)
    assert rt.slices.future_outcome is not None
    assert rt.slices.future_outcome.forward_return_end_ts == end
