# 大阪・神戸エリア 地価ダッシュボード

国土交通省「データプラットフォーム」の GraphQL API からデータをライブ取得し、
**大阪市を中心とした地価（公示地価・都道府県地価調査）と不動産取引価格の動向**を
可視化する Streamlit ダッシュボードです。神戸市にも対応し、設定追加で名古屋市など
他都市にも拡張できます。

## 機能

- 直近の動向 KPI（最新平均地価・前年比・CAGR・地点数）
- 年次推移ラインチャート（複数都市の比較）と前年比の棒グラフ
- 地点別の地価マップ（価格で色分け、ホバーで住所・価格・用途）
- データテーブルと CSV ダウンロード
- 過去複数年分を取得して直近トレンドを把握

## セットアップ

```bash
pip install -r requirements.txt
cp .env.example .env.local
# .env.local を編集し MLIT_API_KEY を設定
```

API キーは [MLIT データプラットフォーム](https://www.mlit-data.jp/) から取得します。

## データ探索（初回のみ推奨）

データセット ID やメタデータの項目名、取得可能な年はプラットフォーム側に依存するため、
初回は探索スクリプトで確認し、結果を `config.py` に反映すると精度が上がります。

```bash
python discover.py
```

出力された `dataset_id` を `config.DATASETS` に、メタデータの項目名を
`config.FIELD_MAP` に転記してください（未設定でもキーワード検索とヒューリスティック
抽出でフォールバック動作します）。サンプルは `data/sample/` に保存されます。

## 起動

```bash
streamlit run app.py
```

ブラウザでサイドバーから都市・テーマ・調査年の範囲・用途区分を選択します。

## 構成

```
app.py            Streamlit エントリ（UI・チャート・マップ）
config.py         リージョン / テーマ / データセットID / フィールド対応
discover.py       データ探索スクリプト（dataset_id・項目名・年の特定）
mlit/client.py    GraphQL クライアント（apikey ヘッダ・リトライ）
mlit/queries.py   GraphQL クエリビルダー
mlit/data.py      キャッシュ付きの高レベルデータ取得（DataFrame 返却）
```

## 他都市の追加（例: 名古屋市）

`config.py` の `REGIONS` に 1 エントリ追加するだけです（`prefecture_code`・
`city_name`・区コード・地図中心を設定）。`discover.py` で対象県のデータ充足を
確認してください。
