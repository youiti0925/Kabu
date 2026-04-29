# ROADMAP.md

Kabu の PR ロードマップと pytest 不変条件候補。承認は段階的。各 PR は明示承認まで着手しない。

---

## 0. 進捗サマリ (2026-04-29 現在)

| 段階 | 内容 | 状態 |
|---|---|---|
| P0.9 docs | 設計・契約・ポリシー docs 一式 (DATA_SOURCES / UNIVERSE / CALENDAR / SCHEMA / POINT_IN_TIME / SURVIVORSHIP / BACKTEST_CONTRACT / AI_REVIEW_SAFETY / ANTI_FX_LEAK / RISKS / ROADMAP / TRACE_ANALYSIS_WORKFLOW) | **完了** (commit 12d060d) |
| N1 guardrails | CI / pre-commit / 5 guard scripts (anti-FX-leak / large-files / forbidden-paths / gitignore / secrets) + smoke pytest | **完了** (commit c95acef、CI green 確認済) |
| N2 方針確定 | DATA_SOURCES / UNIVERSE / CALENDAR / BACKTEST_CONTRACT / SCHEMA / POINT_IN_TIME / ROADMAP の MVP 決定の docs 化 | **完了** (commit 897f5f8、CI green 確認済) |
| PR-S1 | data source interface (Source Protocol) + indicators 純粋関数群 | **完了** (commit 694bba4、CI green 確認済) |
| PR-S2 | decision_trace MVP (kabu.trace.v1 schema / dataclass / builder / JSONL I/O / 11 不変条件テスト) | **完了** (commit 1f80fec、CI green 確認済) |
| PR-S3 | backtest_engine MVP + scripted-action engine + run_metadata.json + future_outcome enrich (`kabu.outcome`) | **完了** (commit 64908cd、CI green 確認済) |
| P3.5 | run output layout 固定 (`kabu.run_paths`) + Trade/SkippedFill/BacktestResult I/O (`kabu.backtest.io`) + SkippedFill 拡張 | **完了** (commit a591972、CI green 確認済) |
| PR-S4 | trace-stats MVP (`kabu.stats`、aggregate / cross / report、bucket 境界 docs 化) | **本 PR で完了予定** |
| PR-S4.5 | attribution MVP (symbol / period 寄与) | 未着手 (要承認) |

---

## 1. 進行ポリシー

- **段階承認制**: 各 PR は単独で承認を得る。MVP 全体の事前承認はしない。
- **docs 先行**: 実装より先に契約・スキーマ・ポリシーを docs に固定する (今回 P0.9 の主旨)。
- **schema_version 固定**: `kabu.trace.v1` を維持。フィールド追加は optional のみ (SCHEMA.md §1-1)。
- **不変条件 first**: 各 PR の test 群は、機能テスト前に不変条件テストを必ず含める。
- **売買ルールは placeholder**: stats が揃うまで本ルール化しない。AI Review が C 提案を出してもルール変更は人間承認制 (AI_REVIEW_SAFETY.md)。

---

## 2. PR ロードマップ (確定版)

