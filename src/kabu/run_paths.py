"""Canonical run-output layout for Kabu.

Fixes the file paths that subsequent PRs (PR-S4 trace-stats and beyond)
read from. The layout under ``base_dir / "runs" / run_id`` is:

    runs/<run_id>/
        run_metadata.json         # written by run_metadata_io
        trace_raw.jsonl           # written by trace_io
        outcome_backfill.jsonl    # written by kabu.outcome
        trace_joined.jsonl        # written by trace_io after join
        trades.jsonl              # written by backtest.io.write_trades_jsonl
        skipped_fills.jsonl       # written by backtest.io.write_skipped_fills_jsonl
        backtest_result.json      # summary + file references (NOT trades body)
        stats/                    # PR-S4+

``runs/`` is gitignored (RISKS.md 5-3) and forbidden by
``scripts/check_no_forbidden_paths.py``. Tests must use ``tmp_path``;
they should never write under the repo's ``runs/``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunPaths:
    """Concrete file paths for one run.

    Values are derived from ``base_dir`` and ``run_id``; nothing on disk
    is touched by construction. Use ``ensure_run_dir()`` to create the
    directory tree right before writing.
    """

    base_dir: Path
    run_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id:
            raise ValueError("RunPaths.run_id must be non-empty")
        # Reject path-traversal characters in run_id.
        for ch in ("/", "\\", "..", "\x00"):
            if ch in self.run_id:
                raise ValueError(
                    f"RunPaths.run_id must not contain {ch!r}: {self.run_id!r}"
                )

    @property
    def runs_dir(self) -> Path:
        return Path(self.base_dir) / "runs"

    @property
    def run_dir(self) -> Path:
        return self.runs_dir / self.run_id

    @property
    def run_metadata_json(self) -> Path:
        return self.run_dir / "run_metadata.json"

    @property
    def trace_raw_jsonl(self) -> Path:
        return self.run_dir / "trace_raw.jsonl"

    @property
    def outcome_backfill_jsonl(self) -> Path:
        return self.run_dir / "outcome_backfill.jsonl"

    @property
    def trace_joined_jsonl(self) -> Path:
        return self.run_dir / "trace_joined.jsonl"

    @property
    def trades_jsonl(self) -> Path:
        return self.run_dir / "trades.jsonl"

    @property
    def skipped_fills_jsonl(self) -> Path:
        return self.run_dir / "skipped_fills.jsonl"

    @property
    def backtest_result_json(self) -> Path:
        return self.run_dir / "backtest_result.json"

    @property
    def stats_dir(self) -> Path:
        return self.run_dir / "stats"

    def ensure_run_dir(self) -> Path:
        """Create the run directory and stats subdir, return ``run_dir``."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.stats_dir.mkdir(parents=True, exist_ok=True)
        return self.run_dir


def build_run_paths(base_dir: str | Path, run_id: str) -> RunPaths:
    return RunPaths(base_dir=Path(base_dir), run_id=run_id)


__all__ = ["RunPaths", "build_run_paths"]
