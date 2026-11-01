"""Ollama の /api/chat を呼ぶ最小クライアント。JSON Schema で出力形式を固定する。"""
from __future__ import annotations

import json
import os
import sys
from typing import Callable, TypeVar

import requests
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

# テストでは (system, user, schema) -> JSON 文字列 の関数に差し替える
LLMFn = Callable[[str, str, dict], str]

OLLAMA_HOST = os.environ.get("OLLAMA_HOST_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e2b")
# OLLAMA_THINK=false で思考出力を切る（true で有効）。未設定ならモデルの既定に任せる
_THINK = os.environ.get("OLLAMA_THINK", "").strip().lower()


def ollama_chat(system: str, user: str, schema: dict) -> str:
    # クラウドモデルを使う場合のみ OLLAMA_API_KEY を環境変数で渡す（コードには書かない）
    headers = {}
    if os.environ.get("OLLAMA_API_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['OLLAMA_API_KEY']}"
    body = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "format": schema,
        "options": {"temperature": 0, "num_ctx": 8192},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if _THINK in ("true", "false"):
        body["think"] = _THINK == "true"
    r = requests.post(f"{OLLAMA_HOST}/api/chat", headers=headers, json=body, timeout=600)
    r.raise_for_status()
    return r.json()["message"]["content"]


UNKNOWN_NUM = -1  # 数値項目で「記載なし」を表す値（負の値は正規の値にならない）


def strict_schema(model: type[BaseModel]) -> dict:
    """null 不可・全項目必須のスキーマを作る。
    Optional（anyOf + null）だと小型モデルが null を選びすぎるため、
    記載なしは "" / -1 で返させ、受け取ったあとに None へ戻す。"""

    def fix(node):
        if isinstance(node, dict):
            if "anyOf" in node:
                branches = [b for b in node["anyOf"] if b.get("type") != "null"]
                if len(branches) == 1:
                    keep = {k: v for k, v in node.items() if k not in ("anyOf", "default")}
                    return fix({**keep, **branches[0]})
            out = {k: fix(v) for k, v in node.items() if k != "default"}
            if out.get("type") == "object" and "properties" in out:
                out["required"] = list(out["properties"])
                out["additionalProperties"] = False
            return out
        if isinstance(node, list):
            return [fix(v) for v in node]
        return node

    return fix(model.model_json_schema())


def _normalize(v):
    """"" と -1 を None に戻す。"""
    if isinstance(v, dict):
        return {k: _normalize(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_normalize(x) for x in v]
    if v == "" or (isinstance(v, (int, float)) and not isinstance(v, bool) and v == UNKNOWN_NUM):
        return None
    return v


def schema_prompt(schema: dict) -> str:
    """format はデコードを制約するだけで、モデルにはスキーマが見えない。
    キー名と説明をプロンプトにも渡して、出力を裏付ける（Ollama 公式の推奨）。"""
    return (
        "\n\n出力は次の JSON Schema に厳密に従う JSON オブジェクト 1 つだけにしてください。"
        "キー名はスキーマの名前をそのまま使い、別名（rent など）や説明文は付けないでください。"
        "全てのキーを必ず出力し、文書に記載が無い項目だけ、文字列は \"\"、数値は -1 にしてください。\n"
        + json.dumps(schema, ensure_ascii=False)
    )


def extract(model: type[T], system: str, user: str, llm: LLMFn = ollama_chat, retries: int = 2) -> T:
    """スキーマに合う JSON が返るまで数回やり直す。"""
    schema = strict_schema(model)
    system = system + schema_prompt(schema)
    last: Exception | None = None
    for _ in range(retries + 1):
        raw = llm(system, user, schema)
        if os.environ.get("LEASE_DEBUG"):
            print(f"[LEASE_DEBUG] raw model output:\n{raw}\n", file=sys.stderr)
        try:
            return model.model_validate(_normalize(json.loads(raw)))
        except Exception as e:  # noqa: BLE001
            last = e
    raise ValueError(f"スキーマに合う出力を得られませんでした: {last}")
