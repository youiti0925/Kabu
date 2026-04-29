# UNIVERSE.md

ユニバース (検証対象銘柄集合) の定義と historical universe の運用方針。survivorship bias の主要対策はここで決める。

---

## 0. MVP 決定 (PR-S0.5 / N2 で確定)

本セクションは「決定」であり、後続 PR は本決定に従う。変更には別途承認が必要。

- D-1. 初期ユニバースは **MVP-1: 自由銘柄リスト** とする (ユーザが明示した数十銘柄)。
- D-2. MVP-2 候補 (日経225 / TOPIX500 / グロース主要銘柄) は historical membership ソース確定までは MVP に入れない。
- D-3. ETF / REIT / ADR / 種類株は MVP では除外。`instrument_type ∈ {"common_stock"}` でフィルタ。
- D-4. historical universe が無い場合、`run_metadata.survivorship_policy = "static_current_listing"` を **必ず保存** し、`run_metadata.survivorship_warning = true` を **必ず保存** する。
- D-5. stats レポート / AI Review の冒頭に **survivorship warning を必ず表示** する。
- D-6. AI Review は survivorship-biased 状態 (D-4 該当) では **Cカテゴリ (ルール変更候補) を出さない**。AI_REVIEW_SAFETY.md §9 と整合。
- D-7. `run_metadata.universe_snapshot_id` を必須化 (SCHEMA.md と整合)。
- D-8. 初期 universe の格納先は `data/universe/` (将来)。MVP では実 CSV はコミットしない。サンプル雛形だけ docs に書き、実データ投入は後続 PR でユーザ承認後。

D-1 / D-3 は MVP-1 開発時の前提。historical universe 採用後は D-4 / D-5 を `survivorship_policy = "historical"` に切り替え可能。

---

## 1. ユニバースとは

- 「いつ、どの銘柄を検証対象に含めるか」の集合。
- ユニバースは bar_ts に依存する。`universe(bar_ts)` で時点ごとに membership が変わる。
- 静的な「現在の上場銘柄リスト」を過去検証に流用するのは survivorship bias の典型的な原因。SURVIVORSHIP.md 参照。

---

## 2. 初期ユニバース候補と MVP 決定

| 名前 | 規模 | MVP 採用 | 備考 |
|---|---|---|---|
| **自由銘柄リスト (ユーザ指定)** | 任意 | **MVP-1 採用 (決定)** | §0 D-1。数十銘柄から始める。CSV はコミットしない (D-8) |
| 日経225 | 大型中心 | MVP-2 候補 | historical membership ソース採用後 |
| TOPIX500 | 中大型 | MVP-2 候補 | historical membership ソース採用後 |
| グロース市場 (グロース250 含む) | 小型中心 | MVP-2 候補 | 流動性が極端に低い銘柄を含むため liquidity_floor が必要 |
| 全上場銘柄 | 約 4000 | MVP 除外 | データ量・survivorship 管理コスト大 |
| 米株 (S&P500 等) | 大型中心 | MVP 除外 (D-1 / DATA_SOURCES.md) | 通貨換算 / 営業日が別 |
| ETF / REIT / ADR | 別カテゴリ | MVP 除外 (D-3) | 配当 / 分配 / 調整方法が異なる |

### 2-1. MVP-1 自由銘柄リストのスキーマ (サンプル)

実 CSV は `data/universe/manual_symbols.csv` を想定。`data/raw/` 配下ではなく、`data/universe/` 配下に置く想定 (PR-S1 着手時に確定)。docs にはサンプル雛形のみ。実データはコミットしない。

```
# data/universe/manual_symbols.example.csv (雛形 / 実データではない)
symbol,name,market,sector,effective_from,effective_to
7203,トヨタ自動車,TSE_PRIME,輸送用機器,2010-01-01,
6758,ソニーグループ,TSE_PRIME,電気機器,2010-01-01,
9984,ソフトバンクグループ,TSE_PRIME,情報通信,2010-01-01,
```

- ヘッダ: `symbol, name, market, sector, effective_from, effective_to`
- `effective_to` が空 = 現時点で active。
- 上場廃止 / 市場区分変更時は新しい行を追加し、旧行の `effective_to` を埋める。
- 文字コードは UTF-8。
- このスキーマは MVP-1 の最小契約。lot_size / tick_size_table_id / listing_date / delisting_date は §4 のフルスキーマで保持。

MVP-2 (日経225 / TOPIX500 / グロース) は historical membership が確保されるまで PR を開かない。

---

## 3. historical universe の必要性

過去の bar に対するシグナルは、その時点で実際に上場していた銘柄だけを対象にする必要がある。

- 上場廃止された銘柄も、廃止日までは「universe@bar_ts」に含める。
- 新規上場銘柄は、上場日以前は universe に含まれない。
- 指数構成は時点で変わる。TOPIX 入替・日経225 入替は historical membership で管理。
- これがないと「現在も生き残っている銘柄だけを集計する」survivorship-biased な結果になる。

