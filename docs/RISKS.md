# RISKS.md

Kabu の既知のリスクと限界。各 stats レポートと AI Review はこのリストを参照する。

---

## 1. バイアス系

### 1-1. look-ahead bias

- 説明: 過去の判断時点で利用できなかった情報を誤って使ってしまう。
- 主な発生源:
  - rolling 指標が未来 bar を参照
  - 「現在の最新 PER」を過去 bar に流用 (PIT 不可ソース)
  - 決算サプライズを結果として知った状態で当日判断に使う
  - future_outcome を decision で参照
- 対策: POINT_IN_TIME.md / DATA_SOURCES.md / SCHEMA.md (future_outcome の独立性)
- 検証: pytest `test_no_lookahead_indicators`, `test_pointintime_slice_null_before_release`, `test_waveform_forward_return_end_ts`

### 1-2. survivorship bias

- 説明: 現在生き残っている銘柄だけで過去検証することによる偏り。
- 主な発生源:
  - 「現在の上場銘柄リスト」を過去 universe に流用
  - 倒産 / 上場廃止銘柄が落ちている
  - 指数構成変更を考慮しない
- 対策: SURVIVORSHIP.md / UNIVERSE.md
- 検証: pytest `test_universe_snapshot_consistency`, `test_delisted_symbol_inclusion`

### 1-3. point-in-time fundamentals 不足

- 説明: 多くの無料データソースは fundamentals を最新値で上書き。過去の bar に流用すると結果として look-ahead bias を内包。
- 影響: PER / PBR / ROE / EPS / 配当利回り 等を含む slice (fundamental_ctx) を MVP で使えない。
- 対策: PIT を保証するソース採用まで PR-S8 を着手しない (DATA_SOURCES.md §6)

### 1-4. selection bias / cherry picking

- 説明: 結果を見て期間 / 銘柄 / 軸を選び直すことで、見せたい結果に寄せる。
- 対策: 集計軸 / bucket 定義を docs / config に固定し、結果を見て後付けで軸を増やすことを禁止。AI Review にも同様の制限。

### 1-5. 過学習 / overfitting

- 説明: 軸数 / bucket 数を増やすほど偽陽性が出る。
- 対策:
  - 最低標本数フィルタ (PR-S4 MVP: `DEFAULT_MINIMUM_N = 30`、`low_sample = true` フラグで警告。docs/STATS.md §1 / docs/ATTRIBUTION.md §2)
  - PR-S4 cross 集計は **2 軸まで** に制限 (3 軸以上は MVP 外)
  - P4.5 attribution は 1 bucket への 50% 超集中を `concentration_warnings` で警告 (docs/ATTRIBUTION.md §2)
  - 将来追加: Benjamini-Hochberg 等の多重検定補正
  - 将来追加: block bootstrap で信頼区間を出す
  - 将来追加: walk-forward / out-of-sample 分割
- AI Review (PR-S10) は将来 low_sample bucket / 集中警告下の bucket を C カテゴリ提案に使ってはならない (AI_REVIEW_SAFETY.md §10 系 / docs/STATS.md §1 / docs/ATTRIBUTION.md §2)。
- TRACE_ANALYSIS_WORKFLOW.md と整合。

### 1-6. 多重検定 / multiple testing

- 説明: bucket × outcome を多軸で出すと偶然の有意差が頻発する。
- 対策: q-value (BH) を bucket 単位で計算し、stats レポートに表示。

---

## 2. 約定 / 市場マイクロ系

### 2-1. 低流動性銘柄の過大評価

- 説明: 板薄銘柄では実際には大量約定できない。出来高フロアを設けないと backtest が現実より良くなる。
- 対策: BACKTEST_CONTRACT.md §4-3 / §4-4 の volume_floor / min_avg_turnover_jpy。

### 2-2. ストップ高安での約定不能

- 説明: 制限値幅 hit 時は実際には約定不可。
- 対策: BACKTEST_CONTRACT.md §4-5。pytest `test_stop_high_low_block`。

### 2-3. 特別気配 / 売買停止

- 説明: 寄り付かない銘柄を約定できる前提で計算するとリターンが歪む。
- 対策: BACKTEST_CONTRACT.md §4-6。

### 2-4. 寄付ギャップ

- 説明: T close → T+1 open の間にギャップが発生する場合、約定価格が想定より大きく動く。
- 対策: スリッページモデルの拡張 (将来)。MVP では `slippage_bps` 固定で扱う。

### 2-5. 配当落ち / 株式分割

- 説明: 調整係数の処理を間違えると PnL が不連続になる。
- 対策: BACKTEST_CONTRACT.md §5。pytest `test_split_adjustment_continuity`, `test_dividend_ex_day_handling`。

---

## 3. データ系

### 3-1. データソース規約変更

- 説明: yfinance / Stooq 等の非公式・準公式ソースは利用規約が変動する。
- 対策:
  - 商用化前提では J-Quants / 有償ベンダの導入が必要 (DATA_SOURCES.md §9)。
  - P4.7 で yfinance を **OHLCV 専用の参考 vendor** として採用したが、`Source` Protocol の裏側に閉じ込めて差し替え可能にしてある (`src/kabu/data/sources/yfinance_source.py`)。
  - vendor 切替時は `tests/invariants/test_vendor_layer_isolation.py` の `_FORBIDDEN_VENDOR_TOKENS` に新 vendor を追加し、構造的に隔離を維持する。
  - VENDOR_SETUP.md §5 に追加手順を明記。

### 3-2. 分割・配当調整ミス

- 説明: vendor 間で調整係数の計算が異なる。
- 対策: adj_close / raw_close を両系列保持。data_snapshot_hash で履歴管理。