| # | PR ID | 内容 | 状態 | 主な docs 依存 | 主な test 依存 |
|---|---|---|---|---|---|
| 1 | PR-S0 | repo 初期化 | **完了** (12d060d) | 全般 | test_no_large_files |
| 2 | PR-S0.5 | DATA_SOURCES / UNIVERSE / CALENDAR の MVP 決定 docs 化 | **本 N2 で完了予定** | DATA_SOURCES.md / UNIVERSE.md / CALENDAR.md | - |
| 3 | PR-S0.7 | CALENDAR / 営業日 / 売買単位 / tick_size 方針 | docs 化済 (実装は PR-S1 で) | CALENDAR.md | - |
| 4 | PR-S0.9 | SCHEMA / POINT_IN_TIME / SURVIVORSHIP / BACKTEST_CONTRACT / AI_REVIEW_SAFETY / ANTI_FX_LEAK / RISKS の docs + CI / pre-commit guardrails | **完了** (12d060d, c95acef) | 全般 | test_no_fx_imports / test_no_large_files / etc. |
| 5 | PR-S1 | data source interface (Source Protocol) + indicators 純粋関数群 | 未着手 (要承認) | DATA_SOURCES.md / SCHEMA.md (technical の adjustment_basis) | test_no_lookahead_indicators / test_split_adjustment_continuity / test_universe_snapshot_consistency |
| 6 | PR-S2 | decision_trace MVP (market / technical / long_term_trend / risk_ctx / decision / execution_assumption / future_outcome=None の最小版 + JSONL I/O) | **完了予定 (本 PR)** | SCHEMA.md / POINT_IN_TIME.md | test_schema_version_required / test_bar_ts_tzaware / test_decision_rule_id_required / test_confidence_value_range / test_technical_adjustment_basis_required / test_assumed_fill_bar_required / test_latency_bars_required / test_forward_return_basis_required / test_decision_does_not_depend_on_outcome / test_library_id_not_top_level / test_trace_jsonl_roundtrip |
| 7 | PR-S2.5 | look-ahead invariant tests harness (テスト基盤強化) | 未着手 | POINT_IN_TIME.md | (上記 + 不変条件チェックの汎用 harness) |
| 8 | PR-S3 | backtest_engine MVP + scripted-decision engine + run_metadata.json + future_outcome enrich パイプライン | **完了予定 (本 PR)** | BACKTEST_CONTRACT.md S0 D-15 / D-18 / SCHEMA.md / POINT_IN_TIME.md 3-7 | test_run_metadata_required / test_trace_jsonl_path_required_for_trades / test_assumed_fill_next_open / test_same_close_fill_forbidden / test_fee_and_slippage_applied / test_dividend_ex_day_handling / test_stop_high_low_block / test_volume_floor_cap / test_survivorship_policy_recorded / test_future_outcome_backfill_separate |
| 9 | PR-S4 | trace-stats MVP (`kabu.stats`: loaders / buckets / aggregate / cross / report) | **完了予定 (本 PR)** | TRACE_ANALYSIS_WORKFLOW.md / STATS.md | test_load_run_inputs_requires_metadata / test_load_run_inputs_run_id_mismatch / test_stats_header_contains_bias_warnings / test_aggregate_final_action_outcome / test_aggregate_symbol_outcome / test_skip_reason_counts / test_trade_pnl_summary / test_low_sample_bucket_flag / test_bucket_boundaries_documented / test_cross_stats_two_axis / test_stats_writer_uses_tmp_path |
| 10 | PR-S4.5 | attribution MVP (symbol / period 寄与) | 未着手 | TRACE_ANALYSIS_WORKFLOW.md | (寄与集計テスト) |
| 11 | PR-S5 | market_index_context + sector_context | 未着手 | DATA_SOURCES.md / CALENDAR.md §0 D-8 (海外時差) / SCHEMA.md | test_us_index_no_lookahead 系 / regime 算出のテスト |
| 12 | PR-S7 | earnings / event_context (**S6 より先に着手**) | 未着手 | CALENDAR.md §0 D-9 / POINT_IN_TIME.md §3 / SCHEMA.md (earnings_ctx / event_ctx) | release_ts 不変条件テスト / blackout テスト |
| 13 | PR-S6 | waveform 移植 (earnings-aware library 前提) | 未着手 (PR-S7 後) | ANTI_FX_LEAK.md §7 / SCHEMA.md (waveform_ctx) | test_waveform_forward_return_end_ts |
| 14 | PR-S6.5 | waveform library quality gates (size cap / feature_set 一貫性 / runtime check) | 未着手 (PR-S6 後) | ANTI_FX_LEAK.md §7 | library 整合テスト |
| 15 | PR-S8 | fundamental_context (**PIT データ採用後のみ着手可**) | 未着手 (PIT 確保まで保留) | DATA_SOURCES.md §0 D-7 / POINT_IN_TIME.md | PIT 不変条件テスト |
| 16 | PR-S10 | AI Review / rule discovery (承認制) | 未着手 | AI_REVIEW_SAFETY.md | test_ai_review_output_schema 系 |
| 17 | PR-S9 | news / theme / sentiment (最後) | 未着手 | POINT_IN_TIME.md (published_ts) / DATA_SOURCES.md | news 不変条件テスト |

注: S6 と S7 はレビュー指摘どおり **S7 を先** にする (DATA_SOURCES.md §0 / ANTI_FX_LEAK.md §7)。理由は、決算前後のノイズを認識しないまま waveform library を作ると、後で library 再構築が必要になる可能性が高いため。

---

## 2-A. PR-S1 着手の前提条件 (N2 で確定)

PR-S1 は以下が **すべて確定している** ことを前提に着手する。確定状況は本 ROADMAP §0 / 各 docs §0 で参照可能。

