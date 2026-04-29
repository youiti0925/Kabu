# UNIVERSE.md

ユニバース (検証対象銘柄集合) の定義と historical universe の運用方針。survivorship bias の主要対策はここで決める。

---

## 1. ユニバースとは

- 「いつ、どの銘柄を検証対象に含めるか」の集合。
- ユニバースは bar_ts に依存する。`universe(bar_ts)` で時点ごとに membership が変わる。
- 静的な「現在の上場銘柄リスト」を過去検証に流用するのは survivorship bias の典型的な原因。SURVIVORSHIP.md 参照。

---

## 2. 初期ユニバース候補

| 名前 | 規模 | 採用候補 | 備考 |
|---|---|---|---|
| 日経225 | 大型中心 | yes (有力候補) | historical membership が比較的取れる |
| TOPIX500 | 中大型 | yes | グロース・バリュー両方を含む |
| グロース市場 (グロース250 含む) | 小型中心 | 検討 | 流動性が極端に低い銘柄を含むため liquidity_floor が必要 |
| 全上場銘柄 | 約 4000 | MVP では除外 | データ量・survivorship 管理コスト大 |
| 自由銘柄リスト (ユーザ指定) | 任意 | yes (デバッグ用) | 例: 数十銘柄から始める |
| 米株 (S&P500 等) | 大型中心 | MVP では除外 | 通貨換算 / 営業日が別 |
| ETF / REIT / ADR | 別カテゴリ | MVP では除外 | 配当 / 分配 / 調整方法が異なる |

MVP の推奨は「自由銘柄リスト (数十銘柄)」または「日経225」のどちらか。確定は要承認。

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

## 6. MVP で historical universe が無い場合の方針

- 暫定で「現在の上場銘柄リスト」をユニバースとして使うことを **許容するが、警告必須** とする。
- run_metadata に以下を保存:
  - `survivorship_policy: "static_current_listing"` (= 現在の上場銘柄のみ。survivorship-biased)
  - `survivorship_warning: true`
- stats レポート / AI Review の冒頭に「結果は survivorship-biased である」旨を必ず表示する。
- 上記は MVP 限定の妥協。PR-S0.5 で historical universe を提供するソースを採用したら直ちに切替。

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

## 10. 要決定チェックリスト

- [ ] 初期ユニバース (日経225 / TOPIX500 / 自由リスト)
- [ ] historical universe ソース (J-Quants / 有償 / 自社蓄積)
- [ ] MVP で「static_current_listing」を許容するか
- [ ] ETF / REIT / ADR / 種類株の MVP 除外ルール
- [ ] 銘柄コードのキー形式 (4桁 / 5桁 / 市場区分付き / ISIN)
- [ ] universe_snapshot のストレージ先 (data/raw/ 配下)
