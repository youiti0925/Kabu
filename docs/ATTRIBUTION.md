# ATTRIBUTION.md

P4.5 attribution MVP の出力契約と運用ルール。

---

## 0. 重要な前提

- **attribution は観測**。原因確定ではなく、銘柄推奨でもなく、売買ルールでもない。
- 出力で扱う概念は **寄与 / 偏り / 集中**。「これが原因」ではない。
- 1 銘柄 / 1 セクター / 1 期間への集中は **リスク警告** として表示する。
- 入力は P3.5 / PR-S4 と同じ `runs/<run_id>/` 配下 (BACKTEST_CONTRACT.md §6-A)。
- 既存 `kabu.stats.load_run_inputs(paths)` を再利用 (重複実装ゼロ)。
- `analytics_version = "kabu.attribution.v1"`。集計軸 / 警告閾値の変更は破壊的変更扱い。

---

## 1. 集計軸

| axis | 由来 | 備考 |
|---|---|---|
| `symbol` | trace + trade + skipped | 全 record 種が key を持つ |
| `sector` | trace.sector / trade.symbol → trace の sector マップ | 紐付かない場合 `unknown` + `unknown_sector` row warning |
| `year` | bar_ts / entry_decision_ts / decision_ts の年 | `YYYY` 形式 |
| `quarter` | 同 | `YYYY-Q1..Q4` 形式 |
| `month` | 同 | `YYYY-MM` 形式 |
| `rule_id` | trace.slices.decision.rule_id | trace 由来のみ |
| `rule_version` | trace.slices.decision.rule_version | trace 由来のみ |
| `skip_reason` | skipped.reason | skipped 由来のみ |
| `outcome` | trace + trade の outcome label | concentration 警告から除外 |

各 axis の row には以下が入る (`AttributionRow`):
- `trace_count` / `trade_count` / `skipped_count`
- `win_count` / `loss_count` / `flat_count` / `unknown_count`
- `total_net_pnl_jpy` / `total_gross_pnl_jpy` / `total_fee_jpy` / `total_slippage_jpy`
- `mean_net_pnl_jpy`
- `contribution_pct` (= 100 × row.total_net_pnl_jpy / overall.total_net_pnl_jpy。分母 0 / None なら None)
- `low_sample` (n < minimum_n)
- `warnings` (row 単位の severity codes)

---

## 2. concentration warnings

| severity | 検出ルール |
|---|---|
| `high_pnl_concentration` | row.|net_pnl| / overall.|net_pnl| > `high_concentration_pct` (default 50%) |
| `high_trade_count_concentration` | row.trade_count / overall.trade_count > `high_concentration_pct` |
| `low_sample` | n < `minimum_n` (default 30)。row.warnings に付与 |
| `unknown_sector` | sector axis の `unknown` bucket。row.warnings に付与 |
| `no_closed_trades` | overall.trade_count > 0 かつ overall.closed_trade_count == 0。report-level |

注意:
- `outcome` axis は concentration 警告から **除外**。「win bucket が支配的」は当然のため。
- 警告は **リスクの提示** であり、原因の確定ではない。

---

## 3. 出力フォーマット

### 3-1. 配置

```
runs/<run_id>/stats/
    attribution.md      # 人間向け
    attribution.json    # 機械可読
```

`run_full_attribution(inp)` がこの 2 ファイルを書く。テストは `tmp_path` のみ使う。

### 3-2. ヘッダ必須項目

Markdown / JSON 両方に以下を含める:
- `run_id`
- `commit_sha`
- `trace_schema_version` (= `kabu.trace.v1`)
- `analytics_version` (= `kabu.attribution.v1`)
- `data_snapshot_hash`
- `universe_snapshot_id`
- `survivorship_policy`
- `survivorship_warning`
- `pit_warnings` (`run_metadata.warnings` のうち `pit*` で始まるもの)
- `other_warnings` (それ以外)
- `generated_at` (UTC, tz-aware)
- `n_total` (= trace_count)
- `trade_count`
- `skipped_count`
- `minimum_n`
- `high_concentration_pct`

---

## 4. 表現ルール

出力 (Markdown / JSON 内のテキスト) で **使ってよい**:
- 寄与
- 偏り
- 集中
- 説明力がありそうな候補
- 追加検証すべき仮説
- 現在の trace では説明不能
- 必要な追加データ
- リスク警告

出力で **使ってはいけない** (pytest `test_attribution_is_observation_not_recommendation` で検査):
- 確定
- これが原因
- これで勝てる
- この銘柄を買うべき
- このルールに変更すべき
- 絶対
- 保証

---

## 5. テスト

- `tests/attribution/test_aggregate.py` (6): symbol pnl / period (year+quarter+month) / sector unknown / rule_id / skip_reason / contribution_pct のゼロ除算
- `tests/attribution/test_concentration.py` (4): single symbol 集中 / バランス時警告なし / no_closed_trades / low_sample row warning
- `tests/attribution/test_report.py` (6): writer は tmp_path / ヘッダ bias 警告 / 禁止表現 / 期待 axis セット / overall totals / outcome 除外

---

## 6. 関連 docs

- BACKTEST_CONTRACT.md §6-A: run output layout
- STATS.md: PR-S4 trace-stats との関係 (補完関係。stats は条件別傾向、attribution は寄与・偏り)
- TRACE_ANALYSIS_WORKFLOW.md §1 step 7-A: attribution パイプライン
- POINT_IN_TIME.md §3-7: future_outcome は post-processing
- AI_REVIEW_SAFETY.md §10 系: low_sample row / outcome 単独 bucket は将来 AI Review の C 提案に使わない
- ROADMAP.md
