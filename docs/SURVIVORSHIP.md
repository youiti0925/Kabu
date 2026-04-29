# SURVIVORSHIP.md

survivorship bias 対策。Kabu は universe を時点付きで管理し、上場廃止 / 入替 / 市場変更を反映する。

---

## 1. survivorship bias とは

- 過去検証の対象を「現在も生き残っている銘柄」だけに絞ってしまうことで、結果が現実より良く見えるバイアス。
- 上場廃止された銘柄 (倒産 / 買収 / 整理 / 上場廃止基準抵触) を universe から落とすと、過去のドローダウンが過小評価される。
- 指数構成銘柄も時点で変わるため、現在の構成を過去に遡って当てると「強かった銘柄だけ」を選ぶ結果になる。

---

## 2. 影響の例

- 「日経225 採用銘柄を 10 年検証」と称して現在の構成だけで検証 → 銘柄入替で抜けた銘柄 (=パフォーマンスが悪化して外された側) のドローダウンが結果に出ない。
- 「過去 10 年で生き残った全銘柄でブレイクアウト戦略を検証」 → 倒産した銘柄が落ちているため、ブレイクアウト失敗 → 上場廃止のテール損失が消える。
- ETF / 指数構成変更 (TOPIX 浮動株調整等) を考慮しないと、買い需要に乗ったリターンを過大評価する。

---

## 3. 設計上の対策

### 3-1. universe_snapshot_id

- universe を時点付きで持つ (UNIVERSE.md §4)。
- bar_ts 時点の membership は `effective_from <= bar_ts.date() AND (effective_to is null OR bar_ts.date() < effective_to)` を満たすものに限る。
- 上場廃止銘柄は `delisting_date` 以前は universe に残し、以降は除外。

### 3-2. 指数 membership 履歴

- TOPIX / 日経225 / グロース250 等の構成変更は別 table で持つ。
- 「TOPIX 採用銘柄を対象に backtest」のような stratified 分析では bar_ts 時点の membership を必ず参照する。

### 3-3. 上場廃止データ

- delisting_date / delisting_reason ({"bankruptcy", "merger_acquired", "going_private", "regulatory", "other"}) を保持。
- バンクラプシーは PnL に終値ベースの大損 (場合によりゼロ) を与える前提。MVP では「delisting_date の翌営業日寄付で強制決済 (fill_price=0 or last_close)」のような保守ルールを backtest_engine に検討。確定は PR-S3 / PR-S5。

### 3-4. 市場変更

- 旧市場 (一部 / 二部 / マザーズ / JASDAQ) → 新市場 (プライム / スタンダード / グロース) の移行履歴。
- 同じ symbol が市場区分だけ変わる場合、universe_snapshot で `market` を時点別に保持する。

---

## 4. MVP で historical universe が無い場合

UNIVERSE.md §6 の暫定方針を再掲。

- run_metadata に以下を必ず保存:
  - `survivorship_policy: "static_current_listing"`
  - `survivorship_warning: true`
- stats レポート / AI Review の冒頭に **必ず** 警告を表示:
  - 「結果は survivorship-biased である可能性が高い」
  - 「historical universe が確認できるソース採用後に再検証が必要」
- AI Review はこの状態で「ルール変更候補 (C)」を出さない (B / D に止める)。AI_REVIEW_SAFETY.md §6 と整合。

---

## 5. stats レポートの必須表示

stats が出力する Markdown / JSON のヘッダに必ず含める:

- `universe_snapshot_id`
- `universe_size_by_year` (e.g. `{2020: 425, 2021: 442, ...}`)
- `survivorship_policy` ∈ {"historical", "static_current_listing"}
- `survivorship_warning` (bool)
- `delisted_symbols_included_count`
- `index_membership_table_id` (使った場合)
- `liquidity_floor_excluded_count`

---

## 6. 不変条件 / pytest

- `test_universe_snapshot_consistency`:
  - signal 対象の symbol set ⊆ universe(bar_ts).members
  - 対象 PR: PR-S1 / PR-S2
- `test_delisted_symbol_inclusion`:
  - 上場廃止銘柄が delisting_date 以前は universe に含まれる
  - 対象 PR: PR-S5 (historical universe 採用後)
- `test_survivorship_policy_recorded`:
  - run_metadata に survivorship_policy が必ず存在
  - 対象 PR: PR-S3

---

## 7. 将来必要なデータ

- 上場廃止銘柄のヒストリカル価格 (廃止前最後の出来高・気配)
- 上場廃止理由 (再構成 / 経営破綻 / 上場廃止基準抵触 / 自主上場廃止)
- 指数入替履歴 (TOPIX / 日経225 / グロース250 / 業種指数)
- 市場区分変更履歴
- 株式交換 / 三角合併 / 株式併合等で symbol が変わるケースの系譜情報
- 親子上場の解消 (TOB 等) による fade out

---

## 8. 関連 docs

- UNIVERSE.md
- DATA_SOURCES.md (historical universe のソース要件)
- POINT_IN_TIME.md (bar_ts と universe membership の整合)
- BACKTEST_CONTRACT.md (上場廃止時の強制決済ルール)
- AI_REVIEW_SAFETY.md (survivorship 警告下の提案制限)
