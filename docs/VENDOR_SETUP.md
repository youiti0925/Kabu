# VENDOR_SETUP.md

P4.7 で導入した参考 vendor (yfinance) の利用準備手順と運用方針。

---

## 0. 重要な前提

- vendor 実装は **Source Protocol の裏側に閉じる** (DATA_SOURCES.md §0 D-3)。
- アプリ全体から直接 `yfinance` を import しない。`src/kabu/data/sources/yfinance_source.py` のみが許可される。`tests/invariants/test_vendor_layer_isolation.py` で構造的に強制。
- vendor SDK は **lazy import** する (関数の中で import)。CI には依存を入れず、デフォルトインストールには vendor 依存を含めない。
- **実データはコミットしない**。`data/raw/`, `data/cache/`, `runs/`, `libs/` は .gitignore + CI guard 二重防御。
- **APIキー / 認証情報を repo に入れない**。`.env` は .gitignore 済み (J-Quants 等の有料 vendor を将来追加する場合)。

---

## 1. P4.7 で採用した vendor: **yfinance** (案 A)

### 1-1. 採用理由

- ユーザー側の追加アクション (API 認証など) なしで動く
- mock 化が容易で CI を外部ネットワーク非依存に保てる
- OHLCV 限定の用途 (PR-S4.7 brief: 「Source Protocol が現実に耐えるか確認」) に十分
- ライセンス上、初期検証 (個人ローカル) であれば許容

### 1-2. 採用範囲

- **OHLCV のみ** (Open / High / Low / Close / Adj Close / Volume)
- 1d 日足
- 日本株 (`<銘柄コード>.T` 形式) と米国指数 (`^GSPC`, `^IXIC`, `^VIX` 等) の両方を取得可能 (実取得はローカル / 手動)

### 1-3. **採用しない範囲** (DATA_SOURCES.md §0 D-6 / D-7 に従う)

- fundamentals (PER / PBR / ROE / EPS / 配当 / コンセンサス)
- earnings 発表日時 (release_ts)
- ニュース / sentiment

これらは PIT 保証がないため、yfinance では扱わない。PR-S8 (fundamentals) は依然 PIT 確保まで未着手。

---

## 2. インストール

### 2-1. デフォルト (CI / 開発者)

```bash
pip install -e ".[dev]"
```

これは yfinance を含まない。pytest はすべて mock 化された `history_fn` を使うため yfinance なしで通る。

### 2-2. vendor 実呼び出しを試したい場合 (手動 / ローカルのみ)

```bash
pip install -e ".[dev,vendor-yfinance]"
```

これは optional extra `vendor-yfinance` を経由して `yfinance>=0.2` を入れる。CI ではこの extra をインストールしない。

---

## 3. 使い方

### 3-1. ユニットテスト (CI / 通常開発)

```python
from kabu.data.sources import YFinanceSource

def fake_history_fn(symbol, start, end):
    return [
        {"date": date(2024, 4, 1), "open": 1000, "high": 1010, ..., "volume": 1_000_000},
        ...
    ]

src = YFinanceSource(history_fn=fake_history_fn)
bars = src.get_ohlcv("7203.T", start, end, as_of=as_of)
```

`history_fn` を渡せば yfinance は **絶対に** import されない (`tests/data/sources/test_yfinance_source.py::test_no_real_yfinance_imported` で検証)。

### 3-2. 実データ取得 (手動 / ローカルのみ)

```python
from kabu.data.sources import YFinanceSource

src = YFinanceSource()  # history_fn=None -> lazy import yfinance
bars = src.get_ohlcv("7203.T", start, end, as_of=as_of)
```

このとき `_default_yfinance_history` 内で `import yfinance` が遅延発火する。yfinance がインストールされていないと `ImportError`。

実取得結果を repo にコミットしない。`data/cache/` 配下に parquet などで保存する場合は CI guard が tracked status を検出してテスト fail。

---

## 4. 既知の制約

- **PIT 保証なし**: yfinance は最新値を返すソース。過去の調整係数 / 価格は事後修正される。MVP の OHLCV であれば問題が比較的小さいが、fundamentals / earnings には絶対に使わない (DATA_SOURCES.md §0 D-6)。
- **API 規約変動**: yfinance は非公式ラッパで、Yahoo Finance 側の API 変更で動作が変わる。商用検討時は J-Quants または有償ベンダに切り替え (DATA_SOURCES.md §10-2)。
- **半日立会・特別休業**: yfinance は半日立会日も通常日と同じ 15:00 close を返す可能性あり。MVP では `bar_close_hour=15`, `bar_close_minute=0`, `fill_lag_minutes=30` 固定。半日立会対応は将来 PR で。
- **指数構成銘柄 (membership)**: yfinance は historical universe を提供しない。survivorship bias 対策は universe_snapshot 側で吸収する設計 (UNIVERSE.md §0 D-4 / D-5)。

---

## 5. 別 vendor を追加する場合の手順

新しい vendor (例: J-Quants, Stooq) を追加する場合は以下の手順を踏むこと。

1. `src/kabu/data/sources/<vendor>_source.py` を新規作成
2. lazy import を厳守 (top-level import は禁止)
3. `tests/invariants/test_vendor_layer_isolation.py` の `_FORBIDDEN_VENDOR_TOKENS` に `"<vendor>"` を追加
4. `pyproject.toml` の `[project.optional-dependencies]` に `vendor-<vendor>` extra を追加
5. CI には vendor extra をインストールしない
6. `tests/data/sources/test_<vendor>_source.py` を mock injection で記述
7. 認証情報が必要な場合 (J-Quants 等):
   - `.env` での運用方針を docs に追記
   - `.env` は .gitignore 済 (P0.9 で固定)
   - 認証情報なしのときの fail を明示
8. DATA_SOURCES.md に PIT / 商用利用 / 認証要件を更新

---

## 6. CI ガード

- **CI は yfinance をインストールしない**。`pyproject.toml` の dev extra のみインストール。
- pytest が yfinance を import したら `test_no_real_yfinance_imported` が fail する。
- 構造ガード `test_vendor_layer_isolation` で `import yfinance` が `src/kabu/data/sources/` 外に漏れていないことを検証。
- `test_yfinance_module_imports_lazily` で yfinance_source.py の top-level import を禁止。
- `test_no_raw_data_committed` で実データのコミットを検出。

---

## 7. 関連 docs

- DATA_SOURCES.md: vendor 比較と PIT 方針
- BACKTEST_CONTRACT.md §6-A: run output layout (`data/cache/` 等を読む)
- POINT_IN_TIME.md §3 / §5: as_of 必須契約
- RISKS.md §3-1 / §5-3: vendor 規約変動 / コミット事故対策
- ROADMAP.md
