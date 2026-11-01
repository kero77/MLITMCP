"""PDF / Excel を LLM に渡せるテキストへ変換する。"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import openpyxl
import pdfplumber


def read_pdf(path: Path) -> str:
    """テキスト層のある PDF から本文を取り出す。スキャン PDF は別途 OCR が必要。"""
    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            parts.append(f"--- page {i} ---\n{page.extract_text() or ''}")
    text = "\n".join(parts)
    if len(text.replace("-", "").strip()) < 20:
        raise ValueError(f"{path.name}: テキストを取得できません（スキャン PDF の可能性。OCR が必要）")
    return text


def _cell(v) -> str:
    if v is None:
        return ""
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    return str(v).replace("\n", " ").replace("|", "/").strip()


def read_excel_rows(path: Path) -> Iterator[tuple[str, list[list[str]]]]:
    """(シート名, 空行を除いた行リスト) を返す。数式は計算済みの値を読む。"""
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    for ws in wb.worksheets:
        rows = [[_cell(c) for c in r] for r in ws.iter_rows(values_only=True)]
        rows = [r for r in rows if any(r)]
        if rows:
            yield ws.title, rows


def rows_to_markdown(rows: list[list[str]]) -> str:
    width = max(len(r) for r in rows)
    return "\n".join("| " + " | ".join(r + [""] * (width - len(r))) + " |" for r in rows)


def chunk_rent_roll(rows: list[list[str]], size: int = 25, header_rows: int = 3) -> Iterator[str]:
    """先頭の見出し行を毎回付けて、size 行ずつ Markdown 化する（長い表を安全に処理するため）。"""
    head, body = rows[:header_rows], rows[header_rows:]
    for i in range(0, len(body), size):
        yield rows_to_markdown(head + body[i : i + size])
