"""Invariant: a Source must not emit bars whose bar_ts_available > as_of.

Policy: POINT_IN_TIME.md 3-1 / 5 / DATA_SOURCES.md S0 D-4.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from kabu.data import InMemorySource, OHLCBar, Source


JST = timezone(timedelta(hours=9))


def _bar(day: int) -> OHLCBar:
    bar_ts = datetime(2024, 4, day, 15, 0, tzinfo=JST)
    bar_ts_available = bar_ts + timedelta(minutes=30)
    return OHLCBar(
        symbol="7203",
        interval="1d",
        bar_ts=bar_ts,
        bar_ts_close=bar_ts,
        bar_ts_available=bar_ts_available,
        open=100.0,
        high=101.0,
        low=99.5,
        close=100.5,
        adj_close=100.5,
        volume=1_000,
        turnover=100_500.0,
    )


def test_source_protocol_runtime_check() -> None:
    src = InMemorySource()
    assert isinstance(src, Source)


def test_inmemory_excludes_bars_after_as_of() -> None:
    src = InMemorySource(bars_by_symbol={"7203": [_bar(1), _bar(2), _bar(3)]})
    as_of = datetime(2024, 4, 2, 16, 0, tzinfo=JST)
    out = src.get_ohlcv(
        "7203",
        start=datetime(2024, 4, 1, tzinfo=JST),
        end=datetime(2024, 4, 30, tzinfo=JST),
        as_of=as_of,
    )
    assert [b.bar_ts.day for b in out] == [1, 2]


def test_inmemory_includes_bar_at_exact_as_of() -> None:
    src = InMemorySource(bars_by_symbol={"7203": [_bar(1)]})
    only = _bar(1)
    out = src.get_ohlcv(
        "7203",
        start=datetime(2024, 4, 1, tzinfo=JST),
        end=datetime(2024, 4, 30, tzinfo=JST),
        as_of=only.bar_ts_available,
    )
    assert len(out) == 1


def test_inmemory_returns_sorted_by_bar_ts() -> None:
    bars = [_bar(3), _bar(1), _bar(2)]
    src = InMemorySource(bars_by_symbol={"7203": bars})
    as_of = datetime(2024, 4, 30, tzinfo=JST)
    out = src.get_ohlcv(
        "7203",
        start=datetime(2024, 4, 1, tzinfo=JST),
        end=datetime(2024, 4, 30, tzinfo=JST),
        as_of=as_of,
    )
    assert [b.bar_ts.day for b in out] == [1, 2, 3]


def test_inmemory_unknown_symbol_returns_empty() -> None:
    src = InMemorySource()
    out = src.get_ohlcv(
        "9999",
        start=datetime(2024, 4, 1, tzinfo=JST),
        end=datetime(2024, 4, 30, tzinfo=JST),
        as_of=datetime(2024, 4, 30, tzinfo=JST),
    )
    assert out == []


def test_as_of_is_required_keyword_only() -> None:
    """The Protocol says ``as_of`` is required and keyword-only.

    Forgetting it must raise TypeError -- this is the structural defense
    behind DATA_SOURCES.md S0 D-4.
    """
    src = InMemorySource()
    with pytest.raises(TypeError):
        # Missing as_of.
        src.get_ohlcv(  # type: ignore[call-arg]
            "7203",
            start=datetime(2024, 4, 1, tzinfo=JST),
            end=datetime(2024, 4, 30, tzinfo=JST),
        )
    with pytest.raises(TypeError):
        # Positional as_of must fail (keyword-only).
        src.get_ohlcv(  # type: ignore[misc]
            "7203",
            datetime(2024, 4, 1, tzinfo=JST),
            datetime(2024, 4, 30, tzinfo=JST),
            datetime(2024, 4, 30, tzinfo=JST),
        )


def test_bar_rejects_naive_datetime() -> None:
    naive = datetime(2024, 4, 1, 15, 0)
    aware = naive.replace(tzinfo=JST)
    with pytest.raises(ValueError):
        OHLCBar(
            symbol="7203",
            interval="1d",
            bar_ts=naive,
            bar_ts_close=aware,
            bar_ts_available=aware,
            open=100, high=101, low=99, close=100,
            adj_close=100, volume=10, turnover=1000,
        )


def test_bar_rejects_close_after_available() -> None:
    bar_ts_close = datetime(2024, 4, 1, 16, 0, tzinfo=JST)
    bar_ts_available = datetime(2024, 4, 1, 15, 30, tzinfo=JST)
    with pytest.raises(ValueError):
        OHLCBar(
            symbol="7203",
            interval="1d",
            bar_ts=bar_ts_available,
            bar_ts_close=bar_ts_close,
            bar_ts_available=bar_ts_available,
            open=100, high=101, low=99, close=100,
            adj_close=100, volume=10, turnover=1000,
        )


def test_inmemory_rejects_naive_as_of() -> None:
    src = InMemorySource()
    with pytest.raises(ValueError):
        src.get_ohlcv(
            "7203",
            start=datetime(2024, 4, 1, tzinfo=JST),
            end=datetime(2024, 4, 30, tzinfo=JST),
            as_of=datetime(2024, 4, 30),
        )
