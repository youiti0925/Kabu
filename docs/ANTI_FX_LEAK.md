# ANTI_FX_LEAK.md

FX 検証アプリ (`youiti0925/test`) の概念 / コードが Kabu に混入しないようにする方針。FX 思想の **流用** と **コード移植** を明確に区別する。

---

## 1. 基本方針

- Kabu は別 repo / 別設計。FX repo に追加する場所ではない。
- FX 側のコードを **無差別コピー禁止**。
- FX 側の安全な設計思想だけを参考にする。
- 「設計思想流用」と「コード移植」を docs / レビューで区別する。

---

## 2. 持ち込んではいけない概念

以下は Kabu の語彙に存在してはならない。grep / lint で禁止する。

### 2-1. 業者・ソース固有

- `OANDA`, `oanda`
- `from oanda`, `import oanda`

### 2-2. FX 固有マクロ

- `DXY` (米ドル指数)
- `USD_exposure`, `usd_exposure`
- `USDJPY_exposure` (ペアの方向性 exposure としての概念)

### 2-3. 通貨ペア前提

- `currency_pair`
- `pip`, `pip_value`, `pip_size`
- `quote_currency`, `base_currency` (FX のペア構造を前提とした命名)

### 2-4. FX の risk_gate / event 概念

- `event_high` (FX イベントカレンダーのリスク高ラベル)
- `spread_abnormal`
- `risk_gate.event_high` 等のアクセサ

### 2-5. FX セッション

- `session_asia`, `session_europe`, `session_us`
- `fx_session`

### 2-6. BUY/SELL 対称前提

- `BUY_or_SELL`
- `direction in ["BUY", "SELL"]`
- 「FX 風の対称ロジック」(両方向シンメトリックなルール)

### 2-7. その他の固有名詞

- `fx.db` 等のスキーマ名 / DB 名
- FX 用の `events.json` 構造

---

## 3. 禁止 grep token (CI lint 案)

PR-S0.9 で CI lint を導入し、以下が `src/kabu/` および `tests/` にヒットしたら fail させる。

```
\bfrom\s+fx\b
\bfrom\s+src\.fx\b
\bimport\s+fx\b
\bOANDA\b
\boanda\b
\bDXY\b
\bUSD_exposure\b
\busd_exposure\b
\bUSDJPY_exposure\b
\bcurrency_pair\b
\bpip\b
\bpip_value\b
\bpip_size\b
\bquote_currency\b
\bbase_currency\b
\bevent_high\b
\bspread_abnormal\b
\bsession_asia\b
\bsession_europe\b
\bsession_us\b
\bfx_session\b
\bfx\.db\b
```

注: `\bfx\b` 単独や `\bbase_currency\b` のようなトークンは将来「外部仕様の説明」「コメント」での利用も拒否する厳しめ運用とする。説明用に使いたい場合は docs (この `docs/` 配下) に書く。

---

## 4. code review 観点

PR レビュー時に必ずチェックする観点:

- 通貨依存の比較 (例 「USDJPY が trend up なら BUY」) が含まれていないか
- macro slice が DXY を直接参照していないか (DXY は持ち込まない)
- risk slice が `event_high` を呼んでいないか
- BUY / SELL の対称二択になっていないか (株 MVP は long_only / cash の二値が初期)
- FX の continuous market 前提が紛れ込んでいないか (例: 24h 連続前提のロジック)
- 「FX repo に存在したファイル名そっくり」の新規ファイルが入っていないか
- 「コード移植」を行った場合、PR description で「思想流用」か「コード移植」を必ず宣言

---

## 5. FX repo からコピーしてよいもの / よくないもの

### 5-1. コード移植 OK の候補 (ただし修正必要)

- waveform_matcher.py (株向けに特徴量・方向ラベルを再定義)
- waveform_library.py (library_id / feature_set / library_kind を株向けに拡張)
- waveform_backtest.py (forward_return_end_ts <= bar_ts 思想を維持)
- attribution.py (通貨ペア寄与は除去)

### 5-2. 思想のみ流用 (コードは新規実装)

- decision_trace.py / decision_trace_build.py
- decision_trace_stats.py
- analyst.py
- market_timeline.py
- cli.py
- macro.py
- data.py (FX側)
- indicators.py (FX側)
- storage.py (FX側)
- tests/ (FX側) — 不変条件のチェックリストだけ docs 化

### 5-3. 移植しない (新規実装)

