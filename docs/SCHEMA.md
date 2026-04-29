# SCHEMA.md

`kabu.trace.v1` スキーマ定義と運用ポリシー。各 PR は本ドキュメントを破壊的変更しない範囲で実装する。

---

## 1. schema_version

- 値: `"kabu.trace.v1"`
- 意味: trace JSONL 1 レコードの構造バージョン。

### 1-1. 運用ポリシー (不変条件)

- フィールド削除禁止 (deprecated 化のみ)
- 型変更禁止
- 追加は optional のみ
- bucket 境界変更は **破壊的変更扱い** (schema_version を `v2` に上げる)
- enum の値追加は許可、削除 / 改名は破壊的
- v2 移行時は `migrations/` ディレクトリに変換スクリプトを必ず用意する
- reader は未知フィールドを drop 可。warning ログを出すことを推奨

### 1-2. schema_version リファレンスの強制

- trace JSONL の各レコードに `schema_version` が必須
- run_metadata に `trace_schema_version` を必須化
- pytest `test_schema_version_required` で守る (ROADMAP.md 参照)

---

## 2. top-level 必須項目

```
schema_version       : "kabu.trace.v1"          # 必須
run_id               : str                      # 必須。run_metadata と紐づく
trace_schema_version : str                      # = schema_version (互換性のため二重保存)
commit_sha           : str                      # 必須
created_at           : datetime                 # 必須 (record 書き込み時刻)
symbol               : str                      # 必須 (例: "7203" / "7203.T" 等。表現は UNIVERSE.md と整合)
market               : str                      # 必須 (例: "TSE_PRIME")
sector               : str                      # 必須 (33業種コード等)
interval             : str                      # 必須 (MVP は "1d" 固定)
bar_ts               : datetime                 # 必須 (timezone-aware)
bar_ts_close         : datetime                 # 必須 (CALENDAR.md 参照)
bar_ts_available     : datetime                 # 必須 (CALENDAR.md 参照)
universe_snapshot_id : str                      # 必須 (UNIVERSE.md 参照)
data_snapshot_hash   : str                      # 必須 (DATA_SOURCES.md 参照)
library_id           : str | null               # optional (waveform_ctx 用、top-level 配置は将来 deprecated 候補)
unavailable_reason   : str | null               # 必須キー (値は null 可)。slice まで届かなかった場合の総括
slices               : { ... }                  # 下記
```

注: `library_id` は v1 互換のため top-level に置くが、将来は `slices.waveform_ctx.library_id` に集約することを推奨。`run_metadata` に複数の `library_ids[]` を持たせる方針も検討対象。

---

## 3. slices 一覧

### 3-1. v1 で定義する slice (MVP で実装するもの)

| slice 名 | 役割 | MVP (PR-S2) | 備考 |
|---|---|---|---|
| market | OHLCV / turnover / gap / 半休フラグ | yes | adjustment_basis の影響を受けない raw |
| technical | SMA / RSI / MACD / BB / ATR 等 | yes | adjustment_basis 必須 |
| long_term_trend | 週次 / 月次 / 52週 / 年初来 | yes | adjustment_basis 必須 |
| volume_liquidity | turnover_zscore / liquidity_regime | PR-S5 | MVP では一部のみ |
| market_index_ctx | 主要指数 / VIX / USDJPY | PR-S5 | CALENDAR.md の海外時差ルール |
| sector_ctx | sector_trend / 相対強度 | PR-S5 | |
| risk_ctx | blocked_by / hold_reason | yes | 拡張は PR-S3 / S7 |
| decision | final_action / rule_id / rule_version | yes | placeholder ルールから運用 |
| execution_assumption | assumed_fill_bar / latency_bars / fee / slippage | yes | BACKTEST_CONTRACT.md |
| future_outcome | forward_return / mfe / mae / outcome_label | yes (post-fill) | 後処理 enrich |

### 3-2. 後続 slice (将来 PR で追加予定)

| slice 名 | PR | 備考 |
|---|---|---|
| waveform_ctx | PR-S6 | library_id / feature_set / similarity_topN |
| earnings_ctx | PR-S7 | release_ts 必須 |
| event_ctx | PR-S7 | corporate_action_today[] |
| fundamental_ctx | PR-S8 | PIT 必須。ない場合は slice ごと出さない |
| news_ctx | PR-S9 | published_ts 必須 |
| margin_ctx | 将来 | 信用買残 / 売残 |
| ownership_ctx | 将来 | 浮動株 / 外国人保有 |
| session_ctx | 将来 | intraday 拡張 |
| microstructure_ctx | 将来 | 板薄度 proxy 等 |

