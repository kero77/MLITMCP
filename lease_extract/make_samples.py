"""架空のダミー書類（賃貸借契約書 PDF とレントロール Excel）を生成する。実在の情報は含まない。"""
from __future__ import annotations

from pathlib import Path

import openpyxl
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

CONTRACT_LINES = [
    "建物賃貸借契約書",
    "",
    "賃貸人（貸主）: 株式会社サンプル不動産",
    "賃借人（借主）: 山田 太郎",
    "物件名: サンプルレジデンス梅田",
    "所在地: 大阪市北区サンプル町1-2-3",
    "部屋番号: 305号室",
    "使用目的: 居住用",
    "契約期間: 令和6年4月1日 から 令和8年3月31日 まで（2年間）",
    "賃料: 月額 98,000円",
    "共益費: 月額 5,000円",
    "敷金: 196,000円",
    "礼金: 98,000円",
    "更新: 更新料は新賃料の1か月分とする。",
    "特約: ペット飼育不可。楽器演奏禁止。",
]


def make_contract_pdf(path: Path) -> None:
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setFont("HeiseiKakuGo-W5", 12)
    y = 800
    for line in CONTRACT_LINES:
        c.drawString(50, y, line)
        y -= 24
    c.save()


def make_rent_roll_xlsx(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "レントロール"
    ws.append(["サンプルレジデンス梅田 レントロール"])
    ws.append(["2025年10月1日現在"])
    ws.append(["号室", "入居者", "面積(㎡)", "賃料", "共益費", "敷金", "契約開始", "契約終了"])
    ws.append(["101", "佐藤 花子", 25.5, 78000, 4000, 156000, "2023-04-01", "2025-03-31"])
    ws.append(["102", "", 25.5, 0, 0, 0, "", ""])  # 空室
    ws.append(["201", "鈴木 一郎", 30.2, 92000, 5000, 184000, "2024-07-01", "2026-06-30"])
    ws.append(["305", "山田 太郎", 38.0, 98000, 5000, 196000, "2024-04-01", "2026-03-31"])
    ws.append(["合計", "", "=SUM(C4:C7)", "=SUM(D4:D7)", "=SUM(E4:E7)", "", "", ""])
    wb.save(path)


if __name__ == "__main__":
    out = Path(__file__).parent / "samples"
    out.mkdir(exist_ok=True)
    make_contract_pdf(out / "contract_dummy.pdf")
    make_rent_roll_xlsx(out / "rentroll_dummy.xlsx")
    print(f"written to {out}")
