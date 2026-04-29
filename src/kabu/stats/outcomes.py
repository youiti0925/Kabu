"""Outcome label extraction.

Trace-level outcome reads from ``future_outcome.outcome_label_static``
or, as a fallback, the sign of ``forward_return_5d``.

Trade-level outcome reads from ``net_pnl_jpy`` sign.

If the input is unknown, returns ``"unknown"``. Aggregation downstream
treats ``"unknown"`` as a separate bucket (POINT_IN_TIME.md 3-7: missing
data is observed, not silently dropped).
"""

from __future__ import annotations

from kabu.backtest.trade import Trade
from kabu.decision_trace import Trace


_OUTCOME_VALUES = ("big_win", "win", "flat", "loss", "big_loss", "unknown")


def trace_outcome_label(trace: Trace) -> str:
    """Return one of {big_win, win, flat, loss, big_loss, unknown}."""
    fo = trace.slices.future_outcome
    if fo is None:
        return "unknown"
    if fo.outcome_label_static is not None:
        return fo.outcome_label_static
    if fo.outcome_label_atr_norm is not None:
        return fo.outcome_label_atr_norm
    r = fo.forward_return_5d
    if r is None:
        return "unknown"
    if r > 0.0:
        return "win"
    if r < 0.0:
        return "loss"
    return "flat"


def trade_outcome_label(trade: Trade) -> str:
    """Return one of {win, loss, flat, unknown}."""
    if trade.net_pnl_jpy is None:
        return "unknown"
    if trade.net_pnl_jpy > 0:
        return "win"
    if trade.net_pnl_jpy < 0:
        return "loss"
    return "flat"


def trace_forward_return_5d(trace: Trace):
    """Return forward_return_5d if present, else None."""
    fo = trace.slices.future_outcome
    if fo is None:
        return None
    return fo.forward_return_5d


__all__ = [
    "trace_outcome_label",
    "trade_outcome_label",
    "trace_forward_return_5d",
]