---

## 4. slice 詳細 (v1)

### 4-1. market

```
open                : float       # 必須 (raw)
high                : float       # 必須 (raw)
low                 : float       # 必須 (raw)
close               : float       # 必須 (raw)
adj_close           : float       # 必須 (split & dividend back-adjusted)
volume              : int         # 必須
turnover            : float       # 必須 (売買代金 = price × volume の集計値)
prev_close          : float       # 必須 (raw)
gap_pct             : float       # 必須 = (open - prev_close) / prev_close
is_halted           : bool        # 必須 (default false)
is_special_quote    : bool        # 必須 (default false)
is_circuit_breaker  : bool        # 必須 (default false)
vwap                : float | null # optional
tick_size           : float | null # optional (PR-S0.7 で確定)
```

### 4-2. technical

```
adjustment_basis : "split_dividend_back_adjusted"   # 必須 (v1 はこの値固定を推奨)
sma20            : float | null
sma60            : float | null
sma200           : float | null
sma200_slope_5d  : float | null   # optional. 後追いで意味を持つ
rsi14            : float | null
macd             : { line: float, signal: float, hist: float } | null
bb_upper         : float | null
bb_lower         : float | null
bb_width         : float | null   # optional 派生
bb_position      : float | null   # optional 派生
atr14            : float | null
close_vs_sma20   : float | null
close_vs_sma60   : float | null
close_vs_sma200  : float | null
```

### 4-3. long_term_trend

```
weekly_trend         : "up" | "down" | "flat" | null
monthly_trend        : "up" | "down" | "flat" | null
dist_52w_high        : float | null   # = (close - high_52w) / high_52w
dist_ytd_high        : float | null
dist_ytd_low         : float | null
dist_alltime_high    : float | null
dist_alltime_low     : float | null
new_high_52w_flag    : bool
new_low_52w_flag     : bool
weekly_return        : float | null
monthly_return       : float | null
quarterly_return     : float | null
```

### 4-4. volume_liquidity

```
avg_turnover_20d   : float | null
avg_turnover_60d   : float | null
turnover_zscore    : float | null
liquidity_regime   : "high" | "mid" | "low" | "very_low" | null
volume_spike       : bool
low_liq_flag       : bool         # liquidity_floor 違反
tradable_size_jpy  : float | null # 1日あたりの執行可能想定額
```

### 4-5. market_index_ctx

```
nikkei_trend          : "up" | "down" | "flat" | null
topix_trend           : "up" | "down" | "flat" | null
growth250_trend       : "up" | "down" | "flat" | null
sp500_trend           : "up" | "down" | "flat" | null
nasdaq_trend          : "up" | "down" | "flat" | null
vix_level             : float | null
usdjpy_trend          : "up" | "down" | "flat" | null
us10y_level           : float | null
jp10y_level           : float | null
regime_risk_on_off    : "risk_on" | "risk_off" | "neutral" | null
breadth               : float | null   # 騰落レシオ等
```

### 4-6. sector_ctx

```
sector_code               : str                # 33業種 / 17業種 (table_id 併記推奨)
sector_trend              : "up" | "down" | "flat" | null
rel_strength_vs_sector    : float | null
growth_vs_value           : "growth" | "value" | "neutral" | null
sector_breadth            : float | null
```

### 4-7. risk_ctx

```
blocked_by            : list[str]   # 例 ["volume_floor", "earnings_blackout"]
hold_reason           : list[str]
unavailable_reason    : str | null
```

### 4-8. decision

```
final_action           : "buy" | "hold" | "sell_to_close" | "no_position"
technical_only_action  : "buy" | "hold" | "sell_to_close" | "no_position"
rule_id                : str
rule_version           : str
rule_params_hash       : str
confidence             : float | null   # 値域 [0, 1] (null 可)
```

注: MVP は long_only / 現物相当のため `sell_to_close` (= ロング決済) と `no_position` のみが close 系の状態。空売りを表す `short_open` 等は v1 では使わない (将来 schema_version 引き上げまたは optional 拡張で対応)。

### 4-9. execution_assumption

```
assumed_fill_bar  : "next_open"           # MVP 固定。CALENDAR.md / BACKTEST_CONTRACT.md と整合
latency_bars      : 1                     # MVP 固定
fill_price        : float | null          # null = 約定不可
slippage_bps      : float
fee_bps           : float
fee_fixed_jpy     : float | null          # optional (固定手数料を併用する場合)
is_realistic      : bool                  # 出来高フロア / ストップ高安 / 売買停止を考慮した約定可否
fill_reason       : str | null            # 例 "ok", "stop_high_blocked", "volume_floor_capped"
```

