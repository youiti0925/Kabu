"""Tests for kabu.stats.loaders."""

from __future__ import annotations

import json

import pytest

from kabu.stats.loaders import load_run_inputs

from tests.stats._fixtures import build_run


def test_load_run_inputs_roundtrip(tmp_path):
    paths = build_run(tmp_path)
    inp = load_run_inputs(paths)
    assert inp.run_metadata.run_id == "r_test"
    assert len(inp.traces) == 35
    assert len(inp.trades) == 1
    assert len(inp.skipped_fills) == 3


def test_load_run_inputs_requires_metadata(tmp_path):
    paths = build_run(tmp_path)
    paths.run_metadata_json.unlink()
    with pytest.raises(ValueError):
        load_run_inputs(paths)


def test_load_run_inputs_requires_trace_joined(tmp_path):
    paths = build_run(tmp_path)
    paths.trace_joined_jsonl.unlink()
    with pytest.raises(ValueError):
        load_run_inputs(paths)


def test_load_run_inputs_run_id_mismatch_metadata_vs_summary(tmp_path):
    paths = build_run(tmp_path)
    obj = json.loads(paths.backtest_result_json.read_text())
    obj["run_id"] = "different_run"
    paths.backtest_result_json.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(ValueError):
        load_run_inputs(paths)


def test_load_run_inputs_run_id_mismatch_trace(tmp_path):
    paths = build_run(tmp_path)
    text = paths.trace_joined_jsonl.read_text(encoding="utf-8")
    lines = text.splitlines()
    obj = json.loads(lines[0])
    obj["run_id"] = "different_run"
    lines[0] = json.dumps(obj)
    paths.trace_joined_jsonl.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_run_inputs(paths)


def test_load_run_inputs_run_id_mismatch_trade(tmp_path):
    paths = build_run(tmp_path)
    text = paths.trades_jsonl.read_text(encoding="utf-8")
    lines = text.splitlines()
    obj = json.loads(lines[0])
    obj["run_id"] = "different_run"
    lines[0] = json.dumps(obj)
    paths.trades_jsonl.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_run_inputs(paths)


def test_load_run_inputs_empty_trades_ok(tmp_path):
    paths = build_run(tmp_path)
    paths.trades_jsonl.unlink()
    inp = load_run_inputs(paths)
    assert inp.trades == ()


def test_load_run_inputs_empty_skipped_ok(tmp_path):
    paths = build_run(tmp_path)
    paths.skipped_fills_jsonl.unlink()
    inp = load_run_inputs(paths)
    assert inp.skipped_fills == ()
