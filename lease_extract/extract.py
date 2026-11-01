"""賃貸契約書(PDF)とレントロール(Excel)から項目を抽出する CLI。

  python -m lease_extract.extract contract.pdf rentroll.xlsx -o out/
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .llm import LLMFn, extract, ollama_chat
from .readers import chunk_rent_roll, read_excel_rows, read_pdf
from .schemas import LeaseContract, RentRollChunk, RentRollRow

SYSTEM = (
    "あなたは不動産書類の項目抽出器です。与えられた文書に書かれている内容だけを使い、"
    "指定された JSON スキーマで出力します。文書に無い項目は推測せず null にします。"
    "金額は円単位の整数（カンマや「円」は除く）、日付は YYYY-MM-DD にします。"
    "和暦は西暦に直します（令和N年=2018+N年）。"
)


def extract_contract(pdf: Path, llm: LLMFn = ollama_chat) -> LeaseContract:
    text = read_pdf(pdf)
    return extract(LeaseContract, SYSTEM, f"次の賃貸借契約書から項目を抽出してください。\n\n{text}", llm)


def extract_rent_roll(xlsx: Path, llm: LLMFn = ollama_chat) -> list[RentRollRow]:
    out: list[RentRollRow] = []
    for sheet, rows in read_excel_rows(xlsx):
        for table in chunk_rent_roll(rows):
            user = (
                f"次のレントロール（シート: {sheet}）の各データ行を 1 行ずつ rows に抽出してください。"
                "見出し行・合計行・小計行は含めません。\n\n" + table
            )
            out += extract(RentRollChunk, SYSTEM, user, llm).rows
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path, help=".pdf は契約書、.xlsx はレントロールとして処理")
    ap.add_argument("-o", "--out", type=Path, default=Path("out"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for f in args.files:
        if f.suffix.lower() == ".pdf":
            data = extract_contract(f).model_dump()
        elif f.suffix.lower() in (".xlsx", ".xlsm"):
            data = [r.model_dump() for r in extract_rent_roll(f)]
        else:
            print(f"skip: {f}")
            continue
        dest = args.out / f"{f.stem}.json"
        dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{f.name} -> {dest}")


if __name__ == "__main__":
    main()
