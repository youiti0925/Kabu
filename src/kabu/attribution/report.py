"""Attribution orchestrator + Markdown / JSON writers (P4.5 MVP).

Outputs:
    runs/<run_id>/stats/attribution.md
    runs/<run_id>/stats/attribution.json

Tests use ``tmp_path`` exclusively.

This file is part of an OBSERVATION layer. It does not assert causation.
Permitted vocabulary in the rendered text:
    "寄与" / "偏り" / "集中" / "説明力がありそうな候補" /
    "追加検証すべき仮説" / "現在の trace では説明不能" /
    "必要な追加データ" / "リスク警告"

Forbidden vocabulary (enforced by
``test_attribution_is_observation_not_recommendation``):
    "確定" / "これが原因" / "これで勝てる" /
    "この銘柄を買うべき" / "このルールに変更すべき" /
    "絶対" / "保証"
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from kabu.attribution.aggregate import (
    AttributionConfig,
    build_axes,
    build_overall_totals,
)
from kabu.attribution.concentration import (
    DEFAULT_HIGH_CONCENTRATION_PCT,
    DEFAULT_MINIMUM_N,
    detect_concentration_warnings,
)
from kabu.attribution.model import (
    AttributionAxis,
    AttributionHeader,
    AttributionReport,
    AttributionRow,
    ConcentrationWarning,
    OverallTotals,
)
from kabu.stats.loaders import RunStatsInput

ANALYTICS_VERSION = "kabu.attribution.v1"


def _make_header(
    inp: RunStatsInput,
    *,
    overall: OverallTotals,
    config: AttributionConfig,
    generated_at: datetime,
) -> AttributionHeader:
    warnings = inp.run_metadata.warnings
    pit_warnings = tuple(w for w in warnings if w.lower().startswith("pit"))
    other_warnings = tuple(w for w in warnings if not w.lower().startswith("pit"))
    return AttributionHeader(
        run_id=inp.run_metadata.run_id,
        commit_sha=inp.run_metadata.commit_sha,
        trace_schema_version=inp.run_metadata.trace_schema_version,
        analytics_version=ANALYTICS_VERSION,
        data_snapshot_hash=inp.run_metadata.data_snapshot_hash,
        universe_snapshot_id=inp.run_metadata.universe_snapshot_id,
        survivorship_policy=inp.run_metadata.survivorship_policy,
        survivorship_warning=inp.run_metadata.survivorship_warning,
        pit_warnings=pit_warnings,
        other_warnings=other_warnings,
        generated_at=generated_at,
        n_total=overall.trace_count,
        trade_count=overall.trade_count,
        skipped_count=overall.skipped_count,
        minimum_n=config.minimum_n,
        high_concentration_pct=config.high_concentration_pct,
    )


def build_attribution_report(
    inp: RunStatsInput,
    *,
    minimum_n: int = DEFAULT_MINIMUM_N,
    high_concentration_pct: float = DEFAULT_HIGH_CONCENTRATION_PCT,
    generated_at: Optional[datetime] = None,
) -> AttributionReport:
    if generated_at is None:
        generated_at = datetime.now(tz=timezone.utc)
    config = AttributionConfig(
        minimum_n=minimum_n,
        high_concentration_pct=high_concentration_pct,
    )
    overall = build_overall_totals(inp)
    axes = build_axes(inp, config=config, overall=overall)
    warnings = detect_concentration_warnings(
        axes,
        overall=overall,
        high_concentration_pct=high_concentration_pct,
    )
    header = _make_header(
        inp,
        overall=overall,
        config=config,
        generated_at=generated_at,
    )
    return AttributionReport(
        header=header,
        overall=overall,
        axes=axes,
        concentration_warnings=warnings,
    )


# --- writer helpers ----------------------------------------------------------


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


def write_attribution_json(path: str | Path, report: AttributionReport) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = _enc(asdict(report))
    with p.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return p.resolve()


def _fmt(v: Optional[float]) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        if abs(v) < 1000:
            return f"{v:.4f}"
        return f"{v:.2f}"
    return str(v)


def _render_header_md(h: AttributionHeader) -> str:
    lines = [
        "# Attribution Report (kabu.attribution.v1)\n",
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
        f"- n_total (trace): {h.n_total}",
        f"- trade_count: {h.trade_count}",
        f"- skipped_count: {h.skipped_count}",
        f"- minimum_n: {h.minimum_n}",
        f"- high_concentration_pct: {h.high_concentration_pct}",
        "",
        "**この report は寄与・偏り・集中の観測です。"
        "売買ルールではなく、特定銘柄の推奨でもありません。"
        "1 bucket への集中は `concentration_warnings` を参照してください。"
        "low_sample が立つ bucket は説明力がありそうな候補としては扱えません。**",
        "",
    ]
    return "\n".join(lines)


def _render_overall_md(o: OverallTotals) -> str:
    return "\n".join(
        [
            "## Overall totals\n",
            f"- trace_count: {o.trace_count}",
            f"- trade_count: {o.trade_count}",
            f"- closed_trade_count: {o.closed_trade_count}",
            f"- skipped_count: {o.skipped_count}",
            f"- total_gross_pnl_jpy: {_fmt(o.total_gross_pnl_jpy)}",
            f"- total_net_pnl_jpy: {_fmt(o.total_net_pnl_jpy)}",
            f"- total_fee_jpy: {_fmt(o.total_fee_jpy)}",
            f"- total_slippage_jpy: {_fmt(o.total_slippage_jpy)}",
            "",
        ]
    )


def _render_axis_md(axis: AttributionAxis) -> str:
    lines = [f"### axis: `{axis.axis}`\n"]
    lines.append(
        "| bucket | trace | trade | skipped | win | loss | flat | unknown | "
        "net_pnl_jpy | mean_net_pnl_jpy | contribution_pct | low_sample | warnings |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for row in axis.rows:
        flag = "**LOW**" if row.low_sample else ""
        warns = ", ".join(row.warnings) if row.warnings else ""
        contribution = (
            f"{row.contribution_pct:.2f}%" if row.contribution_pct is not None else "—"
        )
        lines.append(
            "| {bk} | {tc} | {td} | {sk} | {w} | {l} | {f} | {u} | "
            "{net} | {mean_net} | {contribution} | {flag} | {warns} |".format(
                bk=row.bucket_key,
                tc=row.trace_count,
                td=row.trade_count,
                sk=row.skipped_count,
                w=row.win_count,
                l=row.loss_count,
                f=row.flat_count,
                u=row.unknown_count,
                net=_fmt(row.total_net_pnl_jpy),
                mean_net=_fmt(row.mean_net_pnl_jpy),
                contribution=contribution,
                flag=flag,
                warns=warns,
            )
        )
    lines.append("")
    return "\n".join(lines)


def _render_warnings_md(warnings: Iterable[ConcentrationWarning]) -> str:
    items = list(warnings)
    if not items:
        return "## Concentration / risk warnings\n\n- (none)\n"
    lines = ["## Concentration / risk warnings\n"]
    for w in items:
        lines.append(f"- **{w.severity}** | axis=`{w.axis}` | bucket=`{w.bucket_key}` — {w.detail}")
    lines.append("")
    return "\n".join(lines)


def write_attribution_markdown(
    path: str | Path, report: AttributionReport
) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    parts = [
        _render_header_md(report.header),
        _render_overall_md(report.overall),
        _render_warnings_md(report.concentration_warnings),
        "## Per-axis attribution\n",
    ]
    for axis in report.axes:
        parts.append(_render_axis_md(axis))
    p.write_text("\n".join(parts), encoding="utf-8")
    return p.resolve()


def run_full_attribution(
    inp: RunStatsInput,
    *,
    minimum_n: int = DEFAULT_MINIMUM_N,
    high_concentration_pct: float = DEFAULT_HIGH_CONCENTRATION_PCT,
    generated_at: Optional[datetime] = None,
) -> tuple[AttributionReport, Path, Path]:
    """Compute the report and write attribution.{md,json}.

    Returns ``(report, json_path, md_path)``.
    """
    inp.paths.ensure_run_dir()
    report = build_attribution_report(
        inp,
        minimum_n=minimum_n,
        high_concentration_pct=high_concentration_pct,
        generated_at=generated_at,
    )
    md_path = inp.paths.stats_dir / "attribution.md"
    json_path = inp.paths.stats_dir / "attribution.json"
    write_attribution_markdown(md_path, report)
    write_attribution_json(json_path, report)
    return report, json_path, md_path
