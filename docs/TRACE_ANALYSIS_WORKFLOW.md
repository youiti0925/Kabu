# TRACE_ANALYSIS_WORKFLOW.md

trace 分析のワークフローと集計設計。本ドキュメントは PR-S4 (trace-stats MVP) 以降の運用前提。

---

## 1. 全体フロー

1. **データ取得** (PR-S1): Source Protocol 経由で OHLCV / 銘柄メタ / 営業日 / 主要指数を `data/cache/` に保存。`data_snapshot_hash` を生成。実装は `kabu.data.Source` Protocol + `kabu.data.InMemorySource` (PR-S1)。
2. **decision_trace 生成** (PR-S2): `kabu.decision_trace_build.build_trace(bars=..., ..., cost=...)` で bar 単位に Trace を生成。`kabu.trace_io.write_traces_jsonl` で `runs/<run_id>/trace_raw.jsonl` に append。PR-S2 段階では `decision.final_action = "observe_only"` の placeholder で売買判断は行わない。
3. **backtest** (PR-S3): `kabu.backtest.run_backtest(bars=..., decisions=..., cost=..., run_id=..., trace_jsonl_path=...)` が decision at T close → fill at T+1 open 契約を強制し、`Trade` レコード列を返す。decision は **engine 検証用 scripted action のみ** (PR-S3 brief D-15)。`kabu.run_metadata_io.write_run_metadata_json` で `runs/<run_id>/run_metadata.json` を別ファイルに保存 (BACKTEST_CONTRACT.md S7)。
4. **future_outcome enrich** (PR-S3): bar_ts + N 日経過後に `kabu.outcome.enrich_future_outcomes` が forward_return / mfe / mae を計算、`kabu.outcome.write_outcome_backfill_jsonl` が `runs/<run_id>/outcome_backfill.jsonl` に append。decision builder からは参照禁止 (POINT_IN_TIME.md 3-7)。
5. **trace_joined 生成** (PR-S4): `kabu.outcome.join_traces_with_outcomes` を使って trace_raw と outcome_backfill を (run_id, symbol, bar_ts) で結合し `runs/<run_id>/trace_joined.jsonl` に出力。再現可能 join。
6. **stats 集計** (PR-S4): trace_joined を読み aggregate_many / cross_stats を実行、`runs/<run_id>/stats/` に Markdown + JSON で出力。
7. **attribution** (PR-S4.5): symbol / period / sector / regime 別の損益寄与を分解。
8. **AI Review** (PR-S10): aggregated stats のみを入力として改善提案を生成、`runs/ai_review/<run_id>/proposals.json` に保存。提案は人間承認制。

---

## 2. 集計軸 (cross_stats)

### 2-1. MVP (PR-S4)

- final_action × outcome
- technical_only_action × outcome
- hold_reason × outcome
- blocked_by × outcome
- symbol × outcome (上位 N のみ)
- rule_id / rule_version × outcome

### 2-2. PR-S5 以降

- sector × outcome
- market_index_regime × outcome
- liquidity_regime × outcome
- volume_spike × outcome
- gap_regime × outcome
- close_vs_sma200 bucket × outcome
- rsi14 bucket × outcome
- turnover_zscore bucket × outcome
- new_high_52w_flag × outcome
- weekly_trend × outcome
- monthly_trend × outcome

### 2-3. PR-S6 / S7 / S8 以降

- waveform_bias × outcome
- waveform_bias × earnings_proximity (波形 signal が決算前後で歪むか)
- earnings_proximity × outcome
- earnings_surprise_direction × outcome
- consensus_revision_30d × outcome
- per_bucket × outcome (PIT 採用後)
- pbr_bucket × outcome (PIT 採用後)
- roe_bucket × outcome (PIT 採用後)
- dividend_yield_bucket × outcome (PIT 採用後)

### 2-4. 多軸 cross (3 軸以上)

- sector × market_index_regime × outcome
- earnings_proximity × volume_spike × outcome
- waveform_bias × earnings_proximity × outcome
- liquidity_regime × close_vs_sma200_bucket × outcome
- year × bucket × outcome (時系列安定性)

---

## 3. bucket 定義 (config 駆動)

実装は config ファイルで bucket 境界を保持。実行時に config を切り替えできる。

例 (要決定値):

```yaml
buckets:
  rsi14: [-Inf, 30, 50, 70, Inf]
  close_vs_sma200: [-Inf, -0.10, 0.0, 0.10, Inf]
  turnover_zscore: [-Inf, -1, 0, 1, 2, Inf]
  days_to_earnings: [-Inf, -5, 0, 5, 20, Inf]
  per_trailing: [-Inf, 0, 10, 15, 25, 50, Inf]
  pbr: [-Inf, 0.5, 1.0, 1.5, 3.0, Inf]
```

bucket 境界の変更は SCHEMA.md §1-1 の通り **破壊的変更** 扱い。schema_version を `v2` に上げる。

---

## 4. 統計指標

各 bucket × outcome に対して算出:

