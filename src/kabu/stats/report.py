"""Stats orchestration + Markdown / JSON writers (PR-S4 MVP).

Reads a ``RunStatsInput`` and emits a ``StatsReport`` containing:

- the canonical header (survivorship + PIT warnings + identity fields)
- single-axis aggregations (final_action / technical_only_action /
  rule_id / rule_version / symbol / hold_reason / blocked_by + bucketed
  RSI / SMA200 distance / MACD hist sign)
- 2-axis cross aggregations (e.g. final_action x rsi_bucket)
- skip reason counts
- trade pnl summary

Outputs land under ``runs/<run_id>/stats/`` per RunPaths. Tests use
``tmp_path`` exclusively (BACKTEST_CONTRACT.md S6-A).

This module does NOT generate AI proposals; AI Review is PR-S10.
This module does NOT recommend symbols.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from kabu.backtest.engine import SkippedFill
from kabu.backtest.trade import Trade
from kabu.decision_trace import Trace
from kabu.stats.aggregate import (
    AxisReport,
    BucketStats,
    aggregate_axis,
    cross_axis,
    make_item,
)
from kabu.stats.buckets import (
    bucket_macd_hist,
    bucket_rsi,
    bucket_sma200_distance,
)
from kabu.stats.loaders import RunStatsInput
from kabu.stats.outcomes import (
    trace_forward_return_5d,
    trace_outcome_label,
    trade_outcome_label,
)


# --- Header ------------------------------------------------------------------


@dataclass(frozen=True)
class StatsHeader:
    run_id: str
    commit_sha: str
    trace_schema_version: str
    data_snapshot_hash: str
    universe_snapshot_id: str
    survivorship_policy: str
    survivorship_warning: bool
    pit_warnings: tuple[str, ...]
    other_warnings: tuple[str, ...]
    generated_at: datetime
    n_total: int
    n_filtered: int
    filter_reasons: dict[str, int]
    minimum_n: int
    analytics_version: str = "kabu.stats.v1"


def _make_header(
    inp: RunStatsInput,
    *,
    minimum_n: int,
    generated_at: Optional[datetime] = None,
) -> StatsHeader:
    if generated_at is None:
        generated_at = datetime.now(tz=timezone.utc)
    warnings = inp.run_metadata.warnings
    pit_warnings = tuple(w for w in warnings if w.lower().startswith("pit"))
    other_warnings = tuple(w for w in warnings if not w.lower().startswith("pit"))

    n_total = len(inp.traces)
    filter_reasons: dict[str, int] = {}
    n_filtered = 0
    for t in inp.traces:
        reason = t.unavailable_reason
        if reason:
            filter_reasons[reason] = filter_reasons.get(reason, 0) + 1
            n_filtered += 1

    return StatsHeader(
        run_id=inp.run_metadata.run_id,
        commit_sha=inp.run_metadata.commit_sha,
        trace_schema_version=inp.run_metadata.trace_schema_version,
        data_snapshot_hash=inp.run_metadata.data_snapshot_hash,
        universe_snapshot_id=inp.run_metadata.universe_snapshot_id,
        survivorship_policy=inp.run_metadata.survivorship_policy,
        survivorship_warning=inp.run_metadata.survivorship_warning,
        pit_warnings=pit_warnings,
        other_warnings=other_warnings,
        generated_at=generated_at,
        n_total=n_total,
        n_filtered=n_filtered,
        filter_reasons=dict(sorted(filter_reasons.items())),
        minimum_n=minimum_n,
    )


# --- Trade summary -----------------------------------------------------------


@dataclass(frozen=True)
class TradePnlSummary:
    trade_count: int
    closed_count: int
    open_count: int
    total_gross_pnl_jpy: Optional[float]
    total_net_pnl_jpy: Optional[float]
    total_fee_jpy: float
    total_slippage_jpy: float
    win_count: int
    loss_count: int
    flat_count: int
    unknown_count: int


def _summarize_trades(trades: Iterable[Trade]) -> TradePnlSummary:
    trade_list = list(trades)
    closed = [t for t in trade_list if t.exit_price is not None]
    win = sum(1 for t in trade_list if trade_outcome_label(t) == "win")
    loss = sum(1 for t in trade_list if trade_outcome_label(t) == "loss")
    flat = sum(1 for t in trade_list if trade_outcome_label(t) == "flat")
    unknown = sum(1 for t in trade_list if trade_outcome_label(t) == "unknown")
    gross_present = [t.gross_pnl_jpy for t in trade_list if t.gross_pnl_jpy is not None]
    net_present = [t.net_pnl_jpy for t in trade_list if t.net_pnl_jpy is not None]
    return TradePnlSummary(
        trade_count=len(trade_list),
        closed_count=len(closed),
        open_count=len(trade_list) - len(closed),
        total_gross_pnl_jpy=(sum(gross_present) if gross_present else None),
        total_net_pnl_jpy=(sum(net_present) if net_present else None),
        total_fee_jpy=sum(t.fee_jpy for t in trade_list),
        total_slippage_jpy=sum(t.slippage_jpy for t in trade_list),
        win_count=win,
        loss_count=loss,
        flat_count=flat,
        unknown_count=unknown,
    )


# --- StatsReport -------------------------------------------------------------


@dataclass(frozen=True)
class StatsReport:
    header: StatsHeader
    axes: tuple[AxisReport, ...]
    cross_axes: tuple[AxisReport, ...]
    skip_reason_counts: dict[str, int]
    trade_pnl_summary: TradePnlSummary


def _outcome_with_returns(traces: Iterable[Trace]) -> tuple[
    list[str], list[Optional[float]]
]:
    outs: list[str] = []
    rets: list[Optional[float]] = []
    for t in traces:
        outs.append(trace_outcome_label(t))
        rets.append(trace_forward_return_5d(t))
    return outs, rets


def _items_for_trace_axis(
    traces: list[Trace],
    bucket_fn,
):
    items = []
    for t in traces:
        items.append(
            make_item(
                bucket_key=bucket_fn(t),
                outcome=trace_outcome_label(t),
                forward_return=trace_forward_return_5d(t),
            )
        )
    return items


def _items_for_trade_axis(
    trades: list[Trade],
    key_fn,
):
    items = []
    for tr in trades:
        items.append(
            make_item(
                bucket_key=key_fn(tr),
                outcome=trade_outcome_label(tr),
                net_pnl_jpy=tr.net_pnl_jpy,
            )
        )
    return items


def _key_final_action(trace: Trace) -> str:
    return trace.slices.decision.final_action


def _key_technical_only_action(trace: Trace) -> str:
    return trace.slices.decision.technical_only_action


def _key_rule_id(trace: Trace) -> str:
    return trace.slices.decision.rule_id


def _key_rule_version(trace: Trace) -> str:
    return trace.slices.decision.rule_version


def _key_symbol(trace: Trace) -> str:
    return trace.symbol


def _key_trend_label(trace: Trace) -> str:
    return trace.slices.long_term_trend.trend_label


def _key_rsi(trace: Trace) -> str:
    return bucket_rsi(trace.slices.technical.rsi14)


def _key_sma200_distance(trace: Trace) -> str:
    return bucket_sma200_distance(trace.slices.long_term_trend.close_vs_sma200)


def _key_macd_hist(trace: Trace) -> str:
    macd = trace.slices.technical.macd
    return bucket_macd_hist(macd.hist if macd is not None else None)


def _trade_exit_reason(trade: Trade) -> str:
    return trade.exit_reason or "no_exit"


def _hold_reason_items(traces: list[Trace], minimum_n: int) -> AxisReport:
    items = []
    for t in traces:
        reasons = t.slices.risk_ctx.hold_reason or ("none",)
        for r in reasons:
            items.append(
                make_item(
                    bucket_key=r or "none",
                    outcome=trace_outcome_label(t),
                    forward_return=trace_forward_return_5d(t),
                )
            )
    return aggregate_axis(
        axis="hold_reason_x_outcome",
        items=items,
        minimum_n=minimum_n,
    )


def _blocked_by_items(traces: list[Trace], minimum_n: int) -> AxisReport:
    items = []
    for t in traces:
        blocks = t.slices.risk_ctx.blocked_by or ("none",)
        for r in blocks:
            items.append(
                make_item(
                    bucket_key=r or "none",
                    outcome=trace_outcome_label(t),
                    forward_return=trace_forward_return_5d(t),
                )
            )
    return aggregate_axis(
        axis="blocked_by_x_outcome",
        items=items,
        minimum_n=minimum_n,
    )


def build_stats_report(
    inp: RunStatsInput,
    *,
    minimum_n: int = 30,
    generated_at: Optional[datetime] = None,
) -> StatsReport:
    """Compute the full PR-S4 MVP stats bundle for one run."""
    traces = list(inp.traces)
    trades = list(inp.trades)
    skipped = list(inp.skipped_fills)

    header = _make_header(inp, minimum_n=minimum_n, generated_at=generated_at)

    axes: list[AxisReport] = [
        aggregate_axis(
            axis="final_action_x_outcome",
            items=_items_for_trace_axis(traces, _key_final_action),
            minimum_n=minimum_n,
        ),
        aggregate_axis(
            axis="technical_only_action_x_outcome",
            items=_items_for_trace_axis(traces, _key_technical_only_action),
            minimum_n=minimum_n,
        ),
        aggregate_axis(
            axis="rule_id_x_outcome",
            items=_items_for_trace_axis(traces, _key_rule_id),
            minimum_n=minimum_n,
        ),
        aggregate_axis(
            axis="rule_version_x_outcome",
            items=_items_for_trace_axis(traces, _key_rule_version),
            minimum_n=minimum_n,
        ),
        aggregate_axis(
            axis="symbol_x_outcome",
            items=_items_for_trace_axis(traces, _key_symbol),
            minimum_n=minimum_n,
        ),
        aggregate_axis(
            axis="trend_label_x_outcome",
            items=_items_for_trace_axis(traces, _key_trend_label),
            minimum_n=minimum_n,
        ),
        aggregate_axis(
            axis="rsi_bucket_x_outcome",
            items=_items_for_trace_axis(traces, _key_rsi),
            minimum_n=minimum_n,
        ),
        aggregate_axis(
            axis="sma200_distance_x_outcome",
            items=_items_for_trace_axis(traces, _key_sma200_distance),
            minimum_n=minimum_n,
        ),
        aggregate_axis(
            axis="macd_hist_sign_x_outcome",
            items=_items_for_trace_axis(traces, _key_macd_hist),
            minimum_n=minimum_n,
        ),
        _hold_reason_items(traces, minimum_n),
        _blocked_by_items(traces, minimum_n),
    ]

    if trades:
        axes.append(
            aggregate_axis(
                axis="trade_exit_reason_x_outcome",
                items=_items_for_trade_axis(trades, _trade_exit_reason),
                minimum_n=minimum_n,
            )
        )

    cross_items_final_x_rsi = []
    cross_items_trend_x_rsi = []
    for t in traces:
        outcome = trace_outcome_label(t)
        ret = trace_forward_return_5d(t)
        cross_items_final_x_rsi.append(
            (_key_final_action(t), _key_rsi(t), outcome)
        )
        cross_items_trend_x_rsi.append(
            (_key_trend_label(t), _key_rsi(t), outcome)
        )
    cross_returns_final_x_rsi = [trace_forward_return_5d(t) for t in traces]

    cross_axes: list[AxisReport] = [
        cross_axis(
            axis="final_action_x_rsi_bucket_x_outcome",
            items=cross_items_final_x_rsi,
            minimum_n=minimum_n,
            forward_returns=cross_returns_final_x_rsi,
        ),
        cross_axis(
            axis="trend_label_x_rsi_bucket_x_outcome",
            items=cross_items_trend_x_rsi,
            minimum_n=minimum_n,
            forward_returns=cross_returns_final_x_rsi,
        ),
    ]

    skip_counts: dict[str, int] = {}
    for s in skipped:
        skip_counts[s.reason] = skip_counts.get(s.reason, 0) + 1
    skip_counts = dict(sorted(skip_counts.items()))

    pnl = _summarize_trades(trades)

    return StatsReport(
        header=header,
        axes=tuple(axes),
        cross_axes=tuple(cross_axes),
        skip_reason_counts=skip_counts,
        trade_pnl_summary=pnl,
    )


# --- Writers -----------------------------------------------------------------


def _enc(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, tuple):
        return [_enc(x) for x in obj]
    if isinstance(obj, list):
        return [_enc(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _enc(v) for k, v in obj.items()}
    if isinstance(obj, Path):
        return str(obj)
    return obj


def write_stats_json(path: str | Path, report: StatsReport) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = _enc(asdict(report))
    with p.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return p.resolve()


def _format_float(v: Optional[float]) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.4f}" if abs(v) < 1000 else f"{v:.2f}"
    return str(v)


def _render_axis_md(axis: AxisReport) -> str:
    lines: list[str] = []
    lines.append(f"### {axis.axis}\n")
    lines.append(f"minimum_n: {axis.minimum_n}\n")
    lines.append(
        "| bucket | n | n_unknown | hit_rate | mean_return | mean_net_pnl_jpy | total_net_pnl_jpy | low_sample |"
    )
    lines.append(
        "|---|---|---|---|---|---|---|---|"
    )
    for b in axis.buckets:
        flag = "**LOW**" if b.low_sample else ""
        lines.append(
            "| {bucket} | {n} | {nu} | {hr} | {mr} | {mnp} | {tnp} | {flag} |".format(
                bucket=b.bucket_key,
                n=b.n,
                nu=b.n_unknown_outcome,
                hr=_format_float(b.hit_rate),
                mr=_format_float(b.mean_return),
                mnp=_format_float(b.mean_net_pnl_jpy),
                tnp=_format_float(b.total_net_pnl_jpy),
                flag=flag,
            )
        )
    lines.append("")
    return "\n".join(lines)


def _render_header_md(h: StatsHeader) -> str:
    lines = [
        f"# Stats Report (kabu.stats.v1)\n",
        f"- run_id: `{h.run_id}`",
        f"- commit_sha: `{h.commit_sha}`",
        f"- trace_schema_version: `{h.trace_schema_version}`",
        f"- analytics_version: `{h.analytics_version}`",
        f"- data_snapshot_hash: `{h.data_snapshot_hash}`",
        f"- universe_snapshot_id: `{h.universe_snapshot_id}`",
        f"- survivorship_policy: `{h.survivorship_policy}`",
        f"- survivorship_warning: `{h.survivorship_warning}`",
        f"- pit_warnings: {list(h.pit_warnings) or '[]'}",
        f"- other_warnings: {list(h.other_warnings) or '[]'}",
        f"- generated_at: `{h.generated_at.isoformat()}`",
        f"- n_total: {h.n_total}",
        f"- n_filtered: {h.n_filtered}",
        f"- filter_reasons: {h.filter_reasons or '{}'}",
        f"- minimum_n: {h.minimum_n}",
        "",
        "**This report is observation only. It is NOT a trade rule and",
        "NOT a recommendation to buy or sell any specific symbol. Buckets",
        "with `low_sample = true` (n < minimum_n) must NOT be used as",
        "evidence for rule-change proposals (see AI_REVIEW_SAFETY.md).**",
        "",
    ]
    return "\n".join(lines)


def _render_pnl_md(pnl: TradePnlSummary) -> str:
    lines = [
        "## Trade PnL Summary\n",
        f"- trade_count: {pnl.trade_count}",
        f"- closed_count: {pnl.closed_count}",
        f"- open_count: {pnl.open_count}",
        f"- total_gross_pnl_jpy: {_format_float(pnl.total_gross_pnl_jpy)}",
        f"- total_net_pnl_jpy: {_format_float(pnl.total_net_pnl_jpy)}",
        f"- total_fee_jpy: {_format_float(pnl.total_fee_jpy)}",
        f"- total_slippage_jpy: {_format_float(pnl.total_slippage_jpy)}",
        f"- win_count: {pnl.win_count}",
        f"- loss_count: {pnl.loss_count}",
        f"- flat_count: {pnl.flat_count}",
        f"- unknown_count: {pnl.unknown_count}",
        "",
    ]
    return "\n".join(lines)


def write_stats_markdown(path: str | Path, report: StatsReport) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    parts = [_render_header_md(report.header)]
    parts.append("## Skip reason counts\n")
    if report.skip_reason_counts:
        for reason, count in report.skip_reason_counts.items():
            parts.append(f"- {reason}: {count}")
    else:
        parts.append("- (no skipped fills)")
    parts.append("")
    parts.append(_render_pnl_md(report.trade_pnl_summary))
    parts.append("## Single-axis aggregations\n")
    for axis in report.axes:
        parts.append(_render_axis_md(axis))
    parts.append("## Cross aggregations (2-axis)\n")
    for axis in report.cross_axes:
        parts.append(_render_axis_md(axis))
    p.write_text("\n".join(parts), encoding="utf-8")
    return p.resolve()


def run_full_stats(
    inp: RunStatsInput,
    *,
    minimum_n: int = 30,
    generated_at: Optional[datetime] = None,
) -> tuple[StatsReport, Path, Path]:
    """Compute the report and write both stats.json and stats.md.

    Returns ``(report, json_path, md_path)``. Output goes under
    ``inp.paths.stats_dir``; tests use ``tmp_path``.
    """
    inp.paths.ensure_run_dir()
    report = build_stats_report(
        inp, minimum_n=minimum_n, generated_at=generated_at
    )
    md_path = inp.paths.stats_dir / "summary.md"
    json_path = inp.paths.stats_dir / "summary.json"
    write_stats_markdown(md_path, report)
    write_stats_json(json_path, report)
    return report, json_path, md_path


__all__ = [
    "StatsHeader",
    "StatsReport",
    "TradePnlSummary",
    "build_stats_report",
    "run_full_stats",
    "write_stats_json",
    "write_stats_markdown",
]
