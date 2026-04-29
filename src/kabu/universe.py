"""Universe snapshot and membership query.

Contract references:
- UNIVERSE.md S0 D-1 (MVP-1 = manual symbol list)
- UNIVERSE.md S0 D-7 (universe_snapshot_id required in run_metadata)
- UNIVERSE.md 4 (snapshot schema with effective_from / effective_to)
- POINT_IN_TIME.md 3-5 (membership filter at bar_ts)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class UniverseMember:
    """One row of a universe snapshot.

    `effective_to` is the first date on which the symbol is no longer a
    member. ``None`` means the symbol is currently active.
    """

    symbol: str
    name: str
    market: str
    sector: str
    effective_from: date
    effective_to: date | None = None
    listing_date: date | None = None
    delisting_date: date | None = None

    def __post_init__(self) -> None:
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError(
                "effective_to must be > effective_from "
                f"(symbol={self.symbol!r})"
            )


@dataclass(frozen=True)
class UniverseSnapshot:
    """A point-in-time, immutable universe definition.

    See UNIVERSE.md 4 for the full schema. PR-S1 keeps the minimum subset
    needed by `members_at`.
    """

    universe_snapshot_id: str
    as_of: datetime
    source: str
    members: tuple[UniverseMember, ...]

    def __post_init__(self) -> None:
        if not self.universe_snapshot_id:
            raise ValueError("universe_snapshot_id must be non-empty")
        if self.as_of.tzinfo is None or self.as_of.tzinfo.utcoffset(self.as_of) is None:
            raise ValueError(
                "UniverseSnapshot.as_of must be timezone-aware "
                "(CALENDAR.md S0 D-2)"
            )
        seen: set[tuple[str, date]] = set()
        for m in self.members:
            key = (m.symbol, m.effective_from)
            if key in seen:
                raise ValueError(
                    f"duplicate (symbol, effective_from) entry: {key!r}"
                )
            seen.add(key)

    def members_at(self, bar_ts: datetime) -> tuple[UniverseMember, ...]:
        """Return members active at the given bar timestamp.

        Filter rule (POINT_IN_TIME.md 3-5):
            effective_from <= bar_ts.date() AND
            (effective_to is None OR bar_ts.date() < effective_to)
        """
        if bar_ts.tzinfo is None or bar_ts.tzinfo.utcoffset(bar_ts) is None:
            raise ValueError("bar_ts must be timezone-aware")
        bar_date = bar_ts.date()
        return tuple(
            m
            for m in self.members
            if m.effective_from <= bar_date
            and (m.effective_to is None or bar_date < m.effective_to)
        )
