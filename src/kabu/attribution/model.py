"""Attribution dataclasses (P4.5 MVP)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class AttributionRow:
    """One bucket inside an attribution axis.

    ``contribution_pct`` is 100 * row.total_net_pnl_jpy / overall.total_net_pnl_jpy
    when both are present and the denominator is non-zero. It is ``None``
    when the denominator is zero or either side is missing.

    ``warnings`` is a tuple of severity codes attached to this specific
    row (e.g. ``"low_sample"`` or ``"unknown_sector"``). The report-level
    concentration list lives on ``AttributionReport.concentration_warnings``.
    """

    axis: str
    bucket_key: str
    trace_count: int
    trade_count: int
    skipped_count: int
    win_count: int
    loss_count: int
    flat_count: int
    unknown_count: int
    total_net_pnl_jpy: Optional[float]
    total_gross_pnl_jpy: Optional[float]
    total_fee_jpy: float
    total_slippage_jpy: float
    mean_net_pnl_jpy: Optional[float]
    contribution_pct: Optional[float]
    low_sample: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class AttributionAxis:
    axis: str
    rows: tuple[AttributionRow, ...]


@dataclass(frozen=True)
class ConcentrationWarning:
    """Report-level warning about a concentration of contribution."""

    axis: str
    bucket_key: str
    severity: str  # see kabu.attribution.concentration for the canonical set
    detail: str

    def __post_init__(self) -> None:
        if not isinstance(self.severity, str) or not self.severity:
            raise ValueError("ConcentrationWarning.severity must be non-empty")


@dataclass(frozen=True)
class OverallTotals:
    """Run-level totals used as denominators for contribution_pct."""

    trace_count: int
    trade_count: int
    closed_trade_count: int
    skipped_count: int
    total_net_pnl_jpy: Optional[float]
    total_gross_pnl_jpy: Optional[float]
    total_fee_jpy: float
    total_slippage_jpy: float


@dataclass(frozen=True)
class AttributionHeader:
    """Header carried alongside the report (must mirror StatsHeader fields)."""

    run_id: str
    commit_sha: str
    trace_schema_version: str
    analytics_version: str
    data_snapshot_hash: str
    universe_snapshot_id: str
    survivorship_policy: str
    survivorship_warning: bool
    pit_warnings: tuple[str, ...]
    other_warnings: tuple[str, ...]
    generated_at: datetime
    n_total: int
    trade_count: int
    skipped_count: int
    minimum_n: int
    high_concentration_pct: float


@dataclass(frozen=True)
class AttributionReport:
    header: AttributionHeader
    overall: OverallTotals
    axes: tuple[AttributionAxis, ...]
    concentration_warnings: tuple[ConcentrationWarning, ...]
