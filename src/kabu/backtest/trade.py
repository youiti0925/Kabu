"""Trade and Position dataclasses for the PR-S3 backtest engine.

Contract references:
- BACKTEST_CONTRACT.md S0 / S7 (run_metadata-required fields).
- SCHEMA.md S6 (trace JSONL writer linkage; the ``trace_jsonl_path`` on
  every ``Trade`` is enforced by ``test_trace_jsonl_path_required_for_trades``).
- This module deliberately models long-only / spot-equivalent only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional


def _require_aware(name: str, ts: datetime) -> None:
    if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
        raise ValueError(
            f"{name} must be timezone-aware (CALENDAR.md S0 D-2)"
        )


def _require_nonempty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


@dataclass(frozen=True)
class Position:
    """An open long position (PR-S3 MVP: long_only / spot-equivalent)."""

    symbol: str
    quantity: int
    avg_price: float
    opened_at: datetime
    source_trace_key: str

    def __post_init__(self) -> None:
        _require_nonempty("Position.symbol", self.symbol)
        _require_nonempty("Position.source_trace_key", self.source_trace_key)
        if self.quantity <= 0:
            raise ValueError("Position.quantity must be > 0")
        if self.avg_price <= 0:
            raise ValueError("Position.avg_price must be > 0")
        _require_aware("Position.opened_at", self.opened_at)


@dataclass(frozen=True)
class Trade:
    """A round-trip (or in-progress) long trade.

    ``trace_jsonl_path`` is REQUIRED on every Trade
    (``test_trace_jsonl_path_required_for_trades``).
    """

    trade_id: str
    run_id: str
    symbol: str
    side: Literal["long"]
    quantity: int
    entry_decision_ts: datetime
    entry_fill_ts: datetime
    entry_price: float
    entry_trace_key: str
    trace_jsonl_path: str
    fee_jpy: float = 0.0
    slippage_jpy: float = 0.0
    exit_decision_ts: Optional[datetime] = None
    exit_fill_ts: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_trace_key: Optional[str] = None
    exit_reason: Optional[str] = None
    gross_pnl_jpy: Optional[float] = None
    net_pnl_jpy: Optional[float] = None

    def __post_init__(self) -> None:
        _require_nonempty("Trade.trade_id", self.trade_id)
        _require_nonempty("Trade.run_id", self.run_id)
        _require_nonempty("Trade.symbol", self.symbol)
        _require_nonempty("Trade.entry_trace_key", self.entry_trace_key)
        _require_nonempty("Trade.trace_jsonl_path", self.trace_jsonl_path)
        if self.side != "long":
            raise ValueError(
                "Trade.side must be 'long' in MVP (long-only)"
            )
        if self.quantity <= 0:
            raise ValueError("Trade.quantity must be > 0")
        if self.entry_price <= 0:
            raise ValueError("Trade.entry_price must be > 0")
        _require_aware("Trade.entry_decision_ts", self.entry_decision_ts)
        _require_aware("Trade.entry_fill_ts", self.entry_fill_ts)
        if self.entry_fill_ts < self.entry_decision_ts:
            raise ValueError(
                "Trade.entry_fill_ts must be >= entry_decision_ts "
                "(BACKTEST_CONTRACT.md S0 D-3)"
            )
        if self.exit_decision_ts is not None:
            _require_aware("Trade.exit_decision_ts", self.exit_decision_ts)
        if self.exit_fill_ts is not None:
            _require_aware("Trade.exit_fill_ts", self.exit_fill_ts)
            if self.exit_fill_ts < (self.exit_decision_ts or self.entry_decision_ts):
                raise ValueError(
                    "Trade.exit_fill_ts must be >= exit_decision_ts"
                )
        if self.exit_price is not None and self.exit_price <= 0:
            raise ValueError("Trade.exit_price must be > 0 when set")
        if self.fee_jpy < 0:
            raise ValueError("Trade.fee_jpy must be >= 0")
