"""``future_outcome`` post-processing pipeline (PR-S3 MVP).

Contract references:
- POINT_IN_TIME.md 3-4 / 3-7: ``future_outcome`` is computed AFTER the
  fact and is NEVER consumed by ``decision_trace_build.build_trace``.
- SCHEMA.md S6 / 7-2: backfill records live in a SEPARATE JSONL file
  (e.g. ``runs/<run_id>/outcome_backfill.jsonl``) from ``trace_raw.jsonl``.
- SCHEMA.md S0 D-10: ``forward_return_basis`` is required when present.

This module is intentionally independent of ``decision_trace_build``.
The ``test_future_outcome_backfill_separate_from_raw_trace`` test
verifies the structural separation.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

from kabu.data.source import OHLCBar
from kabu.decision_trace import FutureOutcomeSlice, Trace, TraceSlices


ForwardReturnBasis = Literal["close_to_close", "open_to_close", "open_to_open"]


# --- Dataclasses --------------------------------------------------------------


@dataclass(frozen=True)
class TraceKey:
    """Stable identifier for joining backfill against trace_raw."""

    run_id: str
    symbol: str
    bar_ts: datetime

    def __post_init__(self) -> None:
        for field_name in ("run_id", "symbol"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"TraceKey.{field_name} must be non-empty")
        if self.bar_ts.tzinfo is None or self.bar_ts.tzinfo.utcoffset(self.bar_ts) is None:
            raise ValueError("TraceKey.bar_ts must be timezone-aware")


@dataclass(frozen=True)
class OutcomeBackfillRecord:
    """One row of ``outcome_backfill.jsonl``.

    A record is keyed by (run_id, symbol, bar_ts) and carries a fully-
    constructed ``FutureOutcomeSlice``.
    """

    trace_key: TraceKey
    outcome: FutureOutcomeSlice


# --- Computation --------------------------------------------------------------


def _idx_by_ts(bars: Sequence[OHLCBar]) -> dict[datetime, int]:
    return {b.bar_ts: i for i, b in enumerate(bars)}


def enrich_future_outcomes(
    traces: Sequence[Trace],
    bars_by_symbol: Mapping[str, Sequence[OHLCBar]],
    *,
    horizon_bars: Sequence[int] = (1, 5, 20),
    forward_return_basis: ForwardReturnBasis = "close_to_close",
) -> list[OutcomeBackfillRecord]:
    """Compute forward returns + MFE / MAE for each trace.

    Skips a trace if there are not enough future bars for the maximum
    requested horizon. The decision builder MUST NOT call this; it is
    intentionally located in a separate module.
    """
    if not horizon_bars:
        raise ValueError("horizon_bars must be non-empty")
    if any(h <= 0 for h in horizon_bars):
        raise ValueError("horizon_bars must be all positive")
    horizons = tuple(sorted(set(horizon_bars)))
    max_h = horizons[-1]

    out: list[OutcomeBackfillRecord] = []
    indexes = {sym: _idx_by_ts(bars) for sym, bars in bars_by_symbol.items()}

    for trace in traces:
        bars = bars_by_symbol.get(trace.symbol)
        if not bars:
            continue
        idx_map = indexes[trace.symbol]
        i = idx_map.get(trace.bar_ts)
        if i is None:
            continue
        if i + max_h >= len(bars):
            # Insufficient future bars: skip rather than fabricate.
            continue
        anchor = bars[i]
        ret_at = {}
        for h in horizons:
            future = bars[i + h]
            anchor_p, future_p = _basis_pair(anchor, future, forward_return_basis)
            if anchor_p == 0:
                continue
            ret_at[h] = (future_p - anchor_p) / anchor_p

        # MFE / MAE relative to the anchor close, over (i+1 .. i+max_h]
        mfe = None
        mae = None
        anchor_close = anchor.close
        for j in range(i + 1, i + max_h + 1):
            if anchor_close == 0:
                break
            ret = (bars[j].close - anchor_close) / anchor_close
            mfe = ret if mfe is None else max(mfe, ret)
            mae = ret if mae is None else min(mae, ret)

        forward_return_end_ts = bars[i + max_h].bar_ts

        outcome = FutureOutcomeSlice(
            forward_return_basis=forward_return_basis,
            forward_return_1d=ret_at.get(1),
            forward_return_5d=ret_at.get(5),
            forward_return_20d=ret_at.get(20),
            forward_return_horizon_bars=horizons,
            mfe=mfe,
            mae=mae,
            hit_stop=None,
            forward_return_end_ts=forward_return_end_ts,
        )
        key = TraceKey(
            run_id=trace.run_id,
            symbol=trace.symbol,
            bar_ts=trace.bar_ts,
        )
        out.append(OutcomeBackfillRecord(trace_key=key, outcome=outcome))
    return out


def _basis_pair(anchor: OHLCBar, future: OHLCBar, basis: ForwardReturnBasis) -> tuple[float, float]:
    if basis == "close_to_close":
        return anchor.close, future.close
    if basis == "open_to_close":
        return anchor.open, future.close
    if basis == "open_to_open":
        return anchor.open, future.open
    raise ValueError(f"unknown forward_return_basis: {basis!r}")


# --- I/O ----------------------------------------------------------------------


def _encode(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, tuple):
        return [_encode(x) for x in obj]
    if isinstance(obj, list):
        return [_encode(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _encode(v) for k, v in obj.items()}
    return obj


def write_outcome_backfill_jsonl(
    path: str | Path, records: Iterable[OutcomeBackfillRecord]
) -> int:
    """Append-only JSONL writer.

    The path MUST be different from the trace_raw JSONL path; that is
    enforced as a defensive check here -- the structural separation is
    re-tested in ``test_future_outcome_backfill_separate_from_raw_trace``.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with p.open("w", encoding="utf-8") as f:
        for rec in records:
            payload = {
                "trace_key": _encode(asdict(rec.trace_key)),
                "outcome": _encode(asdict(rec.outcome)),
            }
            f.write(json.dumps(payload, ensure_ascii=False))
            f.write("\n")
            n += 1
    return n


