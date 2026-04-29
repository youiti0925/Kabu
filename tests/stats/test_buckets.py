"""Bucket-boundary documentation tests.

The boundary values themselves live in ``docs/STATS.md``; this test
verifies that the boundary names defined in code match the documented
set, so that any drift is loudly detected in CI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kabu.stats.buckets import (
    MACD_HIST_BUCKETS,
    RSI_BUCKETS,
    SMA200_DISTANCE_BUCKETS,
    bucket_macd_hist,
    bucket_rsi,
    bucket_sma200_distance,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
STATS_MD = REPO_ROOT / "docs" / "STATS.md"


def test_rsi_bucket_assignments():
    assert bucket_rsi(None) == "unknown"
    assert bucket_rsi(20.0) == "rsi_lt_30"
    assert bucket_rsi(29.999) == "rsi_lt_30"
    assert bucket_rsi(30.0) == "rsi_30_to_50"
    assert bucket_rsi(49.999) == "rsi_30_to_50"
    assert bucket_rsi(50.0) == "rsi_50_to_70"
    assert bucket_rsi(69.999) == "rsi_50_to_70"
    assert bucket_rsi(70.0) == "rsi_gte_70"
    assert bucket_rsi(100.0) == "rsi_gte_70"


def test_sma200_distance_bucket_assignments():
    assert bucket_sma200_distance(None) == "unknown"
    assert bucket_sma200_distance(-0.20) == "below_-10pct"
    assert bucket_sma200_distance(-0.10) == "-10_to_0pct"
    assert bucket_sma200_distance(-0.05) == "-10_to_0pct"
    assert bucket_sma200_distance(0.0) == "0_to_10pct"
    assert bucket_sma200_distance(0.05) == "0_to_10pct"
    assert bucket_sma200_distance(0.10) == "above_10pct"
    assert bucket_sma200_distance(0.5) == "above_10pct"


def test_macd_hist_bucket_assignments():
    assert bucket_macd_hist(None) == "unknown"
    assert bucket_macd_hist(0.0) == "zero"
    assert bucket_macd_hist(1.0) == "positive"
    assert bucket_macd_hist(-1.0) == "negative"


def test_bucket_boundaries_documented():
    """Each bucket label defined in code must appear in docs/STATS.md."""
    assert STATS_MD.exists(), f"docs/STATS.md missing at {STATS_MD}"
    text = STATS_MD.read_text(encoding="utf-8")
    for label in RSI_BUCKETS:
        assert label in text, f"RSI bucket {label!r} missing from docs/STATS.md"
    for label in SMA200_DISTANCE_BUCKETS:
        assert label in text, (
            f"SMA200 distance bucket {label!r} missing from docs/STATS.md"
        )
    for label in MACD_HIST_BUCKETS:
        assert label in text, (
            f"MACD hist bucket {label!r} missing from docs/STATS.md"
        )
