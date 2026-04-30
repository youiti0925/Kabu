"""Unit tests for kabu.data.sources.yfinance_source.

CI does NOT install the real yfinance package. All tests inject a fake
``history_fn`` so the lazy ``import yfinance`` inside
``_default_yfinance_history`` is never reached. ``test_no_real_yfinance_imported``
asserts this invariant.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest

from kabu.data import OHLCBar, Source
from kabu.data.sources import YFinanceSource, yfinance_row_to_ohlcbar
from kabu.data.sources.yfinance_source import DATA_SOURCE_NAME

JST = timezone(timedelta(hours=9))


def _fake_rows():
    return [
        {
            "date": date(2024, 4, 1),
            "open": 1000.0,
            "high": 1010.0,
            "low": 995.0,
            "close": 1005.0,
            "adj_close": 1005.0,
            "volume": 1_000_000,
        },
        {
            "date": date(2024, 4, 2),
            "open": 1006.0,
            "high": 1015.0,
            "low": 1002.0,
            "close": 1012.0,
            "adj_close": 1012.0,
            "volume": 900_000,
        },
        {
            "date": date(2024, 4, 3),
            "open": 1013.0,
            "high": 1020.0,
            "low": 1008.0,
            "close": 1018.0,
            "adj_close": 1018.0,
            "volume": 850_000,
        },
    ]


def _fake_history_fn(symbol, start, end):
    return _fake_rows()


# --- Required pytests --------------------------------------------------------


def test_vendor_source_requires_as_of():
    """Missing as_of must raise TypeError; naive as_of must raise ValueError."""
    src = YFinanceSource(history_fn=_fake_history_fn)
    start = datetime(2024, 4, 1, tzinfo=JST)
    end = datetime(2024, 4, 30, tzinfo=JST)

    # Missing keyword raises TypeError (Python's argument resolver).
    with pytest.raises(TypeError):
        src.get_ohlcv("7203", start, end)  # type: ignore[call-arg]

    # Naive datetime raises ValueError.
    with pytest.raises(ValueError):
        src.get_ohlcv("7203", start, end, as_of=datetime(2024, 4, 30))


def test_vendor_source_filters_by_as_of():
    """Bars whose bar_ts_available > as_of must NOT be returned."""
    src = YFinanceSource(history_fn=_fake_history_fn)
    start = datetime(2024, 4, 1, tzinfo=JST)
    end = datetime(2024, 4, 30, tzinfo=JST)

    # as_of caps at 2024-04-02 16:00 JST -> only bars with
    # bar_ts_available <= 2024-04-02 15:30 JST are returned.
    as_of = datetime(2024, 4, 2, 16, 0, tzinfo=JST)
    bars = src.get_ohlcv("7203", start, end, as_of=as_of)
    assert [b.bar_ts.date() for b in bars] == [date(2024, 4, 1), date(2024, 4, 2)]

    as_of2 = datetime(2024, 4, 30, tzinfo=JST)
    bars = src.get_ohlcv("7203", start, end, as_of=as_of2)
    assert [b.bar_ts.date() for b in bars] == [
        date(2024, 4, 1),
        date(2024, 4, 2),
        date(2024, 4, 3),
    ]


def test_vendor_parser_to_ohlcbar():
    """A single yfinance-shaped row converts cleanly to an OHLCBar."""
    bar = yfinance_row_to_ohlcbar(
        {
            "date": date(2024, 4, 1),
            "open": 1000.0,
            "high": 1010.0,
            "low": 995.0,
            "close": 1005.0,
            "adj_close": 1005.0,
            "volume": 1_000_000,
        },
        symbol="7203",
        interval="1d",
    )
    assert bar.symbol == "7203"
    assert bar.interval == "1d"
    assert bar.bar_ts.tzinfo is not None
    assert bar.bar_ts_close < bar.bar_ts_available
    assert bar.bar_ts == bar.bar_ts_available  # CALENDAR.md S0 D-7
    assert bar.bar_ts_close.date() == date(2024, 4, 1)
    assert bar.bar_ts_close.hour == 15
    assert bar.bar_ts_available.hour == 15
    assert bar.bar_ts_available.minute == 30
    assert bar.open == 1000.0
    assert bar.close == 1005.0
    assert bar.adj_close == 1005.0
    assert bar.volume == 1_000_000
    # turnover defaults to close * volume.
    assert bar.turnover == pytest.approx(1005.0 * 1_000_000)


def test_no_real_yfinance_imported():
    """Pytest must NEVER trigger the real yfinance import.

    The lazy import inside ``_default_yfinance_history`` is the only
    place that touches the real package. All vendor tests inject
    ``history_fn``, so ``yfinance`` should never appear in
    ``sys.modules`` while pytest runs.
    """
    assert "yfinance" not in sys.modules, (
        "tests must not import the real yfinance package; use history_fn"
    )


def test_vendor_source_implements_source_protocol():
    """``YFinanceSource`` is structurally a ``Source``."""
    src = YFinanceSource(history_fn=_fake_history_fn)
    assert isinstance(src, Source)


# --- Edge cases --------------------------------------------------------------


def test_vendor_source_rejects_empty_symbol():
    src = YFinanceSource(history_fn=_fake_history_fn)
    start = datetime(2024, 4, 1, tzinfo=JST)
    end = datetime(2024, 4, 30, tzinfo=JST)
    as_of = datetime(2024, 4, 30, tzinfo=JST)
    with pytest.raises(ValueError):
        src.get_ohlcv("", start, end, as_of=as_of)


def test_vendor_source_rejects_start_after_end():
    src = YFinanceSource(history_fn=_fake_history_fn)
    start = datetime(2024, 4, 30, tzinfo=JST)
    end = datetime(2024, 4, 1, tzinfo=JST)
    as_of = datetime(2024, 4, 30, tzinfo=JST)
    with pytest.raises(ValueError):
        src.get_ohlcv("7203", start, end, as_of=as_of)


def test_vendor_source_returns_sorted_bars():
    """Even if the history_fn returns rows in non-sorted order, output is sorted."""
    rows = list(reversed(_fake_rows()))

    def reversed_history(symbol, start, end):
        return rows

    src = YFinanceSource(history_fn=reversed_history)
    start = datetime(2024, 4, 1, tzinfo=JST)
    end = datetime(2024, 4, 30, tzinfo=JST)
    as_of = datetime(2024, 4, 30, tzinfo=JST)
    bars = src.get_ohlcv("7203", start, end, as_of=as_of)
    assert [b.bar_ts.date() for b in bars] == [
        date(2024, 4, 1),
        date(2024, 4, 2),
        date(2024, 4, 3),
    ]


def test_vendor_source_propagates_prev_close():
    """OHLCBar.prev_close threads through consecutive bars."""
    src = YFinanceSource(history_fn=_fake_history_fn)
    start = datetime(2024, 4, 1, tzinfo=JST)
    end = datetime(2024, 4, 30, tzinfo=JST)
    as_of = datetime(2024, 4, 30, tzinfo=JST)
    bars = src.get_ohlcv("7203", start, end, as_of=as_of)
    assert bars[0].prev_close is None
    assert bars[1].prev_close == pytest.approx(1005.0)
    assert bars[2].prev_close == pytest.approx(1012.0)


def test_data_source_name_constant():
    assert DATA_SOURCE_NAME == "yfinance"