- [x] **Source Protocol 方針が確定している** (DATA_SOURCES.md §0 D-3 / D-4 / D-5)
- [x] **初期ユニバース方針が確定している** (UNIVERSE.md §0 D-1: MVP-1 = 自由銘柄リスト)
- [x] **日足 / T close → T+1 open 契約が確定している** (CALENDAR.md §0 D-1 / D-3 / D-4 / D-5 / BACKTEST_CONTRACT.md §0 D-3 / D-5 / D-6)
- [x] **fundamentals は MVP から除外する方針が確定している** (DATA_SOURCES.md §0 D-6 / D-7 / D-8)
- [x] **米国指数の時差ルールが確定している** (CALENDAR.md §0 D-8 / POINT_IN_TIME.md §3-6)
- [x] **schema の必須項目が確定している** (SCHEMA.md §0 D-1〜D-13)

未確定のままでも PR-S1 は着手可能だが、以下は PR-S1 内 / PR-S1 着手直前にユーザ承認が必要 (ROADMAP §6-2 / 各 docs の §10-2):

- 価格データソースの最終ベンダ (yfinance / J-Quants / 自社蓄積)
- 銘柄コードのキー形式 (4桁 / 4桁+市場区分 / ISIN)
- universe スナップショットの格納先
- bar_ts_available のデフォルト遅延の最終値

---

## 3. 各 PR の Definition of Done (DoD)

全 PR 共通:

- 関連 docs の参照が PR description に明記されている
- 該当 docs の不変条件 / テスト候補が test として実装されている (該当 PR 表の test 列)
- pytest が green
- run / artifact 出力先が `runs/` / `libs/` 配下で .gitignore 済み
- run_metadata が必須項目を満たしている (BACKTEST_CONTRACT.md §7)
- ANTI_FX_LEAK の禁止トークンが src/kabu に存在しない (CI lint)
- 売買ルールが placeholder のまま (本 ルール化は明示承認後)

---

## 4. pytest 不変条件 / 候補テスト一覧

| テスト名 | 目的 | 対象 PR |
|---|---|---|
| test_no_lookahead_indicators | rolling 指標が未来 bar を参照しない | PR-S1 |
| test_pointintime_slice_null_before_release | bar_ts < release_ts の slice は null になる | PR-S2 |
| test_universe_snapshot_consistency | signal 対象が universe@bar_ts と一致する | PR-S1 / PR-S2 |
| test_split_adjustment_continuity | 分割後も調整済系列が連続する | PR-S1 |
| test_dividend_ex_day_handling | 配当落ちで意図しない PnL 歪みを出さない | PR-S3 |
| test_stop_high_low_block | ストップ高安 bar で不自然に約定しない | PR-S3 |
| test_volume_floor_cap | 出来高フロア超過注文を約定不可または分割扱いにする | PR-S3 |
| test_waveform_forward_return_end_ts | forward_return_end_ts <= bar_ts を保証 | PR-S6 |
| test_schema_version_required | trace に schema_version が無い場合 fail | PR-S2 |
| test_run_metadata_required | run_metadata 不足なら fail | PR-S3 |
| test_trace_jsonl_path_required_for_trades | trades に trace_jsonl_path が無ければ fail | PR-S3 |
| test_no_fx_imports | src/kabu に FX 固有 token が混入しない | PR-S0.9 (CI で実装済) |
| test_no_large_files | 大容量ファイルや raw data を commit しない | PR-S0 (CI で実装済) |
| test_decision_does_not_depend_on_outcome | decision builder の入力に future_outcome が含まれない | PR-S2 |
| test_delisted_symbol_inclusion | 上場廃止銘柄が delisting_date 以前は universe に含まれる | PR-S5 (historical universe 採用後) |
| test_survivorship_policy_recorded | run_metadata に survivorship_policy が必ず存在 | PR-S3 |
| test_us_index_no_lookahead | 日本 T 日 bar の市場指数 ctx に米国 T 日終値が混入しない | PR-S5 |
| test_bar_ts_tzaware | trace 出力の bar_ts が timezone-aware である | PR-S2 |
| test_assumed_fill_bar_required | execution_assumption.assumed_fill_bar が "next_open" で必須 | PR-S3 |
| test_latency_bars_required | execution_assumption.latency_bars が必須で MVP は 1 | PR-S3 |
| test_decision_rule_id_required | decision の rule_id / rule_version / rule_params_hash が必須 | PR-S2 |
| test_confidence_value_range | decision.confidence ∈ [0.0, 1.0] または null | PR-S2 |
| test_technical_adjustment_basis_required | technical.adjustment_basis が必須 | PR-S2 |
| test_forward_return_basis_required | future_outcome.forward_return_basis が必須 | PR-S3 |
| test_library_id_in_slice | library_id は top-level ではなく slice 内 | PR-S6 |
| test_run_metadata_libraries_array | run_metadata.libraries が配列で {slice, library_id, library_kind, feature_set} を持つ | PR-S6 |
| test_ai_review_output_schema | AI Review の出力が JSON Schema に準拠 | PR-S10 |
| test_ai_review_no_forbidden_words | 禁止表現が含まれない | PR-S10 |
| test_ai_review_cite_or_decline | evidence_stats_ref が空でない | PR-S10 |
| test_ai_review_requires_human_approval_true | requires_human_approval が常に true | PR-S10 |
| test_ai_review_no_symbol_action | 銘柄名 + 動詞のパターンが出ない | PR-S10 |
| test_ai_review_no_category_c_under_survivorship_warning | survivorship 警告下で C が出ない | PR-S10 |

