import asyncio

from faulthunter.case_bank import build_case_bank
from faulthunter.evaluation.capture import build_capture
from faulthunter.evaluation.diagnostics import analyze_case_diagnostics
from faulthunter.evaluation.runner import judge_case
from faulthunter.models import AppCapture, BenchmarkResult, DiagnosticProbe, RunProfile


class DummyTarget:
    def __init__(self, probe_result: DiagnosticProbe, replay_capture: AppCapture | None = None) -> None:
        self._probe_result = probe_result
        self._replay_capture = replay_capture

    async def probe(self, path: str, *, name: str, timeout_s: float = 5.0) -> DiagnosticProbe:
        return self._probe_result

    async def execute(self, case):
        if self._replay_capture is None:
            raise AssertionError("Replay should not be called for this test.")
        return self._replay_capture


def test_failure_diagnostics_identify_service_unreachable():
    case = build_case_bank(RunProfile.SMOKE)[0]
    capture = build_capture(
        case,
        status_code=599,
        latency_ms=3,
        payload={
            "error": "All connection attempts failed",
            "error_type": "ConnectError",
            "endpoint": case.endpoint,
        },
    )
    finding = judge_case(case, capture, BenchmarkResult(source="heuristic", summary="ok"))
    target = DummyTarget(
        DiagnosticProbe(
            name="service_health",
            endpoint="/openapi.json",
            status_code=599,
            latency_ms=12,
            outcome="error",
            note="ConnectError: All connection attempts failed",
        )
    )

    diagnostics = asyncio.run(analyze_case_diagnostics(case, capture, finding, target))

    assert diagnostics.root_cause == "service_unreachable"
    assert "service itself was not reachable" in diagnostics.summary


def test_slow_diagnostics_identify_cold_cache_or_warmup():
    case = build_case_bank(RunProfile.SMOKE)[1]
    initial_capture = build_capture(
        case,
        status_code=200,
        latency_ms=6500,
        payload={
            "market_regime": "BEAR_STRESS",
            "vix_level": 22.0,
            "credit_stress_index": 1.5,
            "sectors": [],
            "consumer_spending": [],
            "capital_flows": [],
            "cash_reserves": [],
            "dxy_level": 103.0,
            "treasury_10y": 4.2,
            "macro_narrative": "Rates are elevated.",
            "fred_fetched_at": "2026-04-04T03:10:00+00:00",
        },
    )
    replay_capture = build_capture(
        case,
        status_code=200,
        latency_ms=1800,
        payload={
            "market_regime": "BEAR_STRESS",
            "vix_level": 22.0,
            "credit_stress_index": 1.5,
            "sectors": [],
            "consumer_spending": [],
            "capital_flows": [],
            "cash_reserves": [],
            "dxy_level": 103.0,
            "treasury_10y": 4.2,
            "macro_narrative": "Rates are elevated.",
            "fred_fetched_at": "2026-04-04T03:10:05+00:00",
        },
    )
    finding = judge_case(case, initial_capture, BenchmarkResult(source="heuristic", summary="ok"))
    target = DummyTarget(
        DiagnosticProbe(
            name="service_health",
            endpoint="/openapi.json",
            status_code=200,
            latency_ms=120,
            outcome="healthy",
            note="Probe returned HTTP 200.",
        ),
        replay_capture=replay_capture,
    )

    diagnostics = asyncio.run(analyze_case_diagnostics(case, initial_capture, finding, target))

    assert diagnostics.root_cause == "cold_cache_or_warmup"
    assert "suggests a cold-cache or warm-up delay" in diagnostics.summary
