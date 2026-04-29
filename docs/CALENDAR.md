# CALENDAR.md

日本市場の営業日 / セッション / bar_ts 定義 / 約定タイミング契約。Kabu は MVP で「日本市場 / 日次 (1d) / 現物相当 / Asia/Tokyo」を前提とする。

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

## 3. bar の定義 (MVP は 1d のみ)

- bar_ts: その bar に紐づく point-in-time 時刻 (UTC でも JST でも構わないが run 内で統一する。MVP は Asia/Tokyo の naive ではなく aware datetime を推奨)。
- bar_ts_close: その bar の close 時刻。日次の通常日は 15:00 JST。半日立会日は短縮された close。
- bar_ts_available: その bar の全フィールドが point-in-time で利用可能な最も早い時刻。EOD データの確定タイミングに依存する。MVP の暫定値は「session_end_ts + 30 分」程度。データソース選定後に確定する。
- 提案: trace の top-level に `bar_ts`, `bar_ts_close`, `bar_ts_available`, `interval` を必須で入れる (SCHEMA.md と整合)。

---

## 4. 約定タイミング契約

- Kabu MVP の契約: **decision at T close (= bar_ts_close[T]) → fill at T+1 open**
- これにより look-ahead と現実性の境界を明確にする。
- same close fill (= 当日 close で fill) は MVP では使わない。
- `execution_assumption.assumed_fill_bar = "next_open"` 固定 (PR-S3 着手時)。
- `execution_assumption.latency_bars = 1` (close → 翌寄り = 1 bar の遅延)。
- 詳細は BACKTEST_CONTRACT.md。

---

## 5. 決算 / IR の発表時刻と利用可能タイミング

決算は発表時刻によって反映可能タイミングが変わる。

| 発表区分 | 例 | bar_ts_available への影響 |
|---|---|---|
| 寄前 (07:00 等) | 同日寄付前に発表 | 同日 09:00 以降に反映可。同日の bar_ts (= 同日 close 確定後) で取り込み可。 |
| 場中 (10:00 等) | 場中発表 (注意: 通常は重要 IR は引け後) | 反映タイミングが歪むため MVP では「次営業日寄付以降」に保守的に丸める。 |
| 引け後 (15:30 / 16:00 等) | 多くの決算 | **翌営業日寄付以降** に反映可。当日 bar の earnings_ctx には入れない。 |
| 翌寄前 | 当日深夜 / 翌朝発表 | 翌営業日寄付以降に反映可。 |

- 結論: 決算の release_ts < 当日 close なら当日 bar に取り込んでよいが、「引け後」発表が最頻ケース。**MVP は保守側に倒し、原則として release_ts < bar_ts_close でなければ取り込まない**。
- timeutil で「release_ts → 次の bar_ts_available」を計算する関数を用意する (PR-S0.7 で stub、PR-S7 で本実装)。

---

## 6. 海外市場との時差

- 日本の bar_ts と米国市場の bar_ts は完全に重ならない。
- 例: 日本の 4/29 (火) 大引け 15:00 JST = 米国 4/29 (火) 02:00 ET。米国市場はその後 9:30 ET (= 日本時間 4/29 22:30) に開く。
- Kabu の MVP ルール: 日本株 trace の bar_ts は Asia/Tokyo 基準。S&P500 / NASDAQ / VIX のような米国指数を `market_index_ctx` に入れる場合、`as_of` は **bar_ts_available 以前に終値が確定している直近の米国セッション** を使う。
- 例: 日本 4/29 (火) bar の market_index_ctx の sp500 は、米国 4/28 (月) 終値を使う。米国 4/29 の終値は日本 4/30 朝以降にしか使えない。
- timeutil でこの「直近の確定米国セッション」を返す関数を提供する (PR-S5 で本実装)。

---

## 7. timezone

- 原則 Asia/Tokyo。
- bar_ts は timezone-aware datetime とする。naive datetime は禁止 (誤計算の温床)。
- 海外指数を扱う場合は内部で UTC 経由で扱い、表示のみ Asia/Tokyo に揃える。

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

## 10. 要決定チェックリスト

- [ ] 営業日カレンダーソース (`exchange-calendars` / J-Quants / 自社)
- [ ] 半日立会の正確な close 時刻
- [ ] bar_ts_available のデフォルト遅延 (15:30 / 16:00 等)
- [ ] timezone 表現 (Asia/Tokyo aware datetime か UTC か)
- [ ] tick_size table のソース
- [ ] 制限値幅 table のソース
- [ ] 売買単位の例外銘柄の扱い
