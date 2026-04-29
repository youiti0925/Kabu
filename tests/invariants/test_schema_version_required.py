"""Invariant: schema_version is required at the top level.

Policy: SCHEMA.md S0 D-1 / S1-2.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from kabu.decision_trace import SCHEMA_VERSION
from kabu.trace_io import (
    read_traces_jsonl,
    trace_from_dict,
    trace_to_dict,
    write_traces_jsonl,
)

from tests.decision_trace._fixtures import make_trace


def test_dataclass_rejects_empty_schema_version():
    with pytest.raises(ValueError):
        make_trace(schema_version="")


def test_dataclass_rejects_unknown_schema_version():
    with pytest.raises(ValueError):
        make_trace(schema_version="kabu.trace.vNEXT")


def test_reader_rejects_dict_without_schema_version():
    d = trace_to_dict(make_trace())
    d.pop("schema_version")
    with pytest.raises(ValueError):
        trace_from_dict(d)


def test_reader_rejects_unknown_schema_version_in_dict():
    d = trace_to_dict(make_trace())
    d["schema_version"] = "kabu.trace.vNEXT"
    with pytest.raises(ValueError):
        trace_from_dict(d)


def test_jsonl_reader_rejects_record_missing_schema_version(tmp_path):
    path = tmp_path / "broken.jsonl"
    d = trace_to_dict(make_trace())
    d.pop("schema_version")
    path.write_text(json.dumps(d) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        list(read_traces_jsonl(path))


def test_writer_emits_correct_schema_version(tmp_path):
    path = tmp_path / "ok.jsonl"
    write_traces_jsonl(path, [make_trace()])
    line = path.read_text(encoding="utf-8").strip()
    obj = json.loads(line)
    assert obj["schema_version"] == SCHEMA_VERSION
    assert obj["trace_schema_version"] == SCHEMA_VERSION