- n (標本数)
- hit_rate (forward_return > 0 の比率)
- mean_return / median_return
- std_return
- min_return / max_return / quartiles
- profit_factor (mean of positive / mean of negative の比)
- max_dd (cumulative return ベースの最大 drawdown)
- mean(mfe) / mean(mae)
- big_win_rate / big_loss_rate (outcome_label_static / atr_norm 両方)
- skew / kurtosis (分布形状)

---

## 5. 統計的精度の取扱

### 5-1. 最低標本数

- bucket × outcome は `n >= 30` を最低基準。`n < 30` の bucket は表示するが「低標本」フラグを付ける。
- 多軸 cross は `n >= 50` を推奨。

### 5-2. 信頼区間

- block bootstrap (block_size = 5 / 10 / 20 営業日) で hit_rate / mean_return の 95% CI を算出。
- 株式の return 系列は autocorrelation を持つため、単純 i.i.d. bootstrap は CI を過小評価する。

### 5-3. 多重検定補正

- bucket 数 × 軸数 だけ仮説検定が増える。
- Benjamini-Hochberg で q-value を bucket 単位で計算し、stats レポートに表示。
- 期待される偽陽性数 (FDR × 検定数) を docs として残し、過学習警報の参考にする。

### 5-4. walk-forward / out-of-sample

- 期間を train / validate / test に分割。
- `stats walk_forward --window 1Y --step 3M` のような CLI を将来用意。
- ルール変更候補 (AI Review カテゴリ C) は walk-forward green を最低条件とする (将来明文化)。

---

## 6. stats レポートの必須ヘッダ

`runs/<run_id>/stats/<bucket_axis>.md` の冒頭に必ず含める。

- run_id
- commit_sha
- trace_schema_version
- data_snapshot_hash
- universe_snapshot_id
- universe_size_by_year
- survivorship_policy / survivorship_warning
- pit_warnings (例: ["pit_fundamentals_disabled"])
- period (start_ts, end_ts)
- interval
- rule_id / rule_version / rule_params_hash (該当 run のもの)
- n_total / n_filtered / filter_reasons
- bucket 定義 / 軸の説明
- 多重検定補正方式 (BH 等)
- bootstrap 設定 (block_size 等)
- low_sample_threshold

---

## 7. attribution (PR-S4.5)

### 7-1. 寄与分解の軸

- symbol 寄与 (上位 / 下位の銘柄)
- sector 寄与
- period 寄与 (年度 / 四半期 / 月)
- market_index_regime 寄与
- rule_id / rule_version 寄与
- bucket 寄与 (該当 PR 以降)

### 7-2. 計算

- 全期間 PnL を上記軸で分解。比率 (%) と絶対額 (JPY) の両方を出す。
- 寄与の偏り (1 銘柄 / 1 セクター集中) を警告として出す。

---

## 8. ワークフローの実行手順 (CLI 想定)

PR-S1 / S3 / S4 で順次整備。CLI 名は仮置き。

```sh
kabu fetch       --symbols ... --start ... --end ... --as_of ...
kabu indicators  --run_id ...
kabu trace       --run_id ... --rule baseline_breakout_v1
kabu backtest    --run_id ... --rule baseline_breakout_v1
kabu enrich      --run_id ...    # future_outcome を付与
kabu join        --run_id ...    # trace_joined.jsonl を生成
kabu stats       --run_id ... --axis "final_action,outcome"
kabu stats cross --run_id ... --axes "sector,market_index_regime,outcome"
kabu attribution --run_id ...
kabu ai_review   --run_id ...    # 要承認後のみ
```

各コマンドは `run_metadata` を更新し、`runs/<run_id>/` 配下に append-only で出力する。

---

## 9. AI Review との接続

- AI Review (PR-S10) は **stats レポートのみ** を入力に取る。trace JSONL や trade record は渡さない (AI_REVIEW_SAFETY.md §6)。
- stats レポートのヘッダ (universe_snapshot_id / survivorship_warning / pit_warnings 等) は必ず AI Review 入力に含める。
- AI Review の出力は別ディレクトリ (`runs/ai_review/<run_id>/`) に保存。backtest 出力と分離。

---

## 10. 分析方針 (取扱い哲学)

- 単独要因で結果を説明しようとしない。
- 複数要因の組み合わせ / 相互作用 / 例外パターンまで確認する。
- 「規則性候補」として記述する。「確定」「これが原因」と書かない (AI_REVIEW_SAFETY.md §3)。
- 大勝ち / 大負けは別 bucket として観測 (outcome_label_static の big_win / big_loss)。
- 入るべきだった bar (technical_only_action = "buy" だが final_action = "no_position") も観測対象。
- 入ったが避けるべきだった bar (loss / big_loss) を bucket × outcome で深掘り。

---

## 11. 関連 docs

- SCHEMA.md (slice / future_outcome の独立性)
- POINT_IN_TIME.md (look-ahead 不変条件)
- SURVIVORSHIP.md (survivorship 警告)
- DATA_SOURCES.md (PIT / data_snapshot_hash)
- UNIVERSE.md (universe_snapshot_id)
- BACKTEST_CONTRACT.md (run_metadata 必須項目)
- AI_REVIEW_SAFETY.md (AI Review との接続)
- ROADMAP.md (PR ごとの集計軸追加タイミング)
