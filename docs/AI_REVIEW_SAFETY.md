# AI_REVIEW_SAFETY.md

AI Review (PR-S10) の安全策。AI Review は **売買判断ではなく、改善提案のみ**。ルール変更は人間承認制。

---

## 1. AI Review の役割

- trace-stats / attribution の出力を入力に取り、改善提案を生成する。
- 売買シグナルを直接出さない。
- 銘柄推奨を直接出さない (例 「9984 を買うべき」を出さない)。
- ルール変更を勝手に commit / PR しない。
- 出力は **提案であり、決定ではない**。

---

## 2. 出力カテゴリ (5 段階)

提案は必ずいずれかに分類される。

- **A. すぐ着手してよい実装改善候補**
  - 例: 「stats レポートのヘッダに universe_size_by_year を追加」
- **B. 検証を増やしてから判断すべき候補**
  - 例: 「sector × earnings_proximity の bucket で勝率差が見えるが標本数不足、N>=100 まで蓄積後に再評価」
- **C. ルール変更候補。ただし未承認**
  - 例: 「volume_spike & close_vs_sma200 > 0 の bar で hit_rate が高い傾向。ルール v2 候補だが要承認」
- **D. リスク・懸念点**
  - 例: 「PIT fundamentals が無いまま fundamental_ctx を入れると look-ahead bias が混入する」
- **E. 後回しでよいもの**
  - 例: 「intraday 拡張は MVP 段階では不要」

---

## 3. 禁止表現

以下を出力に含めてはならない。出力後に linter で検査し、ヒットすれば **rejection** (再生成 or 出力削除)。

- 「確定」
- 「これが原因」
- 「これで勝てる」
- 「この銘柄を買うべき」
- 「このルールに変更すべき」 (= 提案でなく命令調)
- 「絶対」
- 「保証」
- 「100%」
- 「sure thing」「guaranteed」「definitely will」「will profit」
- 銘柄名 (4桁コード / 銘柄シンボル) + 「買う / 売る / 推奨 / おすすめ」の連続パターン

容認される表現:
- 「原因候補」「説明力がありそうな条件」「追加検証すべき仮説」「現在の trace では説明不能」「必要な追加データ」「ルール変更候補。ただし未承認」

---

## 4. 出力 JSON Schema (draft)

AI Review の出力は JSON でしか書けない。自由文は `description` 内に閉じ込める。

```
{
  "schema_version": "kabu.ai_review.v1",
  "run_id": "<string>",
  "generated_at": "<datetime>",
  "input_stats_ref": "<path or hash of stats report used>",
  "proposals": [
    {
      "proposal_id": "<string, unique>",
      "category": "A" | "B" | "C" | "D" | "E",
      "title": "<short title>",
      "description": "<detailed description>",
      "evidence_stats_ref": ["<bucket key 1>", "<bucket key 2>"],
      "confidence": 0.0,
      "risks": ["<risk 1>", "<risk 2>"],
      "requires_human_approval": true,
      "depends_on": ["<other proposal_id>"]
    }
  ]
}
```

- `requires_human_approval` は常に `true`。AI が `false` を出してもバリデーションで `true` に強制上書き。
- `evidence_stats_ref` 空配列は禁止。stats からの引用なしの提案は弾く (cite-or-decline)。
- カテゴリ C の提案は `confidence < 0.5` でも出してよいが、`risks` を最低 1 つ書くこと。

---

## 5. cite-or-decline

- 全提案に `evidence_stats_ref` を必須化 (stats レポートの bucket key 等)。
- 引用が無い / 検証不可能な提案は出力しない (= decline)。
- 引用された bucket key は実際の stats レポートに存在することを post-validation で確認。

---

## 6. 入力制限

- AI Review に渡してよいのは **aggregated stats のみ**。
- 渡してはいけないもの:
  - 個別 trade レコード
  - 個別 trace レコード
  - 銘柄リスト (symbol の集合自体は OK だが「優先順位付き銘柄リスト」は出力させない目的で入力にも入れない)
  - PII / 個人情報
- universe_snapshot_id, survivorship_warning, pit_fundamentals_disabled 等のメタは渡す。
- AI が「特定銘柄が良い」と推論しないよう、stats から symbol 単独のランキングを直接見せないオプションも検討。

---

## 7. 銘柄名 + 動詞 の出力禁止

- 出力 linter で「`\b[0-9]{4}\b\s*(を|は)?\s*(買う|売る|推奨|おすすめ)`」のような正規表現にマッチしたら rejection。
- 海外株シンボル (例 AAPL) も同様に動詞との連続を禁止。
- 「特定銘柄を買え」を構造的に出せない方が安全。

---

## 8. 二段階チェック (generator → critic)

- generator agent: stats を読んで提案を生成。
- critic agent: 別呼び出しで「禁止表現」「cite-or-decline 違反」「過度な銘柄推奨」「カテゴリ判定の妥当性」を検査。
- critic がフラグを立てた提案は再生成または削除。
- critic 自身も同じ禁止表現を出してはならない。

---

## 9. survivorship 警告下の制限

`run_metadata.survivorship_warning == true` の場合:

- カテゴリ C (ルール変更候補) を **出さない**。B / D / E のみに制限。
- 出力ヘッダに「結果は survivorship-biased である可能性が高い。ルール変更候補は historical universe 採用後に再生成する」を含める。

---

## 10. PIT fundamentals 警告下の制限

`run_metadata.warnings` に `"pit_fundamentals_disabled"` が含まれる場合:

- fundamental_ctx を根拠にした提案を出さない (出ても critic が rejection)。
- 該当する bucket key (e.g. PER bucket × outcome) は AI Review の入力から除外。

---

## 11. トークン上限 / 時間上限

- input tokens: 上限を設定 (例 50k)。超える場合は事前に stats を要約する pre-processor を通す。
- output tokens: 上限 (例 8k)。超えたら truncate ではなく rejection。
- wall time: 例 60 秒。超えたら abort。
- これらは run_metadata に保存。

---

## 12. 出力先 / 監査

- AI Review の出力は `runs/ai_review/<run_id>/proposals.json` に保存。
- backtest の `runs/<run_id>/` とは分離する (誤って混ざらないため)。
- 過去の提案は immutable。承認 / 却下の履歴を別ファイルで管理 (例 `runs/ai_review/<run_id>/decisions.json`)。

---

## 13. 不変条件 / pytest 候補

- `test_ai_review_output_schema`: 出力が JSON Schema に準拠
- `test_ai_review_no_forbidden_words`: 禁止表現が含まれない
- `test_ai_review_cite_or_decline`: evidence_stats_ref が空でない
- `test_ai_review_requires_human_approval_true`: requires_human_approval が常に true
- `test_ai_review_no_symbol_action`: 銘柄名 + 動詞のパターンを検出しない
- `test_ai_review_no_category_c_under_survivorship_warning`: survivorship 警告下で C が出ない

---

## 14. 関連 docs

- POINT_IN_TIME.md (PIT 警告の連動)
- SURVIVORSHIP.md (survivorship 警告の連動)
- SCHEMA.md (proposal の入力となる stats のスキーマ前提)
- ROADMAP.md (PR-S10 で実装)