- backtest_engine.py (FX)
- risk_gate.py (FX)
- calendar.py (FX)
- event_overlay.py (FX)
- decision_engine.py (FX) — 売買ルール本体
- events.json (FX)
- oanda.py / live (FX)
- fx.db / FX trades schema

---

## 6. 移植判断テーブル (確定版)

レビュー指摘を反映した最終分類。コード移植判断は以下が一次ソース。

| FX側ファイル/部品 | 株repoへ移植するか | 分類 | 理由 | 株用の置換案 |
|---|---|---|---|---|
| src/fx/waveform_matcher.py | する | コード移植 (修正必要) | OHLC正規化・距離計算・上位N抽出は汎用。BUY/SELL対称前提の方向ラベルはFX寄り。 | src/kabu/waveform_matcher.py。出来高/売買代金/ギャップ/ストップ高安フラグを特徴量に追加。long_only前提で上昇/下降/横ばいの3値ラベル。 |
| src/fx/waveform_library.py | する | コード移植 (修正必要) | JSONLライブラリ・library_id・schema_version 設計は流用可。currency_pair キーは使えない。 | src/kabu/waveform_library.py。symbol/sector/liquidity_regime/earnings_proximity を library key に。universe別 library 切替。 |
| src/fx/waveform_backtest.py | する | コード移植 (修正必要) | forward_return_end_ts <= bar_ts による look-ahead 対策は最重要思想。流用必須。 | src/kabu/waveform_backtest.py。約定モデル・出来高フロア・制限値幅・気配を株式用に置換。 |
| src/fx/decision_trace.py | する | 思想のみ流用 / 新規実装 | slice構造・schema_version・JSONL出力規約は有用。FX固有sliceが多い。 | src/kabu/decision_trace.py。StockDecisionTrace を SCHEMA.md に従って再定義。 |
| src/fx/decision_trace_build.py | する | 思想のみ流用 / 新規実装 | builderパターンは有効。FX の calendar / risk_gate / decision_engine 依存が強い。 | src/kabu/decision_trace_build.py。株式用 slice builder を新設。 |
| src/fx/decision_trace_stats.py | する | 思想のみ流用 / 新規実装 | aggregate_many / cross_stats / final_action × outcome の集計骨格は流用可。集計軸・bucket 定義は株式用に完全置換。 | src/kabu/decision_trace_stats.py。集計軸を SCHEMA.md / TRACE_ANALYSIS_WORKFLOW.md に従って再定義。 |
| src/fx/backtest_engine.py | しない | 移植しない | spread/session/通貨exposure 前提が残る危険。 | src/kabu/backtest_engine.py を新規実装 (BACKTEST_CONTRACT.md 準拠)。 |
| src/fx/cli.py | する | 設計参考 / 新規実装 | argparse + サブコマンド構成と runs/ 出力規約は参考。株では universe / period / interval / library_id / data_source / run_metadata 中心の別コマンド体系になる。 | src/kabu/cli.py。コマンド体系を新規設計。 |
| src/fx/macro.py | する | point-in-time 思想のみ流用 / 新規実装 | DXY / USD exposure 前提を持ち込まない。point-in-time 思想だけ流用。 | src/kabu/macro.py を新規実装。日経225 / TOPIX / グロース250 / S&P500 / NASDAQ / VIX / USDJPY / 10年金利 / 業種別指数。 |
| src/fx/market_timeline.py | する | 思想のみ流用 / 新規実装 | FX の continuous market 前提と株式 (寄付 / 前場 / 後場 / 大引け / 特別気配 / 売買停止) は根本的に異なる。 | src/kabu/market_timeline.py を新規実装。CALENDAR.md と整合。 |
| src/fx/risk_gate.py | しない | 移植しない | event_high / spread_abnormal / 通貨別解釈が前提。 | src/kabu/risk.py を新規実装 (出来高不足 / 売買代金フロア / 制限値幅 / 決算跨ぎ / 低流動性 / 売買停止)。 |
| src/fx/calendar.py | しない | 移植しない | 経済指標カレンダー前提。 | src/kabu/events.py を新規実装。決算 / IR / 上方下方修正 / 増配減配 / 自社株買い / 分割 / TOB / 指数入替 を point-in-time で。 |
| src/fx/event_overlay.py | しない | 移植しない | event_high 依存が強い。 | src/kabu/events.py に earnings_before / earnings_after / blackout として再定義。 |
| src/fx/attribution.py | する | コード移植 (修正必要) | 損益寄与分解の思想は流用可。通貨ペア寄与は除去。 | src/kabu/attribution.py。symbol寄与 / sector寄与 / market_index_regime寄与 / theme寄与。 |
| src/fx/analyst.py | する | 思想のみ流用 / 新規実装 | trace-stats → AIレビュー → 改善提案フローは有効。FX用プロンプトは使わない。 | src/kabu/analyst.py。AI_REVIEW_SAFETY.md の禁止表現 / 出力 schema を組込み。 |
| FX用 decision_engine.py | しない | 移植しない | 売買ルール本体。BUY/SELL/通貨exposure混在で危険。 | 株版 decision slice を別設計。 |
| events.json (FX) | しない | 移植しない | 経済指標固定表。株は決算カレンダー駆動。 | データソース駆動の events ローダー。 |
| oanda.py / live (FX) | しない | 移植しない | 株と無関係。証券会社API接続は禁止。 | なし。 |
| fx.db / FX trades schema | しない | 移植しない | 通貨ペア前提。 | 株式用 trades schema を新規定義。 |
| FX側 data.py | する | 思想のみ流用 / 新規実装 | Source Protocol / vendor非依存 / cache 方針は参考にする。 | src/kabu/data.py を新規実装 (DATA_SOURCES.md 準拠)。 |
| FX側 indicators.py | する | 思想のみ流用 / 新規実装 | テクニカル計算の純粋関数化・pytestしやすい構成は参考にする。 | src/kabu/indicators.py を新規実装。adjustment_basis を必ず明示。 |
| FX側 storage.py | する | 思想のみ流用 / 新規実装 | JSONL / run output / trace_jsonl_path の考え方は参考にする。 | src/kabu/storage.py を新規実装 (SCHEMA.md §6 と整合)。 |
| FX側 tests/ | する | 思想のみ流用 / 新規作成 | look-ahead bias検出、schema regression、waveform forward_return_end_ts 不変条件の考え方を docs に転記する。 | tests/test_*.py を新規。ROADMAP.md の pytest 表参照。 |
| FX側 docs/ | する | 思想のみ流用 / 新規作成 | TRACE_ANALYSIS_WORKFLOW / look-ahead bias 対策の文書化習慣を流用。FX固有docsはそのまま使わない。 | docs/*.md を本 repo で新規。 |

---

## 7. waveform 移植時の注意点

waveform 系は MVP の中で唯一「コード移植」を許す候補。ただし以下を守る。

- 価格スケールの違いに対応するため、log-return ベースで正規化必須。
- 出来高特徴量を入れる場合、log(volume) で扱う (log-normal に近い分布)。
- ストップ高安日 / 売買停止日 / 上場初日 / 大型分割直後の bar は library から除外 or フラグ付け。
- `library_kind ∈ {"global", "per_sector", "per_symbol", "liquidity_tier"}` を library 自身に埋め込み、混在禁止。
- `feature_set` 名 (例 `"v1_5bar_logret"`, `"v2_20bar_logret_volume_gap"`) を library に埋め込み、matcher は同じ feature_set のみ比較する。
- library size cap (例 100k entries) を超えたら新しいライブラリへロールオーバー。
- forward_return_end_ts <= bar_ts を library 書き込み時とロード時の両方で再 assert。
- pytest `test_waveform_forward_return_end_ts` (PR-S6) で守る。

---

## 8. 「思想流用」と「コード移植」の宣言ルール

PR description に必ず以下を含める:

```
## Migration declaration
- 思想流用: <fx file path>, ...
- コード移植: <fx file path> -> <kabu file path>, ...
- 移植コードに対する変更点:
  - <変更点 1>
  - <変更点 2>
- FX 固有概念の除去確認:
  - [ ] OANDA / DXY / pip / event_high / spread_abnormal / FX session / 通貨ペア BUY/SELL 対称 を含まない
  - [ ] CI lint で禁止トークンが検出されない
```

---

## 9. 関連 docs

- DATA_SOURCES.md (FX 側 data.py の思想流用)
- SCHEMA.md (decision_trace の slice を株式用に再定義)
- BACKTEST_CONTRACT.md (FX backtest engine を移植しない理由)
- AI_REVIEW_SAFETY.md (FX 用プロンプトを使わない)
- ROADMAP.md (PR ごとの移植判断適用)
