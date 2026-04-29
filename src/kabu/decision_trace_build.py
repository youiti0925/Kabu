"""Builder for one kabu.trace.v1 trace record.

Contract references:
- POINT_IN_TIME.md 3-7: the builder MUST NOT take ``future_outcome`` as
  input. ``build_trace`` does not declare a ``future_outcome`` parameter
  -- a structural defense backed by ``test_decision_does_not_depend_on_outcome``.
- SCHEMA.md S0 / S4-*: required fields per slice.
- PR-S2 brief: decision is an OBSERVATION marker, not a trade decision.

Inputs:
- ``bars``: a sequence of OHLCBar values, ascending by ``bar_ts``. The
  trace is built for the LAST bar (``bars[-1]``). Indicators run on the
  prefix only -- no future bars are visible by construction.
- top-level metadata (symbol, market, sector, interval, universe / data
  snapshots, run_id, commit_sha) and a placeholder rule.

Outputs:
- A ``Trace`` value. ``future_outcome`` is always ``None`` here; PR-S3 /
  S4 will enrich.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from kabu.data.source import OHLCBar
from kabu.decision_trace import (
    ASSUMED_FILL_BAR_NEXT_OPEN,
    DEFAULT_ADJUSTMENT_BASIS,
    DEFAULT_LATENCY_BARS,
    OBSERVE_ONLY_RULE_ID,
    OBSERVE_ONLY_RULE_VERSION,
    BollingerPoint,
    DecisionSlice,
    ExecutionAssumptionSlice,
    LongTermTrendSlice,
    MACDPoint,
    MarketSlice,
    RiskCtxSlice,
    SCHEMA_VERSION,
    TechnicalSlice,
    Trace,
    TraceSlices,
)
from kabu.indicators.atr import atr as atr_fn
from kabu.indicators.bollinger import bollinger_bands
from kabu.indicators.macd import macd as macd_fn
from kabu.indicators.rsi import rsi as rsi_fn
from kabu.indicators.sma import sma as sma_fn


@dataclass(frozen=True)
class CostAssumptions:
    """Cost parameters that flow through ``execution_assumption``.

    PR-S3 will pick the actual default values; PR-S2 just carries them.
    """

    slippage_bps: float
    fee_bps: float
    fee_fixed_jpy: Optional[float] = None


def hash_rule_params(params: Mapping[str, Any]) -> str:
    """Stable hash of rule parameters for ``decision.rule_params_hash``.

    JSON-serialize with sorted keys so the hash is independent of insertion
    order. Truncated to 16 hex chars (64 bits) -- enough to identify a
    parameter set within a single run.
    """
    blob = json.dumps(dict(params), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return digest[:16]


# --- Slice builders -----------------------------------------------------------


def _build_market_slice(bar: OHLCBar) -> MarketSlice:
    gap_pct: Optional[float] = None
    if bar.prev_close is not None and bar.prev_close != 0:
        gap_pct = (bar.open - bar.prev_close) / bar.prev_close
    return MarketSlice(
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        adj_close=bar.adj_close,
        volume=bar.volume,
        turnover=bar.turnover,
        prev_close=bar.prev_close,
        gap_pct=gap_pct,
    )


def _last_or_none(values: Sequence[Any]) -> Any:
    return values[-1] if values else None


def _build_technical_slice(bars: Sequence[OHLCBar]) -> TechnicalSlice:
    """Compute indicators on adjusted close only (BACKTEST_CONTRACT.md S0 D-9)."""
    closes = [b.adj_close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    raw_closes = [b.close for b in bars]

    sma20 = _last_or_none(sma_fn(closes, 20))
    sma60 = _last_or_none(sma_fn(closes, 60))
    sma200 = _last_or_none(sma_fn(closes, 200))
    rsi14 = _last_or_none(rsi_fn(closes, 14))
    macd_last = _last_or_none(macd_fn(closes))
    bb_last = _last_or_none(bollinger_bands(closes, window=20))
    # ATR uses raw H/L/C (price levels), not the adjusted series.
    atr14 = _last_or_none(atr_fn(highs, lows, raw_closes, window=14))

    macd_point: Optional[MACDPoint]
    if macd_last is None:
        macd_point = None
    else:
        macd_point = MACDPoint(
            line=macd_last.line, signal=macd_last.signal, hist=macd_last.hist
        )

    bb_point: Optional[BollingerPoint]
    if bb_last is None:
        bb_point = None
    else:
        bb_point = BollingerPoint(
            middle=bb_last.middle, upper=bb_last.upper, lower=bb_last.lower
        )

    return TechnicalSlice(
        adjustment_basis=DEFAULT_ADJUSTMENT_BASIS,
        sma20=sma20,
        sma60=sma60,
        sma200=sma200,
        rsi14=rsi14,
        macd=macd_point,
        bb=bb_point,
        atr14=atr14,
    )


def _build_long_term_trend_slice(
    last_bar: OHLCBar, sma200: Optional[float]
) -> LongTermTrendSlice:
    if sma200 is None or sma200 == 0:
        return LongTermTrendSlice(
            close_vs_sma200=None, trend_label="unknown"
        )
    diff = (last_bar.adj_close - sma200) / sma200
    label: str
    if diff > 0:
        label = "above_sma200"
    elif diff < 0:
        label = "below_sma200"
    else:
        label = "unknown"
    return LongTermTrendSlice(
        close_vs_sma200=diff, trend_label=label  # type: ignore[arg-type]
    )


def _build_risk_ctx_slice(unavailable_reason_summary: Optional[str]) -> RiskCtxSlice:
    return RiskCtxSlice(
        blocked_by=(),
        hold_reason=(),
        unavailable_reason_summary=unavailable_reason_summary,
    )


def _build_decision_slice(
    rule_id: str,
    rule_version: str,
    rule_params: Mapping[str, Any],
) -> DecisionSlice:
    """PR-S2 placeholder: observe_only / not_evaluated.

    NO trade signal is produced. ``confidence`` is ``None`` because
    nothing was actually evaluated.
    """
    return DecisionSlice(
        final_action="observe_only",
        technical_only_action="not_evaluated",
        rule_id=rule_id,
        rule_version=rule_version,
        rule_params_hash=hash_rule_params(rule_params),
        confidence=None,
    )


def _build_execution_assumption_slice(
    cost: CostAssumptions,
) -> ExecutionAssumptionSlice:
    return ExecutionAssumptionSlice(
        assumed_fill_bar=ASSUMED_FILL_BAR_NEXT_OPEN,
        latency_bars=DEFAULT_LATENCY_BARS,
        slippage_bps=cost.slippage_bps,
        fee_bps=cost.fee_bps,
        fee_fixed_jpy=cost.fee_fixed_jpy,
        fill_price=None,
        is_realistic=False,
        fill_reason="not_evaluated_in_mvp",
    )


# --- Top-level builder --------------------------------------------------------


def build_trace(
    *,
    bars: Sequence[OHLCBar],
    symbol: str,
    market: str,
    sector: str,
    interval: str,
    universe_snapshot_id: str,
    data_snapshot_hash: str,
    run_id: str,
    commit_sha: str,
    rule_id: str = OBSERVE_ONLY_RULE_ID,
    rule_version: str = OBSERVE_ONLY_RULE_VERSION,
    rule_params: Optional[Mapping[str, Any]] = None,
    cost: CostAssumptions,
    created_at: Optional[datetime] = None,
    unavailable_reason_summary: Optional[str] = None,
) -> Trace:
    """Build one Trace from bars, with bars[-1] as the annotated bar.

    The function intentionally does NOT take ``future_outcome``. Indicators
    are computed on bars only (no future visibility). Decisions are
    placeholders -- this is observation, not trading.
    """
    if not bars:
        raise ValueError("bars must be non-empty")
    last = bars[-1]
    if last.symbol != symbol:
        raise ValueError(
            f"bars[-1].symbol ({last.symbol!r}) does not match "
            f"symbol argument ({symbol!r})"
        )
    if last.interval != interval:
        raise ValueError(
            f"bars[-1].interval ({last.interval!r}) does not match "
            f"interval argument ({interval!r})"
        )

    market_slice = _build_market_slice(last)
    technical_slice = _build_technical_slice(bars)
    long_term_trend_slice = _build_long_term_trend_slice(
        last, technical_slice.sma200
    )
    risk_ctx_slice = _build_risk_ctx_slice(unavailable_reason_summary)
    decision_slice = _build_decision_slice(
        rule_id=rule_id,
        rule_version=rule_version,
        rule_params=dict(rule_params) if rule_params is not None else {},
    )
    execution_slice = _build_execution_assumption_slice(cost)

    slices = TraceSlices(
        market=market_slice,
        technical=technical_slice,
        long_term_trend=long_term_trend_slice,
        risk_ctx=risk_ctx_slice,
        decision=decision_slice,
        execution_assumption=execution_slice,
        future_outcome=None,  # post-processing only; PR-S3 / S4 enrich
    )

    return Trace(
        schema_version=SCHEMA_VERSION,
        trace_schema_version=SCHEMA_VERSION,
        run_id=run_id,
        commit_sha=commit_sha,
        created_at=created_at or datetime.now(tz=timezone.utc),
        symbol=symbol,
        market=market,
        sector=sector,
        interval=interval,
        bar_ts=last.bar_ts,
        bar_ts_close=last.bar_ts_close,
        bar_ts_available=last.bar_ts_available,
        universe_snapshot_id=universe_snapshot_id,
        data_snapshot_hash=data_snapshot_hash,
        slices=slices,
        unavailable_reason=None,
    )


__all__ = [
    "CostAssumptions",
    "build_trace",
    "hash_rule_params",
]
