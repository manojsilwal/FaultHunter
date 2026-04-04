from __future__ import annotations

import asyncio
import math
import re
from typing import Any

from ..models import AppCapture, BenchmarkResult, ParityCheck, TestCase
from ..utils import find_first_key, get_nested_value
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
    gross_margins = info.get("grossMargins")
    if gross_margins is not None:
        gross_margins = float(gross_margins) * 100.0
    return {
        "symbol": symbol,
        "price": float(price) if price is not None else None,
        "currency": currency,
        "market_time": str(market_time) if market_time is not None else None,
        "previous_close": fast.get("previousClose") or info.get("previousClose"),
        "day_high": fast.get("dayHigh") or info.get("dayHigh"),
        "day_low": fast.get("dayLow") or info.get("dayLow"),
        "market_cap": info.get("marketCap"),
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "trailing_eps": info.get("trailingEps"),
        "gross_margins_pct": gross_margins,
        "current_ratio": info.get("currentRatio"),
        "free_cashflow": info.get("freeCashflow"),
    }


_CURRENCY_SUFFIXES = {
    "K": 1_000.0,
    "M": 1_000_000.0,
    "B": 1_000_000_000.0,
    "T": 1_000_000_000_000.0,
}


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        value_f = float(value)
        if math.isnan(value_f) or math.isinf(value_f):
            return None
        return value_f
    if not isinstance(value, str):
        return None

    cleaned = value.strip().replace(",", "")
    if not cleaned or cleaned.lower() in {"n/a", "na", "none", "unknown"}:
        return None
    if cleaned.endswith("%"):
        return _coerce_float(cleaned[:-1])
    if cleaned.startswith("$"):
        return _coerce_float(cleaned[1:])

    match = re.fullmatch(r"(-?\d+(?:\.\d+)?)([KMBT])", cleaned, re.IGNORECASE)
    if match:
        base = float(match.group(1))
        mult = _CURRENCY_SUFFIXES[match.group(2).upper()]
        return base * mult

    try:
        return float(cleaned)
    except ValueError:
        return None


def _build_parity_check(
    *,
    metric: str,
    app_field: str | None,
    app_value: Any,
    benchmark_field: str,
    benchmark_value: Any,
    tolerance_abs: float,
    tolerance_pct: float,
) -> ParityCheck:
    if benchmark_value is None:
        return ParityCheck(
            metric=metric,
            app_field=app_field,
            app_value=app_value,
            benchmark_field=benchmark_field,
            benchmark_value=benchmark_value,
            status="unavailable_in_benchmark",
            note="Yahoo did not return a comparable value.",
        )

    if app_field is None or app_value is None:
        return ParityCheck(
            metric=metric,
            app_field=app_field,
            app_value=app_value,
            benchmark_field=benchmark_field,
            benchmark_value=benchmark_value,
            status="missing_in_app",
            note="The app response did not expose a comparable field for this metric.",
        )

    app_num = _coerce_float(app_value)
    bench_num = _coerce_float(benchmark_value)
    if app_num is None or bench_num is None:
        return ParityCheck(
            metric=metric,
            app_field=app_field,
            app_value=app_value,
            benchmark_field=benchmark_field,
            benchmark_value=benchmark_value,
            status="non_numeric",
            note="Parity metric was present but could not be compared numerically.",
        )

    tolerance = max(tolerance_abs, abs(bench_num) * tolerance_pct)
    delta = abs(app_num - bench_num)
    status = "match" if delta <= tolerance else "mismatch"
    note = f"delta={delta:.2f}, tolerance={tolerance:.2f}"
    return ParityCheck(
        metric=metric,
        app_field=app_field,
        app_value=app_value,
        benchmark_field=benchmark_field,
        benchmark_value=benchmark_value,
        status=status,
        note=note,
    )


def _find_quality_row_value(payload: dict[str, Any], row_id: str) -> tuple[str | None, Any]:
    rows = get_nested_value(payload, "quality.rows")
    if not isinstance(rows, list):
        return None, None
    for idx, row in enumerate(rows):
        if isinstance(row, dict) and row.get("id") == row_id:
            return f"quality.rows[{idx}].value_label", row.get("value_label")
    return None, None


