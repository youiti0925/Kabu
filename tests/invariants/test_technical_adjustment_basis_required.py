"""Invariant: technical.adjustment_basis is required.

Policy: SCHEMA.md S0 D-9 / S4-2.
"""

from __future__ import annotations

import pytest

from kabu.decision_trace import TechnicalSlice
from kabu.trace_io import trace_from_dict, trace_to_dict

from tests.decision_trace._fixtures import make_trace


def test_dataclass_rejects_empty_adjustment_basis():
    with pytest.raises(ValueError):
        TechnicalSlice(adjustment_basis="")


def test_reader_rejects_missing_adjustment_basis():
    d = trace_to_dict(make_trace())
    d["slices"]["technical"].pop("adjustment_basis")
    with pytest.raises(ValueError):
        trace_from_dict(d)
