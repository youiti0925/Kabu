"""Invariant: bar_ts / bar_ts_close / bar_ts_available are timezone-aware.

Policy: CALENDAR.md S0 D-2 / SCHEMA.md S0 D-2 / D-3.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.decision_trace._fixtures import make_trace

JST = timezone(timedelta(hours=9))


def _aware(hour: int = 15, minute: int = 0) -> datetime:
    return datetime(2024, 4, 26, hour, minute, tzinfo=JST)


def _naive(hour: int = 15, minute: int = 0) -> datetime:
    return datetime(2024, 4, 26, hour, minute)


@pytest.mark.parametrize("field_name", ["bar_ts", "bar_ts_close", "bar_ts_available"])
def test_top_level_timestamp_must_be_tzaware(field_name):
    bar_ts = _aware(15, 0)
    bar_ts_close = _aware(15, 0)
    bar_ts_available = _aware(15, 30)
    base = dict(
        bar_ts=bar_ts,
        bar_ts_close=bar_ts_close,
        bar_ts_available=bar_ts_available,
    )
    base[field_name] = _naive()
    with pytest.raises(ValueError):
        make_trace(**base)


def test_created_at_must_be_tzaware():
    with pytest.raises(ValueError):
        make_trace(created_at=_naive())


def test_close_must_be_le_available():
    with pytest.raises(ValueError):
        make_trace(
            bar_ts=_aware(15, 0),
            bar_ts_close=_aware(16, 0),
            bar_ts_available=_aware(15, 30),
        )