無料データソースでは historical membership が手薄なため、MVP では制約を docs に明記したうえで暫定運用する (§6 参照)。

---

## 4. ユニバーススナップショット仕様

実装契約 (PR-S0.7 で確定):

```
universe_snapshot:
  universe_snapshot_id: str   # 一意なID。例 "topix500_2024-12-30"
  as_of: datetime             # スナップショットの基準時刻
  source: str                 # "jquants" / "manual" 等
  members:
    - symbol: str             # 銘柄コード (4桁 + 市場区分なし、または ISIN 等)
      effective_from: date    # この銘柄が universe に含まれ始めた日
      effective_to: date|null # 除外された日 (上場廃止 / 入替 / 上場市場変更)
      market: str             # "TSE_PRIME" / "TSE_STANDARD" / "TSE_GROWTH"
      sector: str             # 業種 (33業種コード等)
      listing_date: date
      delisting_date: date|null
      lot_size: int           # 売買単位 (通常 100)
      tick_size_table_id: str # tick_size の参照テーブル ID
```

- bar_ts に対する membership 判定は `effective_from <= bar_ts.date() AND (effective_to is null OR bar_ts.date() < effective_to)` を満たすメンバーに限る。
- universe_snapshot は immutable。上書き禁止。新しい時点のスナップショットは別 ID で追加。

---

## 5. シグナル / backtest との接続

- backtest_engine は `Backtest(universe_snapshot, calendar, ...)` を受け取り、各 bar で `universe(bar_ts)` を必ず呼ぶ。
- decision_trace は `universe_snapshot_id` を `run_metadata` に保存する。
- stats レポートは「universe_snapshot_id」「universe size by year」「上場廃止銘柄が含まれているか」を必ずヘッダに出す。

---

## 6. MVP で historical universe が無い場合の方針 (決定)

§0 D-4 / D-5 / D-6 を実装契約として展開する。

- 暫定で「現在の上場銘柄リスト」をユニバースとして使うことを **許容するが、警告必須** とする。
- run_metadata に以下を **必ず** 保存 (D-4):
  - `survivorship_policy: "static_current_listing"` (= 現在の上場銘柄のみ。survivorship-biased)
  - `survivorship_warning: true`
- stats レポート / AI Review の冒頭に「結果は survivorship-biased である」旨を **必ず** 表示する (D-5)。
- AI Review は本状態下で **Cカテゴリ (ルール変更候補) を出さない** (D-6)。AI_REVIEW_SAFETY.md §9 と整合。
- 上記は MVP 限定の妥協。historical universe を提供するソースを採用したら直ちに切替 (`survivorship_policy = "historical"`、`survivorship_warning = false`)。
- pytest 候補: `test_survivorship_policy_recorded` (PR-S3) で run_metadata に `survivorship_policy` キーが必ず存在することを検証。

---

## 7. ETF / REIT / ADR / 種類株の扱い

- MVP では除外。
- 除外ロジックは銘柄メタの `instrument_type ∈ {"common_stock"}` でフィルタ。
- 将来採用する場合は配当 / 分配 / 調整係数の取り扱いを別仕様にする。

---

## 8. stats に必ず出す情報

- universe_snapshot_id
- universe size (by year / quarter)
- survivorship_policy
- survivorship_warning
- 上場廃止銘柄の含有数
- 指数入替の含有数 (将来)
- liquidity_floor によって除外された銘柄数

---

## 9. 将来必要なデータ

- TOPIX 入替履歴
- 日経225 入替履歴
- 上場廃止銘柄リスト (廃止日 / 理由)
- 市場区分変更履歴 (旧東証一部 → プライム等)
- 株式分割 / 併合 / 株式交換履歴
- 親子上場の同一性 (合併・分割で symbol が変わる場合の系譜)

---

## 10. チェックリスト

### 10-1. 決定済 (N2 / PR-S0.5 で確定)

- [x] 初期ユニバースは MVP-1 = 自由銘柄リスト (D-1)
- [x] MVP で「static_current_listing」を許容する (D-4)
- [x] AI Review は survivorship-biased 状態で C 提案を出さない (D-6)
- [x] ETF / REIT / ADR / 種類株は MVP 除外 (D-3)
- [x] universe_snapshot_id は run_metadata 必須 (D-7)
- [x] MVP では実 CSV をコミットしない。サンプル雛形のみ docs に記載 (D-8)

### 10-2. 未確定 (PR-S1 着手前にユーザ承認が必要)

- [ ] historical universe ソース (J-Quants / 有償 / 自社蓄積) — MVP-2 着手前
- [ ] 銘柄コードのキー形式 (4桁 / 4桁+市場区分 / ISIN) — PR-S1 着手前に決定
- [ ] universe スナップショットの格納先 (`data/universe/` 想定だが本確定は PR-S1 で)
- [ ] MVP-1 の初期銘柄リスト (実データ投入は別 PR でユーザ承認)
