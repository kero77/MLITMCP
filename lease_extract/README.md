# lease_extract

賃貸借契約書（PDF）とレントロール（Excel）から項目を抽出し、JSON で保存するツールです。
ローカル LLM（Ollama）を使うので、書類の内容は外部に送信されません。

## 使い方

```bash
pip install -r lease_extract/requirements.txt
python -m lease_extract.make_samples            # 架空のダミー書類を生成
ollama pull gemma4:e2b                          # 例。精度が足りなければ大きいモデルへ
OLLAMA_MODEL=gemma4:e2b python -m lease_extract.extract lease_extract/samples/*.pdf lease_extract/samples/*.xlsx -o out/
```

- `OLLAMA_HOST_URL`（既定 `http://localhost:11434`）と `OLLAMA_MODEL` で接続先とモデルを変えます。
- 出力は Ollama の構造化出力（JSON Schema）で固定し、pydantic で検証。不正なら最大 2 回やり直します。
- 数値計算（利回り・DSCR 等）は LLM に任せず、抽出後にコードで計算してください。

## 制約

- テキスト層のある PDF のみ対応。スキャン PDF は OCR が必要です（読み取れない場合はエラーにします）。
- レントロールは 25 行ずつ見出し付きで分割して処理します。列の並びが特殊な表は精度が落ちます。
- 実データの前に、ダミー書類で使用モデルの抽出精度を確認してください。
- テスト（`pytest lease_extract/tests`）は LLM をスタブにしており、モデルの精度は検証しません。
