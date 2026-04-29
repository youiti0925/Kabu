"""Aggregation primitives (PR-S4 MVP).

Provides single-axis grouping and a 2-axis cross. Larger n-axis crosses
are intentionally deferred -- multi-axis aggregation explodes the
multiple-testing surface and PR-S4 stays minimal.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from statistics import fmean
from typing import Optional


@dataclass(frozen=True)
class BucketStats:
    """One row of an axis report.

    All optional numeric fields are ``None`` when the underlying input
    didn't supply them (e.g. forward_return_5d missing). MVP keeps these
    descriptive only.
    """

    bucket_key: str
    n: int
    n_unknown_outcome: int
    outcome_counts: dict[str, int]
    hit_rate: Optional[float]  # n(win + big_win) / n(known)
    mean_return: Optional[float]  # mean of forward_return_5d when present
    mean_net_pnl_jpy: Optional[float]
    total_net_pnl_jpy: Optional[float]
    low_sample: bool


@dataclass(frozen=True)
class AxisReport:
    """A single axis report keyed by ``axis``."""

    axis: str
    minimum_n: int
    buckets: tuple[BucketStats, ...]


def _hit_rate(outcomes: list[str]) -> Optional[float]:
    known = [o for o in outcomes if o != "unknown"]
    if not known:
        return None
    wins = sum(1 for o in known if o in ("win", "big_win"))
    return wins / len(known)


def _maybe_mean(values: list[Optional[float]]) -> Optional[float]:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return fmean(present)


def _maybe_sum(values: list[Optional[float]]) -> Optional[float]:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return float(sum(present))


@dataclass(frozen=True)
class _Item:
    bucket_key: str
    outcome: str
    forward_return: Optional[float] = None
    net_pnl_jpy: Optional[float] = None


def aggregate_axis(
    *,
    axis: str,
    items: Sequence[_Item] | Sequence[tuple[str, str]],
    minimum_n: int = 30,
    forward_returns: Optional[Sequence[Optional[float]]] = None,
    net_pnls: Optional[Sequence[Optional[float]]] = None,
) -> AxisReport:
    """Group items by bucket_key and compute per-bucket descriptive stats.

    Two input shapes are accepted:
    - sequence of ``_Item`` (richer; preserves per-row return / pnl)
    - sequence of ``(bucket_key, outcome)`` tuples (lite path; counts only)

    The lite path is used by simple axes (e.g. ``skip_reason -> count``).
    """
    rich: list[_Item] = []
    if items and isinstance(items[0], _Item):
        rich = list(items)  # type: ignore[arg-type]
    else:
        for i, t in enumerate(items):
            bk, out = t  # type: ignore[misc]
            fr = (
                forward_returns[i]
                if forward_returns is not None and i < len(forward_returns)
                else None
            )
            np_ = (
                net_pnls[i]
                if net_pnls is not None and i < len(net_pnls)
                else None
            )
            rich.append(
                _Item(bucket_key=bk, outcome=out, forward_return=fr, net_pnl_jpy=np_)
            )

    grouped: dict[str, list[_Item]] = {}
    for it in rich:
        grouped.setdefault(it.bucket_key, []).append(it)

    out_buckets: list[BucketStats] = []
    for bucket_key in sorted(grouped):
        group = grouped[bucket_key]
        outcomes = [it.outcome for it in group]
        counts: dict[str, int] = {}
        for o in outcomes:
            counts[o] = counts.get(o, 0) + 1
        n = len(group)
        n_unknown = counts.get("unknown", 0)
        out_buckets.append(
            BucketStats(
                bucket_key=bucket_key,
                n=n,
                n_unknown_outcome=n_unknown,
                outcome_counts=dict(sorted(counts.items())),
                hit_rate=_hit_rate(outcomes),
                mean_return=_maybe_mean([it.forward_return for it in group]),
                mean_net_pnl_jpy=_maybe_mean([it.net_pnl_jpy for it in group]),
                total_net_pnl_jpy=_maybe_sum([it.net_pnl_jpy for it in group]),
                low_sample=n < minimum_n,
            )
        )
    return AxisReport(axis=axis, minimum_n=minimum_n, buckets=tuple(out_buckets))


def cross_axis(
    *,
    axis: str,
    items: Sequence[tuple[str, str, str]],
    minimum_n: int = 30,
    forward_returns: Optional[Sequence[Optional[float]]] = None,
    net_pnls: Optional[Sequence[Optional[float]]] = None,
) -> AxisReport:
    """2-axis cross. Items are ``(axis1_key, axis2_key, outcome)``.

    Bucket keys are encoded as ``"<axis1>::<axis2>"`` so callers can
    recover both axes by splitting the key.
    """
    pairs: list[tuple[str, str]] = []
    for i, (a1, a2, outcome) in enumerate(items):
        pairs.append((f"{a1}::{a2}", outcome))
    return aggregate_axis(
        axis=axis,
        items=pairs,
        minimum_n=minimum_n,
        forward_returns=forward_returns,
        net_pnls=net_pnls,
    )


def make_item(
    bucket_key: str,
    outcome: str,
    *,
    forward_return: Optional[float] = None,
    net_pnl_jpy: Optional[float] = None,
) -> _Item:
    return _Item(
        bucket_key=bucket_key,
        outcome=outcome,
        forward_return=forward_return,
        net_pnl_jpy=net_pnl_jpy,
    )


__all__ = [
    "AxisReport",
    "BucketStats",
    "aggregate_axis",
    "cross_axis",
    "make_item",
]
