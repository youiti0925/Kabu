"""backtest package for Kabu (PR-S3 MVP).

This package implements a minimal backtest engine. It does NOT contain
trade rules. The engine consumes externally-supplied actions
(``ScriptedDecision`` for tests, or the ``decision.final_action`` carried
on a ``Trace``) and produces ``Trade`` records under the contract:

    decision at T close  ->  fill at T+1 open  (BACKTEST_CONTRACT.md S0 D-3)

All actions accepted by the engine -- including the strings ``"buy"``,
``"sell_to_close"``, ``"enter_long"``, and ``"exit_long"`` -- are
**test-only**. They are NOT a recommendation to buy or sell anything.
The MVP rule is intentionally a placeholder; see PR-S2 / S3 briefs.
"""

from kabu.backtest.engine import (
    BacktestResult,
    ScriptedDecision,
    SkippedFill,
    run_backtest,
)
from kabu.backtest.fill import (
    compute_fee,
    compute_long_entry_fill_price,
    compute_long_exit_fill_price,
)
from kabu.backtest.checks import is_unfillable
from kabu.backtest.trade import Position, Trade

__all__ = [
    "BacktestResult",
    "Position",
    "ScriptedDecision",
    "SkippedFill",
    "Trade",
    "compute_fee",
    "compute_long_entry_fill_price",
    "compute_long_exit_fill_price",
    "is_unfillable",
    "run_backtest",
]
