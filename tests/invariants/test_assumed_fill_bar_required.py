"""Invariant: execution_assumption.assumed_fill_bar is required.

Policy: SCHEMA.md S0 D-7.
"""

from __future__ import annotations

import pytest

from kabu.decision_trace import ExecutionAssumptionSlice
from kabu.trace_io import trace_from_dict, trace_to_dict

from tests.decision_trace._fixtures import make_trace


def test_dataclass_rejects_empty_assumed_fill_bar():
    with pytest.raises(ValueError):
        ExecutionAssumptionSlice(
            assumed_fill_bar="",
            latency_bars=1,
            slippage_bps=5.0,
            fee_bps=5.0,
        )


def test_reader_rejects_missing_assumed_fill_bar():
    d = trace_to_dict(make_trace())
    d["slices"]["execution_assumption"].pop("assumed_fill_bar")
    with pytest.raises(ValueError):
        trace_from_dict(d)
