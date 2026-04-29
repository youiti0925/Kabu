"""Invariant: decision.rule_id / rule_version / rule_params_hash required.

Policy: SCHEMA.md S0 D-5.
"""

from __future__ import annotations

import pytest

from kabu.decision_trace import DecisionSlice
from kabu.trace_io import trace_from_dict, trace_to_dict

from tests.decision_trace._fixtures import make_trace


@pytest.mark.parametrize(
    "field_name", ["rule_id", "rule_version", "rule_params_hash"]
)
def test_dataclass_rejects_empty(field_name):
    valid = dict(
        final_action="observe_only",
        technical_only_action="not_evaluated",
        rule_id="trace_mvp_observe_only",
        rule_version="0.1.0",
        rule_params_hash="0123456789abcdef",
    )
    valid[field_name] = ""
    with pytest.raises(ValueError):
        DecisionSlice(**valid)


@pytest.mark.parametrize(
    "field_name", ["rule_id", "rule_version", "rule_params_hash"]
)
def test_reader_rejects_missing(field_name):
    d = trace_to_dict(make_trace())
    d["slices"]["decision"].pop(field_name)
    with pytest.raises(ValueError):
        trace_from_dict(d)
