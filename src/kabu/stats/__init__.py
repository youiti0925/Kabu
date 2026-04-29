"""kabu.stats: trace / trade / outcome aggregation (PR-S4 MVP).

Observation only. This sub-package does NOT implement trade rules.
It does NOT recommend symbols. It does NOT generate AI proposals.
It reads the run output set fixed in P3.5 and produces Markdown + JSON
reports under ``runs/<run_id>/stats/``.

Bucket boundaries are documented in ``docs/STATS.md``. Changing them
is treated as an analytics-version change.
"""

from kabu.stats.aggregate import (
    AxisReport,
    BucketStats,
    aggregate_axis,
    cross_axis,
)
from kabu.stats.buckets import (
    MACD_HIST_BUCKETS,
    RSI_BUCKETS,
    SMA200_DISTANCE_BUCKETS,
    bucket_macd_hist,
    bucket_rsi,
    bucket_sma200_distance,
)
from kabu.stats.loaders import RunStatsInput, load_run_inputs
from kabu.stats.outcomes import trace_outcome_label, trade_outcome_label
from kabu.stats.report import (
    StatsHeader,
    StatsReport,
    TradePnlSummary,
    build_stats_report,
    run_full_stats,
    write_stats_json,
    write_stats_markdown,
)

DEFAULT_MINIMUM_N = 30

__all__ = [
    "AxisReport",
    "BucketStats",
    "DEFAULT_MINIMUM_N",
    "MACD_HIST_BUCKETS",
    "RSI_BUCKETS",
    "RunStatsInput",
    "SMA200_DISTANCE_BUCKETS",
    "StatsHeader",
    "StatsReport",
    "TradePnlSummary",
    "aggregate_axis",
    "build_stats_report",
    "bucket_macd_hist",
    "bucket_rsi",
    "bucket_sma200_distance",
    "cross_axis",
    "load_run_inputs",
    "run_full_stats",
    "trace_outcome_label",
    "trade_outcome_label",
    "write_stats_json",
    "write_stats_markdown",
]
