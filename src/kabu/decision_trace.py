"""kabu.trace.v1 schema (dataclasses + validation).

Contract references:
- SCHEMA.md S0 D-1..D-13 (required fields, library_id placement)
- POINT_IN_TIME.md 3-1 / 3-7 (slice null when not yet released; future_outcome
  is post-processing only)
- BACKTEST_CONTRACT.md S0 D-3..D-9
- CALENDAR.md S0 D-1..D-10

This module defines the data model only. It does NOT make trade decisions.
It does NOT compute returns or backtest. Builders live in
``decision_trace_build``; JSONL I/O lives in ``trace_io``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional

# --- Constants ----------------------------------------------------------------

SCHEMA_VERSION: str = "kabu.trace.v1"
"""Top-level schema version (SCHEMA.md S1)."""

DEFAULT_ADJUSTMENT_BASIS: str = "split_dividend_back_adjusted"
"""technical.adjustment_basis fixed value for v1 (SCHEMA.md S0 D-9)."""

ASSUMED_FILL_BAR_NEXT_OPEN: str = "next_open"
"""execution_assumption.assumed_fill_bar fixed value for MVP (SCHEMA.md S0 D-7)."""

DEFAULT_LATENCY_BARS: int = 1
"""execution_assumption.latency_bars fixed value for MVP (SCHEMA.md S0 D-8)."""

# PR-S2 placeholder rule. NOT a trade decision (per PR-S2 brief).
OBSERVE_ONLY_RULE_ID: str = "trace_mvp_observe_only"
OBSERVE_ONLY_RULE_VERSION: str = "0.1.0"

# Decision enum values used in PR-S2 MVP. Trade-aware values
# ("buy", "sell_to_close", "no_position") are reserved for later PRs.
FinalAction = Literal[
    "observe_only",
    "buy",
    "hold",
    "sell_to_close",
    "no_position",
]
TechnicalOnlyAction = Literal[
    "not_evaluated",
    "buy",
    "hold",
    "sell_to_close",
    "no_position",
]
TrendLabel = Literal["above_sma200", "below_sma200", "unknown"]


# --- Validation helpers -------------------------------------------------------


def _require_aware(name: str, ts: datetime) -> None:
    if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
        raise ValueError(
            f"{name} must be timezone-aware (CALENDAR.md S0 D-2)"
        )


def _require_nonempty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")


# --- Slices -------------------------------------------------------------------


@dataclass(frozen=True)
class MarketSlice:
    """SCHEMA.md S4-1. Raw OHLCV + adjusted close + gap/halt flags."""

    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: int
    turnover: float
    prev_close: Optional[float] = None
    gap_pct: Optional[float] = None
    is_halted: bool = False
    is_special_quote: bool = False
    is_circuit_breaker: bool = False
    vwap: Optional[float] = None
    tick_size: Optional[float] = None
    unavailable_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if self.high < self.low:
            raise ValueError("market.high must be >= market.low")
        if self.volume < 0:
            raise ValueError("market.volume must be >= 0")


@dataclass(frozen=True)
class MACDPoint:
    line: float
    signal: float
    hist: float


@dataclass(frozen=True)
class BollingerPoint:
    middle: float
    upper: float
    lower: float


@dataclass(frozen=True)
class TechnicalSlice:
    """SCHEMA.md S4-2. ``adjustment_basis`` is required (S0 D-9)."""

    adjustment_basis: str
    sma20: Optional[float] = None
    sma60: Optional[float] = None
    sma200: Optional[float] = None
    rsi14: Optional[float] = None
    macd: Optional[MACDPoint] = None
    bb: Optional[BollingerPoint] = None
    atr14: Optional[float] = None
    unavailable_reason: Optional[str] = None

    def __post_init__(self) -> None:
        _require_nonempty("technical.adjustment_basis", self.adjustment_basis)


@dataclass(frozen=True)
class LongTermTrendSlice:
    """SCHEMA.md S4-3 (MVP subset). PR-S5 expands this."""

    close_vs_sma200: Optional[float]
    trend_label: TrendLabel
    unavailable_reason: Optional[str] = None


@dataclass(frozen=True)
class RiskCtxSlice:
    """SCHEMA.md S4-7. risk_gate is NOT implemented in PR-S2."""

    blocked_by: tuple[str, ...] = ()
    hold_reason: tuple[str, ...] = ()
    unavailable_reason_summary: Optional[str] = None


@dataclass(frozen=True)
class DecisionSlice:
    """SCHEMA.md S4-8 + S0 D-5 / D-6.

    PR-S2 contract: this is an OBSERVATION marker, not a trade decision.
    rule_id / rule_version / rule_params_hash are required;
    confidence is in [0.0, 1.0] or None.
    """

    final_action: FinalAction
    technical_only_action: TechnicalOnlyAction
    rule_id: str
    rule_version: str
    rule_params_hash: str
    confidence: Optional[float] = None

    def __post_init__(self) -> None:
        _require_nonempty("decision.rule_id", self.rule_id)
        _require_nonempty("decision.rule_version", self.rule_version)
        _require_nonempty("decision.rule_params_hash", self.rule_params_hash)
        if self.confidence is not None:
            if not isinstance(self.confidence, (int, float)):
                raise TypeError("decision.confidence must be float or None")
            if not (0.0 <= float(self.confidence) <= 1.0):
                raise ValueError(
                    "decision.confidence must be within [0.0, 1.0] or None"
                )


@dataclass(frozen=True)
class ExecutionAssumptionSlice:
    """SCHEMA.md S4-9 + S0 D-7 / D-8.

    PR-S2 keeps this as metadata only -- no actual fill happens here.
    fill_price / is_realistic / fill_reason carry the keys but null /
    sentinel values until PR-S3 wires them up.
    """

    assumed_fill_bar: str
    latency_bars: int
    slippage_bps: float
    fee_bps: float
    fee_fixed_jpy: Optional[float] = None
    fill_price: Optional[float] = None
    is_realistic: bool = False
    fill_reason: Optional[str] = None

    def __post_init__(self) -> None:
        _require_nonempty(
            "execution_assumption.assumed_fill_bar", self.assumed_fill_bar
        )
        if not isinstance(self.latency_bars, int):
            raise TypeError(
                "execution_assumption.latency_bars must be int"
            )
        if self.latency_bars < 0:
            raise ValueError(
                "execution_assumption.latency_bars must be >= 0"
            )
        if self.slippage_bps < 0:
            raise ValueError("slippage_bps must be >= 0")
        if self.fee_bps < 0:
            raise ValueError("fee_bps must be >= 0")


@dataclass(frozen=True)
class FutureOutcomeSlice:
    """SCHEMA.md S4-10 + S0 D-10 / D-11.

    Post-processing only. The decision builder must NOT take this slice
    as input (POINT_IN_TIME.md 3-7). When a trace contains a
    FutureOutcomeSlice, ``forward_return_basis`` is required.
    """

    forward_return_basis: Literal["close_to_close", "open_to_close", "open_to_open"]
    forward_return_1d: Optional[float] = None
    forward_return_5d: Optional[float] = None
    forward_return_20d: Optional[float] = None
    forward_return_horizon_bars: tuple[int, ...] = ()
    mfe: Optional[float] = None
    mae: Optional[float] = None
    hit_stop: Optional[bool] = None
    outcome_label_static: Optional[
        Literal["big_win", "win", "flat", "loss", "big_loss"]
    ] = None
    outcome_label_atr_norm: Optional[
        Literal["big_win", "win", "flat", "loss", "big_loss"]
    ] = None
    forward_return_end_ts: Optional[datetime] = None

    def __post_init__(self) -> None:
        _require_nonempty(
            "future_outcome.forward_return_basis", self.forward_return_basis
        )
        if self.forward_return_end_ts is not None:
            _require_aware(
                "future_outcome.forward_return_end_ts",
                self.forward_return_end_ts,
            )


# --- Slices container ---------------------------------------------------------


@dataclass(frozen=True)
class TraceSlices:
    """The body of a trace, grouped by slice (SCHEMA.md S2 -> ``slices``)."""

    market: MarketSlice
    technical: TechnicalSlice
    long_term_trend: LongTermTrendSlice
    risk_ctx: RiskCtxSlice
    decision: DecisionSlice
    execution_assumption: ExecutionAssumptionSlice
    future_outcome: Optional[FutureOutcomeSlice] = None
    # Slices reserved for later PRs (PR-S5/S6/S7/S8/S9) intentionally absent.


# --- Trace --------------------------------------------------------------------


@dataclass(frozen=True)
class Trace:
    """One ``kabu.trace.v1`` record (SCHEMA.md S2)."""

    schema_version: str
    trace_schema_version: str
    run_id: str
    commit_sha: str
    created_at: datetime
    symbol: str
    market: str
    sector: str
    interval: str
    bar_ts: datetime
    bar_ts_close: datetime
    bar_ts_available: datetime
    universe_snapshot_id: str
    data_snapshot_hash: str
    slices: TraceSlices
    unavailable_reason: Optional[str] = None

    def __post_init__(self) -> None:
        _require_nonempty("schema_version", self.schema_version)
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"unsupported schema_version: {self.schema_version!r}; "
                f"this build only writes {SCHEMA_VERSION!r}"
            )
        _require_nonempty("trace_schema_version", self.trace_schema_version)
        if self.trace_schema_version != self.schema_version:
            raise ValueError(
                "trace_schema_version must equal schema_version"
            )
        _require_nonempty("run_id", self.run_id)
        _require_nonempty("commit_sha", self.commit_sha)
        _require_nonempty("symbol", self.symbol)
        _require_nonempty("market", self.market)
        _require_nonempty("sector", self.sector)
        _require_nonempty("interval", self.interval)
        _require_nonempty("universe_snapshot_id", self.universe_snapshot_id)
        _require_nonempty("data_snapshot_hash", self.data_snapshot_hash)
        for name in ("created_at", "bar_ts", "bar_ts_close", "bar_ts_available"):
            _require_aware(name, getattr(self, name))
        if self.bar_ts_close > self.bar_ts_available:
            raise ValueError(
                "bar_ts_close must be <= bar_ts_available "
                "(CALENDAR.md S0 D-6)"
            )


# --- run_metadata side --------------------------------------------------------


@dataclass(frozen=True)
class LibraryRef:
    """One entry of run_metadata.libraries (SCHEMA.md S0 D-12 / D-13).

    PR-S2 only defines the type; PR-S6 (waveform) populates it.
    """

    slice: str
    library_id: str
    library_kind: str
    feature_set: str

    def __post_init__(self) -> None:
        _require_nonempty("LibraryRef.slice", self.slice)
        _require_nonempty("LibraryRef.library_id", self.library_id)
        _require_nonempty("LibraryRef.library_kind", self.library_kind)
        _require_nonempty("LibraryRef.feature_set", self.feature_set)


@dataclass(frozen=True)
class RunMetadata:
    """Minimal stub for run_metadata used by PR-S2.

    BACKTEST_CONTRACT.md S7 lists the canonical required fields. PR-S2
    keeps a small subset; PR-S3 will round it out.
    """

    run_id: str
    commit_sha: str
    created_at: datetime
    trace_schema_version: str
    interval: str
    universe_snapshot_id: str
    data_snapshot_hash: str
    survivorship_policy: str
    survivorship_warning: bool
    currency: str
    report_currency: str
    tax_basis: str
    libraries: tuple[LibraryRef, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_nonempty("run_metadata.run_id", self.run_id)
        _require_nonempty("run_metadata.commit_sha", self.commit_sha)
        _require_aware("run_metadata.created_at", self.created_at)
        _require_nonempty(
            "run_metadata.trace_schema_version", self.trace_schema_version
        )
        if self.trace_schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"unsupported trace_schema_version: "
                f"{self.trace_schema_version!r}"
            )
        _require_nonempty("run_metadata.interval", self.interval)
        _require_nonempty(
            "run_metadata.universe_snapshot_id", self.universe_snapshot_id
        )
        _require_nonempty(
            "run_metadata.data_snapshot_hash", self.data_snapshot_hash
        )
        _require_nonempty(
            "run_metadata.survivorship_policy", self.survivorship_policy
        )
        _require_nonempty("run_metadata.currency", self.currency)
        _require_nonempty(
            "run_metadata.report_currency", self.report_currency
        )
        _require_nonempty("run_metadata.tax_basis", self.tax_basis)


__all__ = [
    "SCHEMA_VERSION",
    "DEFAULT_ADJUSTMENT_BASIS",
    "ASSUMED_FILL_BAR_NEXT_OPEN",
    "DEFAULT_LATENCY_BARS",
    "OBSERVE_ONLY_RULE_ID",
    "OBSERVE_ONLY_RULE_VERSION",
    "MarketSlice",
    "MACDPoint",
    "BollingerPoint",
    "TechnicalSlice",
    "LongTermTrendSlice",
    "RiskCtxSlice",
    "DecisionSlice",
    "ExecutionAssumptionSlice",
    "FutureOutcomeSlice",
    "TraceSlices",
    "Trace",
    "LibraryRef",
    "RunMetadata",
]
