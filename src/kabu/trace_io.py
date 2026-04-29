"""JSONL writer / reader for kabu.trace.v1 traces.

Contract references:
- SCHEMA.md S6 (one record per line, append-only, UTF-8, datetimes as ISO 8601).
- SCHEMA.md S0 D-12: top-level ``library_id`` is deprecated; the writer
  never emits it, the reader emits a DeprecationWarning if it is present
  in input and drops the field.
- POINT_IN_TIME.md 3-1: validation triggers on read via dataclass
  ``__post_init__``.

This module deliberately does NOT write into ``runs/``. Callers choose
the path; tests use ``tmp_path``. ``runs/`` and ``data/raw/`` /
``data/cache/`` are blocked by ``scripts/check_no_forbidden_paths.py``.
"""

from __future__ import annotations

import json
import warnings
from collections.abc import Iterable, Iterator
from dataclasses import asdict, fields, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from kabu.decision_trace import (
    BollingerPoint,
    DecisionSlice,
    ExecutionAssumptionSlice,
    FutureOutcomeSlice,
    LongTermTrendSlice,
    MACDPoint,
    MarketSlice,
    RiskCtxSlice,
    SCHEMA_VERSION,
    TechnicalSlice,
    Trace,
    TraceSlices,
)


# --- to-dict -----------------------------------------------------------------


