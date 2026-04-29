# Kabu

Stock analysis research and backtest platform.

## Status

- Phase: P0.9 (docs先行 + repo最小初期化のみ)
- 実装はまだ存在しない
- 売買ルールは未確定
- 証券会社API接続 / live発注 / 自動売買 / 銘柄推奨は行わない

## 目的

- 株式投資で利益最大化を目指すための検証基盤
- 損失を減らす / 大損を避ける / PFを改善する / 最大DDを下げる
- 勝ちやすい条件 / 負けやすい条件 / 大勝ち条件 / 大負け条件を観測する
- 判断基準を改善する
- 将来的に AI 分析・半自動化・自動化の土台にする

ただし、現時点ではデータ取得・backtest・decision_trace・trace-stats・規則性候補の発見・改善提案・bias 対策までを目的にする。

## 立ち位置

- 別 repo `youiti0925/test` (FX 検証アプリ) は参考元
- FX 側のコードを無差別にコピーしない
- FX 固有の概念 (DXY / OANDA / pip / event_high / spread_abnormal / FX session / BUY/SELL対称) は持ち込まない
- 詳細は `docs/ANTI_FX_LEAK.md`

## ディレクトリ

```
.
├── README.md
├── pyproject.toml
├── .gitignore
├── docs/                  # 設計・方針・契約 (本フェーズの主成果物)
├── src/
│   └── kabu/              # 実装パッケージ (現状は __init__.py のみ)
├── tests/                 # pytest (現状は __init__.py のみ)
└── data/
    └── .gitkeep           # data/raw, data/cache は .gitignore 済み
```

`runs/` と `libs/` は実行時に生成される。コミットは禁止。

## ドキュメント

| ドキュメント | 内容 |
|---|---|
| `docs/ROADMAP.md` | PR ロードマップと pytest 不変条件候補 |
| `docs/DATA_SOURCES.md` | データソース比較と as_of / PIT 方針 |
| `docs/UNIVERSE.md` | ユニバースと historical universe / survivorship |
| `docs/CALENDAR.md` | 営業日 / 寄付・大引け / bar_ts 定義 |
| `docs/SCHEMA.md` | `kabu.trace.v1` スキーマと運用ポリシー |
| `docs/POINT_IN_TIME.md` | look-ahead bias 対策と不変条件 |
| `docs/SURVIVORSHIP.md` | survivorship bias 対策 |
| `docs/BACKTEST_CONTRACT.md` | 約定タイミング・コスト・調整方針 |
| `docs/AI_REVIEW_SAFETY.md` | AI Review の安全策 |
| `docs/ANTI_FX_LEAK.md` | FX repo からの混入防止と移植判断表 |
| `docs/RISKS.md` | 既知の bias と限界 |
| `docs/TRACE_ANALYSIS_WORKFLOW.md` | trace 分析ワークフロー |

## 禁止事項 (明示承認まで)

- 売買ルール確定
- 自動売買 / live 発注 / 証券会社 API 接続
- 銘柄推奨の断定
- 「この銘柄を買うべき」「これが原因」「確定」等の表現
- FX repo からの無差別コピー
- `runs/` `libs/` `data/raw/` `data/cache/` のコミット

## 開発

```sh
pip install -e .[dev]
pytest
```

実装はまだ無いので pytest は collect 0 / pass 0 で完了する想定。