### 3-3. 銘柄コードの不整合

- 説明: 4桁 / 5桁 / 市場区分付き / ISIN 等で表現が異なる。系譜が変わるケース (合併・株式交換) に注意。
- 対策: UNIVERSE.md §10。symbol 表現を universe_snapshot に固定。

### 3-4. 再現性喪失

- 説明: データソース更新で過去 run が再現不能になる。
- 対策: data_snapshot_hash の保存 (DATA_SOURCES.md §4)。

---

## 4. 統計 / 分析系

### 4-1. 因果と相関の混同

- 説明: bucket × outcome に有意差があっても、因果ではない可能性。
- 対策: AI_REVIEW_SAFETY.md の禁止表現 (「これが原因」「確定」)。

### 4-2. 期間依存

- 説明: 強い相場 / 弱い相場の期間に偏ると signal が偏って見える。
- 対策: 年度別 / 四半期別の stratified stats (TRACE_ANALYSIS_WORKFLOW.md)。

### 4-3. autocorrelation

- 説明: returns / hit_rate は時系列相関を持つ。単純な t-test は p-value を過小評価する。
- 対策: block bootstrap / Newey-West (TRACE_ANALYSIS_WORKFLOW.md)。

---

## 5. システム / 運用系

### 5-1. AI Review 暴走

- 説明: AI が「確定」「買うべき」「これが原因」を出す / 銘柄推奨を出す / 売買シグナルを出す。
- 対策: AI_REVIEW_SAFETY.md の禁止表現 / 出力 schema / cite-or-decline / generator → critic。

### 5-2. FX ロジック混入

- 説明: FX repo からのコピペで通貨ペア前提や DXY 依存ロジックが紛れ込む。
- 対策: ANTI_FX_LEAK.md の grep / lint / レビュー観点。

### 5-3. runs / libs / data の commit 事故

- 説明: backtest 出力 / waveform library / 大容量 raw データを誤って commit。
- 対策 (PR-S0.9 で導入済み + P3.5 で強化):
  - .gitignore で `runs/`, `libs/`, `data/raw/`, `data/cache/`, `*.parquet`, `*.duckdb`, `*.sqlite`, `*.csv`, `*.pkl`, `*.feather`, `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/` を除外
  - pre-commit hook で 1MB 超ファイルの commit を阻止 (`pre-commit-hooks.check-added-large-files` + `scripts/check_no_large_files.py`)
  - CI (`.github/workflows/guardrails.yml`) で `runs/ libs/ data/raw/ data/cache/` 配下や `*.parquet` 等の追跡を検出する `scripts/check_no_forbidden_paths.py` を実行
  - `scripts/check_gitignore.py` で `.gitignore` の必須エントリ抜けを検出
  - `scripts/check_secrets.py` で軽量な secret スキャン (heuristic)
  - **P3.5 で `kabu.run_paths.RunPaths` を導入**: 全 run 出力は `base_dir / "runs" / run_id / ...` に閉じる構造。テストは `tmp_path` のみを使う規約。`tests/invariants/test_no_committed_run_outputs.py` が pytest 内でも `git ls-files` で `runs/` `libs/` `data/raw/` `data/cache/` 配下に追跡ファイルが無いことを検証する。
  - **P3.5 で `RunPaths.run_id` のサニタイズ**: `..`, `/`, `\`, `\x00` を含む `run_id` を `ValueError` で拒否 (path traversal 防止)。
- 後続強化 (将来 PR):
  - secret scan は heuristic スクリプトを暫定運用。本格的には [gitleaks](https://github.com/gitleaks/gitleaks) もしくは detect-secrets を CI に組み込む
  - `scripts/check_no_fx_leak.py` の禁止 token は段階的に拡張 (例: `BUY/SELL` 対称前提) し、`ruff` カスタムルール化を検討

### 5-4. schema 破壊的変更

- 説明: 既存 trace JSONL が読めなくなる schema 変更。
- 対策: SCHEMA.md §1-1 の運用ポリシー (削除禁止 / 型変更禁止 / 追加 only)。v2 移行時は migrations/ で変換スクリプトを用意。

### 5-5. 再現性の崩壊

- 説明: commit_sha / data_snapshot_hash / universe_snapshot_id を保存しないと過去 run が再現不能。
- 対策: BACKTEST_CONTRACT.md §7 の run_metadata 必須項目。

---

## 6. 法務 / コンプライアンス

### 6-1. 銘柄推奨と金融商品取引法

- 説明: 「この銘柄を買え」と断定する出力は投資助言業に該当する可能性。
- 対策: AI_REVIEW_SAFETY.md の銘柄名 + 動詞 禁止 / 売買シグナルを直接出さない。

### 6-2. データソースのライセンス

- 説明: 商用利用不可のソースを利用すると法的リスク。
- 対策: DATA_SOURCES.md §9 のライセンス記録。

---

## 7. 既知の MVP 限界

- historical universe が無い場合は survivorship-biased。
- PIT fundamentals が無い場合は fundamental_ctx を出さない。
- 米株 / 海外指数は MVP では指数のみ対応。個別米株は将来。
- 信用 / 空売り / オプション / 先物は MVP 外。
- ニュース / sentiment は PR-S9 まで保留。
- intraday は MVP 外。

---

## 8. 関連 docs

- POINT_IN_TIME.md
- SURVIVORSHIP.md
- DATA_SOURCES.md
- UNIVERSE.md
- CALENDAR.md
- SCHEMA.md
- BACKTEST_CONTRACT.md
- AI_REVIEW_SAFETY.md
- ANTI_FX_LEAK.md
- ROADMAP.md
- TRACE_ANALYSIS_WORKFLOW.md
