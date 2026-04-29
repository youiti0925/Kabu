# BACKTEST_CONTRACT.md

backtest の約定タイミング・コスト・調整方針の契約。MVP は long_only / 現物相当 / 日次 (1d)。

---

## 1. 基本方針

- MVP は long_only / 現物相当のみ。空売り・信用は MVP 外。
- 通貨は JPY 固定 (currency=JPY)。海外株は MVP 外。
- bar interval は `1d` のみ。intraday は将来。
- 単一銘柄 backtest は portfolio size = 1 の特殊例として実装する (将来の portfolio 拡張に備える)。

---

## 2. 約定タイミング契約

### 2-1. decision timing

- 判定: 当日 (T) の close 確定後、すなわち `bar_ts_close[T]` 以降。
- close 確定は CALENDAR.md の半日立会等を考慮した `bar_ts_close` を使う。

### 2-2. fill timing

- 約定: 翌営業日 (T+1) の寄付。
- すなわち `assumed_fill_bar = "next_open"`、`latency_bars = 1` を MVP 固定。
- same close fill (T close で約定) は **MVP では使わない**。look-ahead と区別がつかなくなるため。
- 翌営業日が祝日 / 半日立会の場合は `next_business_day(T+1)` を使う (CALENDAR.md)。

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

## 6. 調整済 vs 未調整 価格の使い分け

| 用途 | 系列 |
|---|---|
| technical / long_term_trend / waveform 計算 | adj_close (split & dividend back-adjusted) |
| 約定価格 (fill_price) | raw open / close |
| 出来高比較 (turnover_zscore 等) | turnover (= raw price × volume) ベース |
| ギャップ計算 (gap_pct) | raw close → raw open |
| 表示用 chart | 用途で選択。SCHEMA は両系列を保持 |

`technical.adjustment_basis = "split_dividend_back_adjusted"` を v1 で固定する。

---

## 7. run_metadata に必ず残す項目

- run_id
- commit_sha
- created_at
- data_source / data_source_version
- data_snapshot_hash
- universe_snapshot_id
- survivorship_policy
- survivorship_warning
- calendar_id
- trace_schema_version
- interval
- period (start_ts, end_ts)
- costs: { fee_bps, fee_fixed_jpy, slippage_bps }
- volume_floor_ratio
- min_avg_turnover_jpy
- assumed_fill_bar ("next_open")
- latency_bars (1)
- tax_basis ("pretax")
- rule_id / rule_version / rule_params_hash (judgement に使った placeholder ルール)
- warnings[] (例: "static_current_listing_universe", "pit_fundamentals_disabled")
- unavailable_reason_summary
- library_ids[] (waveform 等を使った場合)

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

## 10. 要決定チェックリスト

- [ ] fee_bps / fee_fixed_jpy のデフォルト値
- [ ] slippage_bps のデフォルト値
- [ ] volume_floor_ratio のデフォルト値
- [ ] min_avg_turnover_jpy のデフォルト値
- [ ] 上場廃止時の強制決済価格 (last_known_close / 0 / 比率)
- [ ] 単元未満の取扱 (許可するか)
- [ ] `volume_split_adjusted` を保持するか
- [ ] tick_size table のソース
- [ ] 制限値幅 table のソース

---

## 11. 関連 docs

- CALENDAR.md (bar_ts_close / next_business_day)
- SCHEMA.md (execution_assumption / decision)
- POINT_IN_TIME.md (look-ahead 不変条件)
- SURVIVORSHIP.md (上場廃止の取り扱い)
- DATA_SOURCES.md (調整済 / 未調整の保持)
