"""Invariant: execution_assumption.latency_bars is required.

Policy: SCHEMA.md S0 D-8.
"""

from __future__ import annotations

import pytest

from kabu.decision_trace import ExecutionAssumptionSlice
from kabu.trace_io import trace_from_dict, trace_to_dict

from tests.decision_trace._fixtures import make_trace


def test_dataclass_rejects_non_int_latency():
    with pytest.raises(TypeError):
        ExecutionAssumptionSlice(
            assumed_fill_bar="next_open",
            latency_bars=1.0,  # type: ignore[arg-type]
            slippage_bps=5.0,
            fee_bps=5.0,
        )


def test_dataclass_rejects_negative_latency():
    with pytest.raises(ValueError):
        ExecutionAssumptionSlice(
            assumed_fill_bar="next_open",
            latency_bars=-1,
            slippage_bps=5.0,
            fee_bps=5.0,
        )


def test_reader_rejects_missing_latency_bars():
    d = trace_to_dict(make_trace())
    d["slices"]["execution_assumption"].pop("latency_bars")
    with pytest.raises(ValueError):
        trace_from_dict(d)
