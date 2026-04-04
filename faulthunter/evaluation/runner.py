from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..case_bank import build_case_bank
from .diagnostics import analyze_case_diagnostics
from ..models import BenchmarkResult, EvalRun, Finding, ReportKind, RunProfile, Severity, TestCase, Verdict
from ..targets.tradetalk import TradeTalkTargetClient
from ..utils import get_nested_value
from ..verifiers.research import build_benchmark


def _benchmark_summary(case: TestCase, benchmark: BenchmarkResult) -> str:
    field_list = ", ".join(case.required_fields) if case.required_fields else "current context"
    evidence_bits = []
    if benchmark.summary:
        evidence_bits.append(benchmark.summary)
    if benchmark.browser_probe_url:
        evidence_bits.append(f"Browser evidence captured from {benchmark.browser_probe_url}.")
    if case.recommendation_expected:
        base = (
            f"This is a {case.required_freshness} recommendation request. "
            f"A cautious answer should ground on {field_list} and ask for more data if freshness is unclear."
        )
    else:
        base = (
        f"This case should provide enough context for {case.feature}. "
        f"Key evidence fields: {field_list}."
        )
    return " ".join([base] + evidence_bits).strip()


def _parity_summary(benchmark: BenchmarkResult) -> str:
    if not benchmark.parity_checks:
        return "No Yahoo parity depth was available for this case."
    counts: dict[str, int] = {}
    for check in benchmark.parity_checks:
        counts[check.status] = counts.get(check.status, 0) + 1
    ordered = ["match", "mismatch", "missing_in_app", "unavailable_in_benchmark", "non_numeric"]
    bits = [f"{status}={counts[status]}" for status in ordered if counts.get(status)]
    return " | ".join(bits) if bits else "No parity outcomes recorded."


def _price_mismatch(case: TestCase, capture, benchmark: BenchmarkResult) -> tuple[bool, str]:
    if not case.parity_field or benchmark.reference_price is None or not isinstance(capture.raw_payload, dict):
        return False, ""

    actual = get_nested_value(capture.raw_payload, case.parity_field)
    if actual is None:
        return False, ""

    try:
        actual_f = float(actual)
        expected_f = float(benchmark.reference_price)
    except (TypeError, ValueError):
        return False, ""

    tolerance = max(2.0, abs(expected_f) * 0.02)
    if abs(actual_f - expected_f) <= tolerance:
        return False, ""
    return True, f"Payload value {actual_f:.2f} diverges from Yahoo reference {expected_f:.2f} beyond tolerance {tolerance:.2f}."


def _apply_latency_judgment(
    case: TestCase,
    capture,
    *,
    verdict: Verdict,
    severity: Severity,
    failure_category: list[str],
    issue: str,
    recommended_fix: list[str],
) -> tuple[Verdict, Severity, list[str], str, list[str], bool]:
    slow_response = capture.latency_ms > case.slow_latency_ms
    if not slow_response:
        return verdict, severity, failure_category, issue, recommended_fix, False

    if "slow_response" not in failure_category:
        failure_category = [*failure_category, "slow_response"]

    latency_note = (
        f"Response time was {capture.latency_ms}ms, above the {case.slow_latency_ms}ms threshold for this case."
    )

    if verdict == Verdict.PASS:
        verdict = Verdict.WARNING
        severity = Severity.MEDIUM
        issue = latency_note
    else:
        issue = f"{issue} {latency_note}"

    if "Reduce latency with caching, lighter payload assembly, or prefetching for this endpoint." not in recommended_fix:
        recommended_fix = [
            *recommended_fix,
            "Reduce latency with caching, lighter payload assembly, or prefetching for this endpoint.",
        ]

    return verdict, severity, failure_category, issue, recommended_fix, True


