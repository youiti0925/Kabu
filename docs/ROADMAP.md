# ROADMAP.md

Kabu の PR ロードマップと pytest 不変条件候補。承認は段階的。各 PR は明示承認まで着手しない。

---

## 1. 進行ポリシー

- **段階承認制**: 各 PR は単独で承認を得る。MVP 全体の事前承認はしない。
- **docs 先行**: 実装より先に契約・スキーマ・ポリシーを docs に固定する (今回 P0.9 の主旨)。
- **schema_version 固定**: `kabu.trace.v1` を維持。フィールド追加は optional のみ (SCHEMA.md §1-1)。
- **不変条件 first**: 各 PR の test 群は、機能テスト前に不変条件テストを必ず含める。
- **売買ルールは placeholder**: stats が揃うまで本ルール化しない。AI Review が C 提案を出してもルール変更は人間承認制 (AI_REVIEW_SAFETY.md)。

---

## 2. PR ロードマップ (確定版)

| # | PR ID | 内容 | 主な docs 依存 | 主な test 依存 |
|---|---|---|---|---|
| 1 | PR-S0 | repo 初期化 (本 PR / 完了) | 全般 | test_no_large_files |
| 2 | PR-S0.5 | DATA_SOURCES / UNIVERSE | DATA_SOURCES.md / UNIVERSE.md | - |
| 3 | PR-S0.7 | CALENDAR / 営業日 / 売買単位 / tick_size 方針 | CALENDAR.md | - |
| 4 | PR-S0.9 | SCHEMA / POINT_IN_TIME / SURVIVORSHIP / BACKTEST_CONTRACT / AI_REVIEW_SAFETY / ANTI_FX_LEAK / RISKS | 全般 | test_no_fx_imports |
| 5 | PR-S1 | data source interface (Source Protocol) + indicators 純粋関数群 | DATA_SOURCES.md / SCHEMA.md (technical の adjustment_basis) | test_no_lookahead_indicators / test_split_adjustment_continuity / test_universe_snapshot_consistency |
| 6 | PR-S2 | decision_trace MVP (market / technical / long_term_trend / decision / future_outcome / risk_ctx の最小版) | SCHEMA.md / POINT_IN_TIME.md | test_pointintime_slice_null_before_release / test_schema_version_required |
| 7 | PR-S2.5 | look-ahead invariant tests harness (テスト基盤強化) | POINT_IN_TIME.md | (上記 + 不変条件チェックの汎用 harness) |
| 8 | PR-S3 | backtest_engine MVP + placeholder ルール + trace JSONL 出力 + run_metadata | BACKTEST_CONTRACT.md / SCHEMA.md | test_dividend_ex_day_handling / test_stop_high_low_block / test_volume_floor_cap / test_run_metadata_required / test_trace_jsonl_path_required_for_trades |
| 9 | PR-S4 | trace-stats MVP (final_action × outcome ほか) | TRACE_ANALYSIS_WORKFLOW.md | (集計 IO テスト) |
| 10 | PR-S4.5 | attribution MVP (symbol / period 寄与) | TRACE_ANALYSIS_WORKFLOW.md | (寄与集計テスト) |
| 11 | PR-S5 | market_index_context + sector_context | DATA_SOURCES.md / CALENDAR.md (海外時差) / SCHEMA.md | (時差ロジック / regime 算出のテスト) |
| 12 | PR-S7 | earnings / event_context (S6 より先に着手) | CALENDAR.md / POINT_IN_TIME.md / SCHEMA.md (earnings_ctx / event_ctx) | (release_ts 不変条件テスト / blackout テスト) |
| 13 | PR-S6 | waveform 移植 (earnings-aware library 前提) | ANTI_FX_LEAK.md §7 / SCHEMA.md (waveform_ctx) | test_waveform_forward_return_end_ts |
| 14 | PR-S6.5 | waveform library quality gates (size cap / feature_set 一貫性 / runtime check) | ANTI_FX_LEAK.md §7 | (library 整合テスト) |
| 15 | PR-S8 | fundamental_context (PIT データ採用後のみ) | DATA_SOURCES.md §6 / POINT_IN_TIME.md | (PIT 不変条件テスト) |
| 16 | PR-S10 | AI Review / rule discovery (承認制) | AI_REVIEW_SAFETY.md | test_ai_review_output_schema 系 |
| 17 | PR-S9 | news / theme / sentiment (最後) | POINT_IN_TIME.md (published_ts) / DATA_SOURCES.md | (news 不変条件テスト) |

注: S6 と S7 はレビュー指摘どおり **S7 を先** にする。理由は、決算前後のノイズを認識しないまま waveform library を作ると、後で library 再構築が必要になる可能性が高いため (ANTI_FX_LEAK.md §7)。

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
| test_no_fx_imports | src/kabu に FX 固有 token が混入しない | PR-S0.9 |
| test_no_large_files | 大容量ファイルや raw data を commit しない | PR-S0 |
| test_decision_does_not_depend_on_outcome | decision builder の入力に future_outcome が含まれない | PR-S2 |
| test_delisted_symbol_inclusion | 上場廃止銘柄が delisting_date 以前は universe に含まれる | PR-S5 (historical universe 採用後) |
| test_survivorship_policy_recorded | run_metadata に survivorship_policy が必ず存在 | PR-S3 |
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

## 6. 要決定事項 (再掲)

PR-S1 着手前に以下を確定する。

- [ ] データソース (DATA_SOURCES.md §10)
- [ ] 初期ユニバース (UNIVERSE.md §10)
- [ ] historical universe の有無 / MVP の暫定 policy
- [ ] 通貨と海外株の扱い
- [ ] 売買単位 (単元のみ / 単元未満可)
- [ ] 約定タイミング契約 (T close → T+1 open)
- [ ] adjustment_basis 固定値
- [ ] outcome_label のしきい値方式 (static / atr-norm / 両併存)
- [ ] schema_version 運用ポリシーの最終確認
- [ ] decision.confidence の値域
- [ ] AI Review 安全仕様の最終確認
- [ ] 単一 vs portfolio の API 形

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
