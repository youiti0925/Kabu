# BACKTEST_CONTRACT.md

backtest の約定タイミング・コスト・調整方針の契約。MVP は long_only / 現物相当 / 日次 (1d)。

---

## 0. MVP 決定 (PR-S0.5 / N2 で確定 + PR-S3 で実装)

本セクションは「決定」であり、後続 PR は本決定に従う。変更には別途承認が必要。

- D-1. **MVP は long_only / 現物相当のみ**。空売り・信用は MVP 外。
- D-2. **税前 PnL** (`tax_basis = "pretax"`)。配当税 / 譲渡税は将来課題。
- D-3. **decision at T close → fill at T+1 open** (CALENDAR.md §0 D-3 / D-4 と整合)。PR-S3 の `kabu.backtest.engine.run_backtest` で構造的に強制。
- D-4. **same close fill (T close で約定) は MVP では禁止** (CALENDAR.md §0 D-5)。`assumed_fill_bar="same_close"` 等を渡すと engine が `ValueError` で拒否。pytest `test_same_close_fill_forbidden` で固定。
- D-5. `execution_assumption.assumed_fill_bar = "next_open"` を **必須** で持つ。
- D-6. `execution_assumption.latency_bars = 1` を **必須** で持つ。engine も `latency_bars != 1` を `ValueError` で拒否。
- D-7. `slippage_bps` を `run_metadata.costs.slippage_bps` に **必ず保存**。pytest `test_fee_and_slippage_applied` で fill price への反映を確認。
- D-8. `fee_bps` および `fee_fixed_jpy` を `run_metadata.costs.fee_bps` / `run_metadata.costs.fee_fixed_jpy` に **必ず保存**。
- D-9. **technical / long_term_trend / waveform 計算は adj_close 系列、約定価格 (fill_price) は raw 系列**。PR-S3 engine の `compute_long_entry_fill_price` は raw open のみを参照。pytest `test_dividend_ex_day_handling` で簡易確認。
- D-10. 売買単位 (lot_size) は **100 株を MVP の基本**。PR-S3 engine の `target_jpy_per_trade // entry_price // lot_size * lot_size` で量を計算。下限未満は `below_lot_size` で skip。
- D-11. 出来高フロア / 売買代金フロアは **PR-S3 で導入**。`min_volume` / `min_turnover_jpy` で表現。違反時は `volume_zero` / `volume_floor` / `turnover_zero` / `turnover_floor` の reason で skip。pytest `test_volume_floor_cap` で固定。
- D-12. ストップ高 / ストップ安 / 特別気配 / 売買停止は **fill 不可または保守的処理**。PR-S3 では `OHLCBar.is_halted / is_special_quote / is_circuit_breaker` の bar フラグ proxy で判定 (`kabu.backtest.checks.is_unfillable`)。pytest `test_stop_high_low_block`。正確な制限値幅 table は後続 PR。
- D-13. `run_metadata` の必須項目は §7 を参照。これらが揃わない run は出力しない (pytest `test_run_metadata_required` で検証)。`kabu.run_metadata_io.read_run_metadata_json` が必須キー欠落で `ValueError`。
- D-14. `currency = "JPY"` 固定 / `report_currency = "JPY"` 固定 (DATA_SOURCES.md §0 D-2)。
- D-15. **PR-S3 の action は engine 検証用 placeholder** (`enter_long`, `exit_long`, `no_position`, `observe_only`)。これは **売買ルールではない / 銘柄推奨ではない**。`buy / sell_to_close` 文字列も engine が受け取れるが「テスト用 action 表現」。実戦ルール化は別 PR で別承認が必要。
- D-16. **`trace_jsonl_path` は Trade に必須**。PR-S3 engine が全 Trade に stamp。pytest `test_trace_jsonl_path_required_for_trades` で固定。
- D-17. **`survivorship_policy` は run_metadata に必須**。pytest `test_survivorship_policy_recorded` で固定。
- D-18. **future_outcome は post-processing**。`kabu.outcome.enrich_future_outcomes` で別経路として実装。`kabu.decision_trace_build.build_trace` から import / 引数受け取り 共に禁止。pytest `test_decision_does_not_depend_on_outcome` (PR-S2) と `test_future_outcome_backfill_separate_from_raw_trace` (PR-S3) で固定。`outcome_backfill.jsonl` は `trace_raw.jsonl` と **別ファイル**。

---

## 1. 基本方針 (決定)

§0 を反映した基本方針。