def judge_case(case: TestCase, capture, benchmark: BenchmarkResult) -> Finding:
    missing_fields = [field for field in case.required_fields if field not in capture.available_fields]
    needs_freshness = case.required_freshness in {"intraday", "same_day"}
    missing_freshness = needs_freshness and not capture.freshness_timestamp
    answered_recommendation = bool(capture.recommendation)
    should_have_requested_more_data = case.recommendation_expected and (missing_fields or missing_freshness)

    verdict = Verdict.PASS
    severity = Severity.LOW
    failure_category: list[str] = []
    issue = "Response has the minimum expected fields for this evaluator slice."
    recommended_fix: list[str] = []
    benchmark_evidence = list(benchmark.evidence)
    price_mismatch, price_issue = _price_mismatch(case, capture, benchmark)

    if capture.status_code >= 400:
        verdict = Verdict.FAIL
        severity = Severity.HIGH
        failure_category = ["endpoint_failure"]
        issue = f"Target returned HTTP {capture.status_code} for {case.endpoint}."
        recommended_fix = ["Stabilize the endpoint before judging recommendation quality."]
    elif price_mismatch:
        verdict = Verdict.FAIL if case.required_freshness == "intraday" else Verdict.WARNING
        severity = Severity.HIGH if verdict == Verdict.FAIL else Severity.MEDIUM
        failure_category = ["stale_data", "factual_mismatch"]
        issue = price_issue
        recommended_fix = ["Refresh price-sensitive fields against an independent real-time source before answering."]
    elif should_have_requested_more_data and answered_recommendation:
        verdict = Verdict.FAIL
        severity = Severity.HIGH
        failure_category = ["incomplete_data", "confidence_overreach"]
        issue = "The app produced a directional answer without the freshness or evidence fields this case requires."
        if missing_freshness:
            recommended_fix.append("Attach and surface explicit freshness timestamps for time-sensitive answers.")
        if missing_fields:
            recommended_fix.append("Fetch the missing real-time evidence before issuing a recommendation.")
    elif missing_fields or missing_freshness:
        verdict = Verdict.WARNING
        severity = Severity.MEDIUM
        failure_category = ["missing_context"]
        issue = "The response is usable, but the evidence surface is incomplete for this scenario."
        recommended_fix.append("Expand the response payload so evaluators can confirm evidence coverage.")

    verdict, severity, failure_category, issue, recommended_fix, slow_response = _apply_latency_judgment(
        case,
        capture,
        verdict=verdict,
        severity=severity,
        failure_category=failure_category,
        issue=issue,
        recommended_fix=recommended_fix,
    )

    required_additional_data = []
    if missing_freshness:
        required_additional_data.append("freshness timestamp")
    required_additional_data.extend(missing_fields)

    return Finding(
        test_id=case.id,
        feature=case.feature,
        endpoint=case.endpoint,
        method=case.method.upper(),
        request_payload=dict(case.query),
        user_question=case.user_question,
        app_answer_summary=capture.summary,
        benchmark_summary=_benchmark_summary(case, benchmark),
        benchmark_source=benchmark.source,
        benchmark_evidence=benchmark_evidence,
        parity_summary=_parity_summary(benchmark),
        parity_checks=list(benchmark.parity_checks),
        response_time_ms=capture.latency_ms,
        slow_threshold_ms=case.slow_latency_ms,
        slow_response=slow_response,
        verdict=verdict,
        severity=severity,
        failure_category=failure_category,
        issue=issue,
        should_have_requested_more_data=bool(should_have_requested_more_data),
        required_additional_data=required_additional_data,
        recommended_fix=recommended_fix,
    )


async def run_evaluation(
    profile: RunProfile,
    target_base_url: str,
    report_kind: ReportKind,
    timeout_s: float,
    *,
    repo_root,
    browser_probe_enabled: bool,
    browser_probe_timeout_s: float,
) -> EvalRun:
    cases = build_case_bank(profile)
    findings: list[Finding] = []
    async with TradeTalkTargetClient(base_url=target_base_url, timeout_s=timeout_s) as target:
        for case in cases:
            capture = await target.execute(case)
            benchmark = await build_benchmark(
                case,
                capture,
                repo_root=repo_root,
                browser_probe_enabled=browser_probe_enabled,
                browser_probe_timeout_s=browser_probe_timeout_s,
            )
            finding = judge_case(case, capture, benchmark)
            diagnostics = await analyze_case_diagnostics(case, capture, finding, target)
            finding.diagnostic_root_cause = diagnostics.root_cause
            finding.diagnostic_summary = diagnostics.summary
            finding.diagnostic_evidence = diagnostics.evidence
            finding.diagnostic_probes = diagnostics.probes
            findings.append(finding)

    return EvalRun(
        run_id=f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}",
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        profile=profile,
        report_kind=report_kind,
        target_base_url=target_base_url,
        findings=findings,
    )
