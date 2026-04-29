"""Stats input loader.

Reads the run output set fixed in P3.5 and returns a single bundle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from kabu.backtest.io import (
    BacktestResultSummary,
    read_backtest_result_json,
    read_skipped_fills_jsonl,
    read_trades_jsonl,
)
from kabu.backtest.engine import SkippedFill
from kabu.backtest.trade import Trade
from kabu.decision_trace import RunMetadata, SCHEMA_VERSION, Trace
from kabu.run_metadata_io import read_run_metadata_json
from kabu.run_paths import RunPaths
from kabu.trace_io import read_traces_jsonl


@dataclass(frozen=True)
class RunStatsInput:
    """All inputs PR-S4 stats consumes."""

    paths: RunPaths
    run_metadata: RunMetadata
    backtest_result_summary: BacktestResultSummary
    traces: tuple[Trace, ...]
    trades: tuple[Trade, ...]
    skipped_fills: tuple[SkippedFill, ...]


def _require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise ValueError(f"required input missing: {label} ({path})")


def load_run_inputs(paths: RunPaths) -> RunStatsInput:
    """Load all inputs for one run.

    Required:
      - run_metadata.json
      - backtest_result.json
      - trace_joined.jsonl

    Optional (may be empty):
      - trades.jsonl
      - skipped_fills.jsonl

    Consistency checks:
      - run_metadata.run_id == backtest_result.run_id
      - run_metadata.trace_schema_version == SCHEMA_VERSION
      - every trace.run_id == run_metadata.run_id
      - every trade.run_id == run_metadata.run_id
      - every skipped_fill.run_id == run_metadata.run_id
      - run_metadata.survivorship_policy is non-empty
    """
    _require_file(paths.run_metadata_json, "run_metadata.json")
    _require_file(paths.backtest_result_json, "backtest_result.json")
    _require_file(paths.trace_joined_jsonl, "trace_joined.jsonl")

    metadata = read_run_metadata_json(paths.run_metadata_json)
    summary = read_backtest_result_json(paths.backtest_result_json)

    if metadata.trace_schema_version != SCHEMA_VERSION:
        raise ValueError(
            f"run_metadata.trace_schema_version {metadata.trace_schema_version!r} "
            f"does not match SCHEMA_VERSION {SCHEMA_VERSION!r}"
        )
    if not metadata.survivorship_policy:
        raise ValueError("run_metadata.survivorship_policy is required")
    if metadata.run_id != summary.run_id:
        raise ValueError(
            f"run_id mismatch: run_metadata={metadata.run_id!r} vs "
            f"backtest_result={summary.run_id!r}"
        )

    traces = tuple(read_traces_jsonl(paths.trace_joined_jsonl))
    if not traces:
        raise ValueError(
            f"trace_joined.jsonl is empty: {paths.trace_joined_jsonl}"
        )
    for t in traces:
        if t.run_id != metadata.run_id:
            raise ValueError(
                f"trace.run_id {t.run_id!r} does not match run_metadata "
                f"{metadata.run_id!r}"
            )
        if t.trace_schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"trace.trace_schema_version {t.trace_schema_version!r} "
                f"does not match SCHEMA_VERSION {SCHEMA_VERSION!r}"
            )

    trades: tuple[Trade, ...] = ()
    if paths.trades_jsonl.exists():
        trades = tuple(read_trades_jsonl(paths.trades_jsonl))
        for t in trades:
            if t.run_id != metadata.run_id:
                raise ValueError(
                    f"trade.run_id {t.run_id!r} does not match run_metadata "
                    f"{metadata.run_id!r}"
                )

    skipped: tuple[SkippedFill, ...] = ()
    if paths.skipped_fills_jsonl.exists():
        skipped = tuple(read_skipped_fills_jsonl(paths.skipped_fills_jsonl))
        for s in skipped:
            if s.run_id != metadata.run_id:
                raise ValueError(
                    f"skipped_fill.run_id {s.run_id!r} does not match "
                    f"run_metadata {metadata.run_id!r}"
                )

    return RunStatsInput(
        paths=paths,
        run_metadata=metadata,
        backtest_result_summary=summary,
        traces=traces,
        trades=trades,
        skipped_fills=skipped,
    )


__all__ = ["RunStatsInput", "load_run_inputs"]
