"""Fill-price computation, fees, and slippage.

PR-S3 contract:
- Fill price uses the **raw** open of the next bar (BACKTEST_CONTRACT.md
  S0 D-9 / S6).
- Slippage is applied in the unfavorable direction for the trader:
  long entry  -> price is bumped UP   by ``slippage_bps`` bps;
  long exit   -> price is bumped DOWN by ``slippage_bps`` bps.
- Fees are proportional ``fee_bps`` plus optional fixed ``fee_fixed_jpy``.
"""

from __future__ import annotations

from typing import Optional

_BPS_DENOM = 10_000.0


def compute_long_entry_fill_price(open_price: float, slippage_bps: float) -> float:
    """raw open + slippage (long entry pays UP)."""
    if open_price <= 0:
        raise ValueError("open_price must be > 0")
    if slippage_bps < 0:
        raise ValueError("slippage_bps must be >= 0")
    return open_price * (1.0 + slippage_bps / _BPS_DENOM)


def compute_long_exit_fill_price(open_price: float, slippage_bps: float) -> float:
    """raw open - slippage (long exit pays DOWN)."""
    if open_price <= 0:
        raise ValueError("open_price must be > 0")
    if slippage_bps < 0:
        raise ValueError("slippage_bps must be >= 0")
    return open_price * (1.0 - slippage_bps / _BPS_DENOM)


def compute_fee(
    notional_jpy: float,
    fee_bps: float,
    fee_fixed_jpy: Optional[float],
) -> float:
    """Fee = ``notional * fee_bps / 10000 + fee_fixed_jpy`` (when set)."""
    if notional_jpy < 0:
        raise ValueError("notional_jpy must be >= 0")
    if fee_bps < 0:
        raise ValueError("fee_bps must be >= 0")
    fee = notional_jpy * fee_bps / _BPS_DENOM
    if fee_fixed_jpy is not None:
        if fee_fixed_jpy < 0:
            raise ValueError("fee_fixed_jpy must be >= 0")
        fee += fee_fixed_jpy
    return fee


def compute_slippage_cost(
    raw_open: float, fill_price: float, quantity: int
) -> float:
    """Absolute JPY cost of slippage relative to raw open."""
    return abs(fill_price - raw_open) * quantity
