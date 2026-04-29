"""Invariant: adjusted vs raw price separation survives an ex-dividend day.

PR-S3 simplified version (per brief): just verify the engine uses RAW
open as the fill price and that the indicator side relies on adj_close.
A precise dividend-PnL test will be added when an event_ctx /
ex_dividend_flag is wired up (PR-S7).

Policy: BACKTEST_CONTRACT.md S0 D-9 / S6 / SCHEMA.md S0 D-9.
"""

from __future__ import annotations

import pytest

from kabu.backtest import ScriptedDecision, run_backtest
from kabu.backtest.fill import compute_long_entry_fill_price
from kabu.decision_trace_build import CostAssumptions
from kabu.indicators.sma import sma

from tests.backtest._fixtures import make_bars, replace_bar


def _build_ex_div_series(n=10, ex_idx=4, dividend=10.0):
    """Synthetic series where the raw close drops by ``dividend`` at ``ex_idx``.

    Adjusted close back-adjusts by subtracting ``dividend`` from pre-ex bars
    so the adjusted series stays continuous.
    """
    bars = make_bars(n)
    out = []
    for i, b in enumerate(bars):
        if i < ex_idx:
            new_close = b.close
            new_open = b.open
            new_high = b.high
            new_low = b.low
            new_adj = b.adj_close - dividend
        elif i == ex_idx:
            new_close = b.close - dividend
            new_open = b.open - dividend
            new_high = b.high - dividend
            new_low = b.low - dividend
            new_adj = new_close
        else:
            new_close = b.close - dividend
            new_open = b.open - dividend
            new_high = b.high - dividend
            new_low = b.low - dividend
            new_adj = new_close
        prev_close = out[-1].close if out else None
        out.append(
            replace_bar(
                b,
                open=new_open,
                high=new_high,
                low=new_low,
                close=new_close,
                adj_close=new_adj,
                prev_close=prev_close,
            )
        )
    return out


def test_engine_fill_uses_raw_open_not_adj_close(tmp_path):
    bars = _build_ex_div_series()
    cost = CostAssumptions(slippage_bps=0.0, fee_bps=0.0, fee_fixed_jpy=None)
    decisions = [ScriptedDecision(bar_ts=bars[2].bar_ts, action="enter_long")]
    result = run_backtest(
        bars=bars,
        decisions=decisions,
        cost=cost,
        run_id="r1",
        trace_jsonl_path=tmp_path / "trace_raw.jsonl",
    )
    trade = result.trades[0]
    # With slippage_bps=0, fill price equals next bar's RAW open.
    assert trade.entry_price == pytest.approx(bars[3].open)
    # Sanity: raw open differs from adj_close at this index for our fixture.
    assert bars[3].open != pytest.approx(bars[3].adj_close)


def test_indicators_run_on_adjusted_series_stay_continuous():
    bars = _build_ex_div_series(n=12, ex_idx=4, dividend=10.0)
    adj = [b.adj_close for b in bars]
    raw = [b.close for b in bars]
    sma_adj = sma(adj, window=3)
    sma_raw = sma(raw, window=3)
    # The adjusted SMA should be flat-to-monotone across ex_idx, while the
    # raw SMA shows a drop. We compare the magnitude of the change.
    # Pick indices where both windows are filled and span ex_idx (index 4).
    drop_raw = sma_raw[5] - sma_raw[3]
    drop_adj = sma_adj[5] - sma_adj[3]
    assert drop_raw is not None and drop_adj is not None
    assert drop_raw < drop_adj  # raw drops more than adjusted
