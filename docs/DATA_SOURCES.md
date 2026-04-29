# DATA_SOURCES.md

データソース選定方針と運用契約。Kabu の MVP データは「価格 / 出来高 / 売買代金 / 銘柄メタ / 営業日 / 主要指数」を最低限とする。fundamentals / news / earnings は point-in-time 性が確認できたソースを採用するまで MVP には入れない。

---

## 0. MVP 決定 (PR-S0.5 / N2 で確定)

本セクションは「決定」であり、後続 PR は本決定に従う。変更には別途承認が必要。

- D-1. 初期対象市場は **日本株のみ**。米国株 / 海外個別株 / 海外 ETF / ADR は MVP 対象外。
- D-2. `currency = "JPY"` 固定。`run_metadata.report_currency = "JPY"` 固定。為替換算 PnL は MVP 対象外。
- D-3. PR-S1 では **Source Protocol を先に作る**。具体的なベンダ実装はこの裏に閉じ込める。アプリ全体から `yfinance` / `Stooq` / 他ベンダを直接呼ぶことは禁止。
- D-4. 全データアクセサは `as_of: datetime` を **必須引数** にする。デフォルト「今」は禁止 (POINT_IN_TIME.md §3 / §5 と整合)。
- D-5. `run_metadata.data_source` および `run_metadata.data_source_version` を **必ず保存** する。
- D-6. `fundamental_ctx` は **MVP では実装しない**。null で出すこともしない (= slice 自体を出さないか、`unavailable_reason="pit_not_available"` で全フィールド null)。
- D-7. PR-S8 (`fundamental_ctx`) は **PIT fundamentals が確保できるまで着手不可**。これは前提条件であり、N2 / PR-S0.5 / PR-S0.7 / PR-S0.9 / PR-S1 で覆さない。
- D-8. AI Review (PR-S10) は PIT fundamentals が無い場合、**ファンダ由来のルール変更候補 (Cカテゴリ) を出さない**。AI_REVIEW_SAFETY.md §10 と整合。
- D-9. 主要指数 (S&P500 / NASDAQ / VIX) は時差ありで使う場合、CALENDAR.md §6 のルール (T 日の日本株判断時点で見えていた値だけを使う) を必ず守る。

具体ベンダの最終選定 (yfinance vs J-Quants vs 自社蓄積 vs 有償) は §10 のチェックリスト未確定枠として残す。PR-S1 では Protocol 定義 + 単一の参照実装 (差し替え可能) を入れる。

---

## 1. 必要データの全体像

| カテゴリ | 必要項目 | MVP対象 | 備考 |
|---|---|---|---|
| 価格 | OHLCV (調整済 / 未調整) | yes | adjustment は SCHEMA.md / BACKTEST_CONTRACT.md と整合 |
| 出来高 | volume / turnover | yes | turnover (売買代金) を必須化 |
| 銘柄メタ | symbol / market / sector / listing_date / delisting_date / lot_size / tick_size | yes | UNIVERSE.md と整合 |
| 営業日 | exchange_calendar | yes | CALENDAR.md と整合 |
| 主要指数 | 日経225 / TOPIX / グロース250 / S&P500 / NASDAQ / VIX / USDJPY / 10Y | yes (MVPは index のみ) | macro は別 PR |
| 決算カレンダー | next_earnings_ts / 発表区分 | no (PR-S7) | release_ts 必須 |
| 業績 | EPS / 売上 / 利益 / コンセンサス | no (PR-S8) | PIT 必須 |
| ファンダ | PER / PBR / ROE / 配当 | no (PR-S8) | PIT 必須 |
| ニュース | headline / published_ts / source | no (PR-S9) | published_ts 必須 |
| 信用 | 信用買残 / 売残 / 倍率 | no (将来) | 週次。MVP 外 |
| 浮動株 | float / 外国人保有 | no (将来) | MVP 外 |

---

## 2. 候補ソース比較

| ソース | 価格 | 調整済 | 出来高 | 銘柄メタ | 決算 | fundamentals | PIT | historical universe | ニュース | ライセンス | 主な懸念 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| yfinance | △ (Yahooラッパ) | △ (back-adjusted) | yes | △ | △ | △ (最新値) | **no** | **no** | no | 非公式 / 規約変動 | PIT 不可。商用化リスク |
| Stooq | yes (日次中心) | △ | yes | △ | no | no | no | no | no | 緩い | 銘柄カバレッジと欠損 |
| J-Quants (JPX) | yes | yes | yes | yes | yes | yes | **概ね yes** | **概ね yes** | △ | 商用利用は要確認 | 認証必要 / 米株なし / プラン別カバレッジ |
| 有償ベンダ (Bloomberg / Refinitiv / QUICK 等) | yes | yes | yes | yes | yes | yes (vintage) | yes | yes | yes | 商用 (高額) | コスト |
| 自社蓄積 (snapshot) | カスタム | カスタム | カスタム | カスタム | カスタム | カスタム | yes (構造で保証) | yes | △ | 自由 | 自前運用コスト |

