"""Bucket boundaries (PR-S4 MVP).

These are observation buckets. They are NOT trade rules. Users must NOT
read "rsi < 30 -> buy" into them; they only make groups for descriptive
statistics.

If a boundary changes, it is a breaking analytics change -- bump the
analytics version in the report header. See ``docs/STATS.md``.
"""

from __future__ import annotations

from typing import Optional


# --- RSI ---------------------------------------------------------------------

# RSI ranges by half-open intervals (left inclusive, right exclusive),
# except the final upper bucket which includes its boundary.
RSI_BUCKETS: tuple[str, ...] = (
    "rsi_lt_30",
    "rsi_30_to_50",
    "rsi_50_to_70",
    "rsi_gte_70",
    "unknown",
)


def bucket_rsi(rsi: Optional[float]) -> str:
    if rsi is None:
        return "unknown"
    if rsi < 30:
        return "rsi_lt_30"
    if rsi < 50:
        return "rsi_30_to_50"
    if rsi < 70:
        return "rsi_50_to_70"
    return "rsi_gte_70"


# --- SMA200 distance ---------------------------------------------------------

# close_vs_sma200 = (close - sma200) / sma200, so units are fractions.
SMA200_DISTANCE_BUCKETS: tuple[str, ...] = (
    "below_-10pct",
    "-10_to_0pct",
    "0_to_10pct",
    "above_10pct",
    "unknown",
)


def bucket_sma200_distance(close_vs_sma200: Optional[float]) -> str:
    if close_vs_sma200 is None:
        return "unknown"
    if close_vs_sma200 < -0.10:
        return "below_-10pct"
    if close_vs_sma200 < 0.0:
        return "-10_to_0pct"
    if close_vs_sma200 < 0.10:
        return "0_to_10pct"
    return "above_10pct"


# --- MACD hist sign ----------------------------------------------------------

MACD_HIST_BUCKETS: tuple[str, ...] = (
    "positive",
    "negative",
    "zero",
    "unknown",
)


def bucket_macd_hist(hist: Optional[float]) -> str:
    if hist is None:
        return "unknown"
    if hist > 0.0:
        return "positive"
    if hist < 0.0:
        return "negative"
    return "zero"
