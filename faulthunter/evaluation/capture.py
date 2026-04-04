from __future__ import annotations

from typing import Any

from ..models import AppCapture, TestCase


def _flatten_paths(prefix: str, value: Any, out: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            out.append(child_prefix)
            _flatten_paths(child_prefix, child, out)


def _available_fields(payload: dict[str, Any]) -> list[str]:
    out: list[str] = []
    _flatten_paths("", payload, out)
    return sorted(set(out))


def build_capture(case: TestCase, status_code: int, latency_ms: int, payload: Any) -> AppCapture:
    if not isinstance(payload, dict):
        return AppCapture(
            endpoint=case.endpoint,
            status_code=status_code,
            latency_ms=latency_ms,
            summary=str(payload)[:400],
            raw_payload=str(payload)[:2000],
        )

    available_fields = _available_fields(payload)
    summary = f"{case.feature} response captured."
    recommendation = None
    confidence = None
    freshness = None

    if payload.get("error"):
        return AppCapture(
            endpoint=case.endpoint,
            status_code=status_code,
            latency_ms=latency_ms,
            summary=f"Request failed: {payload.get('error')}",
            available_fields=available_fields,
            raw_payload=payload,
        )

    if case.endpoint == "/decision-terminal":
        verdict = (payload.get("verdict") or {})
        valuation = (payload.get("valuation") or {})
        recommendation = verdict.get("headline_verdict")
        confidence = (verdict.get("expert_bullish_pct") or 0) / 100.0 if verdict.get("expert_bullish_pct") is not None else None
        freshness = payload.get("generated_at_utc")
        summary = (
            f"Decision Terminal says {recommendation or 'no verdict'}"
            f" with price {valuation.get('current_price_usd', 'N/A')}."
        )
    elif case.endpoint == "/macro":
        recommendation = payload.get("market_regime")
        freshness = payload.get("fred_fetched_at")
        summary = (
            f"Macro regime {payload.get('market_regime', 'unknown')}; "
            f"VIX {payload.get('vix_level', 'N/A')} and DXY {payload.get('dxy_level', 'N/A')}."
        )
    elif case.endpoint == "/advisor/gold":
        briefing = payload.get("briefing") or {}
        recommendation = briefing.get("directional_bias")
        confidence = briefing.get("confidence_0_1")
        context = payload.get("context") or {}
        freshness = context.get("as_of_utc") or context.get("generated_at_utc")
        summary = f"Gold advisor bias {recommendation or 'unknown'}."
    elif case.endpoint == "/trace":
        recommendation = payload.get("global_verdict")
        confidence = payload.get("confidence")
        summary = f"Swarm verdict {recommendation or 'unknown'}."
    elif case.endpoint == "/debate":
        recommendation = payload.get("verdict")
        confidence = payload.get("consensus_confidence")
        summary = f"Debate verdict {recommendation or 'unknown'}."
    else:
        summary = f"Captured payload from {case.endpoint}."

    return AppCapture(
        endpoint=case.endpoint,
        status_code=status_code,
        latency_ms=latency_ms,
        summary=summary,
        recommendation=recommendation,
        confidence=confidence,
        freshness_timestamp=freshness,
        available_fields=available_fields,
        raw_payload=payload,
    )