注:
- 「PIT (point-in-time)」= 過去のある時点で利用可能だった生の値が再現できるか。修正後の数値で上書きされていないか。
- yfinance / Stooq は基本「最新値」しか返さない。fundamentals に使うと look-ahead bias を構造的に内包する。
- J-Quants は日本株 / 日本市場主要データを比較的 PIT に近い形で提供できるが、プランや項目で差があるため採用前に項目別に確認する。

---

## 3. MVP 決定 (採用範囲)

§0 を踏まえた具体的な MVP スコープ。

- 採用 (MVP):
  - 日本株の OHLCV (raw + adjusted) / volume / turnover
  - 銘柄メタ (symbol / market / sector / listing_date / delisting_date / lot_size / tick_size)
  - 営業日カレンダー (CALENDAR.md と整合)
  - 主要指数: 日経225 / TOPIX / グロース250 (日本側)
  - 主要指数: S&P500 / NASDAQ / VIX / USDJPY / 10Y (時差は CALENDAR.md §6 のルールで参照)
- 不採用 (MVP):
  - fundamentals / earnings / news (D-6 / D-7 参照)
  - 海外個別株
  - 信用残 / 浮動株 / 外国人保有 / セクターローテーション指数 等

実装ベンダ候補は §2 を参照。§10 のチェックリストでユーザが選定。PR-S1 では選定確定までは Protocol + 単一の参照実装にとどめ、実データ取得処理の本格実装は行わない。

---

## 4. as_of / PIT 必須運用ルール

実装が始まったら以下を必ず守る。

- 全データアクセサは `as_of: datetime` を必須引数に持つ。デフォルト「今」は禁止。
- as_of より後にしか公開されていないデータは返してはならない。
- 「今の最新値」を過去検証に使ってはならない。たとえばランタイムの `yfinance.Ticker(...).info` のような最新値スナップショットを過去 bar の判断に使うことを禁止する。
- vintage が必要なデータは `(data_id, captured_at)` のペアで保存する。値を上書きせず追記する。
- 各 run の冒頭で「使ったデータスナップショット hash」を `run_metadata.data_snapshot_hash` に保存する。
- データソース変更は破壊的変更扱い。`run_metadata.data_source` と `run_metadata.data_source_version` を必須化する。

---

## 5. 「最新値」を過去に使わない方針

- 最新値しか返せないソースは fundamentals / earnings / news に **使わない**。
- 価格 / 出来高 / OHLCV は最新値で来ても問題が比較的小さい (bar の confirm 後は変わらない前提)。ただし以下に注意。
  - 株式分割 / 配当による既往データの調整は「事後」に発生する。`adj_close` は事後修正される系列。
  - 採用方針: `adj_close` と `raw_close` の両方を保持し、計算用と約定価格用を切り分ける (BACKTEST_CONTRACT.md 参照)。
- 「過去の bar に対して、現時点で取得した値を使ってはいけないデータ」のリストを以下に固定する。
  - PER / PBR / ROE / EPS / 配当利回り / 自己資本比率 (fundamentals)
  - コンセンサス (consensus)
  - 業績予想 / 上方修正 / 下方修正
  - 決算サプライズ
  - 信用買残 / 売残 (発表時刻付き)
  - 浮動株 / 外国人保有比率
  - ニュース / sentiment
  - 指数構成銘柄 (membership)

これらは PIT を保証するソースを採用しない限り `decision_trace` に **入れない**。

---

## 6. PIT fundamentals が無い場合の方針 (決定)

§0 D-6 / D-7 / D-8 を実装契約として展開する。

- PR-S8 (`fundamental_ctx`) は PIT を保証するソースを採用するまで **着手しない** (D-7)。
- それまでは `fundamental_ctx` を null で出すこと **すら** しない (空 slice 自体を schema から外す or `unavailable_reason="pit_not_available"` で全フィールド null) (D-6)。
- どちらの形でも、stats / AI Review はその slice を集計対象から除外する。
- `analyst.py` (PR-S10) のプロンプトに「PIT が確認されていない fundamentals を根拠に提案を作らない」を組み込む (D-8)。
- run_metadata に `warnings` 配列を持ち、`"pit_fundamentals_disabled"` を MVP 期間中は必ず含める。