- MVP は long_only / 現物相当のみ (D-1)。空売り・信用は MVP 外。
- 通貨は JPY 固定 (`currency = "JPY"` / `report_currency = "JPY"`) (D-14)。海外株は MVP 外。
- bar interval は `1d` のみ (CALENDAR.md §0 D-1)。intraday は将来。
- 税前 PnL (D-2)。`run_metadata.tax_basis = "pretax"` を必ず保存。
- 単一銘柄 backtest は portfolio size = 1 の特殊例として実装する (将来の portfolio 拡張に備える)。

---

## 2. 約定タイミング契約 (決定)

§0 D-3 / D-4 / D-5 / D-6 を実装契約として展開する。

### 2-1. decision timing

- 判定: 当日 (T) の close 確定後、すなわち `bar_ts_close[T]` 以降 (D-3)。
- close 確定は CALENDAR.md の半日立会等を考慮した `bar_ts_close` を使う。
- decision builder は **future_outcome を入力に取らない** (POINT_IN_TIME.md §3-4 / SCHEMA.md §4-10)。

### 2-2. fill timing

- 約定: 翌営業日 (T+1) の寄付 (D-3)。
- `assumed_fill_bar = "next_open"` を **必須** で trace に持つ (D-5)。
- `latency_bars = 1` を **必須** で trace に持つ (D-6)。
- same close fill (T close で約定) は **MVP では禁止** (D-4)。look-ahead と区別がつかなくなるため。
- 翌営業日が祝日 / 半日立会の場合は `next_business_day(T+1)` を使う (CALENDAR.md §1 / §4)。

### 2-3. fill_price

- `execution_assumption.fill_price` は raw (未調整) の T+1 open を使う。
- スリッページは `slippage_bps` で表現し、long エントリ時は `fill_price * (1 + slippage_bps/10000)`。
- 退出時は同様にロング方向に不利な側へ寄せる。
- 詳細実装は PR-S3。

---

## 3. コストモデル

### 3-1. 手数料

- 表現: `fee_bps` (bps 単位の比例手数料) + `fee_fixed_jpy` (optional, 固定手数料)。
- MVP デフォルトは `fee_bps = 5` (= 0.05%) を仮置き。確定値は要承認。
- 売り買い両側に課す。

### 3-2. スリッページ

- `slippage_bps` で表現。MVP デフォルト `slippage_bps = 5` を仮置き。
- 将来は `liquidity_regime` / `tradable_size_jpy` / 注文サイズに応じた可変モデルへ。

### 3-3. 税金

- MVP は **税前**。
- run_metadata に `tax_basis: "pretax"` を必ず記録。
- 配当税・譲渡税は将来課題。

---

## 4. 注文制約

### 4-1. 売買単位

- MVP は単元 (lot_size, 通常 100 株) のみ。単元未満は不可。
- 計算: 注文株数は `floor(target_jpy / fill_price / lot_size) * lot_size`。

### 4-2. tick_size

- 株価帯ごとに tick_size が変わる。CALENDAR.md §9 と UNIVERSE.md §4 で参照される table を使用。
- `fill_price` は tick_size に丸める (long 側は不利方向 = 切り上げ)。

### 4-3. 出来高フロア (volume floor)

- 1 日の売買代金の `volume_floor_ratio` (デフォルト 1%) を超える注文は約定不可、または分割。
- MVP の最小実装: 超過なら `is_realistic = false`、`fill_reason = "volume_floor_capped"`、`fill_price = null`。

### 4-4. 売買代金フロア

- 銘柄の `avg_turnover_20d` が `min_avg_turnover_jpy` (例 1 億円) 未満なら `low_liq_flag = true` で約定不可扱い (MVP)。

### 4-5. 制限値幅 (値幅制限)

- 前日終値帯で決まる table を使う (PR-S0.7 / PR-S5)。
- 当日 open が制限値幅 hit (= ストップ高 / ストップ安) なら約定不可、`fill_reason = "stop_high_blocked"` / `"stop_low_blocked"`。

### 4-6. 特別気配 / 売買停止

- `market.is_special_quote == true` または `market.is_halted == true` の bar では約定不可。
- events.py 由来のフラグを参照。
- `fill_reason = "special_quote"` / `"halted"`。

---

## 5. コーポレートアクション

### 5-1. 配当落ち

- ex_date の bar では `event_ctx.ex_dividend_flag = true`。
- 計算指標は adj_close (= total return / split-and-dividend back-adjusted) で連続性を保つ。
- 約定価格は raw (未調整) を使う。
- pytest `test_dividend_ex_day_handling` で「ex_date 前後で意図しない PnL 歪みが出ない」ことを検証 (PR-S3)。

