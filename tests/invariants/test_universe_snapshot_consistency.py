"""Invariant: signal candidates must respect universe@bar_ts.

Policy: UNIVERSE.md S0 D-7 / POINT_IN_TIME.md 3-5.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from kabu.universe import UniverseMember, UniverseSnapshot


JST = timezone.utc  # placeholder tz; calendar mapping arrives in PR-S5


def _ts(y: int, m: int, d: int) -> datetime:
    return datetime(y, m, d, tzinfo=JST)


def _make_snapshot() -> UniverseSnapshot:
    members = (
        # active throughout
        UniverseMember(
            symbol="A",
            name="Alpha",
            market="TSE_PRIME",
            sector="食料品",
            effective_from=date(2020, 1, 1),
        ),
        # listed mid-period
        UniverseMember(
            symbol="B",
            name="Beta",
            market="TSE_PRIME",
            sector="情報通信",
            effective_from=date(2022, 6, 1),
        ),
        # delisted mid-period
        UniverseMember(
            symbol="C",
            name="Gamma",
            market="TSE_STANDARD",
            sector="小売業",
            effective_from=date(2018, 1, 1),
            effective_to=date(2023, 4, 1),
            delisting_date=date(2023, 3, 31),
        ),
    )
    return UniverseSnapshot(
        universe_snapshot_id="test_snap_v1",
        as_of=_ts(2024, 1, 1),
        source="manual",
        members=members,
    )


def test_member_active_throughout_appears() -> None:
    snap = _make_snapshot()
    syms = {m.symbol for m in snap.members_at(_ts(2021, 6, 1))}
    assert syms == {"A", "C"}


def test_member_before_listing_excluded() -> None:
    snap = _make_snapshot()
    syms = {m.symbol for m in snap.members_at(_ts(2021, 1, 1))}
    assert "B" not in syms


def test_member_after_listing_included() -> None:
    snap = _make_snapshot()
    syms = {m.symbol for m in snap.members_at(_ts(2022, 12, 1))}
    assert "B" in syms


def test_member_on_or_after_effective_to_excluded() -> None:
    snap = _make_snapshot()
    # effective_to == 2023-04-01 -> from that day onward, not a member.
    syms_after = {m.symbol for m in snap.members_at(_ts(2023, 4, 1))}
    assert "C" not in syms_after
    syms_before = {m.symbol for m in snap.members_at(_ts(2023, 3, 31))}
    assert "C" in syms_before


def test_naive_bar_ts_rejected() -> None:
    snap = _make_snapshot()
    with pytest.raises(ValueError):
        snap.members_at(datetime(2022, 1, 1))  # naive


def test_naive_as_of_rejected() -> None:
    members = (
        UniverseMember(
            symbol="A",
            name="Alpha",
            market="TSE_PRIME",
            sector="食料品",
            effective_from=date(2020, 1, 1),
        ),
    )
    with pytest.raises(ValueError):
        UniverseSnapshot(
            universe_snapshot_id="x",
            as_of=datetime(2024, 1, 1),  # naive
            source="manual",
            members=members,
        )


def test_duplicate_symbol_effective_from_rejected() -> None:
    dup = (
        UniverseMember(
            symbol="A", name="Alpha", market="TSE_PRIME", sector="食料品",
            effective_from=date(2020, 1, 1),
        ),
        UniverseMember(
            symbol="A", name="Alpha", market="TSE_PRIME", sector="食料品",
            effective_from=date(2020, 1, 1),
        ),
    )
    with pytest.raises(ValueError):
        UniverseSnapshot(
            universe_snapshot_id="x",
            as_of=_ts(2024, 1, 1),
            source="manual",
            members=dup,
        )


def test_effective_to_before_from_rejected() -> None:
    with pytest.raises(ValueError):
        UniverseMember(
            symbol="A",
            name="Alpha",
            market="TSE_PRIME",
            sector="食料品",
            effective_from=date(2022, 1, 1),
            effective_to=date(2021, 1, 1),
        )


def test_empty_universe_snapshot_id_rejected() -> None:
    with pytest.raises(ValueError):
        UniverseSnapshot(
            universe_snapshot_id="",
            as_of=_ts(2024, 1, 1),
            source="manual",
            members=(),
        )
