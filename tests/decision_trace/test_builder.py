"""Builder unit tests for kabu.decision_trace_build.

These verify that ``build_trace`` produces a valid Trace with placeholder
decision slice (PR-S2: observation, not trading), correct top-level
metadata propagation, and indicator values for the latest bar.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from kabu.decision_trace import (
    ASSUMED_FILL_BAR_NEXT_OPEN,
    DEFAULT_ADJUSTMENT_BASIS,
    DEFAULT_LATENCY_BARS,
    OBSERVE_ONLY_RULE_ID,
    OBSERVE_ONLY_RULE_VERSION,
    SCHEMA_VERSION,
)
from kabu.decision_trace_build import build_trace, hash_rule_params

from tests.decision_trace._fixtures import default_cost, make_bars


def _build(bars=None, **overrides):
    bars = bars if bars is not None else make_bars(250)
    base = dict(
        bars=bars,
        symbol="7203",
        market="TSE_PRIME",
        sector="輸送用機器",
        interval="1d",
        universe_snapshot_id="manual_v1",
        data_snapshot_hash="deadbeef" * 4,
        run_id="run_test_0001",
        commit_sha="abcdef0123456789",
        cost=default_cost(),
    )
    base.update(overrides)
    return build_trace(**base)


def test_build_returns_valid_trace_with_placeholder_decision():
    trace = _build()
    assert trace.schema_version == SCHEMA_VERSION
    assert trace.trace_schema_version == SCHEMA_VERSION
    assert trace.symbol == "7203"
    assert trace.interval == "1d"
    assert trace.slices.decision.final_action == "observe_only"
    assert trace.slices.decision.technical_only_action == "not_evaluated"
    assert trace.slices.decision.rule_id == OBSERVE_ONLY_RULE_ID
    assert trace.slices.decision.rule_version == OBSERVE_ONLY_RULE_VERSION
    assert trace.slices.decision.confidence is None
    assert trace.slices.future_outcome is None


def test_technical_uses_default_adjustment_basis():
    trace = _build()
    assert trace.slices.technical.adjustment_basis == DEFAULT_ADJUSTMENT_BASIS


def test_execution_assumption_uses_mvp_defaults():
    trace = _build()
    ex = trace.slices.execution_assumption
    assert ex.assumed_fill_bar == ASSUMED_FILL_BAR_NEXT_OPEN
    assert ex.latency_bars == DEFAULT_LATENCY_BARS
    assert ex.slippage_bps == 5.0
    assert ex.fee_bps == 5.0


def test_long_term_trend_label_above_sma200_in_uptrend():
    trace = _build()
    assert trace.slices.long_term_trend.trend_label == "above_sma200"
    assert trace.slices.long_term_trend.close_vs_sma200 is not None
    assert trace.slices.long_term_trend.close_vs_sma200 > 0


def test_short_history_yields_unknown_long_term_trend():
    trace = _build(bars=make_bars(50))  # SMA200 not filled
    assert trace.slices.long_term_trend.trend_label == "unknown"
    assert trace.slices.long_term_trend.close_vs_sma200 is None
    assert trace.slices.technical.sma200 is None


def test_indicators_populated_when_history_long_enough():
    trace = _build()
    t = trace.slices.technical
    assert t.sma20 is not None
    assert t.sma60 is not None
    assert t.sma200 is not None
    assert t.rsi14 is not None
    assert t.macd is not None
    assert t.bb is not None
    assert t.atr14 is not None


def test_market_slice_carries_gap_pct():
    trace = _build()
    m = trace.slices.market
    assert m.prev_close is not None
    assert m.gap_pct is not None


def test_build_rejects_empty_bars():
    with pytest.raises(ValueError):
        build_trace(
            bars=[],
            symbol="7203",
            market="TSE_PRIME",
            sector="輸送用機器",
            interval="1d",
            universe_snapshot_id="manual_v1",
            data_snapshot_hash="deadbeef",
            run_id="run_test_0001",
            commit_sha="abcdef",
            cost=default_cost(),
        )


def test_build_rejects_symbol_mismatch():
    bars = make_bars(50, symbol="7203")
    with pytest.raises(ValueError):
        _build(bars=bars, symbol="6758")


def test_build_rejects_interval_mismatch():
    bars = make_bars(50)
    with pytest.raises(ValueError):
        _build(bars=bars, interval="1h")


def test_hash_rule_params_is_stable_under_key_order():
    a = hash_rule_params({"x": 1, "y": 2})
    b = hash_rule_params({"y": 2, "x": 1})
    assert a == b


def test_hash_rule_params_distinguishes_different_inputs():
    a = hash_rule_params({"x": 1})
    b = hash_rule_params({"x": 2})
    assert a != b


def test_created_at_defaults_to_utc_now_aware():
    trace = _build()
    assert trace.created_at.tzinfo is not None


def test_explicit_created_at_is_preserved():
    ts = datetime(2024, 4, 26, 16, 0, tzinfo=timezone.utc)
    trace = _build(created_at=ts)
    assert trace.created_at == ts
