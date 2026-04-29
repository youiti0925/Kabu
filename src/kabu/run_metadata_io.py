"""JSON writer / reader for ``RunMetadata``.

A run is invalid if its ``run_metadata.json`` is missing or incomplete.
``test_run_metadata_required`` and ``test_survivorship_policy_recorded``
enforce this from the test side.

The file lives next to the trace JSONL (typically ``runs/<run_id>/run_metadata.json``).
PR-S3 chooses path; tests use ``tmp_path``. ``runs/`` is .gitignored
(RISKS.md 5-3).
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from kabu.decision_trace import LibraryRef, RunMetadata, SCHEMA_VERSION


_REQUIRED_TOP_LEVEL_FIELDS = (
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


def _encode(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, tuple):
        return [_encode(x) for x in obj]
    if isinstance(obj, list):
        return [_encode(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _encode(v) for k, v in obj.items()}
    return obj


def run_metadata_to_dict(meta: RunMetadata) -> dict[str, Any]:
    return _encode(asdict(meta))  # type: ignore[return-value]


def write_run_metadata_json(path: str | Path, meta: RunMetadata) -> Path:
    """Write a single ``RunMetadata`` as JSON. Returns the absolute Path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(run_metadata_to_dict(meta), f, ensure_ascii=False, indent=2)
    return p.resolve()


def _parse_dt(value: Any, name: str) -> datetime:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be ISO 8601 string")
    return datetime.fromisoformat(value)


def run_metadata_from_dict(d: dict[str, Any]) -> RunMetadata:
    """Validate the dict and return a RunMetadata.

    Missing required fields raise ``ValueError`` so consumers can fail
    fast (this is what ``test_run_metadata_required`` exercises).
    """
    missing = [k for k in _REQUIRED_TOP_LEVEL_FIELDS if k not in d]
    if missing:
        raise ValueError(
            f"run_metadata is missing required field(s): {sorted(missing)} "
            f"(BACKTEST_CONTRACT.md S7)"
        )
    if d["trace_schema_version"] != SCHEMA_VERSION:
        raise ValueError(
            f"run_metadata.trace_schema_version must be {SCHEMA_VERSION!r}; "
            f"got {d['trace_schema_version']!r}"
        )

    libraries: list[LibraryRef] = []
    for raw in d.get("libraries", ()) or ():
        libraries.append(
            LibraryRef(
                slice=raw["slice"],
                library_id=raw["library_id"],
                library_kind=raw["library_kind"],
                feature_set=raw["feature_set"],
            )
        )

    return RunMetadata(
        run_id=d["run_id"],
        commit_sha=d["commit_sha"],
        created_at=_parse_dt(d["created_at"], "run_metadata.created_at"),
        trace_schema_version=d["trace_schema_version"],
        interval=d["interval"],
        universe_snapshot_id=d["universe_snapshot_id"],
        data_snapshot_hash=d["data_snapshot_hash"],
        survivorship_policy=d["survivorship_policy"],
        survivorship_warning=bool(d.get("survivorship_warning", False)),
        currency=d["currency"],
        report_currency=d["report_currency"],
        tax_basis=d["tax_basis"],
        libraries=tuple(libraries),
        warnings=tuple(d.get("warnings", ())),
    )


def read_run_metadata_json(path: str | Path) -> RunMetadata:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return run_metadata_from_dict(data)


__all__ = [
    "run_metadata_to_dict",
    "run_metadata_from_dict",
    "write_run_metadata_json",
    "read_run_metadata_json",
]
