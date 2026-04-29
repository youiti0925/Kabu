"""Invariant: run_metadata.survivorship_policy is recorded.

Policy: UNIVERSE.md S0 D-4 / D-5 / BACKTEST_CONTRACT.md S7.
"""

from __future__ import annotations

import json

import pytest

from kabu.run_metadata_io import (
    read_run_metadata_json,
    run_metadata_to_dict,
    write_run_metadata_json,
)

from tests.backtest._fixtures import make_run_metadata


def test_writer_emits_survivorship_policy(tmp_path):
    path = tmp_path / "run_metadata.json"
    write_run_metadata_json(path, make_run_metadata())
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["survivorship_policy"] == "static_current_listing"
    assert data["survivorship_warning"] is True


def test_reader_rejects_missing_survivorship_policy(tmp_path):
    path = tmp_path / "run_metadata.json"
    write_run_metadata_json(path, make_run_metadata())
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("survivorship_policy")
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        read_run_metadata_json(path)


def test_dataclass_rejects_empty_survivorship_policy():
    with pytest.raises(ValueError):
        make_run_metadata(survivorship_policy="")


def test_historical_policy_round_trips(tmp_path):
    path = tmp_path / "run_metadata.json"
    write_run_metadata_json(
        path,
        make_run_metadata(
            survivorship_policy="historical",
            survivorship_warning=False,
        ),
    )
    rt = read_run_metadata_json(path)
    assert rt.survivorship_policy == "historical"
    assert rt.survivorship_warning is False
