"""Concentration warning rules (P4.5 MVP).

Severity codes:
- ``high_pnl_concentration``         -- one bucket carries > X% of total net pnl
- ``high_trade_count_concentration`` -- one bucket carries > X% of total trades
- ``low_sample``                     -- per-row marker; n < minimum_n
- ``unknown_sector``                 -- attached to the row when bucket_key is "unknown" on the sector axis
- ``no_closed_trades``               -- run-level: there are no closed trades to attribute net pnl to

The first two are computed at the report level (``detect_concentration_warnings``).
``low_sample`` and ``unknown_sector`` are attached row-by-row in
``aggregate.py``. ``no_closed_trades`` is attached at the report level
when the run has zero closed trades.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Optional

from kabu.attribution.model import (
    AttributionAxis,
    AttributionRow,
    ConcentrationWarning,
    OverallTotals,
)


DEFAULT_HIGH_CONCENTRATION_PCT: float = 50.0
DEFAULT_MINIMUM_N: int = 30


def _abs_or_none(v: Optional[float]) -> Optional[float]:
    if v is None:
        return None
    return abs(v)


def detect_concentration_warnings(
    axes: Iterable[AttributionAxis],
    overall: OverallTotals,
    *,
    high_concentration_pct: float = DEFAULT_HIGH_CONCENTRATION_PCT,
) -> tuple[ConcentrationWarning, ...]:
    """Return the list of report-level concentration warnings.

    Excludes the ``outcome`` axis from the concentration check (a single
    "win" bucket carrying most of the contribution is expected and not
    a concentration risk in the same sense).
    """
    out: list[ConcentrationWarning] = []
    threshold_frac = high_concentration_pct / 100.0
    overall_total_net = _abs_or_none(overall.total_net_pnl_jpy)
    overall_trade_count = overall.trade_count

    for axis in axes:
        if axis.axis == "outcome":
            continue
        for row in axis.rows:
            row_total_net = _abs_or_none(row.total_net_pnl_jpy)
            if (
                overall_total_net is not None
                and overall_total_net > 0
                and row_total_net is not None
                and row_total_net / overall_total_net > threshold_frac
            ):
                pct = 100.0 * row_total_net / overall_total_net
                out.append(
                    ConcentrationWarning(
                        axis=axis.axis,
                        bucket_key=row.bucket_key,
                        severity="high_pnl_concentration",
                        detail=(
                            f"このbucketが |net_pnl| の {pct:.1f}% に寄与し、"
                            f"閾値 {high_concentration_pct:.1f}% を超えています。偏りに注意。"
                        ),
                    )
                )
            if (
                overall_trade_count > 0
                and row.trade_count > 0
                and (row.trade_count / overall_trade_count) > threshold_frac
            ):
                pct = 100.0 * row.trade_count / overall_trade_count
                out.append(
                    ConcentrationWarning(
                        axis=axis.axis,
                        bucket_key=row.bucket_key,
                        severity="high_trade_count_concentration",
                        detail=(
                            f"このbucketが trade_count の {pct:.1f}% を占め、"
                            f"閾値 {high_concentration_pct:.1f}% を超えています。"
                        ),
                    )
                )

    if overall.trade_count > 0 and overall.closed_trade_count == 0:
        out.append(
            ConcentrationWarning(
                axis="overall",
                bucket_key="(run)",
                severity="no_closed_trades",
                detail=(
                    "run 内に closed trade が存在しないため、"
                    "net_pnl 寄与が計算できません。集計は trace / skipped のみに限定されます。"
                ),
            )
        )

    return tuple(out)
