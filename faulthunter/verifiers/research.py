from __future__ import annotations

import asyncio
from typing import Any

from ..models import AppCapture, BenchmarkResult, TestCase
from .browser import run_browser_probe


def _extract_yahoo_snapshot(symbol: str) -> dict[str, Any]:
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    fast = ticker.fast_info
    info = {}
    try:
        info = ticker.info or {}
    except Exception:
        info = {}

    price = fast.get("lastPrice") or fast.get("regularMarketPrice") or info.get("currentPrice")
    currency = info.get("currency") or "USD"
    market_time = fast.get("lastTradeTime")
    return {
        "symbol": symbol,
        "price": float(price) if price is not None else None,
        "currency": currency,
        "market_time": str(market_time) if market_time is not None else None,
    }


async def build_benchmark(
    case: TestCase,
    capture: AppCapture,
    *,
    repo_root,
    browser_probe_enabled: bool,
    browser_probe_timeout_s: float,
) -> BenchmarkResult:
    evidence: list[str] = []
    reference_price = None
    freshness_timestamp = None
    browser_probe_url = case.browser_probe_url
    browser_probe_excerpt = None
    unavailable_reason = None
    source = "heuristic"
    summary = "No independent benchmark available for this case yet."

    if case.benchmark_symbol:
        try:
            snap = await asyncio.to_thread(_extract_yahoo_snapshot, case.benchmark_symbol)
            reference_price = snap.get("price")
            freshness_timestamp = snap.get("market_time")
            source = "yahoo_finance"
            if reference_price is not None:
                evidence.append(f"{case.benchmark_symbol} reference price: {reference_price:.2f} {snap.get('currency', 'USD')}")
                summary = (
                    f"Yahoo Finance reference for {case.benchmark_symbol} is {reference_price:.2f} "
                    f"{snap.get('currency', 'USD')}."
                )
            else:
                unavailable_reason = f"Yahoo returned no price for {case.benchmark_symbol}."
                summary = unavailable_reason
        except Exception as exc:
            source = "yahoo_finance"
            unavailable_reason = f"Yahoo fetch failed: {exc}"
            summary = unavailable_reason

    if browser_probe_enabled and browser_probe_url:
        probe = await asyncio.to_thread(
            run_browser_probe,
            repo_root,
            browser_probe_url,
            browser_probe_timeout_s,
        )
        if probe:
            browser_probe_excerpt = probe.get("excerpt")
            evidence.append(f"Browser probe title: {probe.get('title', 'n/a')}")

    if capture.status_code >= 400:
        summary = "Independent verification skipped because the target endpoint failed."

    return BenchmarkResult(
        source=source,
        summary=summary,
        evidence=evidence,
        reference_price=reference_price,
        reference_symbol=case.benchmark_symbol,
        freshness_timestamp=freshness_timestamp,
        browser_probe_url=browser_probe_url if browser_probe_excerpt else None,
        browser_probe_excerpt=browser_probe_excerpt,
        unavailable_reason=unavailable_reason,
    )
