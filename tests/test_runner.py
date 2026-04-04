from faulthunter.case_bank import build_case_bank
from faulthunter.evaluation.capture import build_capture
from faulthunter.evaluation.runner import judge_case
from faulthunter.models import AppCapture, BenchmarkResult, RunProfile, Severity, Verdict


def test_decision_case_missing_freshness_fails():
    case = build_case_bank(RunProfile.SMOKE)[0]
    capture = AppCapture(
        endpoint=case.endpoint,
        status_code=200,
        latency_ms=1000,
        summary="Decision Terminal says BUY.",
        recommendation="BUY",
        confidence=0.8,
        freshness_timestamp=None,
        available_fields=["valuation.current_price_usd", "verdict.headline_verdict"],
        raw_payload={},
    )

    finding = judge_case(case, capture, BenchmarkResult(source="yahoo_finance", summary="ok"))
    assert finding.verdict == Verdict.FAIL
    assert finding.severity == Severity.HIGH
    assert finding.should_have_requested_more_data is True
    assert finding.response_time_ms == 1000
    assert finding.slow_response is False


def test_gold_case_uses_as_of_utc_as_freshness_signal():
    case = build_case_bank(RunProfile.SMOKE)[2]
    capture = build_capture(
        case,
        status_code=200,
        latency_ms=1000,
        payload={
            "context": {
                "as_of_utc": "2026-04-04T02:40:25.925628+00:00",
                "macro": {"dxy_spot": 100.1},
            },
            "briefing": {
                "directional_bias": "neutral",
                "confidence_0_1": 0.45,
            },
        },
    )

    finding = judge_case(case, capture, BenchmarkResult(source="yahoo_finance", summary="ok"))
    assert finding.verdict == Verdict.PASS
    assert finding.should_have_requested_more_data is False


def test_price_mismatch_fails_intraday_decision_case():
    case = build_case_bank(RunProfile.SMOKE)[0]
    capture = build_capture(
        case,
        status_code=200,
        latency_ms=1000,
        payload={
            "generated_at_utc": "2026-04-04T02:40:30.023234+00:00",
            "valuation": {"current_price_usd": 255.92},
            "verdict": {"headline_verdict": "NEUTRAL"},
        },
    )
    benchmark = BenchmarkResult(
        source="yahoo_finance",
        summary="Yahoo says 240.00 USD.",
        evidence=["AAPL reference price: 240.00 USD"],
        reference_price=240.0,
        reference_symbol="AAPL",
    )

    finding = judge_case(case, capture, benchmark)
    assert finding.verdict == Verdict.FAIL
    assert "stale_data" in finding.failure_category


def test_latency_warning_is_flagged_for_otherwise_passing_case():
    case = build_case_bank(RunProfile.SMOKE)[1]
    capture = build_capture(
        case,
        status_code=200,
        latency_ms=6500,
        payload={
            "market_regime": "BEAR_STRESS",
            "vix_level": 23.8,
            "credit_stress_index": 1.4,
            "sectors": [],
            "consumer_spending": [],
            "capital_flows": [],
            "cash_reserves": [],
            "dxy_level": 103.0,
            "treasury_10y": 4.3,
            "macro_narrative": "Dollar firm and yields elevated.",
            "fred_fetched_at": "2026-04-04T02:50:00+00:00",
        },
    )
    benchmark = BenchmarkResult(source="heuristic", summary="ok")

    finding = judge_case(case, capture, benchmark)
    assert finding.verdict == Verdict.WARNING
    assert finding.slow_response is True
    assert "slow_response" in finding.failure_category