---

## 5. CI / pre-commit (PR-S0.9 で導入済み + 将来拡張)

導入済み (PR-S0.9):

- `.github/workflows/guardrails.yml` で push / pull_request 時に以下を実行
  1. `scripts/check_gitignore.py` (.gitignore 必須エントリ抜け検出)
  2. `scripts/check_no_forbidden_paths.py` (`runs/ libs/ data/raw/ data/cache/` および `*.parquet/*.duckdb/*.sqlite/*.csv/*.pkl/*.feather/.env` の追跡検出)
  3. `scripts/check_no_large_files.py` (1MB 超ファイル検出)
  4. `scripts/check_no_fx_leak.py` (ANTI_FX_LEAK.md §3 の禁止 token を `src/kabu/`, `tests/`, `docs/` で検出。allowlist: `docs/ANTI_FX_LEAK.md`, `docs/RISKS.md`, `README.md`)
  5. `scripts/check_secrets.py` (heuristic secret scan)
  6. `pytest -ra` (テスト未収集 = exit 5 を許容)
- `.pre-commit-config.yaml` で同等のチェックを pre-commit でも実行
  - `pre-commit-hooks` の `end-of-file-fixer` / `trailing-whitespace` / `check-merge-conflict` / `check-yaml` / `check-toml` / `check-added-large-files` / `detect-private-key`
  - 上記 5 つの local hook

将来拡張:

- secret scan の本格化 (gitleaks / detect-secrets を CI に組み込み。RISKS.md 5-3)
- ANTI_FX_LEAK.md §3 の `BUY/SELL` 対称前提など意味論的禁止の追加
- ruff / black / mypy の段階導入 (実装が始まる PR-S1 以降)
- main / develop 等のブランチ保護を guardrails.yml の green を必須にする

---

## 6. 要決定事項

### 6-1. 決定済 (N2 / PR-S0.5 で確定)

