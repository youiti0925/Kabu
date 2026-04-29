"""Invariant: run_metadata must contain all required fields.

Policy: BACKTEST_CONTRACT.md S7. Missing required fields -> the run is invalid.
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


_REQUIRED = (
    "run_id",
    "commit_sha",
    "created_at",
    "trace_schema_version",
    "interval",
    "universe_snapshot_id",
    "data_snapshot_hash",
    "survivorship_policy",
    "currency",
    "report_currency",
    "tax_basis",
)


@pytest.mark.parametrize("field_name", _REQUIRED)
def test_reader_rejects_missing_required_field(tmp_path, field_name):
    path = tmp_path / "run_metadata.json"
    write_run_metadata_json(path, make_run_metadata())
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop(field_name)
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        read_run_metadata_json(path)


def test_dataclass_rejects_empty_required():
    with pytest.raises(ValueError):
        make_run_metadata(run_id="")
    with pytest.raises(ValueError):
        make_run_metadata(survivorship_policy="")
    with pytest.raises(ValueError):
        make_run_metadata(currency="")


def test_writer_includes_required_fields(tmp_path):
    path = tmp_path / "run_metadata.json"
    write_run_metadata_json(path, make_run_metadata())
    data = json.loads(path.read_text(encoding="utf-8"))
    for f in _REQUIRED:
        assert f in data, f"writer must include {f!r}"
