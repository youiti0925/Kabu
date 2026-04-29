"""I/O roundtrip + required-field tests for P3.5.

Covers:
- ``test_trade_jsonl_roundtrip``
- ``test_trade_jsonl_path_required_on_read``
- ``test_skipped_fill_jsonl_roundtrip``
- ``test_backtest_result_json_roundtrip``
- ``test_run_paths_use_tmp_path``
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from kabu.backtest import (
    BacktestResultSummary,
    ScriptedDecision,
    SkippedFill,
    Trade,
    read_backtest_result_json,
    read_skipped_fills_jsonl,
    read_trades_jsonl,
    run_backtest,
    summarize_backtest_result,
    write_backtest_outputs,
    write_backtest_result_json,
    write_skipped_fills_jsonl,
    write_trades_jsonl,
)
from kabu.run_paths import RunPaths, build_run_paths

from tests.backtest._fixtures import DEFAULT_COST, make_bars

JST = timezone(timedelta(hours=9))


# --- Trade roundtrip ---------------------------------------------------------


def _build_round_trip(tmp_path):
    """Run a small backtest end-to-end so we have realistic Trade / Skipped data."""
    bars = make_bars(10)
    decisions = [
        ScriptedDecision(bar_ts=bars[1].bar_ts, action="enter_long"),
        ScriptedDecision(bar_ts=bars[5].bar_ts, action="exit_long"),
        ScriptedDecision(bar_ts=bars[7].bar_ts, action="exit_long"),  # skip: not_long
    ]
    return run_backtest(
        bars=bars,
        decisions=decisions,
        cost=DEFAULT_COST,
        run_id="r_test",
        trace_jsonl_path=tmp_path / "runs" / "r_test" / "trace_raw.jsonl",
    )


def test_trade_jsonl_roundtrip(tmp_path):
    result = _build_round_trip(tmp_path)
    assert len(result.trades) == 1
    path = tmp_path / "trades.jsonl"
    n = write_trades_jsonl(path, result.trades)
    assert n == 1
    loaded = list(read_trades_jsonl(path))
    assert len(loaded) == 1
    rt = loaded[0]
    src = result.trades[0]
    assert rt.trade_id == src.trade_id
    assert rt.symbol == src.symbol
    assert rt.run_id == src.run_id
    assert rt.trace_jsonl_path == src.trace_jsonl_path
    assert rt.entry_decision_ts == src.entry_decision_ts
    assert rt.entry_fill_ts == src.entry_fill_ts
    assert rt.exit_fill_ts == src.exit_fill_ts
    assert rt.entry_price == pytest.approx(src.entry_price)
    assert rt.exit_price == pytest.approx(src.exit_price)
    assert rt.fee_jpy == pytest.approx(src.fee_jpy)
    assert rt.slippage_jpy == pytest.approx(src.slippage_jpy)
    assert rt.gross_pnl_jpy == pytest.approx(src.gross_pnl_jpy)
    assert rt.net_pnl_jpy == pytest.approx(src.net_pnl_jpy)


def test_trade_datetimes_preserve_timezone(tmp_path):
    result = _build_round_trip(tmp_path)
    path = tmp_path / "trades.jsonl"
    write_trades_jsonl(path, result.trades)
    loaded = list(read_trades_jsonl(path))
    assert loaded[0].entry_decision_ts.tzinfo is not None
    assert loaded[0].entry_fill_ts.tzinfo is not None


def test_trade_side_is_long_only_round_trip(tmp_path):
    result = _build_round_trip(tmp_path)
    path = tmp_path / "trades.jsonl"
    write_trades_jsonl(path, result.trades)
    raw = path.read_text(encoding="utf-8").strip()
    obj = json.loads(raw.splitlines()[0])
    assert obj["side"] == "long"


# --- Required-field validation on Trade read --------------------------------


def test_trade_jsonl_path_required_on_read(tmp_path):
    """A trade JSON missing or empty trace_jsonl_path must fail on read."""
    result = _build_round_trip(tmp_path)
    src = result.trades[0]
    base_obj = {
        "trade_id": src.trade_id,
        "run_id": src.run_id,
        "symbol": src.symbol,
        "side": src.side,
        "quantity": src.quantity,
        "entry_decision_ts": src.entry_decision_ts.isoformat(),
        "entry_fill_ts": src.entry_fill_ts.isoformat(),
        "entry_price": src.entry_price,
        "entry_trace_key": src.entry_trace_key,
        "fee_jpy": src.fee_jpy,
        "slippage_jpy": src.slippage_jpy,
    }

    # Missing trace_jsonl_path key
    p1 = tmp_path / "missing.jsonl"
    p1.write_text(json.dumps(base_obj) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        list(read_trades_jsonl(p1))

    # Empty trace_jsonl_path value
    p2 = tmp_path / "empty.jsonl"
    obj_empty = dict(base_obj, trace_jsonl_path="")
    p2.write_text(json.dumps(obj_empty) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        list(read_trades_jsonl(p2))


@pytest.mark.parametrize("missing_field", ["run_id", "symbol"])
def test_trade_required_str_fields_rejected_when_empty(tmp_path, missing_field):
    result = _build_round_trip(tmp_path)
    src = result.trades[0]
    base_obj = {
        "trade_id": src.trade_id,
        "run_id": src.run_id,
        "symbol": src.symbol,
        "side": src.side,
        "quantity": src.quantity,
        "entry_decision_ts": src.entry_decision_ts.isoformat(),
        "entry_fill_ts": src.entry_fill_ts.isoformat(),
        "entry_price": src.entry_price,
        "entry_trace_key": src.entry_trace_key,
        "trace_jsonl_path": src.trace_jsonl_path,
    }
    base_obj[missing_field] = ""
    path = tmp_path / "broken.jsonl"
    path.write_text(json.dumps(base_obj) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        list(read_trades_jsonl(path))


# --- SkippedFill roundtrip ---------------------------------------------------


def test_skipped_fill_jsonl_roundtrip(tmp_path):
    result = _build_round_trip(tmp_path)
    assert len(result.skipped) >= 1
    path = tmp_path / "skipped_fills.jsonl"
    n = write_skipped_fills_jsonl(path, result.skipped)
    assert n == len(result.skipped)
    loaded = list(read_skipped_fills_jsonl(path))
    assert len(loaded) == len(result.skipped)
    for src, rt in zip(result.skipped, loaded):
        assert rt.run_id == src.run_id
        assert rt.symbol == src.symbol
        assert rt.decision_ts == src.decision_ts
        assert rt.attempted_fill_ts == src.attempted_fill_ts
        assert rt.intended_action == src.intended_action
        assert rt.reason == src.reason
        assert rt.decision_ts.tzinfo is not None
        assert rt.attempted_fill_ts.tzinfo is not None


def test_skipped_fill_required_fields_rejected_on_read(tmp_path):
    bars = make_bars(2)
    raw = {
        "run_id": "r1",
        "symbol": "7203",
        "decision_ts": bars[0].bar_ts.isoformat(),
        "attempted_fill_ts": bars[1].bar_ts.isoformat(),
        "intended_action": "enter_long",
        "reason": "halted",
    }
    for missing in ("run_id", "symbol", "reason"):
        path = tmp_path / f"broken_{missing}.jsonl"
        broken = dict(raw)
        broken[missing] = ""
        path.write_text(json.dumps(broken) + "\n", encoding="utf-8")
        with pytest.raises(ValueError):
            list(read_skipped_fills_jsonl(path))


# --- BacktestResult JSON roundtrip ------------------------------------------


def test_backtest_result_json_roundtrip(tmp_path):
    result = _build_round_trip(tmp_path)
    paths = build_run_paths(tmp_path, run_id=result.run_id)
    summary = write_backtest_outputs(
        paths=paths,
        result=result,
        created_at=datetime(2024, 4, 30, 16, 0, tzinfo=JST),
    )
    assert isinstance(summary, BacktestResultSummary)
    rt = read_backtest_result_json(paths.backtest_result_json)
    assert rt.run_id == result.run_id
    assert rt.trade_count == len(result.trades)
    assert rt.skipped_count == len(result.skipped)
    assert rt.open_position_count == len(result.closing_positions)
    assert rt.initial_cash_jpy == pytest.approx(result.initial_cash_jpy)
    assert rt.final_cash_jpy == pytest.approx(result.final_cash_jpy)
    assert rt.trace_jsonl_path == result.trace_jsonl_path
    assert rt.trades_jsonl_path == str(paths.trades_jsonl)
    assert rt.skipped_fills_jsonl_path == str(paths.skipped_fills_jsonl)
    assert rt.created_at.tzinfo is not None


def test_backtest_result_json_does_not_contain_trades_body(tmp_path):
    """The summary file must NOT carry the body of trades / skipped."""
    result = _build_round_trip(tmp_path)
    paths = build_run_paths(tmp_path, run_id=result.run_id)
    write_backtest_outputs(
        paths=paths,
        result=result,
        created_at=datetime(2024, 4, 30, 16, 0, tzinfo=JST),
    )
    text = paths.backtest_result_json.read_text(encoding="utf-8")
    obj = json.loads(text)
    assert "trades" not in obj
    assert "skipped" not in obj
    assert "closing_positions" not in obj
    assert "trades_jsonl_path" in obj
    assert "skipped_fills_jsonl_path" in obj


def test_backtest_result_json_required_fields(tmp_path):
    result = _build_round_trip(tmp_path)
    paths = build_run_paths(tmp_path, run_id=result.run_id)
    write_backtest_outputs(
        paths=paths,
        result=result,
        created_at=datetime(2024, 4, 30, 16, 0, tzinfo=JST),
    )
    text = paths.backtest_result_json.read_text(encoding="utf-8")
    obj = json.loads(text)
    obj.pop("run_id")
    paths.backtest_result_json.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(ValueError):
        read_backtest_result_json(paths.backtest_result_json)


def test_summary_dataclass_rejects_naive_created_at():
    with pytest.raises(ValueError):
        BacktestResultSummary(
            run_id="r1",
            created_at=datetime(2024, 4, 30, 16, 0),  # naive
            initial_cash_jpy=1.0,
            final_cash_jpy=1.0,
            trade_count=0,
            skipped_count=0,
            open_position_count=0,
            trace_jsonl_path="/a",
            trades_jsonl_path="/b",
            skipped_fills_jsonl_path="/c",
        )


def test_summary_dataclass_rejects_empty_required():
    with pytest.raises(ValueError):
        BacktestResultSummary(
            run_id="",
            created_at=datetime(2024, 4, 30, 16, 0, tzinfo=JST),
            initial_cash_jpy=1.0,
            final_cash_jpy=1.0,
            trade_count=0,
            skipped_count=0,
            open_position_count=0,
            trace_jsonl_path="/a",
            trades_jsonl_path="/b",
            skipped_fills_jsonl_path="/c",
        )


# --- RunPaths ----------------------------------------------------------------


def test_run_paths_use_tmp_path(tmp_path):
    """All run output paths must live under the supplied base_dir.

    The test uses ``tmp_path`` -- never the repo's own ``runs/``.
    """
    paths = build_run_paths(tmp_path, run_id="r_xyz")
    assert isinstance(paths, RunPaths)
    expected_root = (tmp_path / "runs" / "r_xyz").resolve()
    paths_to_check = (
        paths.run_metadata_json,
        paths.trace_raw_jsonl,
        paths.outcome_backfill_jsonl,
        paths.trace_joined_jsonl,
        paths.trades_jsonl,
        paths.skipped_fills_jsonl,
        paths.backtest_result_json,
        paths.stats_dir,
    )
    for p in paths_to_check:
        # Each leaf file/dir must be under ``tmp_path/runs/r_xyz``.
        assert expected_root in p.resolve().parents or p.resolve() == expected_root
        # And under tmp_path more broadly.
        assert tmp_path.resolve() in p.resolve().parents


def test_run_paths_rejects_path_traversal():
    with pytest.raises(ValueError):
        build_run_paths("/tmp", run_id="../escape")
    with pytest.raises(ValueError):
        build_run_paths("/tmp", run_id="a/b")
    with pytest.raises(ValueError):
        build_run_paths("/tmp", run_id="")


def test_run_paths_ensure_run_dir_creates_stats(tmp_path):
    paths = build_run_paths(tmp_path, run_id="r_create")
    assert not paths.run_dir.exists()
    paths.ensure_run_dir()
    assert paths.run_dir.is_dir()
    assert paths.stats_dir.is_dir()
