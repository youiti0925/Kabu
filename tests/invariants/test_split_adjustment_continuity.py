"""Invariant: technical indicators on adjusted close stay continuous through a split.

Policy: BACKTEST_CONTRACT.md S0 D-9 / S5-2 / SCHEMA.md S0 D-9.

Strategy:
- Build a synthetic series where a 2-for-1 split happens at index ``s``.
- The RAW close drops by half at ``s``.
- The ADJUSTED close (back-adjusted: pre-split values are halved) remains
  continuous.
- An indicator computed on the adjusted series must show no ex-day jump.
- The same indicator on the RAW series MUST show a discontinuity, proving
  the test discriminates real misbehavior.
"""

from __future__ import annotations

import math

from kabu.indicators.sma import sma


def _build_series(n: int = 60, split_at: int = 30, split_ratio: float = 2.0):
    """Return (raw_close, adj_close) where the split lands at ``split_at``."""
    raw = [100.0 + 0.5 * i for i in range(split_at)]
    raw_post = [raw[-1] / split_ratio + 0.5 * i for i in range(n - split_at)]
    raw.extend(raw_post)
    # back-adjust: pre-split values divided by split_ratio so the level
    # before and after the split sits on the same scale.
    adj = [v / split_ratio for v in raw[:split_at]] + raw[split_at:]
    return raw, adj


def test_sma_on_adjusted_is_continuous_across_split() -> None:
    raw, adj = _build_series(n=60, split_at=30, split_ratio=2.0)
    sma_adj = sma(adj, window=5)
    s = 30
    before = sma_adj[s - 1]
    after = sma_adj[s]
    assert before is not None and after is not None
    # A continuous, slowly-rising adjusted series should not jump by more
    # than the inherent SMA shift (a small fraction of the level).
    assert math.isclose(before, after, rel_tol=0.02), (
        f"adjusted SMA jumped across split: {before} -> {after}"
    )


def test_sma_on_raw_close_jumps_across_split() -> None:
    """Sanity: the test discriminates -- raw series MUST jump."""
    raw, adj = _build_series(n=60, split_at=30, split_ratio=2.0)
    sma_raw = sma(raw, window=5)
    s = 30
    before = sma_raw[s - 1]
    after = sma_raw[s + 4]  # window has fully rotated past the split
    assert before is not None and after is not None
    assert after < before * 0.7, (
        f"raw SMA failed to drop across split: {before} -> {after}"
    )
