"""Attribution axis builders (P4.5 MVP).

Each axis groups records (traces / trades / skipped) by some key and
computes per-bucket totals + outcome counts + contribution_pct.

Inputs come from ``kabu.stats.RunStatsInput`` (re-using the loader from
PR-S4 -- no duplicate I/O implementation).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from kabu.attribution.model import (
    AttributionAxis,
    AttributionRow,
    OverallTotals,
)
from kabu.backtest.engine import SkippedFill
from kabu.backtest.trade import Trade
from kabu.decision_trace import Trace
from kabu.stats.loaders import RunStatsInput
from kabu.stats.outcomes import trace_outcome_label, trade_outcome_label


@dataclass(frozen=True)
class AttributionConfig:
    minimum_n: int = 30
    high_concentration_pct: float = 50.0


# --- helpers -----------------------------------------------------------------


def _safe_pct(part: Optional[float], total: Optional[float]) -> Optional[float]:
    """Return 100 * part / total, or None on missing data / zero denominator."""
    if part is None or total is None:
        return None
    if total == 0:
        return None
    return 100.0 * part / total


def _trade_outcome_counts(trades: Iterable[Trade]) -> tuple[int, int, int, int]:
    """(win, loss, flat, unknown)."""
    win = loss = flat = unknown = 0
    for t in trades:
        label = trade_outcome_label(t)
        if label == "win":
            win += 1
        elif label == "loss":
            loss += 1
        elif label == "flat":
            flat += 1
        else:
            unknown += 1
    return win, loss, flat, unknown


def _trace_outcome_counts(traces: Iterable[Trace]) -> tuple[int, int, int, int]:
    """(win, loss, flat, unknown). Maps big_win/big_loss into win/loss."""
    win = loss = flat = unknown = 0
    for t in traces:
        label = trace_outcome_label(t)
        if label in ("win", "big_win"):
            win += 1
        elif label in ("loss", "big_loss"):
            loss += 1
        elif label == "flat":
            flat += 1
        else:
            unknown += 1
    return win, loss, flat, unknown


# --- overall totals ----------------------------------------------------------


def build_overall_totals(inp: RunStatsInput) -> OverallTotals:
    trades = list(inp.trades)
    closed = [t for t in trades if t.exit_price is not None]
    nets = [t.net_pnl_jpy for t in trades if t.net_pnl_jpy is not None]
    gross = [t.gross_pnl_jpy for t in trades if t.gross_pnl_jpy is not None]
    return OverallTotals(
        trace_count=len(inp.traces),
        trade_count=len(trades),
        closed_trade_count=len(closed),
        skipped_count=len(inp.skipped_fills),
        total_net_pnl_jpy=(sum(nets) if nets else None),
        total_gross_pnl_jpy=(sum(gross) if gross else None),
        total_fee_jpy=sum(t.fee_jpy for t in trades),
        total_slippage_jpy=sum(t.slippage_jpy for t in trades),
    )


# --- axis builders -----------------------------------------------------------


def _make_row(
    *,
    axis: str,
    bucket_key: str,
    traces: list[Trace],
    trades: list[Trade],
    skipped: list[SkippedFill],
    overall: OverallTotals,
    config: AttributionConfig,
    extra_warnings: tuple[str, ...] = (),
) -> AttributionRow:
    nets = [t.net_pnl_jpy for t in trades if t.net_pnl_jpy is not None]
    gross = [t.gross_pnl_jpy for t in trades if t.gross_pnl_jpy is not None]
    total_net = sum(nets) if nets else None
    total_gross = sum(gross) if gross else None
    total_fee = sum(t.fee_jpy for t in trades)
    total_slip = sum(t.slippage_jpy for t in trades)
    mean_net = (total_net / len(nets)) if (total_net is not None and nets) else None
    contribution_pct = _safe_pct(total_net, overall.total_net_pnl_jpy)

    if traces:
        win, loss, flat, unknown = _trace_outcome_counts(traces)
    else:
        win, loss, flat, unknown = _trade_outcome_counts(trades)

    n_for_low_sample = len(traces) + len(trades) + len(skipped)
    low_sample = n_for_low_sample < config.minimum_n
    warnings = list(extra_warnings)
    if low_sample:
        warnings.append("low_sample")

    return AttributionRow(
        axis=axis,
        bucket_key=bucket_key,
        trace_count=len(traces),
        trade_count=len(trades),
        skipped_count=len(skipped),
        win_count=win,
        loss_count=loss,
        flat_count=flat,
        unknown_count=unknown,
        total_net_pnl_jpy=total_net,
        total_gross_pnl_jpy=total_gross,
        total_fee_jpy=total_fee,
        total_slippage_jpy=total_slip,
        mean_net_pnl_jpy=mean_net,
        contribution_pct=contribution_pct,
        low_sample=low_sample,
        warnings=tuple(warnings),
    )


def _by_key(
    *,
    axis: str,
    inp: RunStatsInput,
    overall: OverallTotals,
    config: AttributionConfig,
    trace_key: Optional[Callable[[Trace], str]] = None,
    trade_key: Optional[Callable[[Trade], str]] = None,
    skipped_key: Optional[Callable[[SkippedFill], str]] = None,
    extra_warning_for: Optional[Callable[[str], tuple[str, ...]]] = None,
) -> AttributionAxis:
    grouped_traces: dict[str, list[Trace]] = {}
    grouped_trades: dict[str, list[Trade]] = {}
    grouped_skipped: dict[str, list[SkippedFill]] = {}
    keys: set[str] = set()

    if trace_key is not None:
        for t in inp.traces:
            k = trace_key(t)
            grouped_traces.setdefault(k, []).append(t)
            keys.add(k)
    if trade_key is not None:
        for t in inp.trades:
            k = trade_key(t)
            grouped_trades.setdefault(k, []).append(t)
            keys.add(k)
    if skipped_key is not None:
        for s in inp.skipped_fills:
            k = skipped_key(s)
            grouped_skipped.setdefault(k, []).append(s)
            keys.add(k)

    rows: list[AttributionRow] = []
    for key in sorted(keys):
        extra = extra_warning_for(key) if extra_warning_for is not None else ()
        rows.append(
            _make_row(
                axis=axis,
                bucket_key=key,
                traces=grouped_traces.get(key, []),
                trades=grouped_trades.get(key, []),
                skipped=grouped_skipped.get(key, []),
                overall=overall,
                config=config,
                extra_warnings=extra,
            )
        )
    return AttributionAxis(axis=axis, rows=tuple(rows))


# --- specific axes -----------------------------------------------------------


def _symbol_of_trace(t: Trace) -> str:
    return t.symbol


def _symbol_of_trade(t: Trade) -> str:
    return t.symbol


def _symbol_of_skipped(s: SkippedFill) -> str:
    return s.symbol


def _build_symbol_to_sector(traces: Iterable[Trace]) -> dict[str, str]:
    out: dict[str, str] = {}
    for t in traces:
        if t.symbol not in out and t.sector:
            out[t.symbol] = t.sector
    return out


def _make_sector_keyer(traces: Iterable[Trace]) -> dict[str, str]:
    return _build_symbol_to_sector(traces)


def _year(ts: datetime) -> str:
    return f"{ts.year:04d}"


def _quarter(ts: datetime) -> str:
    return f"{ts.year:04d}-Q{(ts.month - 1) // 3 + 1}"


def _month(ts: datetime) -> str:
    return f"{ts.year:04d}-{ts.month:02d}"


def build_axes(
    inp: RunStatsInput,
    config: AttributionConfig,
    overall: OverallTotals,
) -> tuple[AttributionAxis, ...]:
    sym_to_sector = _make_sector_keyer(inp.traces)

    def trace_sector(t: Trace) -> str:
        return t.sector or "unknown"

    def trade_sector(t: Trade) -> str:
        return sym_to_sector.get(t.symbol) or "unknown"

    def skipped_sector(s: SkippedFill) -> str:
        return sym_to_sector.get(s.symbol) or "unknown"

    def sector_warn(key: str) -> tuple[str, ...]:
        return ("unknown_sector",) if key == "unknown" else ()

    def trace_period(period_fn):
        return lambda t: period_fn(t.bar_ts)

    def trade_period(period_fn):
        return lambda t: period_fn(t.entry_decision_ts)

    def skipped_period(period_fn):
        return lambda s: period_fn(s.decision_ts)

    axes: list[AttributionAxis] = []

    # symbol
    axes.append(
        _by_key(
            axis="symbol",
            inp=inp,
            overall=overall,
            config=config,
            trace_key=_symbol_of_trace,
            trade_key=_symbol_of_trade,
            skipped_key=_symbol_of_skipped,
        )
    )

    # sector (with unknown_sector warning)
    axes.append(
        _by_key(
            axis="sector",
            inp=inp,
            overall=overall,
            config=config,
            trace_key=trace_sector,
            trade_key=trade_sector,
            skipped_key=skipped_sector,
            extra_warning_for=sector_warn,
        )
    )

    # period: year / quarter / month
    for axis_name, period_fn in (
        ("year", _year),
        ("quarter", _quarter),
        ("month", _month),
    ):
        axes.append(
            _by_key(
                axis=axis_name,
                inp=inp,
                overall=overall,
                config=config,
                trace_key=trace_period(period_fn),
                trade_key=trade_period(period_fn),
                skipped_key=skipped_period(period_fn),
            )
        )

    # rule_id / rule_version (trace only)
    axes.append(
        _by_key(
            axis="rule_id",
            inp=inp,
            overall=overall,
            config=config,
            trace_key=lambda t: t.slices.decision.rule_id,
        )
    )
    axes.append(
        _by_key(
            axis="rule_version",
            inp=inp,
            overall=overall,
            config=config,
            trace_key=lambda t: t.slices.decision.rule_version,
        )
    )

    # skip_reason (skipped only)
    axes.append(
        _by_key(
            axis="skip_reason",
            inp=inp,
            overall=overall,
            config=config,
            skipped_key=lambda s: s.reason,
        )
    )

    # outcome (trace + trade)
    axes.append(
        _by_key(
            axis="outcome",
            inp=inp,
            overall=overall,
            config=config,
            trace_key=trace_outcome_label,
            trade_key=trade_outcome_label,
        )
    )

    return tuple(axes)
