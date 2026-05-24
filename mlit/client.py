"""Minimal synchronous GraphQL client for the MLIT Data Platform API.

Reads MLIT_API_KEY / MLIT_BASE_URL from the environment (with .env.local / .env
support) and sends GraphQL queries as POST bodies, retrying transient errors.
"""

from __future__ import annotations

import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

DEFAULT_BASE_URL = "https://data-platform.mlit.go.jp/api/v1/"

# Load .env.local first (takes priority), then .env. Existing env vars win.
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env.local")
load_dotenv(_ROOT / ".env")


class MlitApiError(RuntimeError):
    """Raised when the API responds with GraphQL errors or an unexpected shape."""


class TransientHttpError(RuntimeError):
    """Retryable HTTP/network failure (429, 5xx, timeouts)."""


class MlitClient:
    """Thin GraphQL client. Call ``execute(query)`` with a query string."""

    _RETRYABLE_STATUS = {429, 500, 502, 503, 504}

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_s: float | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("MLIT_API_KEY")
        if not self.api_key:
            raise MlitApiError(
                "MLIT_API_KEY is not set. Put it in .env.local "
                "(see .env.example) or export it before running."
            )
        self.base_url = (base_url or os.getenv("MLIT_BASE_URL") or DEFAULT_BASE_URL).rstrip("/") + "/"
        self.timeout_s = float(timeout_s or os.getenv("MLIT_TIMEOUT_S") or 30.0)
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "apikey": self.api_key,
            }
        )

    @retry(
        retry=retry_if_exception_type(TransientHttpError),
        wait=wait_exponential(multiplier=1, min=0.5, max=8),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def execute(self, query: str) -> dict:
        """Run a GraphQL query string and return the ``data`` object."""
        try:
            resp = self._session.post(
                self.base_url, json={"query": query}, timeout=self.timeout_s
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise TransientHttpError(f"network error: {exc}") from exc

        if resp.status_code in self._RETRYABLE_STATUS:
            raise TransientHttpError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        if resp.status_code != 200:
            raise MlitApiError(f"HTTP {resp.status_code}: {resp.text[:500]}")

        payload = resp.json()
        if payload.get("errors"):
            raise MlitApiError(f"GraphQL errors: {payload['errors']}")
        if "data" not in payload:
            raise MlitApiError(f"unexpected response (no 'data'): {str(payload)[:300]}")
        return payload["data"]