### 4-10. future_outcome

```
forward_return_5d        : float | null
forward_return_20d       : float | null
forward_return_horizon_bars : list[int]   # 例 [1, 5, 20, 60]
mfe                      : float | null   # max favorable excursion
mae                      : float | null   # max adverse excursion
hit_stop                 : bool | null
outcome_label_static     : "big_win" | "win" | "flat" | "loss" | "big_loss" | null
outcome_label_atr_norm   : "big_win" | "win" | "flat" | "loss" | "big_loss" | null
forward_return_basis     : "close_to_close" | "open_to_close" | "open_to_open"
forward_return_end_ts    : datetime | null
```

注 (極めて重要):
- future_outcome は **post-processing で enrich** される。decision / risk / execution の判定には **絶対に参照しない**。
- look-ahead invariant は POINT_IN_TIME.md 参照。
- forward_return_end_ts <= 取得時の bar_ts という考え方は waveform にも適用する。

---

## 5. 共通方針

### 5-1. unavailable_reason

各 slice は以下のいずれかを `unavailable_reason` キーで持てる (slice 直下に配置)。

- `pit_not_available`
- `not_yet_released`
- `vendor_404`
- `network_error`
- `license_blocked`
- `out_of_universe`
- `insufficient_history`
- `feature_set_mismatch` (waveform_ctx)

slice の値が null + reason 付き は許容。reason だけ無く null は不可 (= 必ず理由を残す)。

### 5-2. adjusted vs unadjusted

- `market.*` は raw (未調整)。
- `technical.*` および `long_term_trend.*` は `adjustment_basis = "split_dividend_back_adjusted"` を前提とした計算結果。
- `execution_assumption.fill_price` は raw 系列を使う (=「実際の約定価格」)。
- これにより「指標は adjusted、約定は raw」の使い分けを構造で固定する。

### 5-3. rule_id / rule_version / rule_params_hash

- rule_id: ルールの論理 ID (例 `"baseline_breakout_v1"`)。
- rule_version: そのルール内のセマンティックバージョン (例 `"1.0.0"`)。
- rule_params_hash: そのルールに渡されたパラメータ JSON の hash。
- これにより stats で「rule × outcome」の比較が可能。MVP の placeholder ルールでも必ず付与する。

### 5-4. confidence

- 型: float
- 値域: [0, 1]
- null 可
- ルールが提供しない場合は null。null は「未定義」であり「中立」ではない。stats では分布として扱い、bucket は [0, 0.33, 0.66, 1] を初期推奨。

### 5-5. universe / data snapshot

- `universe_snapshot_id` を必ず持つ (UNIVERSE.md)。
- `data_snapshot_hash` を必ず持つ (DATA_SOURCES.md)。

---

## 6. JSONL 出力規約

- 1 レコード = 1 行 (改行で区切る)。
- ファイル分割: `runs/<run_id>/trace_raw.jsonl` (live record) と `runs/<run_id>/outcome_backfill.jsonl` (future_outcome 後処理) を分ける。
- 結合済み trace を生成する場合は `runs/<run_id>/trace_joined.jsonl` を別途出す (再現可能 join)。
- どのファイルも append-only。中身の編集禁止。
- 文字コード: UTF-8。
- 数値は IEEE 754 double。null は JSON null。
- `runs/` は .gitignore 済み (RISKS.md / .gitignore 参照)。

---

## 7. v2 への移行ポリシー (将来)

- v1 では入れていない slice (waveform_ctx, earnings_ctx, ..., margin_ctx 等) を入れる際は、可能な限り optional 追加で v1 のまま実現する。
- 既存フィールドの意味を変える必要が出たら v2 を切り、`migrations/v1_to_v2.py` を追加。
- intraday (1m / 5m / 15m / 60m) を本格対応する場合は v2 を切ることを推奨 (bar_ts 周りの不変条件が変わるため)。

---

## 8. 関連 docs

- POINT_IN_TIME.md: bar_ts と release_ts の不変条件
- BACKTEST_CONTRACT.md: assumed_fill_bar / fill_price 等
- CALENDAR.md: bar_ts_close / bar_ts_available の定義
- UNIVERSE.md: universe_snapshot_id / market / sector
- DATA_SOURCES.md: adjustment / data_snapshot_hash