### 5-2. 株式分割

- ex_date の bar では `event_ctx.corporate_action_today` に `"split"` を含める。
- 過去の adj_close は分割後ベースに再計算される (vendor 側で発生)。
- 過去の volume も分割調整するか raw のままにするかは vendor 仕様で異なる。MVP は `volume_split_adjusted` も併存させる方向で要決定。
- pytest `test_split_adjustment_continuity` で「分割を跨いだ adj_close が連続」を検証。

### 5-3. 上場廃止

- delisting_date を超えた bar では universe から除外。
- 保有していた場合は delisting_date の翌営業日寄付で強制決済 (MVP の保守ルール)。
- 倒産 / 整理銘柄の最終約定価格は `last_known_close` または 0 円 (要決定。デフォルトは `last_known_close * 0.5` 等の保守側を提案)。
- 詳細は SURVIVORSHIP.md §3-3 参照。

---

## 6. 調整済 vs 未調整 価格の使い分け (決定)

§0 D-9 を実装契約として展開する。詳細境界は PR-S1 (indicators) / PR-S3 (backtest) で再確認。

| 用途 | 系列 | 備考 |
|---|---|---|
| technical / long_term_trend / waveform 計算 | **adj_close** (split & dividend back-adjusted) | `technical.adjustment_basis = "split_dividend_back_adjusted"` を必須 (SCHEMA.md §4-2) |
| 約定価格 (fill_price) | **raw** open / close | tick_size に丸める |
| 出来高比較 (turnover_zscore 等) | turnover (= raw price × volume) ベース | turnover は調整係数の影響が比較的小さい |
| ギャップ計算 (gap_pct) | raw close → raw open | `market.prev_close` と `market.open` から計算 |
| 表示用 chart | 用途で選択 | SCHEMA は両系列を保持 |

`technical.adjustment_basis = "split_dividend_back_adjusted"` を v1 で固定する (SCHEMA.md §4-2)。これは schema の **必須** フィールド。

---

## 6-A. Run output layout (P3.5 で決定)

P3.5 で `kabu.run_paths.RunPaths` / `build_run_paths(base_dir, run_id)` を導入し、以下のファイル配置を **MVP 決定** として固定した。PR-S4 trace-stats はこの配置を入力前提とする。

```
runs/<run_id>/
    run_metadata.json         # kabu.run_metadata_io
    trace_raw.jsonl           # kabu.trace_io
    outcome_backfill.jsonl    # kabu.outcome
    trace_joined.jsonl        # kabu.trace_io after join
    trades.jsonl              # kabu.backtest.io.write_trades_jsonl
    skipped_fills.jsonl       # kabu.backtest.io.write_skipped_fills_jsonl
    backtest_result.json      # summary + file references (NOT trades body)
    stats/                    # PR-S4+
```

注意:

- `backtest_result.json` は **summary + file references**。`trades` 本体は `trades.jsonl`、`skipped` 本体は `skipped_fills.jsonl` に分離 (ストリーミング読み込みと append-only を維持するため)。
- `kabu.backtest.io.BacktestResultSummary` の必須フィールド: `run_id`, `created_at` (tz-aware), `initial_cash_jpy`, `final_cash_jpy`, `trade_count`, `skipped_count`, `open_position_count`, `trace_jsonl_path`, `trades_jsonl_path`, `skipped_fills_jsonl_path`。reader が欠落で `ValueError`。
- `kabu.backtest.engine.SkippedFill` は P3.5 で `run_id` / `symbol` / `attempted_fill_ts` を必須に拡張。pytest `test_skipped_fill_jsonl_roundtrip` で round-trip を保証。
- `runs/` は **git 管理しない** (RISKS.md 5-3 / `.gitignore` / `scripts/check_no_forbidden_paths.py`)。テストはすべて `tmp_path` を使う。pytest `test_run_paths_use_tmp_path` / `test_no_committed_run_outputs`。
- `RunPaths.run_id` は path traversal を含む文字列を拒否 (`..`, `/`, `\\`, `\x00`)。
- `kabu.backtest.io.write_backtest_outputs(*, paths, result, created_at)` で trades.jsonl / skipped_fills.jsonl / backtest_result.json を一括 write。

---

## 7. run_metadata に必ず残す項目 (決定)

§0 D-13 / D-7 / D-8 を実装契約として展開する。

