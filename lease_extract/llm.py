"""Ollama の /api/chat を呼ぶ最小クライアント。JSON Schema で出力形式を固定する。"""
from __future__ import annotations

import os
from typing import Callable, TypeVar

import requests
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

# テストでは (system, user, schema) -> JSON 文字列 の関数に差し替える
LLMFn = Callable[[str, str, dict], str]

OLLAMA_HOST = os.environ.get("OLLAMA_HOST_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e2b")


def ollama_chat(system: str, user: str, schema: dict) -> str:
    # クラウドモデルを使う場合のみ OLLAMA_API_KEY を環境変数で渡す（コードには書かない）
    headers = {}
    if os.environ.get("OLLAMA_API_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['OLLAMA_API_KEY']}"
    r = requests.post(
        f"{OLLAMA_HOST}/api/chat",
        headers=headers,
        json={
            "model": OLLAMA_MODEL,
            "stream": False,
            "format": schema,
            "options": {"temperature": 0, "num_ctx": 8192},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=600,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]


def extract(model: type[T], system: str, user: str, llm: LLMFn = ollama_chat, retries: int = 2) -> T:
    """スキーマに合う JSON が返るまで数回やり直す。"""
    schema = model.model_json_schema()
    last: Exception | None = None
    for _ in range(retries + 1):
        raw = llm(system, user, schema)
        try:
            return model.model_validate_json(raw)
        except Exception as e:  # noqa: BLE001
            last = e
    raise ValueError(f"スキーマに合う出力を得られませんでした: {last}")
