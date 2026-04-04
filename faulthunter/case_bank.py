from __future__ import annotations

from .models import RunProfile, TestCase


_BASE_CASES = [
    TestCase(
        id="decision-aapl-today",
        feature="decision_terminal",
        user_question="Should I buy AAPL today?",
        challenge_type="urgent_decision_prompt",
        required_freshness="intraday",
        endpoint="/decision-terminal",
        query={"ticker": "AAPL"},
        recommendation_expected=True,
        required_fields=["generated_at_utc", "valuation.current_price_usd", "verdict.headline_verdict"],
        benchmark_symbol="AAPL",
        parity_field="valuation.current_price_usd",
        browser_probe_url="https://finance.yahoo.com/quote/AAPL",
        slow_latency_ms=15000,
    ),
    TestCase(
        id="macro-allocation-week",
        feature="macro",
        user_question="How should I think about equity versus commodity allocation this week?",
        challenge_type="macro_allocation",
        required_freshness="same_day",
        endpoint="/macro",
        required_fields=["market_regime", "vix_level", "dxy_level", "treasury_10y", "macro_narrative"],
        slow_latency_ms=5000,
    ),
    TestCase(
        id="gold-hedge-week",
        feature="gold",
        user_question="Should I hedge with gold this week?",
        challenge_type="hedging_decision",
        required_freshness="same_day",
        endpoint="/advisor/gold",
        recommendation_expected=True,
        required_fields=["briefing.directional_bias", "briefing.confidence_0_1", "context.macro.dxy_spot"],
        benchmark_symbol="GC=F",
        parity_field="context.macro.gold_futures_last_usd",
        browser_probe_url="https://finance.yahoo.com/quote/GC=F",
        slow_latency_ms=7000,
    ),
]

_DAILY_CASES = _BASE_CASES + [
    TestCase(
        id="trace-nvda-today",
        feature="trace",
        user_question="Is NVDA still a buy right now?",
        challenge_type="time_sensitive_trace",
        required_freshness="intraday",
        endpoint="/trace",
        query={"ticker": "NVDA"},
        recommendation_expected=True,
        required_fields=["global_verdict", "confidence"],
        benchmark_symbol="NVDA",
        browser_probe_url="https://finance.yahoo.com/quote/NVDA",
        slow_latency_ms=15000,
    ),
    TestCase(
        id="debate-tsla-thesis",
        feature="debate",
        user_question="Stress-test the bull and bear case for TSLA right now.",
        challenge_type="polarizing_asset",
        required_freshness="same_day",
        endpoint="/debate",
        query={"ticker": "TSLA"},
        required_fields=["verdict", "consensus_confidence", "arguments"],
        benchmark_symbol="TSLA",
        browser_probe_url="https://finance.yahoo.com/quote/TSLA",
        slow_latency_ms=25000,
    ),
]


def build_case_bank(profile: RunProfile) -> list[TestCase]:
    if profile == RunProfile.SMOKE:
        return list(_BASE_CASES)
    if profile == RunProfile.DAILY:
        return list(_DAILY_CASES)
    return list(_DAILY_CASES)
