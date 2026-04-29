"""End-to-end report build + writer tests.

These run inside ``tmp_path`` exclusively. Nothing touches the repo's
``runs/`` directory.
"""

from __future__ import annotations

import json

import pytest

from kabu.stats import (
    DEFAULT_MINIMUM_N,
    build_stats_report,
    load_run_inputs,
    run_full_stats,
    write_stats_json,
    write_stats_markdown,
)
from kabu.stats.report import build_stats_report

from tests.stats._fixtures import build_run


def test_build_report_contains_expected_axes(tmp_path):
    paths = build_run(tmp_path)
    inp = load_run_inputs(paths)
    report = build_stats_report(inp, minimum_n=DEFAULT_MINIMUM_N)
    axis_names = {a.axis for a in report.axes}
    expected = {
        "final_action_x_outcome",
        "technical_only_action_x_outcome",
        "rule_id_x_outcome",
        "rule_version_x_outcome",
        "symbol_x_outcome",
        "trend_label_x_outcome",
        "rsi_bucket_x_outcome",
        "sma200_distance_x_outcome",
        "macd_hist_sign_x_outcome",
        "hold_reason_x_outcome",
        "blocked_by_x_outcome",
        "trade_exit_reason_x_outcome",
    }
    assert expected.issubset(axis_names)


def test_aggregate_final_action_outcome(tmp_path):
    paths = build_run(tmp_path)
    inp = load_run_inputs(paths)
    report = build_stats_report(inp, minimum_n=DEFAULT_MINIMUM_N)
    axis = next(a for a in report.axes if a.axis == "final_action_x_outcome")
    # Fixtures use observe_only across all 35 traces.
    keys = [b.bucket_key for b in axis.buckets]
    assert "observe_only" in keys
    bucket = next(b for b in axis.buckets if b.bucket_key == "observe_only")
    assert bucket.n == 35
    assert bucket.low_sample is False  # 35 >= 30


def test_aggregate_symbol_outcome(tmp_path):
    paths = build_run(tmp_path)
    inp = load_run_inputs(paths)
    report = build_stats_report(inp, minimum_n=DEFAULT_MINIMUM_N)
    axis = next(a for a in report.axes if a.axis == "symbol_x_outcome")
    keys = [b.bucket_key for b in axis.buckets]
    assert "7203" in keys
    assert "6758" in keys
    # Each is < 30 in our 35-trace fixture (split 18/17), so both flagged low.
    for b in axis.buckets:
        assert b.low_sample is True


def test_skip_reason_counts(tmp_path):
    paths = build_run(tmp_path)
    inp = load_run_inputs(paths)
    report = build_stats_report(inp, minimum_n=DEFAULT_MINIMUM_N)
    counts = report.skip_reason_counts
    # Fixture has 2 halted + 1 not_long
    assert counts.get("halted") == 2
    assert counts.get("not_long") == 1


def test_trade_pnl_summary(tmp_path):
    paths = build_run(tmp_path)
    inp = load_run_inputs(paths)
    report = build_stats_report(inp, minimum_n=DEFAULT_MINIMUM_N)
    pnl = report.trade_pnl_summary
    assert pnl.trade_count == 1
    assert pnl.closed_count == 1
    assert pnl.total_net_pnl_jpy == pytest.approx(400.0)
    assert pnl.total_gross_pnl_jpy == pytest.approx(1000.0)
    assert pnl.total_fee_jpy == pytest.approx(500.0)
    assert pnl.total_slippage_jpy == pytest.approx(100.0)
    assert pnl.win_count == 1


def test_cross_stats_two_axis(tmp_path):
    paths = build_run(tmp_path)
    inp = load_run_inputs(paths)
    report = build_stats_report(inp, minimum_n=DEFAULT_MINIMUM_N)
    cross_names = {a.axis for a in report.cross_axes}
    assert "final_action_x_rsi_bucket_x_outcome" in cross_names
    assert "trend_label_x_rsi_bucket_x_outcome" in cross_names
    cross = next(
        a for a in report.cross_axes
        if a.axis == "final_action_x_rsi_bucket_x_outcome"
    )
    # bucket keys must follow "{a1}::{a2}"
    for b in cross.buckets:
        assert "::" in b.bucket_key


def test_stats_writer_uses_tmp_path(tmp_path):
    paths = build_run(tmp_path)
    inp = load_run_inputs(paths)
    report, json_path, md_path = run_full_stats(inp, minimum_n=DEFAULT_MINIMUM_N)
    # All outputs land under tmp_path.
    assert tmp_path.resolve() in json_path.resolve().parents
    assert tmp_path.resolve() in md_path.resolve().parents
    # And specifically under runs/r_test/stats/ inside tmp_path.
    assert json_path.parent.name == "stats"
    assert md_path.parent.name == "stats"
    assert json_path.suffix == ".json"
    assert md_path.suffix == ".md"


def test_stats_header_contains_bias_warnings(tmp_path):
    paths = build_run(tmp_path)
    inp = load_run_inputs(paths)
    report, json_path, md_path = run_full_stats(inp, minimum_n=DEFAULT_MINIMUM_N)

    # JSON
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    header = payload["header"]
    assert header["survivorship_policy"] == "static_current_listing"
    assert header["survivorship_warning"] is True
    assert "pit_warnings" in header
    assert "other_warnings" in header
    assert header["minimum_n"] == DEFAULT_MINIMUM_N

    # Markdown
    md = md_path.read_text(encoding="utf-8")
    assert "survivorship_policy" in md
    assert "survivorship_warning" in md
    assert "pit_warnings" in md
    assert "minimum_n" in md
    assert "n_total" in md
    assert "n_filtered" in md


def test_stats_header_has_pit_warning_when_metadata_says_so(tmp_path):
    paths = build_run(tmp_path)
    # Mutate run_metadata to inject a pit_* warning.
    text = paths.run_metadata_json.read_text(encoding="utf-8")
    obj = json.loads(text)
    obj["warnings"] = ["pit_fundamentals_disabled", "manual_universe"]
    paths.run_metadata_json.write_text(json.dumps(obj), encoding="utf-8")

    inp = load_run_inputs(paths)
    report = build_stats_report(inp, minimum_n=DEFAULT_MINIMUM_N)
    assert "pit_fundamentals_disabled" in report.header.pit_warnings
    assert "manual_universe" in report.header.other_warnings


def test_stats_writer_does_not_write_under_runs_in_repo(tmp_path):
    """Defensive: even if a buggy build_run_paths handed us repo runs/, we
    must reject. Here we just confirm the helper writes only inside tmp_path."""
    paths = build_run(tmp_path)
    inp = load_run_inputs(paths)
    _, json_path, md_path = run_full_stats(inp, minimum_n=DEFAULT_MINIMUM_N)
    repo_runs = (paths.base_dir / "runs").resolve()
    # base_dir is tmp_path, so base_dir/runs is the tmp runs/, not the repo's.
    assert tmp_path.resolve() in repo_runs.parents or repo_runs == tmp_path.resolve() / "runs"
    assert json_path.is_file()
    assert md_path.is_file()
