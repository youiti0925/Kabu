# CALENDAR.md

日本市場の営業日 / セッション / bar_ts 定義 / 約定タイミング契約。Kabu は MVP で「日本市場 / 日次 (1d) / 現物相当 / Asia/Tokyo」を前提とする。

---

## 0. MVP 決定 (PR-S0.5 / N2 で確定)

本セクションは「決定」であり、後続 PR は本決定に従う。変更には別途承認が必要。

- D-1. **interval = "1d"** 固定。intraday は MVP 対象外。
- D-2. **timezone = Asia/Tokyo**。bar_ts / bar_ts_close / bar_ts_available はすべて timezone-aware datetime。naive datetime は禁止。
- D-3. **decision timing = T close** (= `bar_ts_close[T]` 以降)。
- D-4. **fill = T+1 open**。`assumed_fill_bar = "next_open"` / `latency_bars = 1` を MVP 固定。
- D-5. **same close fill (T close で約定) は MVP では禁止**。look-ahead と区別がつかなくなるため。
- D-6. `bar_ts_close` と `bar_ts_available` を **分けて持つ**。
- D-7. **bar_ts は原則 `bar_ts_available`** とする。trace の判断に使う「その時点で見えていた情報」の境界を `bar_ts_available` で明示する。
- D-8. **米国指数 / NASDAQ / S&P500 / VIX は日付ズレに注意し、日本株 T 日判断時点で見えていた値だけを使う**。すなわち、日本 T 日 bar の `market_index_ctx` は **米国 (T-1) 日終値** または「`as_of <= bar_ts_available[T]` を満たす直近の米国セッション終値」を使う。米国 T 日終値は日本 T+1 日朝以降にしか使えない。
- D-9. 引け後発表 (15:00 以降) の決算 / IR は **翌営業日寄付以降** にしか反映しない。場中発表 (09:00 - 15:00) は発表時刻以降に反映可。発表時刻が不明な場合は **安全側で翌営業日寄付以降** に丸める。
- D-10. earnings / event データが無い場合は `unavailable_reason` 付きで null として扱う (slice 自体は schema に存在する)。

---

## 1. 営業日

- 取引所: 東京証券取引所 (JPX / TSE)
- 営業日: 月〜金から祝日 / 年末年始 / 特別休業を除く
- 祝日 / 特別休業の判定は exchange_calendar (例: `exchange-calendars` ライブラリの `XTKS`) から取得する想定。確定は PR-S0.7。
- 半日立会の特殊日 (例: 大納会の振替等) は普段と異なる close 時刻になる場合があるため、`session_end_ts` を bar_ts ごとに保持する。

---

## 2. セッション (intraday)

- 前場: 09:00 - 11:30 (Asia/Tokyo)
- 昼休み: 11:30 - 12:30
- 後場: 12:30 - 15:00
- 大引け: 15:00 (= 後場 close)
- これらは MVP の intraday 拡張時の参照値。MVP は日次なので前場 / 後場の区別を直接は使わない。

---

## 3. bar の定義 (MVP は 1d 固定。決定)

§0 D-1 / D-2 / D-6 / D-7 を実装契約として展開する。

- `interval = "1d"` 固定 (D-1)。schema 必須項目 (SCHEMA.md §2)。
- `bar_ts`: その bar に紐づく point-in-time 時刻。**timezone-aware** とする (D-2)。**原則として `bar_ts_available` と等しい** (D-7)。
- `bar_ts_close`: その bar の close 時刻。日次の通常日は 15:00 JST。半日立会日は短縮された close (D-6)。
- `bar_ts_available`: その bar の全フィールドが point-in-time で利用可能な最も早い時刻 (D-6)。EOD データの確定タイミングに依存する。MVP の暫定値は「`bar_ts_close + 30 分`」程度。データソース選定後に PR-S1 で確定 (`exchange_calendar_id` と紐づけ)。
- trace の top-level に `bar_ts`, `bar_ts_close`, `bar_ts_available`, `interval` を **必須** で入れる (SCHEMA.md §2 と整合)。

---

## 4. 約定タイミング契約 (決定)

§0 D-3 / D-4 / D-5 を実装契約として展開する。

- Kabu MVP の契約: **decision at T close (= `bar_ts_close[T]`) → fill at T+1 open** (D-3 / D-4)。
- これにより look-ahead と現実性の境界を明確にする。
- **same close fill (= 当日 close で fill) は MVP では禁止** (D-5)。
- `execution_assumption.assumed_fill_bar = "next_open"` を **必須** で持つ (SCHEMA.md §4-9 / D-4)。
- `execution_assumption.latency_bars = 1` (close → 翌寄り = 1 bar の遅延) を **必須** で持つ (SCHEMA.md §4-9 / D-4)。
- 翌営業日が祝日 / 半日立会の場合は `next_business_day(T+1)` を使う (BACKTEST_CONTRACT.md §2-2)。
- 詳細は BACKTEST_CONTRACT.md §2。

---

## 5. 決算 / IR の発表時刻と利用可能タイミング (決定)

§0 D-9 / D-10 を実装契約として展開する。

