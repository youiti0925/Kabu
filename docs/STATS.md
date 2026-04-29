# STATS.md

PR-S4 trace-stats MVP の出力契約と bucket 境界。

---

## 0. 重要な前提

- **PR-S4 は観測用集計**。売買ルール / 銘柄推奨 / AI Review ではない。
- 集計対象は P3.5 で固定された `runs/<run_id>/` 配下の出力 (BACKTEST_CONTRACT.md §6-A)。
- 入力主軸:
  - `trace_joined.jsonl`
  - `trades.jsonl`
  - `skipped_fills.jsonl`
  - `run_metadata.json`
  - `backtest_result.json`
- テストはすべて `tmp_path` を使用。実 `runs/` への書き込みは禁止。
- `analytics_version = "kabu.stats.v1"`。bucket 境界変更は破壊的変更扱い。`v2` を切り `migrations/` を併設する方針。

---

## 1. 最低標本数 (minimum_n)

- デフォルト `DEFAULT_MINIMUM_N = 30`。
- `n < minimum_n` の bucket には `low_sample = true` フラグを付ける。
- low_sample bucket は **隠さず警告付きで表示** する。
- AI Review (PR-S10) は将来 low_sample bucket を **C カテゴリ提案 (ルール変更候補)** に使ってはならない (AI_REVIEW_SAFETY.md §10 系)。本 PR では AI Review 自体は実装しない。

---

## 2. bucket 境界

### 2-1. RSI (`bucket_rsi`)

| 境界 | label |
|---|---|
| `rsi < 30` | `rsi_lt_30` |
| `30 <= rsi < 50` | `rsi_30_to_50` |
| `50 <= rsi < 70` | `rsi_50_to_70` |
| `rsi >= 70` | `rsi_gte_70` |
| `rsi is None` | `unknown` |

### 2-2. SMA200 距離 (`bucket_sma200_distance`)

`close_vs_sma200 = (close - sma200) / sma200` (fraction; -0.10 = -10%).

| 境界 | label |
|---|---|
| `< -0.10` | `below_-10pct` |
| `-0.10 <= x < 0.0` | `-10_to_0pct` |
| `0.0 <= x < 0.10` | `0_to_10pct` |
| `x >= 0.10` | `above_10pct` |
| `x is None` | `unknown` |

### 2-3. MACD ヒスト符号 (`bucket_macd_hist`)

| 境界 | label |
|---|---|
| `hist > 0.0` | `positive` |
| `hist < 0.0` | `negative` |
| `hist == 0.0` | `zero` |
| `hist is None` | `unknown` |

### 2-4. 変更ポリシー

- 境界値・label・範囲を変えると既存 stats が再計算される。`analytics_version` を上げ `migrations/` を用意する。
- pytest `test_bucket_boundaries_documented` がコード上の bucket 名と本 docs の対応をチェックする。

---

## 3. 集計軸 (PR-S4 MVP)

### 3-1. 単一軸 (trace 由来)

- `final_action_x_outcome`
- `technical_only_action_x_outcome`
- `rule_id_x_outcome`
- `rule_version_x_outcome`
- `symbol_x_outcome`
- `trend_label_x_outcome`
- `rsi_bucket_x_outcome`
- `sma200_distance_x_outcome`
- `macd_hist_sign_x_outcome`
- `hold_reason_x_outcome`
- `blocked_by_x_outcome`

### 3-2. 単一軸 (trade 由来)

- `trade_exit_reason_x_outcome` (trades が空でなければ出力)

### 3-3. 2 軸 cross

- `final_action_x_rsi_bucket_x_outcome`
- `trend_label_x_rsi_bucket_x_outcome`

bucket key は `"<axis1>::<axis2>"` 形式。3 軸以上は MVP 外 (多重検定の指数的増加を防ぐため)。

### 3-4. その他

- `skip_reason_counts: dict[str, int]`: `skipped_fills.jsonl` の reason 別カウント。
- `trade_pnl_summary`: trade 全体の win/loss/flat/unknown カウント、gross/net pnl 合計、fee/slippage 合計。

---

## 4. outcome ラベル

### 4-1. trace-level (`trace_outcome_label`)

優先順:
1. `slices.future_outcome.outcome_label_static` が存在 → そのまま採用
2. `slices.future_outcome.outcome_label_atr_norm` → 代替
3. `slices.future_outcome.forward_return_5d` の符号 (>0=win / <0=loss / 0=flat)
4. `future_outcome` 自体が None または return が None → `unknown`

許容 label: `big_win | win | flat | loss | big_loss | unknown`。

### 4-2. trade-level (`trade_outcome_label`)

`Trade.net_pnl_jpy` の符号:
- `>0` → `win`
- `<0` → `loss`
- `0` → `flat`
- `None` → `unknown`

---

## 5. 出力フォーマット

### 5-1. 配置

```
runs/<run_id>/stats/
    summary.md
    summary.json
```

`run_full_stats(inp)` がこの 2 ファイルを書く。

### 5-2. ヘッダ必須項目

Markdown / JSON 両方に以下を含める:
- `run_id`
- `commit_sha`
- `trace_schema_version` (= `kabu.trace.v1`)
- `analytics_version` (= `kabu.stats.v1`)
- `data_snapshot_hash`
- `universe_snapshot_id`
- `survivorship_policy`
- `survivorship_warning`
- `pit_warnings` (run_metadata.warnings のうち `pit*` で始まるもの)
- `other_warnings` (それ以外)
- `generated_at` (UTC, tz-aware)
- `n_total`
- `n_filtered`
- `filter_reasons` (dict[str, int])
- `minimum_n`

### 5-3. 各 BucketStats の出力フィールド

- `bucket_key`
- `n`
- `n_unknown_outcome`
- `outcome_counts` (dict[str, int])
- `hit_rate` (None or float, unknown を除外して計算)
- `mean_return` (None or float, forward_return_5d の存在分の平均)
- `mean_net_pnl_jpy` / `total_net_pnl_jpy` (None or float)
- `low_sample` (bool, n < minimum_n)

---

## 6. filter / unavailable_reason

- `n_total = len(traces)` (joined trace の総数)
- `n_filtered = sum(1 for t in traces if t.unavailable_reason)` 
- `filter_reasons[reason] = count`
- ヘッダに表示。bucket からは除外しない (PR-S4 MVP は全件 bucket 化する; PR-S5+ で filter 適用を検討)。

---

## 7. テスト

- `tests/stats/test_loaders.py` (loader 不変条件: required files / run_id 一致 / schema_version 一致)
- `tests/stats/test_buckets.py` (bucket 境界 + 本 docs との照合)
- `tests/stats/test_aggregate.py` (low_sample flag / hit_rate / mean / cross_axis)
- `tests/stats/test_report.py` (end-to-end + ヘッダ + writer)

---

## 8. 関連 docs

- BACKTEST_CONTRACT.md §6-A: run output layout
- TRACE_ANALYSIS_WORKFLOW.md §1: 全体パイプライン
- POINT_IN_TIME.md §3-7: future_outcome は post-processing
- AI_REVIEW_SAFETY.md §10 系: low_sample bucket を C 提案に使わない
- ROADMAP.md
