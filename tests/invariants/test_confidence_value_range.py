"""Invariant: decision.confidence in [0.0, 1.0] or None.

Policy: SCHEMA.md S0 D-6 / S5-4.
"""

from __future__ import annotations

import pytest

from kabu.decision_trace import DecisionSlice


def _make(confidence):
    return DecisionSlice(
        final_action="observe_only",
        technical_only_action="not_evaluated",
        rule_id="r",
        rule_version="0.1.0",
        rule_params_hash="0123456789abcdef",
        confidence=confidence,
    )


@pytest.mark.parametrize("v", [0.0, 0.25, 0.5, 1.0])
def test_in_range_is_accepted(v):
    assert _make(v).confidence == pytest.approx(v)


def test_none_is_accepted():
    assert _make(None).confidence is None


@pytest.mark.parametrize("v", [-0.001, -0.5, 1.0001, 2.0])
def test_out_of_range_is_rejected(v):
    with pytest.raises(ValueError):
        _make(v)


def test_non_numeric_is_rejected():
    with pytest.raises(TypeError):
        _make("0.5")  # type: ignore[arg-type]