| 発表区分 | 例 | bar_ts_available への影響 |
|---|---|---|
| 寄前 (07:00 等) | 同日寄付前に発表 | 同日 09:00 以降に反映可。同日の bar_ts (= 同日 close 確定後) で取り込み可。 |
| 場中 (10:00 等) | 場中発表 (通常は重要 IR は引け後) | 発表時刻以降に反映可。MVP は **次営業日寄付以降に保守的に丸める** (D-9)。 |
| 引け後 (15:30 / 16:00 等) | 多くの決算 | **翌営業日寄付以降** に反映可。当日 bar の earnings_ctx には入れない (D-9)。 |
| 翌寄前 | 当日深夜 / 翌朝発表 | 翌営業日寄付以降に反映可。 |
| 不明 | 発表時刻が取得できない | **安全側で翌営業日寄付以降** (D-9)。 |

- MVP の保守ルール: **原則として `release_ts < bar_ts_close` でなければ当日 bar には取り込まない** (D-9)。
- earnings / event データそのものが取得できない場合は `unavailable_reason` 付きで null とする (D-10)。
- timeutil で「release_ts → 次の `bar_ts_available`」を計算する関数を用意する (PR-S0.7 で stub、PR-S7 で本実装)。

---

## 6. 海外市場との時差 (決定)

§0 D-8 を実装契約として展開する。**米国指数 / NASDAQ / S&P500 / VIX は日付ズレに注意し、日本株 T 日判断時点で見えていた値だけを使う**。

- 日本の bar_ts と米国市場の bar_ts は完全に重ならない。
- 例: 日本の 4/29 (火) 大引け 15:00 JST = 米国 4/29 (火) 02:00 ET。米国市場はその後 9:30 ET (= 日本時間 4/29 22:30) に開く。
- Kabu の MVP ルール (決定): 日本株 trace の bar_ts は Asia/Tokyo 基準。S&P500 / NASDAQ / VIX / USDJPY / 米10Y のような米国セッション系列を `market_index_ctx` に入れる場合、その値は **`as_of <= bar_ts_available[T]` を満たす直近の米国セッション終値** を使う。
- 例: 日本 4/29 (火) bar の `market_index_ctx.sp500_*` は、米国 4/28 (月) 終値を使う。米国 4/29 の終値は日本 4/30 朝以降にしか使えない。
- これは look-ahead bias を防ぐ不変条件であり、POINT_IN_TIME.md §3 にも反映されている。
- timeutil でこの「直近の確定米国セッション」を返す関数を提供する (PR-S5 で本実装)。
- pytest 候補: `test_us_index_no_lookahead` (PR-S5) で「日本 T 日 bar に米国 T 日終値が混入していない」ことを検証。

---

## 7. timezone (決定)

§0 D-2 を実装契約として展開する。

- **原則 Asia/Tokyo** (D-2)。
- bar_ts / bar_ts_close / bar_ts_available は **timezone-aware** datetime とする。**naive datetime は禁止** (誤計算の温床)。
- 海外指数を扱う場合は内部で UTC 経由で扱い、表示のみ Asia/Tokyo に揃える。
- pytest 候補: `test_bar_ts_tzaware` (PR-S2) で trace 出力の bar_ts が tz-aware であることを検証。

---

## 8. intraday 拡張時の注意点

MVP は 1d だが、将来の intraday 拡張に備えて以下を docs として固定する。

- 前場引け (11:30) を独立した bar にするかは要決定。
- 寄付ギャップ (T+1 open vs T close) は intraday では「same day open」になるため約定契約が変わる。
- 板薄銘柄では特別気配で寄り付かないことが頻発するため、bar_ts_available の概念がより重要になる。
- intraday の interval (5min / 15min / 30min / 60min) は別 schema_version で扱うことを推奨。

---

## 9. 売買単位 / tick_size

- 売買単位 (lot_size): 通常 100 株。一部例外あり。MVP は単元のみ (単元未満は不可)。
- tick_size: 株価帯で異なる。`tick_size_table_id` を universe_snapshot に紐づけ、price から tick を引ける関数を timeutil で提供する。
- 制限値幅 (値幅制限): 前日終値で決まる。table を取得する手段は PR-S0.7 で確定 (J-Quants 等から取得想定)。

---

## 10. チェックリスト

### 10-1. 決定済 (N2 / PR-S0.5 で確定)

- [x] interval = "1d" 固定 (D-1)
- [x] timezone = Asia/Tokyo / aware datetime 必須 (D-2)
- [x] decision at T close → fill at T+1 open (D-3 / D-4)
- [x] same close fill 禁止 (D-5)
- [x] bar_ts_close と bar_ts_available を分けて持つ (D-6)
- [x] bar_ts は原則 bar_ts_available (D-7)
- [x] 米国指数の時差ルール (D-8)
- [x] 引け後発表は翌営業日寄付以降、不明は安全側で翌営業日寄付以降 (D-9)
- [x] earnings / event 欠損は null + unavailable_reason (D-10)

### 10-2. 未確定 (PR-S1 着手前にユーザ承認が必要)

- [ ] 営業日カレンダーソース (`exchange-calendars` / J-Quants / 自社)
- [ ] 半日立会の正確な close 時刻 table
- [ ] bar_ts_available のデフォルト遅延の最終値 (15:30 / 16:00 / 30 分後)
- [ ] tick_size table のソース
- [ ] 制限値幅 table のソース
- [ ] 売買単位の例外銘柄の扱い
