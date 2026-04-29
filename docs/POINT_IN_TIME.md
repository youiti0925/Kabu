# POINT_IN_TIME.md

look-ahead bias を構造で防ぐための point-in-time (PIT) 運用契約。本ドキュメントの不変条件は CI / pytest で守る対象。

---

## 1. look-ahead bias とは

- 過去の判断時点で実際には利用できなかった情報を、検証時に誤って使ってしまうこと。
- 結果として backtest が現実より良く見える (「未来を見て買う」状態)。
- データの「最新値で過去を上書き」「結果ラベルを判断に使う」「将来 bar から指標を計算」が代表的な発生源。

---

## 2. 用語定義

| 用語 | 定義 |
|---|---|
| bar_ts | その bar に紐づく point-in-time 時刻 (CALENDAR.md / SCHEMA.md と同義) |
| bar_ts_close | bar の close 時刻 (例 15:00 JST) |
| bar_ts_available | bar の全フィールドが PIT で利用可能な最も早い時刻 |
| release_ts | データ (決算 / IR / コンセンサス等) が公開された時刻 |
| effective_ts | そのデータが実際に判断に反映可能になる時刻 (release_ts + 反映ラグ) |
| reported_at | レコードがデータソース上で「報告された」と記録されている時刻 |
| captured_at | 自社が vendor からそのレコードを取得した時刻 |
| as_of | データアクセサに渡す「この時刻における利用可能データ」を指す引数 |

`reported_at` と `release_ts` は厳密には別物。reported_at がある場合はそれを優先し、release_ts と一致するなら省略可。

---

## 3. 不変条件

### 3-1. slice レベル

- 任意の slice について `slice.source_release_ts <= bar_ts_available` が成立する場合のみ slice 値を埋める。
- 上記が成立しないなら slice 値は null + `unavailable_reason ∈ {"not_yet_released", "pit_not_available"}`。
- pytest `test_pointintime_slice_null_before_release` でこの不変条件を検証。

### 3-2. indicator レベル

- 任意の rolling 指標 (SMA / RSI / MACD / BB / ATR 等) は、bar_ts より後の bar を参照しない。
- rolling 窓未満は NaN (= null) にする。前方補完 (`bfill`) を含む過去側の補完は禁止。
- pytest `test_no_lookahead_indicators` で検証。

### 3-3. waveform レベル

- waveform library に格納する各エントリの `forward_return_end_ts` は、当該エントリの参照時刻 `bar_ts` 以下である。
- すなわち「現時点で確定している将来リターン」しか library に入れない。
- pytest `test_waveform_forward_return_end_ts` で検証。

### 3-4. outcome レベル

- `future_outcome.*` は decision / risk / execution_assumption の判定で **絶対に** 参照されない。
- これは「未来の結果を見て当時の判断を変える」ことを禁じる根本ルール。
- 設計レベル: `decision_trace_build` の builder は future_outcome を読まない。outcome は別パイプラインで後処理 enrich する。
- pytest 候補: `test_decision_does_not_depend_on_outcome` (実装方針: builder の入力に future_outcome を含めない型シグネチャで強制)。

### 3-5. universe / membership レベル

- 任意の bar_ts に対するシグナル対象は、`universe_snapshot_id` の `effective_from <= bar_ts.date() AND (effective_to is null OR bar_ts.date() < effective_to)` を満たす銘柄に限る。
- pytest `test_universe_snapshot_consistency` で検証 (UNIVERSE.md / SURVIVORSHIP.md と整合)。

---

## 4. 反映タイミングのルール

### 4-1. 決算 / IR

- release_ts が場中 (09:00 - 15:00 JST) に発生したものは、当日 close 後に取り込んでよい (release_ts < bar_ts_close)。
- ただし MVP は保守側に倒し、「引け後発表 (15:00 以降) は翌営業日寄付以降にしか取り込まない」を初期ルールとする。
- 「寄前発表」「寄付発表 (誤って 09:00 ジャストに出る等)」は別関数 `next_available_bar_ts(release_ts, calendar)` で扱う。

### 4-2. コンセンサス / アナリスト予想

- 更新履歴を `consensus_history(symbol, effective_ts, value)` の形で保持する。
- bar_ts に対しては `effective_ts <= bar_ts_available` を満たす最新値のみ参照可。
- 「現時点で見えるコンセンサス」は将来 bar の判断に使ってはならない。

### 4-3. ニュース

- `published_ts` が必須。`published_ts <= bar_ts_available` のものだけが news_ctx に入る。
- ニュースのタイトル / 本文の hash を保存し、再現可能にする (sentiment 算出が将来再評価される可能性)。

### 4-4. fundamentals

- `reported_at` (決算短信公開時刻) を必須。
- 修正後の数値で過去を上書きするデータソースは fundamentals に **使わない** (DATA_SOURCES.md §5)。

### 4-5. 配当 / 分割 / コーポレートアクション

- `ex_date` (権利落ち日) ベースで反映。
- 株式分割の調整係数は事後発生する。`adj_close` は捕捉時点の最新調整係数で計算したものとする。
- 過去の adj_close が後から書き換わる現象を `data_snapshot_hash` で検知できるようにする。

---

## 5. データレベルの実装ルール

- 全データアクセサに `as_of: datetime` を必須引数で持たせる。
- `as_of` のデフォルト「今」は禁止。明示しないとアクセサがエラーを返す。
- アクセサは `as_of` より後に発生 / 公開されたデータを返してはならない。
- vintage が必要なデータは `(data_id, captured_at)` のペアで保存。値の上書きを禁止する。
- `run_metadata.data_snapshot_hash` に「使ったデータの hash」を保存。

---

## 6. PIT を保証できないデータの扱い

- 「PIT 不可」が判明したデータは trace に **入れない**。null で出すこともしない (= slice 自体を出さないか、`unavailable_reason="pit_not_available"` で全フィールド null)。
- 例: 無料データソースで取得した PER / PBR / ROE。
- これらをどうしても使いたい場合、PIT を保証する代替ソースを採用するまで PR を進めない (PR-S8 の前提条件)。

---

## 7. 不変条件チェックの実装方針

- 単体テストで不変条件を assert (ROADMAP.md の pytest 表参照)。
- CI で test_pointintime_slice_null_before_release 等を必須グリーンに。
- builder 側で「future_outcome を読まない」を型シグネチャ / 関数引数の形で強制。
- waveform library 書き込み時とロード時の両方で `forward_return_end_ts <= bar_ts` を再 assert。

---

## 8. よくあるアンチパターン (禁止例)

- pandas の `df["close"].rolling(20).mean().shift(-20)` のような未来 shift。
- 「現在の最新 PER を過去 bar の判断に使う」(yfinance.info を時系列で使う等)。
- 「決算サプライズが大きかった銘柄」を結果ラベルから取り、当日の判断に使う。
- 「上場廃止された銘柄を universe から最初から除外する」(survivorship)。
- 「現時点で構成されている指数 membership を過去に遡って適用する」。

---

## 9. 関連 docs

- DATA_SOURCES.md (as_of / vintage / 「最新値」を使わない)
- UNIVERSE.md / SURVIVORSHIP.md (universe_snapshot_id)
- CALENDAR.md (bar_ts_close / bar_ts_available)
- SCHEMA.md (slice の unavailable_reason / future_outcome の独立性)
