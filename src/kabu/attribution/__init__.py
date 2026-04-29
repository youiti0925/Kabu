"""kabu.attribution: contribution / concentration analysis (P4.5 MVP).

P4.5 decomposes the run's PnL, trade count, skip count, and outcomes by
symbol / sector / period (year / quarter / month) / rule_id / rule_version /
skip_reason / outcome. It produces an attribution report whose purpose is
to highlight CONTRIBUTION and CONCENTRATION -- not causation, not a buy /
sell recommendation, not a trade rule.

Permitted vocabulary in outputs (per PR brief):
    "寄与" / "偏り" / "集中" / "説明力がありそうな候補" /
    "追加検証すべき仮説" / "現在の trace では説明不能" /
    "必要な追加データ" / "リスク警告"

Vocabulary forbidden in outputs:
    "確定" / "これが原因" / "これで勝てる" /
    "この銘柄を買うべき" / "このルールに変更すべき" /
    "絶対" / "保証"

The forbidden-phrase rule is enforced by
``test_attribution_is_observation_not_recommendation``.

This sub-package does NOT generate AI proposals (PR-S10).
This sub-package does NOT recommend any specific symbol.
"""

from kabu.attribution.aggregate import (
    AttributionConfig,
    build_axes,
    build_overall_totals,
)
from kabu.attribution.concentration import (
    DEFAULT_HIGH_CONCENTRATION_PCT,
    DEFAULT_MINIMUM_N,
    detect_concentration_warnings,
)
from kabu.attribution.model import (
    AttributionAxis,
    AttributionHeader,
    AttributionReport,
    AttributionRow,
    ConcentrationWarning,
    OverallTotals,
)
from kabu.attribution.report import (
    build_attribution_report,
    run_full_attribution,
    write_attribution_json,
    write_attribution_markdown,
)

__all__ = [
    "AttributionAxis",
    "AttributionConfig",
    "AttributionHeader",
    "AttributionReport",
    "AttributionRow",
    "ConcentrationWarning",
    "DEFAULT_HIGH_CONCENTRATION_PCT",
    "DEFAULT_MINIMUM_N",
    "OverallTotals",
    "build_attribution_report",
    "build_axes",
    "build_overall_totals",
    "detect_concentration_warnings",
    "run_full_attribution",
    "write_attribution_json",
    "write_attribution_markdown",
]
