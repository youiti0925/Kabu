"""Writer + observation-only-phrasing tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from kabu.attribution import (
    DEFAULT_HIGH_CONCENTRATION_PCT,
    DEFAULT_MINIMUM_N,
    run_full_attribution,
)
from kabu.stats.loaders import load_run_inputs

from tests.stats._fixtures import build_run


JST = timezone(timedelta(hours=9))


def test_attribution_writer_uses_tmp_path(tmp_path):
    paths = build_run(tmp_path, run_id="r_attr_tmp")
    inp = load_run_inputs(paths)
    report, json_path, md_path = run_full_attribution(inp)
    assert tmp_path.resolve() in json_path.resolve().parents
    assert tmp_path.resolve() in md_path.resolve().parents
    assert json_path.parent.name == "stats"
    assert md_path.parent.name == "stats"
    assert json_path.suffix == ".json"
    assert md_path.suffix == ".md"
    assert json_path.name == "attribution.json"
    assert md_path.name == "attribution.md"


def test_attribution_header_contains_bias_warnings(tmp_path):
    """Header in BOTH Markdown and JSON must surface survivorship + PIT warnings."""
    paths = build_run(tmp_path, run_id="r_attr_hdr")
    # Inject a pit_* warning into run_metadata.json.
    text = paths.run_metadata_json.read_text(encoding="utf-8")
    obj = json.loads(text)
    obj["warnings"] = ["pit_fundamentals_disabled", "static_current_listing_universe"]
    paths.run_metadata_json.write_text(json.dumps(obj), encoding="utf-8")

    inp = load_run_inputs(paths)
    report, json_path, md_path = run_full_attribution(inp)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    h = payload["header"]
    assert h["survivorship_policy"] == "static_current_listing"
    assert h["survivorship_warning"] is True
    assert "pit_fundamentals_disabled" in h["pit_warnings"]
    assert "static_current_listing_universe" in h["other_warnings"]
    assert h["analytics_version"] == "kabu.attribution.v1"
    assert h["minimum_n"] == DEFAULT_MINIMUM_N
    assert h["high_concentration_pct"] == DEFAULT_HIGH_CONCENTRATION_PCT

    md = md_path.read_text(encoding="utf-8")
    assert "survivorship_policy" in md
    assert "survivorship_warning" in md
    assert "pit_warnings" in md
    assert "pit_fundamentals_disabled" in md


_FORBIDDEN_PHRASES = (
    "確定",
    "これが原因",
    "これで勝てる",
    "この銘柄を買うべき",
    "このルールに変更すべき",
    "絶対",
    "保証",
)


def test_attribution_is_observation_not_recommendation(tmp_path):
    """Neither the Markdown nor the JSON output must contain forbidden phrases."""
    paths = build_run(tmp_path, run_id="r_attr_obs")
    inp = load_run_inputs(paths)
    report, json_path, md_path = run_full_attribution(inp)

    md = md_path.read_text(encoding="utf-8")
    js = json_path.read_text(encoding="utf-8")
    for phrase in _FORBIDDEN_PHRASES:
        assert phrase not in md, (
            f"forbidden phrase {phrase!r} appeared in attribution.md"
        )
        assert phrase not in js, (
            f"forbidden phrase {phrase!r} appeared in attribution.json"
        )


def test_attribution_report_contains_expected_axes(tmp_path):
    paths = build_run(tmp_path, run_id="r_attr_axes")
    inp = load_run_inputs(paths)
    report, _, _ = run_full_attribution(inp)
    axis_names = {a.axis for a in report.axes}
    expected = {
        "symbol",
        "sector",
        "year",
        "quarter",
        "month",
        "rule_id",
        "rule_version",
        "skip_reason",
        "outcome",
    }
    assert expected == axis_names


def test_attribution_overall_totals_present(tmp_path):
    paths = build_run(tmp_path, run_id="r_attr_overall")
    inp = load_run_inputs(paths)
    report, _, _ = run_full_attribution(inp)
    assert report.overall.trace_count == 35
    assert report.overall.trade_count == 1
    assert report.overall.skipped_count == 3


def test_outcome_axis_excluded_from_concentration_warnings(tmp_path):
    """Even if 'win' bucket dominates contribution, the outcome axis is exempted."""
    paths = build_run(tmp_path, run_id="r_attr_out")
    inp = load_run_inputs(paths)
    report, _, _ = run_full_attribution(inp)
    for w in report.concentration_warnings:
        assert w.axis != "outcome", (
            "outcome axis should not produce concentration warnings"
        )