def read_outcome_backfill_jsonl(path: str | Path) -> Iterator[OutcomeBackfillRecord]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            d = json.loads(line)
            tk = d["trace_key"]
            out = d["outcome"]
            key = TraceKey(
                run_id=tk["run_id"],
                symbol=tk["symbol"],
                bar_ts=datetime.fromisoformat(tk["bar_ts"]),
            )
            end_ts = out.get("forward_return_end_ts")
            outcome = FutureOutcomeSlice(
                forward_return_basis=out["forward_return_basis"],
                forward_return_1d=out.get("forward_return_1d"),
                forward_return_5d=out.get("forward_return_5d"),
                forward_return_20d=out.get("forward_return_20d"),
                forward_return_horizon_bars=tuple(
                    out.get("forward_return_horizon_bars") or ()
                ),
                mfe=out.get("mfe"),
                mae=out.get("mae"),
                hit_stop=out.get("hit_stop"),
                outcome_label_static=out.get("outcome_label_static"),
                outcome_label_atr_norm=out.get("outcome_label_atr_norm"),
                forward_return_end_ts=(
                    datetime.fromisoformat(end_ts) if end_ts is not None else None
                ),
            )
            yield OutcomeBackfillRecord(trace_key=key, outcome=outcome)


# --- Join ---------------------------------------------------------------------


def join_traces_with_outcomes(
    traces: Sequence[Trace],
    backfill: Iterable[OutcomeBackfillRecord],
) -> list[Trace]:
    """Return new Trace instances with future_outcome populated.

    Trace immutability is preserved -- new ``Trace`` instances are
    constructed; original traces are not mutated.
    """
    by_key: dict[tuple[str, str, datetime], FutureOutcomeSlice] = {}
    for rec in backfill:
        by_key[
            (rec.trace_key.run_id, rec.trace_key.symbol, rec.trace_key.bar_ts)
        ] = rec.outcome

    out: list[Trace] = []
    for t in traces:
        key = (t.run_id, t.symbol, t.bar_ts)
        outcome = by_key.get(key)
        if outcome is None:
            out.append(t)
            continue
        new_slices = TraceSlices(
            market=t.slices.market,
            technical=t.slices.technical,
            long_term_trend=t.slices.long_term_trend,
            risk_ctx=t.slices.risk_ctx,
            decision=t.slices.decision,
            execution_assumption=t.slices.execution_assumption,
            future_outcome=outcome,
        )
        out.append(_replace_trace_slices(t, new_slices))
    return out


def _replace_trace_slices(t: Trace, slices: TraceSlices) -> Trace:
    return Trace(
        schema_version=t.schema_version,
        trace_schema_version=t.trace_schema_version,
        run_id=t.run_id,
        commit_sha=t.commit_sha,
        created_at=t.created_at,
        symbol=t.symbol,
        market=t.market,
        sector=t.sector,
        interval=t.interval,
        bar_ts=t.bar_ts,
        bar_ts_close=t.bar_ts_close,
        bar_ts_available=t.bar_ts_available,
        universe_snapshot_id=t.universe_snapshot_id,
        data_snapshot_hash=t.data_snapshot_hash,
        slices=slices,
        unavailable_reason=t.unavailable_reason,
    )


__all__ = [
    "OutcomeBackfillRecord",
    "TraceKey",
    "ForwardReturnBasis",
    "enrich_future_outcomes",
    "write_outcome_backfill_jsonl",
    "read_outcome_backfill_jsonl",
    "join_traces_with_outcomes",
]
