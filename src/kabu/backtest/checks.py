"""Conservative unfillability checks.

PR-S3 brief: stop-high / stop-low precise tables are deferred to a later
PR. For MVP, the following bar-level flags are taken as "unfillable":

- ``is_halted``           -> "halted"
- ``is_special_quote``    -> "special_quote"
- ``is_circuit_breaker``  -> "circuit_breaker"
- ``volume == 0``          -> "volume_zero"
- ``turnover == 0``        -> "turnover_zero"
- ``volume < min_volume``  -> "volume_floor"
- ``turnover < min_turnover_jpy`` -> "turnover_floor"

If none of the above apply, the bar is fillable.
"""

from __future__ import annotations

from typing import Optional

from kabu.data.source import OHLCBar


def is_unfillable(
    bar: OHLCBar,
    *,
    min_volume: int = 1,
    min_turnover_jpy: float = 1.0,
) -> Optional[str]:
    """Return a reason string if the bar cannot be used as a fill, else None."""
    if bar.is_halted:
        return "halted"
    if bar.is_special_quote:
        return "special_quote"
    if bar.is_circuit_breaker:
        return "circuit_breaker"
    if bar.volume <= 0:
        return "volume_zero"
    if bar.turnover <= 0:
        return "turnover_zero"
    if bar.volume < min_volume:
        return "volume_floor"
    if bar.turnover < min_turnover_jpy:
        return "turnover_floor"
    return None
