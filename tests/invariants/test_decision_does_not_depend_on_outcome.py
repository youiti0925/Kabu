"""Invariant: the trace builder must not accept future_outcome as input.

Policy: POINT_IN_TIME.md 3-7 / SCHEMA.md S0 D-11.

The builder cannot see future returns by construction: the function
signature does not declare a ``future_outcome`` (or any future-return)
parameter. This test introspects the signature to enforce that.
"""

from __future__ import annotations

import inspect

import pytest

from kabu.decision_trace_build import build_trace

from tests.decision_trace._fixtures import default_cost, make_bars


FORBIDDEN_PARAM_NAMES = {
    "future_outcome",
    "future_return",
    "future_returns",
    "forward_return",
    "forward_return_5d",
    "forward_return_20d",
    "outcome",
    "outcome_label",
}


def test_build_trace_signature_does_not_accept_future_outcome():
    sig = inspect.signature(build_trace)
    for name in sig.parameters:
        assert name.lower() not in FORBIDDEN_PARAM_NAMES, (
            f"build_trace must not accept '{name}'"
        )


def test_passing_future_outcome_keyword_raises_typeerror():
    bars = make_bars(50)
    with pytest.raises(TypeError):
        build_trace(  # type: ignore[call-arg]
            bars=bars,
            symbol="7203",
            market="TSE_PRIME",
            sector="輸送用機器",
            interval="1d",
            universe_snapshot_id="manual_v1",
            data_snapshot_hash="deadbeef",
            run_id="r1",
            commit_sha="c1",
            cost=default_cost(),
            future_outcome={"forward_return_5d": 0.05},
        )


def test_built_trace_has_future_outcome_none():
    bars = make_bars(50)
    trace = build_trace(
        bars=bars,
        symbol="7203",
        market="TSE_PRIME",
        sector="輸送用機器",
        interval="1d",
        universe_snapshot_id="manual_v1",
        data_snapshot_hash="deadbeef",
        run_id="r1",
        commit_sha="c1",
        cost=default_cost(),
    )
    assert trace.slices.future_outcome is None
