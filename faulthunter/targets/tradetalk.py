from __future__ import annotations

import time
from typing import Any, Optional

import httpx

from ..evaluation.capture import build_capture
from ..models import DiagnosticProbe, TestCase


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

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout_s: float | None = None,
    ) -> tuple[int, int, Any]:
        if self._client is None:
            raise RuntimeError("TradeTalkTargetClient must be used as an async context manager.")

        started = time.perf_counter()
        try:
            response = await self._client.request(
                method.upper(),
                f"{self.base_url}{path}",
                params=params,
                json=json_body,
                timeout=timeout_s or self.timeout_s,
            )
        except httpx.HTTPError as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return 599, latency_ms, {
                "error": str(exc),
                "error_type": exc.__class__.__name__,
                "endpoint": path,
            }

        latency_ms = int((time.perf_counter() - started) * 1000)
        try:
            payload: Any = response.json()
        except ValueError:
            payload = response.text
        return response.status_code, latency_ms, payload

    async def execute(self, case: TestCase):
        status_code, latency_ms, payload = await self._request(
            case.method,
            case.endpoint,
            params=case.query if case.method.upper() == "GET" else None,
            json_body=case.query if case.method.upper() != "GET" else None,
        )
        return build_capture(case, status_code, latency_ms, payload)

    async def probe(self, path: str, *, name: str, timeout_s: float = 5.0) -> DiagnosticProbe:
        status_code, latency_ms, payload = await self._request("GET", path, timeout_s=timeout_s)
        if isinstance(payload, dict) and payload.get("error"):
            outcome = "error"
            note = f"{payload.get('error_type') or 'HTTPError'}: {payload.get('error')}"
        elif status_code >= 500 or status_code == 599:
            outcome = "unhealthy"
            note = f"Probe returned HTTP {status_code}."
        elif status_code >= 400:
            outcome = "client_error"
            note = f"Probe returned HTTP {status_code}."
        else:
            outcome = "healthy"
            note = f"Probe returned HTTP {status_code}."
        return DiagnosticProbe(
            name=name,
            endpoint=path,
            status_code=status_code,
            latency_ms=latency_ms,
            outcome=outcome,
            note=note,
        )