- [x] 初期対象市場: 日本株のみ (DATA_SOURCES.md §0 D-1)
- [x] 通貨: JPY 固定 / report_currency: JPY 固定 (DATA_SOURCES.md §0 D-2)
- [x] 海外株 / ADR / 海外 ETF: MVP 対象外 (DATA_SOURCES.md §0 D-1)
- [x] 初期ユニバース: MVP-1 自由銘柄リスト (UNIVERSE.md §0 D-1)
- [x] historical universe MVP 暫定 policy: static_current_listing 許容 (UNIVERSE.md §0 D-4)
- [x] survivorship warning を stats / AI Review で必ず出す (UNIVERSE.md §0 D-5)
- [x] AI Review は survivorship-biased 状態で C 提案を出さない (UNIVERSE.md §0 D-6)
- [x] PR-S1 では Source Protocol を先に作る / ベンダ直叩き禁止 (DATA_SOURCES.md §0 D-3)
- [x] as_of 必須 / デフォルト「今」禁止 (DATA_SOURCES.md §0 D-4)
- [x] data_source / data_source_version を run_metadata に必須保存 (DATA_SOURCES.md §0 D-5)
- [x] fundamentals は MVP 実装しない / PR-S8 は PIT 確保まで未着手 (DATA_SOURCES.md §0 D-6 / D-7)
- [x] interval = 1d 固定 (CALENDAR.md §0 D-1)
- [x] timezone = Asia/Tokyo / aware datetime 必須 (CALENDAR.md §0 D-2)
- [x] decision at T close → fill at T+1 open (CALENDAR.md §0 D-3 / D-4 / BACKTEST_CONTRACT.md §0 D-3)
- [x] same close fill 禁止 (CALENDAR.md §0 D-5 / BACKTEST_CONTRACT.md §0 D-4)
- [x] bar_ts_close と bar_ts_available を分けて持つ / bar_ts は原則 bar_ts_available (CALENDAR.md §0 D-6 / D-7)
- [x] 米国指数の時差ルール (CALENDAR.md §0 D-8 / POINT_IN_TIME.md §3-6)
- [x] 引け後発表 / 不明発表は翌営業日寄付以降 (CALENDAR.md §0 D-9)
- [x] earnings / event 欠損は null + unavailable_reason (CALENDAR.md §0 D-10)
- [x] long_only / 現物相当 / 税前 PnL (BACKTEST_CONTRACT.md §0 D-1 / D-2)
- [x] slippage_bps / fee_bps / fee_fixed_jpy を run_metadata に必須保存 (BACKTEST_CONTRACT.md §0 D-7 / D-8)
- [x] technical = adj / fill = raw (BACKTEST_CONTRACT.md §0 D-9 / SCHEMA.md §0 D-9)
- [x] schema 必須: interval / bar_ts_close / bar_ts_available (SCHEMA.md §0 D-1 / D-2 / D-3)
- [x] schema 必須: decision.rule_id / rule_version / rule_params_hash (SCHEMA.md §0 D-5)
- [x] decision.confidence ∈ [0.0, 1.0] または null (SCHEMA.md §0 D-6)
- [x] schema 必須: execution_assumption.assumed_fill_bar / latency_bars (SCHEMA.md §0 D-7 / D-8)
- [x] schema 必須: technical.adjustment_basis (SCHEMA.md §0 D-9)
- [x] schema 必須: future_outcome.forward_return_basis (SCHEMA.md §0 D-10)
- [x] future_outcome は decision builder の入力に含めない (SCHEMA.md §0 D-11 / POINT_IN_TIME.md §3-7)
- [x] library_id は top-level ではなく slice 内 (SCHEMA.md §0 D-12)
- [x] run_metadata.libraries は配列で {slice, library_id, library_kind, feature_set} を持つ (SCHEMA.md §0 D-13)
- [x] schema_version 運用ポリシー: 削除禁止 / 型変更禁止 / 追加 only (SCHEMA.md §1-1)

### 6-2. 未確定 (PR-S1 / PR-S3 / PR-S5 / PR-S7 / PR-S8 着手前にユーザ承認が必要)

- [ ] 価格データソースの最終ベンダ (yfinance / J-Quants / 自社蓄積) — PR-S1
- [ ] 主要指数のソース — PR-S5
- [ ] 銘柄コードのキー形式 — PR-S1
- [ ] universe スナップショットの格納先 — PR-S1
- [ ] 営業日カレンダーソース / 半日立会 close 時刻 / bar_ts_available 遅延 — PR-S1
- [ ] tick_size table / 制限値幅 table のソース — PR-S0.7 後半 / PR-S5
- [ ] 売買単位の例外 (単元未満許可するか) — PR-S3
- [ ] fee_bps / slippage_bps / volume_floor_ratio / min_avg_turnover_jpy のデフォルト値 — PR-S3
- [ ] 上場廃止時の強制決済価格 — PR-S3
- [ ] outcome_label のしきい値方式 (static / atr-norm / 両併存) — PR-S3
- [ ] 単一 vs portfolio の API 形 — PR-S5
- [ ] PIT fundamentals ソース — PR-S8 着手前
- [ ] AI Review に渡すモデル / プロンプト方針 — PR-S10

---

## 7. 関連 docs

- README.md
- DATA_SOURCES.md
- UNIVERSE.md
- CALENDAR.md
- SCHEMA.md
- POINT_IN_TIME.md
- SURVIVORSHIP.md
- BACKTEST_CONTRACT.md
- AI_REVIEW_SAFETY.md
- ANTI_FX_LEAK.md
- RISKS.md
- TRACE_ANALYSIS_WORKFLOW.md