def _build_parity_checks(case: TestCase, capture: AppCapture, snapshot: dict[str, Any]) -> list[ParityCheck]:
    if not case.benchmark_symbol or not snapshot or not isinstance(capture.raw_payload, dict):
        return []

    payload = capture.raw_payload
    checks: list[ParityCheck] = []

    if case.feature == "decision_terminal":
        checks.append(
            _build_parity_check(
                metric="current_price",
                app_field=case.parity_field,
                app_value=get_nested_value(payload, case.parity_field or ""),
                benchmark_field="price",
                benchmark_value=snapshot.get("price"),
                tolerance_abs=2.0,
                tolerance_pct=0.02,
            )
        )
        gross_margin_field, gross_margin_value = _find_quality_row_value(payload, "margin")
        checks.append(
            _build_parity_check(
                metric="gross_margin_pct",
                app_field=gross_margin_field,
                app_value=gross_margin_value,
                benchmark_field="gross_margins_pct",
                benchmark_value=snapshot.get("gross_margins_pct"),
                tolerance_abs=2.0,
                tolerance_pct=0.05,
            )
        )
        current_ratio_field, current_ratio_value = _find_quality_row_value(payload, "current_ratio")
        checks.append(
            _build_parity_check(
                metric="current_ratio",
                app_field=current_ratio_field,
                app_value=current_ratio_value,
                benchmark_field="current_ratio",
                benchmark_value=snapshot.get("current_ratio"),
                tolerance_abs=0.1,
                tolerance_pct=0.05,
            )
        )
        fcf_field, fcf_value = _find_quality_row_value(payload, "fcf")
        checks.append(
            _build_parity_check(
                metric="free_cashflow",
                app_field=fcf_field,
                app_value=fcf_value,
                benchmark_field="free_cashflow",
                benchmark_value=snapshot.get("free_cashflow"),
                tolerance_abs=1_000_000_000.0,
                tolerance_pct=0.1,
            )
        )
        return checks

    explicit_price_field = case.parity_field or None
    explicit_price_value = get_nested_value(payload, case.parity_field or "") if case.parity_field else None
    if explicit_price_value is None:
        explicit_price_field, explicit_price_value = find_first_key(
            payload,
            {"current_price", "currentPrice", "current_price_usd", "price"},
        )
    checks.append(
        _build_parity_check(
            metric="current_price",
            app_field=explicit_price_field,
            app_value=explicit_price_value,
            benchmark_field="price",
            benchmark_value=snapshot.get("price"),
            tolerance_abs=2.0,
            tolerance_pct=0.02,
        )
    )

    market_cap_field, market_cap_value = find_first_key(payload, {"market_cap", "marketCap"})
    checks.append(
        _build_parity_check(
            metric="market_cap",
            app_field=market_cap_field,
            app_value=market_cap_value,
            benchmark_field="market_cap",
            benchmark_value=snapshot.get("market_cap"),
            tolerance_abs=5_000_000_000.0,
            tolerance_pct=0.1,
        )
    )

    pe_field, pe_value = find_first_key(payload, {"pe_ratio", "trailingPE", "pe"})
    checks.append(
        _build_parity_check(
            metric="trailing_pe",
            app_field=pe_field,
            app_value=pe_value,
            benchmark_field="trailing_pe",
            benchmark_value=snapshot.get("trailing_pe"),
            tolerance_abs=1.0,
            tolerance_pct=0.1,
        )
    )
    return checks


def _parity_summary(parity_checks: list[ParityCheck]) -> str:
    if not parity_checks:
        return "No Yahoo parity checks were available for this case."

    counts: dict[str, int] = {}
    for check in parity_checks:
        counts[check.status] = counts.get(check.status, 0) + 1
    ordered = ["match", "mismatch", "missing_in_app", "unavailable_in_benchmark", "non_numeric"]
    bits = [f"{status}={counts[status]}" for status in ordered if counts.get(status)]
    return "Yahoo parity depth: " + ", ".join(bits) + "."


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
                if snap.get("trailing_pe") is not None:
                    evidence.append(f"Yahoo trailing PE: {float(snap['trailing_pe']):.2f}")
                if snap.get("market_cap") is not None:
                    evidence.append(f"Yahoo market cap: {float(snap['market_cap']) / 1_000_000_000:.2f}B")
                if snap.get("gross_margins_pct") is not None:
                    evidence.append(f"Yahoo gross margin: {float(snap['gross_margins_pct']):.1f}%")
                summary = _parity_summary(_build_parity_checks(case, capture, snap))
            else:
                unavailable_reason = f"Yahoo returned no price for {case.benchmark_symbol}."
                summary = unavailable_reason
        except Exception as exc:
            source = "yahoo_finance"
            unavailable_reason = f"Yahoo fetch failed: {exc}"
            summary = unavailable_reason
            snap = {}
    else:
        snap = {}

    parity_checks = _build_parity_checks(case, capture, snap)
    if source == "yahoo_finance" and parity_checks and reference_price is not None:
        summary = _parity_summary(parity_checks)

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
        snapshot=snap,
        parity_checks=parity_checks,
        browser_probe_url=browser_probe_url if browser_probe_excerpt else None,
        browser_probe_excerpt=browser_probe_excerpt,
        unavailable_reason=unavailable_reason,
    )
