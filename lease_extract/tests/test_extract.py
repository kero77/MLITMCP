"""LLM をスタブにして、読み取り・チャンク分割・スキーマ検証・リトライの流れを確認する。"""
import json
from pathlib import Path

import pytest

from lease_extract.extract import extract_contract, extract_rent_roll
from lease_extract.llm import extract
from lease_extract.make_samples import make_contract_pdf, make_rent_roll_xlsx
from lease_extract.readers import chunk_rent_roll, read_excel_rows, read_pdf
from lease_extract.schemas import LeaseContract


@pytest.fixture()
def samples(tmp_path: Path):
    pdf, xlsx = tmp_path / "c.pdf", tmp_path / "r.xlsx"
    make_contract_pdf(pdf)
    make_rent_roll_xlsx(xlsx)
    return pdf, xlsx


def test_read_pdf_contains_key_fields(samples):
    text = read_pdf(samples[0])
    assert "98,000円" in text and "サンプルレジデンス梅田" in text


def test_excel_formula_values_and_empty_rows(samples):
    (_, rows), = list(read_excel_rows(samples[1]))
    assert rows[2][0] == "号室"
    assert rows[-1][0] == "合計"  # 数式は未計算(None)でも落ちない


def test_chunks_repeat_header(samples):
    (_, rows), = list(read_excel_rows(samples[1]))
    chunks = list(chunk_rent_roll(rows, size=2))
    assert len(chunks) == 3
    assert all("号室" in c for c in chunks)


def test_extract_contract_with_stub_llm(samples):
    seen = {}

    def llm(system, user, schema):
        seen["user"] = user
        return json.dumps({"monthly_rent": 98000, "lessee": "山田 太郎"})

    r = extract_contract(samples[0], llm)
    assert r.monthly_rent == 98000 and r.deposit is None
    assert "令和6年4月1日" in seen["user"]


def test_rent_roll_aggregates_chunks(samples):
    calls = []

    def llm(system, user, schema):
        calls.append(user)
        return json.dumps({"rows": [{"room_number": "x", "monthly_rent": 1}]})

    rows = extract_rent_roll(samples[1], llm)
    assert len(rows) == len(calls) == 1  # 5 データ行 → 1 チャンク


def test_retry_then_fail():
    n = {"c": 0}

    def bad(system, user, schema):
        n["c"] += 1
        return "not json"

    with pytest.raises(ValueError):
        extract(LeaseContract, "s", "u", bad, retries=2)
    assert n["c"] == 3


def test_retry_recovers():
    outs = iter(["oops", '{"monthly_rent": 5}'])
    assert extract(LeaseContract, "s", "u", lambda *a: next(outs)).monthly_rent == 5


def test_schema_is_in_prompt_not_only_in_format():
    seen = {}

    def llm(system, user, schema):
        seen["system"] = system
        return "{}"

    extract(LeaseContract, "s", "u", llm)
    assert "monthly_rent" in seen["system"] and "月額賃料" in seen["system"]
