"""Backtest engine core (PR-S3 MVP).

This file does NOT contain trade rules. It consumes externally-supplied
actions and:

1. Validates the fill contract
       decision at T close  ->  fill at T+1 open
   (BACKTEST_CONTRACT.md S0 D-3..D-6 / CALENDAR.md S0 D-3..D-5).
2. Produces a list of ``Trade`` records, applying fee + slippage.
3. Skips fills when the next bar is unfillable
   (``checks.is_unfillable``: halted / special_quote / circuit_breaker /
   volume / turnover floors).

The engine accepts the following action strings. THESE ARE TEST-ONLY
ACTIONS, not trading rules and not a recommendation to do anything in
real markets:

    "enter_long" | "buy"         -> open a long position if flat
    "exit_long"  | "sell_to_close" -> close an existing long position
    "no_position" | "hold" | "observe_only" -> no action

Same-close fill is rejected: ``assumed_fill_bar="same_close"`` raises
``ValueError`` (BACKTEST_CONTRACT.md S0 D-4 / S2-2 / pytest
``test_same_close_fill_forbidden``).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from kabu.backtest.checks import is_unfillable
from kabu.backtest.fill import (
    compute_fee,
    compute_long_entry_fill_price,
    compute_long_exit_fill_price,
    compute_slippage_cost,
)
from kabu.backtest.trade import Position, Trade
from kabu.data.source import OHLCBar
from kabu.decision_trace import (
    ASSUMED_FILL_BAR_NEXT_OPEN,
    DEFAULT_LATENCY_BARS,
    Trace,
)


# Acceptable action strings. These are TEST-ONLY mappings, not a rule.
_ENTER_ACTIONS = frozenset({"enter_long", "buy"})
_EXIT_ACTIONS = frozenset({"exit_long", "sell_to_close"})
_NOOP_ACTIONS = frozenset({"no_position", "hold", "observe_only", "not_evaluated"})


@dataclass(frozen=True)
class ScriptedDecision:
    """Test-only decision input for the engine.

    NOT a trading rule. NOT a recommendation. ``ScriptedDecision`` exists
    so engine tests can drive the contract without coupling to any rule
    implementation.
    """

    bar_ts: datetime
    action: str

    def __post_init__(self) -> None:
        if self.bar_ts.tzinfo is None or self.bar_ts.tzinfo.utcoffset(self.bar_ts) is None:
            raise ValueError("ScriptedDecision.bar_ts must be timezone-aware")
        norm = self.action.lower()
        if norm not in _ENTER_ACTIONS | _EXIT_ACTIONS | _NOOP_ACTIONS:
            raise ValueError(
                f"unknown ScriptedDecision.action {self.action!r}; "
                f"see kabu.backtest.engine for the allowed set"
            )


@dataclass(frozen=True)
class SkippedFill:
    """A decision the engine could not act on, with a stable reason code."""

    decision_ts: datetime
    intended_action: str
    reason: str  # "no_next_bar" | "halted" | "below_lot_size" | etc.


@dataclass(frozen=True)
class BacktestResult:
    run_id: str
    trades: tuple[Trade, ...]
    closing_positions: tuple[Position, ...]
    skipped: tuple[SkippedFill, ...]
    initial_cash_jpy: float
    final_cash_jpy: float
    trace_jsonl_path: str


# --- Helpers -----------------------------------------------------------------


def _classify(action: str) -> Literal["enter", "exit", "noop"]:
    norm = action.lower()
    if norm in _ENTER_ACTIONS:
        return "enter"
    if norm in _EXIT_ACTIONS:
        return "exit"
    if norm in _NOOP_ACTIONS:
        return "noop"
    raise ValueError(f"unknown action {action!r}")


def _index_bars_by_ts(bars: Sequence[OHLCBar]) -> dict[datetime, int]:
    return {bar.bar_ts: i for i, bar in enumerate(bars)}


def _trace_key_for_bar(symbol: str, bar_ts: datetime) -> str:
    return f"{symbol}@{bar_ts.isoformat()}"


# --- Core engine -------------------------------------------------------------


def run_backtest(
    *,
    bars: Sequence[OHLCBar],
    decisions: Sequence[ScriptedDecision],
    cost,
    run_id: str,
    trace_jsonl_path: str | Path,
    assumed_fill_bar: str = ASSUMED_FILL_BAR_NEXT_OPEN,
    latency_bars: int = DEFAULT_LATENCY_BARS,
    initial_cash_jpy: float = 10_000_000.0,
    lot_size: int = 100,
    target_jpy_per_trade: float = 1_000_000.0,
    min_volume: int = 1,
    min_turnover_jpy: float = 1.0,
) -> BacktestResult:
    """Run a backtest.

    ``cost`` is a ``kabu.decision_trace_build.CostAssumptions``. We accept
    it positionally-named (no specific import here to avoid cycles).

    ``trace_jsonl_path`` is mandatory (it is stamped onto every Trade for
    reproducibility -- ``test_trace_jsonl_path_required_for_trades``).
    """
    # --- contract ------------------------------------------------------------
    if assumed_fill_bar != ASSUMED_FILL_BAR_NEXT_OPEN:
        raise ValueError(
            f"assumed_fill_bar must be {ASSUMED_FILL_BAR_NEXT_OPEN!r} in MVP "
            f"(BACKTEST_CONTRACT.md S0 D-4 / D-5). same-close fill is forbidden."
        )
    if latency_bars != DEFAULT_LATENCY_BARS:
        raise ValueError(
            f"latency_bars must be {DEFAULT_LATENCY_BARS} in MVP "
            f"(BACKTEST_CONTRACT.md S0 D-6)"
        )
    if not run_id:
        raise ValueError("run_id is required")
    trace_jsonl_path_str = str(trace_jsonl_path)
    if not trace_jsonl_path_str:
        raise ValueError("trace_jsonl_path is required (stamped on each Trade)")
    if lot_size <= 0:
        raise ValueError("lot_size must be > 0")
    if target_jpy_per_trade <= 0:
        raise ValueError("target_jpy_per_trade must be > 0")

    # --- iterate decisions ---------------------------------------------------
    bars_sorted = list(bars)
    bars_sorted.sort(key=lambda b: b.bar_ts)
    bar_index = _index_bars_by_ts(bars_sorted)

    trades: list[Trade] = []
    skipped: list[SkippedFill] = []
    open_position: Optional[Position] = None
    cash = initial_cash_jpy
    next_trade_seq = 0

    for d in sorted(decisions, key=lambda x: x.bar_ts):
        kind = _classify(d.action)
        if kind == "noop":
            continue

        idx = bar_index.get(d.bar_ts)
        if idx is None:
            skipped.append(
                SkippedFill(
                    decision_ts=d.bar_ts,
                    intended_action=d.action,
                    reason="decision_bar_not_found",
                )
            )
            continue
        if idx + latency_bars >= len(bars_sorted):
            skipped.append(
                SkippedFill(
                    decision_ts=d.bar_ts,
                    intended_action=d.action,
                    reason="no_next_bar",
                )
            )
            continue

        next_bar = bars_sorted[idx + latency_bars]
        unfillable = is_unfillable(
            next_bar,
            min_volume=min_volume,
            min_turnover_jpy=min_turnover_jpy,
        )
        if unfillable is not None:
            skipped.append(
                SkippedFill(
                    decision_ts=d.bar_ts,
                    intended_action=d.action,
                    reason=unfillable,
                )
            )
            continue

        symbol = next_bar.symbol

        if kind == "enter":
            if open_position is not None:
                # Already long: ignore the redundant entry but record it.
                skipped.append(
                    SkippedFill(
                        decision_ts=d.bar_ts,
                        intended_action=d.action,
                        reason="already_long",
                    )
                )
                continue
            entry_price = compute_long_entry_fill_price(
                next_bar.open, cost.slippage_bps
            )
            qty = int(target_jpy_per_trade // entry_price // lot_size) * lot_size
            if qty <= 0:
                skipped.append(
                    SkippedFill(
                        decision_ts=d.bar_ts,
                        intended_action=d.action,
                        reason="below_lot_size",
                    )
                )
                continue
            notional = entry_price * qty
            fee = compute_fee(notional, cost.fee_bps, cost.fee_fixed_jpy)
            slip = compute_slippage_cost(next_bar.open, entry_price, qty)
            cash -= notional + fee
            trade_id = f"{run_id}-{next_trade_seq:05d}"
            next_trade_seq += 1
            entry_trace_key = _trace_key_for_bar(symbol, d.bar_ts)
            trade = Trade(
                trade_id=trade_id,
                run_id=run_id,
                symbol=symbol,
                side="long",
                quantity=qty,
                entry_decision_ts=d.bar_ts,
                entry_fill_ts=next_bar.bar_ts,
                entry_price=entry_price,
                entry_trace_key=entry_trace_key,
                trace_jsonl_path=trace_jsonl_path_str,
                fee_jpy=fee,
                slippage_jpy=slip,
            )
            trades.append(trade)
            open_position = Position(
                symbol=symbol,
                quantity=qty,
                avg_price=entry_price,
                opened_at=next_bar.bar_ts,
                source_trace_key=entry_trace_key,
            )

        elif kind == "exit":
            if open_position is None:
                skipped.append(
                    SkippedFill(
                        decision_ts=d.bar_ts,
                        intended_action=d.action,
                        reason="not_long",
                    )
                )
                continue
            exit_price = compute_long_exit_fill_price(
                next_bar.open, cost.slippage_bps
            )
            qty = open_position.quantity
            notional = exit_price * qty
            fee = compute_fee(notional, cost.fee_bps, cost.fee_fixed_jpy)
            slip = compute_slippage_cost(next_bar.open, exit_price, qty)
            cash += notional - fee
            # Update the latest open trade with exit info + PnL.
            entry_trade = trades[-1]
            gross = (exit_price - entry_trade.entry_price) * qty
            net = gross - (entry_trade.fee_jpy + fee)
            updated = _replace_trade(
                entry_trade,
                exit_decision_ts=d.bar_ts,
                exit_fill_ts=next_bar.bar_ts,
                exit_price=exit_price,
                exit_trace_key=_trace_key_for_bar(symbol, d.bar_ts),
                exit_reason="scripted_exit",
                fee_jpy=entry_trade.fee_jpy + fee,
                slippage_jpy=entry_trade.slippage_jpy + slip,
                gross_pnl_jpy=gross,
                net_pnl_jpy=net,
            )
            trades[-1] = updated
            open_position = None

    # --- finalize ------------------------------------------------------------
    closing_positions: tuple[Position, ...] = (
        (open_position,) if open_position is not None else ()
    )
    if open_position is not None:
        # Mark-to-market against the last bar's close.
        last_bar = bars_sorted[-1]
        unrealized_value = last_bar.close * open_position.quantity
    else:
        unrealized_value = 0.0
    final_cash = cash + unrealized_value

    return BacktestResult(
        run_id=run_id,
        trades=tuple(trades),
        closing_positions=closing_positions,
        skipped=tuple(skipped),
        initial_cash_jpy=initial_cash_jpy,
        final_cash_jpy=final_cash,
        trace_jsonl_path=trace_jsonl_path_str,
    )


def _replace_trade(trade: Trade, **changes) -> Trade:
    """Re-build a Trade dataclass with overrides."""
    base = {
        "trade_id": trade.trade_id,
        "run_id": trade.run_id,
        "symbol": trade.symbol,
        "side": trade.side,
        "quantity": trade.quantity,
        "entry_decision_ts": trade.entry_decision_ts,
        "entry_fill_ts": trade.entry_fill_ts,
        "entry_price": trade.entry_price,
        "entry_trace_key": trade.entry_trace_key,
        "trace_jsonl_path": trade.trace_jsonl_path,
        "fee_jpy": trade.fee_jpy,
        "slippage_jpy": trade.slippage_jpy,
        "exit_decision_ts": trade.exit_decision_ts,
        "exit_fill_ts": trade.exit_fill_ts,
        "exit_price": trade.exit_price,
        "exit_trace_key": trade.exit_trace_key,
        "exit_reason": trade.exit_reason,
        "gross_pnl_jpy": trade.gross_pnl_jpy,
        "net_pnl_jpy": trade.net_pnl_jpy,
    }
    base.update(changes)
    return Trade(**base)


def decisions_from_traces(traces: Iterable[Trace]) -> list[ScriptedDecision]:
    """Convert traces into engine-input decisions.

    The engine treats each trace's ``decision.final_action`` as the
    action for that bar. PR-S2 only emits ``"observe_only"``, so this
    path triggers no fills until later PRs introduce a real rule. This
    function is a convenience wrapper for tests that exercise the
    trace-driven path.
    """
    return [
        ScriptedDecision(bar_ts=t.bar_ts, action=t.slices.decision.final_action)
        for t in traces
    ]
