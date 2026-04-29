"""Aggregator + cross_axis tests."""

from __future__ import annotations

import pytest

from kabu.stats.aggregate import aggregate_axis, cross_axis, make_item


def test_low_sample_bucket_flag():
    items = [make_item("a", "win") for _ in range(5)]  # n < 30
    rep = aggregate_axis(axis="x", items=items, minimum_n=30)
    assert len(rep.buckets) == 1
    assert rep.buckets[0].low_sample is True


def test_full_sample_bucket_no_flag():
    items = [make_item("a", "win") for _ in range(35)]
    rep = aggregate_axis(axis="x", items=items, minimum_n=30)
    assert rep.buckets[0].low_sample is False


def test_aggregate_groups_by_bucket_key():
    items = (
        [make_item("a", "win") for _ in range(2)]
        + [make_item("b", "loss") for _ in range(3)]
    )
    rep = aggregate_axis(axis="x", items=items, minimum_n=30)
    keys = [b.bucket_key for b in rep.buckets]
    assert keys == ["a", "b"]
    a_bucket = next(b for b in rep.buckets if b.bucket_key == "a")
    b_bucket = next(b for b in rep.buckets if b.bucket_key == "b")
    assert a_bucket.n == 2
    assert b_bucket.n == 3


def test_hit_rate_excludes_unknown():
    items = [
        make_item("a", "win"),
        make_item("a", "win"),
        make_item("a", "loss"),
        make_item("a", "unknown"),
        make_item("a", "unknown"),
    ]
    rep = aggregate_axis(axis="x", items=items, minimum_n=30)
    bucket = rep.buckets[0]
    assert bucket.n == 5
    assert bucket.n_unknown_outcome == 2
    # hit_rate = 2 wins / 3 known = 0.6667
    assert bucket.hit_rate == pytest.approx(2 / 3)


def test_mean_return_skips_none():
    items = [
        make_item("a", "win", forward_return=0.10),
        make_item("a", "loss", forward_return=-0.05),
        make_item("a", "unknown", forward_return=None),
    ]
    rep = aggregate_axis(axis="x", items=items, minimum_n=30)
    assert rep.buckets[0].mean_return == pytest.approx((0.10 + -0.05) / 2)


def test_mean_return_all_none_returns_none():
    items = [make_item("a", "unknown", forward_return=None) for _ in range(3)]
    rep = aggregate_axis(axis="x", items=items, minimum_n=30)
    assert rep.buckets[0].mean_return is None


def test_pnl_sum_present_when_any():
    items = [
        make_item("a", "win", net_pnl_jpy=1000.0),
        make_item("a", "loss", net_pnl_jpy=-500.0),
        make_item("a", "unknown", net_pnl_jpy=None),
    ]
    rep = aggregate_axis(axis="x", items=items, minimum_n=30)
    assert rep.buckets[0].total_net_pnl_jpy == pytest.approx(500.0)
    assert rep.buckets[0].mean_net_pnl_jpy == pytest.approx(250.0)


def test_cross_axis_two_axis():
    items = [
        ("buy", "rsi_lt_30", "win"),
        ("buy", "rsi_lt_30", "loss"),
        ("buy", "rsi_gte_70", "win"),
        ("hold", "rsi_lt_30", "loss"),
    ]
    rep = cross_axis(axis="x", items=items, minimum_n=30)
    keys = [b.bucket_key for b in rep.buckets]
    assert "buy::rsi_lt_30" in keys
    assert "buy::rsi_gte_70" in keys
    assert "hold::rsi_lt_30" in keys


def test_lite_path_with_returns_alignment():
    items = [
        ("a", "win"),
        ("a", "loss"),
        ("b", "unknown"),
    ]
    forward_returns = [0.05, -0.02, None]
    rep = aggregate_axis(
        axis="x",
        items=items,
        minimum_n=30,
        forward_returns=forward_returns,
    )
    a = next(b for b in rep.buckets if b.bucket_key == "a")
    b = next(b for b in rep.buckets if b.bucket_key == "b")
    assert a.mean_return == pytest.approx((0.05 + -0.02) / 2)
    assert b.mean_return is None
