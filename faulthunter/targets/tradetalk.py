from __future__ import annotations

import time
from typing import Any, Optional

import httpx

from ..evaluation.capture import build_capture
from ..models import TestCase


class TradeTalkTargetClient:
    def __init__(self, base_url: str, timeout_s: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "TradeTalkTargetClient":
        self._client = httpx.AsyncClient(timeout=self.timeout_s, follow_redirects=True)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def execute(self, case: TestCase):
        if self._client is None:
            raise RuntimeError("TradeTalkTargetClient must be used as an async context manager.")

        started = time.perf_counter()
        try:
            response = await self._client.request(
                case.method.upper(),
                f"{self.base_url}{case.endpoint}",
                params=case.query if case.method.upper() == "GET" else None,
                json=case.query if case.method.upper() != "GET" else None,
            )
        except httpx.HTTPError as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return build_capture(
                case,
                status_code=599,
                latency_ms=latency_ms,
                payload={"error": str(exc), "endpoint": case.endpoint},
            )

        latency_ms = int((time.perf_counter() - started) * 1000)
        try:
            payload: Any = response.json()
        except ValueError:
            payload = response.text
        return build_capture(case, response.status_code, latency_ms, payload)