def _encode(obj: Any) -> Any:
    """Serialize datetimes to ISO 8601; leave the rest to ``asdict``."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, tuple):
        return [_encode(x) for x in obj]
    if isinstance(obj, list):
        return [_encode(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _encode(v) for k, v in obj.items()}
    if is_dataclass(obj):
        return _encode(asdict(obj))
    return obj


def trace_to_dict(trace: Trace) -> dict[str, Any]:
    """Convert a Trace to a JSON-serializable dict.

    The returned dict never contains a top-level ``library_id`` key
    (SCHEMA.md S0 D-12).
    """
    raw = _encode(asdict(trace))
    assert isinstance(raw, dict)
    # Defensive: drop anything that may have crept in.
    raw.pop("library_id", None)
    return raw


# --- from-dict ---------------------------------------------------------------


def _parse_datetime(value: Any, name: str) -> datetime:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be ISO 8601 string, got {type(value).__name__}")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} is not ISO 8601: {value!r}") from exc


def _filter_kwargs(cls: Any, data: dict[str, Any]) -> dict[str, Any]:
    """Keep only keys that match a dataclass field name."""
    names = {f.name for f in fields(cls)}
    return {k: v for k, v in data.items() if k in names}


def _market_from_dict(d: dict[str, Any]) -> MarketSlice:
    return MarketSlice(**_filter_kwargs(MarketSlice, d))


def _technical_from_dict(d: dict[str, Any]) -> TechnicalSlice:
    if "adjustment_basis" not in d:
        raise ValueError(
            "technical.adjustment_basis is required (SCHEMA.md S0 D-9)"
        )
    macd = d.get("macd")
    bb = d.get("bb")
    kwargs = _filter_kwargs(TechnicalSlice, d)
    if macd is not None:
        kwargs["macd"] = MACDPoint(**macd)
    if bb is not None:
        kwargs["bb"] = BollingerPoint(**bb)
    return TechnicalSlice(**kwargs)


def _long_term_trend_from_dict(d: dict[str, Any]) -> LongTermTrendSlice:
    return LongTermTrendSlice(**_filter_kwargs(LongTermTrendSlice, d))


def _risk_ctx_from_dict(d: dict[str, Any]) -> RiskCtxSlice:
    kwargs = _filter_kwargs(RiskCtxSlice, d)
    if "blocked_by" in kwargs:
        kwargs["blocked_by"] = tuple(kwargs["blocked_by"])
    if "hold_reason" in kwargs:
        kwargs["hold_reason"] = tuple(kwargs["hold_reason"])
    return RiskCtxSlice(**kwargs)


def _decision_from_dict(d: dict[str, Any]) -> DecisionSlice:
    for required in ("rule_id", "rule_version", "rule_params_hash"):
        if required not in d:
            raise ValueError(
                f"decision.{required} is required (SCHEMA.md S0 D-5)"
            )
    return DecisionSlice(**_filter_kwargs(DecisionSlice, d))


def _execution_from_dict(d: dict[str, Any]) -> ExecutionAssumptionSlice:
    if "assumed_fill_bar" not in d:
        raise ValueError(
            "execution_assumption.assumed_fill_bar is required (SCHEMA.md S0 D-7)"
        )
    if "latency_bars" not in d:
        raise ValueError(
            "execution_assumption.latency_bars is required (SCHEMA.md S0 D-8)"
        )
    return ExecutionAssumptionSlice(**_filter_kwargs(ExecutionAssumptionSlice, d))


def _future_outcome_from_dict(d: dict[str, Any] | None) -> FutureOutcomeSlice | None:
    if d is None:
        return None
    if "forward_return_basis" not in d:
        raise ValueError(
            "future_outcome.forward_return_basis is required when "
            "future_outcome is present (SCHEMA.md S0 D-10)"
        )
    kwargs = _filter_kwargs(FutureOutcomeSlice, d)
    if kwargs.get("forward_return_horizon_bars") is not None:
        kwargs["forward_return_horizon_bars"] = tuple(
            kwargs["forward_return_horizon_bars"]
        )
    end_ts = kwargs.get("forward_return_end_ts")
    if isinstance(end_ts, str):
        kwargs["forward_return_end_ts"] = _parse_datetime(
            end_ts, "future_outcome.forward_return_end_ts"
        )
    return FutureOutcomeSlice(**kwargs)


def _slices_from_dict(d: dict[str, Any]) -> TraceSlices:
    for required in (
        "market",
        "technical",
        "long_term_trend",
        "risk_ctx",
        "decision",
        "execution_assumption",
    ):
        if required not in d:
            raise ValueError(f"slices.{required} is required")
    return TraceSlices(
        market=_market_from_dict(d["market"]),
        technical=_technical_from_dict(d["technical"]),
        long_term_trend=_long_term_trend_from_dict(d["long_term_trend"]),
        risk_ctx=_risk_ctx_from_dict(d["risk_ctx"]),
        decision=_decision_from_dict(d["decision"]),
        execution_assumption=_execution_from_dict(d["execution_assumption"]),
        future_outcome=_future_outcome_from_dict(d.get("future_outcome")),
    )


def trace_from_dict(d: dict[str, Any]) -> Trace:
    """Validate and construct a Trace from a JSON-loaded dict."""
    if "schema_version" not in d:
        raise ValueError(
            "schema_version is required (SCHEMA.md S1-2 / S0 D-1)"
        )
    if d["schema_version"] != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported schema_version: {d['schema_version']!r}; "
            f"this build only reads {SCHEMA_VERSION!r}"
        )

    if "library_id" in d:
        warnings.warn(
            "Top-level 'library_id' is deprecated; library references "
            "now live inside each slice and in run_metadata.libraries[] "
            "(SCHEMA.md S0 D-12 / D-13). The field is being dropped on read.",
            DeprecationWarning,
            stacklevel=2,
        )
        d = {k: v for k, v in d.items() if k != "library_id"}

    if "slices" not in d:
        raise ValueError("trace.slices is required")

    parsed = dict(d)
    for ts_name in ("created_at", "bar_ts", "bar_ts_close", "bar_ts_available"):
        if ts_name not in parsed:
            raise ValueError(f"top-level '{ts_name}' is required")
        parsed[ts_name] = _parse_datetime(parsed[ts_name], ts_name)
    parsed["slices"] = _slices_from_dict(d["slices"])

    return Trace(**_filter_kwargs(Trace, parsed))


# --- file I/O ----------------------------------------------------------------


def write_traces_jsonl(path: str | Path, traces: Iterable[Trace]) -> int:
    """Append-write traces to ``path`` as JSON Lines. Returns count written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for trace in traces:
            d = trace_to_dict(trace)
            f.write(json.dumps(d, ensure_ascii=False))
            f.write("\n")
            n += 1
    return n


def read_traces_jsonl(path: str | Path) -> Iterator[Trace]:
    """Yield traces from a JSONL file. Validates each record on read."""
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            yield trace_from_dict(json.loads(line))


__all__ = [
    "trace_to_dict",
    "trace_from_dict",
    "write_traces_jsonl",
    "read_traces_jsonl",
]
