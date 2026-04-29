"""I/O for Trade / SkippedFill / BacktestResult (P3.5).

P3.5 fixes the on-disk format that PR-S4 (trace-stats) will read. The
contract is:

- Trade            -> ``trades.jsonl``        (one record per line)
- SkippedFill      -> ``skipped_fills.jsonl`` (one record per line)
- BacktestResult   -> ``backtest_result.json`` (summary + file references)

The summary file does NOT carry the body of trades / skipped fills; the
canonical body lives in the JSONL files. This keeps stats input cheap
to scan and trades append-only.

Datetimes are encoded as ISO 8601 strings preserving timezone. Readers
re-parse via ``datetime.fromisoformat``.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from kabu.backtest.engine import BacktestResult, SkippedFill
from kabu.backtest.trade import Trade


# --- Encode helpers ----------------------------------------------------------


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


def _parse_dt(value: Any, name: str) -> datetime:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be ISO 8601 string, got {type(value).__name__}")
    return datetime.fromisoformat(value)


def _parse_dt_optional(value: Any, name: str) -> Optional[datetime]:
    if value is None:
        return None
    return _parse_dt(value, name)


# --- Trade JSONL -------------------------------------------------------------


_TRADE_REQUIRED = (
    "trade_id",
    "run_id",
    "symbol",
    "side",
    "quantity",
    "entry_decision_ts",
    "entry_fill_ts",
    "entry_price",
    "entry_trace_key",
    "trace_jsonl_path",
)


def trade_to_dict(trade: Trade) -> dict[str, Any]:
    return _enc(asdict(trade))  # type: ignore[return-value]


def trade_from_dict(d: dict[str, Any]) -> Trade:
    for required in _TRADE_REQUIRED:
        if required not in d:
            raise ValueError(f"trade.{required} is required")
        if isinstance(d[required], str) and not d[required] and required not in (
            # numeric / non-string keys handled below
        ):
            raise ValueError(f"trade.{required} must be non-empty")
    if not d.get("trace_jsonl_path"):
        raise ValueError("trade.trace_jsonl_path is required (non-empty)")
    if not d.get("run_id"):
        raise ValueError("trade.run_id is required (non-empty)")
    if not d.get("symbol"):
        raise ValueError("trade.symbol is required (non-empty)")
    return Trade(
        trade_id=d["trade_id"],
        run_id=d["run_id"],
        symbol=d["symbol"],
        side=d["side"],
        quantity=int(d["quantity"]),
        entry_decision_ts=_parse_dt(d["entry_decision_ts"], "trade.entry_decision_ts"),
        entry_fill_ts=_parse_dt(d["entry_fill_ts"], "trade.entry_fill_ts"),
        entry_price=float(d["entry_price"]),
        entry_trace_key=d["entry_trace_key"],
        trace_jsonl_path=d["trace_jsonl_path"],
        fee_jpy=float(d.get("fee_jpy", 0.0)),
        slippage_jpy=float(d.get("slippage_jpy", 0.0)),
        exit_decision_ts=_parse_dt_optional(
            d.get("exit_decision_ts"), "trade.exit_decision_ts"
        ),
        exit_fill_ts=_parse_dt_optional(d.get("exit_fill_ts"), "trade.exit_fill_ts"),
        exit_price=(float(d["exit_price"]) if d.get("exit_price") is not None else None),
        exit_trace_key=d.get("exit_trace_key"),
        exit_reason=d.get("exit_reason"),
        gross_pnl_jpy=(
            float(d["gross_pnl_jpy"]) if d.get("gross_pnl_jpy") is not None else None
        ),
        net_pnl_jpy=(
            float(d["net_pnl_jpy"]) if d.get("net_pnl_jpy") is not None else None
        ),
    )


def write_trades_jsonl(path: str | Path, trades: Iterable[Trade]) -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with p.open("w", encoding="utf-8") as f:
        for t in trades:
            f.write(json.dumps(trade_to_dict(t), ensure_ascii=False))
            f.write("\n")
            n += 1
    return n


def read_trades_jsonl(path: str | Path) -> Iterator[Trade]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            yield trade_from_dict(json.loads(line))


# --- SkippedFill JSONL -------------------------------------------------------


_SKIPPED_REQUIRED = (
    "run_id",
    "symbol",
    "decision_ts",
    "attempted_fill_ts",
    "intended_action",
    "reason",
)


def skipped_fill_to_dict(skipped: SkippedFill) -> dict[str, Any]:
    return _enc(asdict(skipped))  # type: ignore[return-value]


def skipped_fill_from_dict(d: dict[str, Any]) -> SkippedFill:
    missing = [k for k in _SKIPPED_REQUIRED if k not in d]
    if missing:
        raise ValueError(f"skipped_fill is missing required field(s): {sorted(missing)}")
    if not d["run_id"]:
        raise ValueError("skipped_fill.run_id must be non-empty")
    if not d["symbol"]:
        raise ValueError("skipped_fill.symbol must be non-empty")
    if not d["reason"]:
        raise ValueError("skipped_fill.reason must be non-empty")
    return SkippedFill(
        run_id=d["run_id"],
        symbol=d["symbol"],
        decision_ts=_parse_dt(d["decision_ts"], "skipped_fill.decision_ts"),
        attempted_fill_ts=_parse_dt(
            d["attempted_fill_ts"], "skipped_fill.attempted_fill_ts"
        ),
        intended_action=d["intended_action"],
        reason=d["reason"],
    )


def write_skipped_fills_jsonl(
    path: str | Path, skipped: Iterable[SkippedFill]
) -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with p.open("w", encoding="utf-8") as f:
        for s in skipped:
            f.write(json.dumps(skipped_fill_to_dict(s), ensure_ascii=False))
            f.write("\n")
            n += 1
    return n


def read_skipped_fills_jsonl(path: str | Path) -> Iterator[SkippedFill]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            yield skipped_fill_from_dict(json.loads(line))


# --- BacktestResultSummary JSON ----------------------------------------------


@dataclass(frozen=True)
class BacktestResultSummary:
    """Persistable summary view of a BacktestResult.

    The full run output set is:
    - ``backtest_result.json``     <- this dataclass (summary + paths)
    - ``trades.jsonl``             <- Trade body
    - ``skipped_fills.jsonl``      <- SkippedFill body

    Stats (PR-S4) reads ``trades.jsonl`` directly. The summary is mainly
    a manifest: counts, cash deltas, and pointers to the body files.
    """

    run_id: str
    created_at: datetime
    initial_cash_jpy: float
    final_cash_jpy: float
    trade_count: int
    skipped_count: int
    open_position_count: int
    trace_jsonl_path: str
    trades_jsonl_path: str
    skipped_fills_jsonl_path: str

    def __post_init__(self) -> None:
        for name in (
            "run_id",
            "trace_jsonl_path",
            "trades_jsonl_path",
            "skipped_fills_jsonl_path",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"BacktestResultSummary.{name} must be non-empty")
        if self.created_at.tzinfo is None or self.created_at.tzinfo.utcoffset(
            self.created_at
        ) is None:
            raise ValueError("BacktestResultSummary.created_at must be timezone-aware")
        if self.trade_count < 0:
            raise ValueError("trade_count must be >= 0")
        if self.skipped_count < 0:
            raise ValueError("skipped_count must be >= 0")
        if self.open_position_count < 0:
            raise ValueError("open_position_count must be >= 0")


def summarize_backtest_result(
    result: BacktestResult,
    *,
    created_at: datetime,
    trades_jsonl_path: str | Path,
    skipped_fills_jsonl_path: str | Path,
) -> BacktestResultSummary:
    return BacktestResultSummary(
        run_id=result.run_id,
        created_at=created_at,
        initial_cash_jpy=result.initial_cash_jpy,
        final_cash_jpy=result.final_cash_jpy,
        trade_count=len(result.trades),
        skipped_count=len(result.skipped),
        open_position_count=len(result.closing_positions),
        trace_jsonl_path=str(result.trace_jsonl_path),
        trades_jsonl_path=str(trades_jsonl_path),
        skipped_fills_jsonl_path=str(skipped_fills_jsonl_path),
    )


def backtest_result_summary_to_dict(s: BacktestResultSummary) -> dict[str, Any]:
    return _enc(asdict(s))  # type: ignore[return-value]


_SUMMARY_REQUIRED = (
    "run_id",
    "created_at",
    "initial_cash_jpy",
    "final_cash_jpy",
    "trade_count",
    "skipped_count",
    "open_position_count",
    "trace_jsonl_path",
    "trades_jsonl_path",
    "skipped_fills_jsonl_path",
)


def backtest_result_summary_from_dict(d: dict[str, Any]) -> BacktestResultSummary:
    missing = [k for k in _SUMMARY_REQUIRED if k not in d]
    if missing:
        raise ValueError(
            f"backtest_result is missing required field(s): {sorted(missing)}"
        )
    return BacktestResultSummary(
        run_id=d["run_id"],
        created_at=_parse_dt(d["created_at"], "backtest_result.created_at"),
        initial_cash_jpy=float(d["initial_cash_jpy"]),
        final_cash_jpy=float(d["final_cash_jpy"]),
        trade_count=int(d["trade_count"]),
        skipped_count=int(d["skipped_count"]),
        open_position_count=int(d["open_position_count"]),
        trace_jsonl_path=d["trace_jsonl_path"],
        trades_jsonl_path=d["trades_jsonl_path"],
        skipped_fills_jsonl_path=d["skipped_fills_jsonl_path"],
    )


def write_backtest_result_json(
    path: str | Path, summary: BacktestResultSummary
) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(
            backtest_result_summary_to_dict(summary),
            f,
            ensure_ascii=False,
            indent=2,
        )
    return p.resolve()


def read_backtest_result_json(path: str | Path) -> BacktestResultSummary:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        return backtest_result_summary_from_dict(json.load(f))


# --- Convenience: write all three files at once ------------------------------


def write_backtest_outputs(
    *,
    paths,
    result: BacktestResult,
    created_at: datetime,
) -> BacktestResultSummary:
    """Write trades.jsonl, skipped_fills.jsonl, and backtest_result.json.

    ``paths`` should be a ``kabu.run_paths.RunPaths``. We do not import
    it here to avoid a hard cycle; duck typing is enough -- we only
    use ``trades_jsonl``, ``skipped_fills_jsonl``, ``backtest_result_json``,
    and ``ensure_run_dir`` attributes.
    """
    paths.ensure_run_dir()
    write_trades_jsonl(paths.trades_jsonl, result.trades)
    write_skipped_fills_jsonl(paths.skipped_fills_jsonl, result.skipped)
    summary = summarize_backtest_result(
        result,
        created_at=created_at,
        trades_jsonl_path=str(paths.trades_jsonl),
        skipped_fills_jsonl_path=str(paths.skipped_fills_jsonl),
    )
    write_backtest_result_json(paths.backtest_result_json, summary)
    return summary


__all__ = [
    "BacktestResultSummary",
    "backtest_result_summary_from_dict",
    "backtest_result_summary_to_dict",
    "read_backtest_result_json",
    "read_skipped_fills_jsonl",
    "read_trades_jsonl",
    "skipped_fill_from_dict",
    "skipped_fill_to_dict",
    "summarize_backtest_result",
    "trade_from_dict",
    "trade_to_dict",
    "write_backtest_outputs",
    "write_backtest_result_json",
    "write_skipped_fills_jsonl",
    "write_trades_jsonl",
]