- `run_id`
- `commit_sha`
- `created_at`
- `data_source` / `data_source_version` (DATA_SOURCES.md §0 D-5)
- `data_snapshot_hash`
- `universe_snapshot_id` (UNIVERSE.md §0 D-7)
- `survivorship_policy` (UNIVERSE.md §0 D-4)
- `survivorship_warning` (UNIVERSE.md §0 D-4)
- `calendar_id`
- `trace_schema_version` (SCHEMA.md §1)
- `interval` (CALENDAR.md §0 D-1 / SCHEMA.md §2)
- `currency` = "JPY" (DATA_SOURCES.md §0 D-2)
- `report_currency` = "JPY" (DATA_SOURCES.md §0 D-2)
- `period` (`start_ts`, `end_ts`)
- `costs`: `{ fee_bps, fee_fixed_jpy, slippage_bps }` (D-7 / D-8)
- `volume_floor_ratio`
- `min_avg_turnover_jpy`
- `assumed_fill_bar` = "next_open" (D-5)
- `latency_bars` = 1 (D-6)
- `tax_basis` = "pretax" (D-2)
- `rule_id` / `rule_version` / `rule_params_hash` (judgement に使った placeholder ルール)
- `warnings[]` (例: `"static_current_listing_universe"`, `"pit_fundamentals_disabled"`)
- `unavailable_reason_summary`
- `libraries[]`: `[{slice, library_id, library_kind, feature_set}]` (waveform 等を使った場合。SCHEMA.md §0 / §2 と整合)

これらが満たされない run は出力しない。pytest `test_run_metadata_required` (PR-S3) で検証する。

---

## 8. ポートフォリオ拡張への布石

将来の PR (S5 以降) で複数銘柄に拡張する際の API 形を MVP から仮固定する。

- `Order(symbol, side, target_jpy_or_qty, time_in_force, ...)`
- `Fill(order_id, fill_price, fill_qty, fill_ts, fee, slippage, fill_reason)`
- `PortfolioState(cash, positions, ts)`
- 単一銘柄は positions の長さが常に 0 か 1 の特殊例。
- 制約: max_positions, per_symbol_cap_pct, per_sector_cap_pct, turnover_cap (MVP では未使用、将来用に reserve)。

---

## 9. 不変条件 / pytest

- `test_dividend_ex_day_handling` (PR-S3)
- `test_stop_high_low_block` (PR-S3)
- `test_volume_floor_cap` (PR-S3)
- `test_run_metadata_required` (PR-S3)
- `test_trace_jsonl_path_required_for_trades` (PR-S3)
- `test_split_adjustment_continuity` (PR-S1)

---

## 10. チェックリスト

### 10-1. 決定済 (N2 / PR-S0.5 で確定)

- [x] long_only / 現物相当 (D-1)
- [x] 税前 PnL (D-2)
- [x] decision at T close → fill at T+1 open (D-3)
- [x] same close fill 禁止 (D-4)
- [x] assumed_fill_bar / latency_bars 必須 (D-5 / D-6)
- [x] slippage_bps / fee_bps / fee_fixed_jpy を run_metadata に必須保存 (D-7 / D-8)
- [x] technical = adj / fill = raw (D-9)
- [x] currency = JPY 固定 / report_currency = JPY 固定 (D-14)
- [x] 売買単位は MVP の基本 = 100 株 (D-10。例外確認は PR-S3 着手前)
- [x] 出来高フロア / 売買代金フロアは PR-S3 で導入 (D-11。閾値は PR-S3 着手前にユーザ承認)
- [x] ストップ高安 / 特別気配 / 売買停止は fill 不可または保守的処理 (D-12。PR-S3 で実装)

### 10-2. 未確定 (PR-S3 着手前にユーザ承認が必要)

- [ ] fee_bps / fee_fixed_jpy のデフォルト値
- [ ] slippage_bps のデフォルト値
- [ ] volume_floor_ratio のデフォルト値
- [ ] min_avg_turnover_jpy のデフォルト値
- [ ] 上場廃止時の強制決済価格 (`last_known_close` / `0` / 比率)
- [ ] 単元未満の取扱 (基本は不可だが例外運用の可否)
- [ ] `volume_split_adjusted` を保持するか
- [ ] tick_size table のソース
- [ ] 制限値幅 table のソース
- [ ] `outcome_label` のしきい値方式 (`static` / `atr_norm` / 両併存)

---

## 11. 関連 docs

- CALENDAR.md (bar_ts_close / next_business_day)
- SCHEMA.md (execution_assumption / decision)
- POINT_IN_TIME.md (look-ahead 不変条件)
- SURVIVORSHIP.md (上場廃止の取り扱い)
- DATA_SOURCES.md (調整済 / 未調整の保持)