---

## 7. 取得・キャッシュ層の設計指針 (決定 + 実装契約)

実装は PR-S1 で行うが、契約はここで固定する (§0 D-3 / D-4 / D-5)。

- `Source` を Protocol として定義 (例: `class Source(Protocol): def get_ohlcv(symbol, start, end, *, as_of) -> DataFrame`)。**Protocol を先に作り、ベンダ実装はその裏に閉じ込める。**
- 実装は `YFinanceSource` / `JQuantsSource` 等のクラスでベンダ差を吸収。`data.py` 直叩きは禁止。アプリ全体から具体ベンダ名を呼ばない。
- 全データアクセサに `as_of: datetime` を必須引数で持たせる。デフォルト値は禁止 (signature レベルで強制)。
- ローカルキャッシュは `data/cache/` 配下に parquet by symbol-date で immutable layout。上書き禁止 / 追記のみ。
- `data/raw/` はベンダから取得した生データを captured_at 付きで保存 (将来 PIT 再現のため)。
- `data/raw/` `data/cache/` は CI / .gitignore で commit が構造的に阻止されている (RISKS.md 5-3 / scripts/check_no_forbidden_paths.py)。
- cache の hit/miss は run_metadata に統計として残す (`data_cache_stats`)。
- ベンダ間でカラム名 / 型を必ず正規化する。caller はベンダ名を知らない。
- `run_metadata.data_source` および `run_metadata.data_source_version` は必須 (D-5)。データソース変更は破壊的変更扱い。

---

## 8. 欠損 / 失敗の取り扱い

- データ欠損は `unavailable_reason` を slice に必ず残す (`pit_not_available`, `not_yet_released`, `vendor_404`, `network_error`, `license_blocked` 等)。
- ランタイム例外で run を落とさない。スキップ + 集計時に `n_filtered` と理由内訳を出す。
- ニュース / fundamentals が欠損していても decision_trace 全体は書く。trace は append-only。

---

## 9. ライセンスと再現性

- 各ソースの利用規約 / 商用利用条件を `docs/DATA_SOURCES.md` のこの節に記録する (採用時に追記)。
- yfinance / Stooq は規約変動・スクレイピング制限の影響を受けやすい。商用化検討時に再評価する。
- J-Quants の商用利用は API プラン契約で明示確認する。
- run の再現には以下を保存する。
  - `data_source`, `data_source_version`
  - `data_snapshot_hash`
  - `as_of` (run 全体の as_of)
  - `commit_sha`

---

## 10. チェックリスト

### 10-1. 決定済 (N2 / PR-S0.5 で確定)

- [x] 初期対象市場: 日本株のみ (D-1)
- [x] 通貨: JPY 固定 (D-2)
- [x] 海外株 / ADR / 海外 ETF の扱い: MVP 対象外 (D-1)
- [x] PR-S1 では Source Protocol を先に作る (D-3)
- [x] アプリ全体からベンダ直叩き禁止 (D-3)
- [x] `as_of` 引数必須 / デフォルト「今」禁止 (D-4)
- [x] `run_metadata.data_source` / `data_source_version` 必須 (D-5)
- [x] fundamentals は MVP 実装しない (D-6)
- [x] PR-S8 は PIT fundamentals 確保まで未着手 (D-7)
- [x] AI Review はファンダ由来の C 提案を出さない (D-8)
- [x] 米国指数の時差ルール (CALENDAR.md §6) に従う (D-9)

### 10-2. 未確定 (PR-S1 着手前にユーザ承認が必要)

- [ ] 価格データソースの最終ベンダ (yfinance / J-Quants / 自社蓄積 / 併用)
- [ ] 主要指数のソース (Stooq / yfinance / 公式)
- [ ] fundamentals / earnings の PIT ソース (PR-S7 / S8 着手前まで延期可)
- [ ] ニュースソース (PR-S9 まで延期可)
- [ ] キャッシュ format (parquet 推奨 / duckdb 検討)
- [ ] ベンダ規約の確認結果 (商用利用 / レート制限 / アカウント要件)

10-2 が確定するまで PR-S1 (data source interface) は具体的な vendor を選ばず、Protocol 定義 + 単一の参照実装 (差し替え可能、stub 相当) にとどめる。
