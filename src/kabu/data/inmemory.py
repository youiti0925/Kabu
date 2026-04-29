"""In-memory reference implementation of the Source Protocol.

For testing and PR-S1 plumbing. NOT a real data source. No vendor SDK.

Contract references:
- DATA_SOURCES.md S0 D-3 / D-4 (Protocol first; as_of required)
- POINT_IN_TIME.md 3-1 / 5 (no bar with bar_ts_available > as_of)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from kabu.data.source import OHLCBar


@dataclass
class InMemorySource:
    """Returns pre-loaded bars while honoring point-in-time invariants."""

    bars_by_symbol: dict[str, list[OHLCBar]] = field(default_factory=dict)

    def get_ohlcv(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        *,
        as_of: datetime,
    ) -> list[OHLCBar]:
        if start > end:
            raise ValueError("start must be <= end")
        for ts, name in ((start, "start"), (end, "end"), (as_of, "as_of")):
            if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
                raise ValueError(
                    f"{name} must be timezone-aware (CALENDAR.md S0 D-2)"
                )

        bars = self.bars_by_symbol.get(symbol, [])
        out = [
            b
            for b in bars
            if start <= b.bar_ts <= end and b.bar_ts_available <= as_of
        ]
        out.sort(key=lambda b: b.bar_ts)
        return out
