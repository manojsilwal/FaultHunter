from faulthunter.models import DiagnosticProbe, EvalRun, Finding, ParityCheck, ReportKind, RunProfile, Severity, Verdict
from faulthunter.reports.markdown import render_markdown


def test_render_markdown_contains_summary_table():
    run = EvalRun(
        run_id="run-1",
        generated_at_utc="2026-04-03T00:00:00+00:00",
        profile=RunProfile.SMOKE,
        report_kind=ReportKind.MANUAL,
        target_base_url="http://localhost:8000",
        findings=[
            Finding(
                test_id="decision-aapl",
                feature="decision_terminal",
                endpoint="/decision-terminal",
                method="GET",
                request_payload={"ticker": "AAPL"},
                user_question="Should I buy AAPL today?",
                app_answer_summary="Decision Terminal says BUY.",
                benchmark_summary="Need same-day price and freshness.",
                benchmark_source="yahoo_finance",
                benchmark_evidence=["AAPL reference price: 200.00 USD"],
                parity_summary="match=1 | missing_in_app=2",
                parity_checks=[
                    ParityCheck(
                        metric="current_price",
                        app_field="valuation.current_price_usd",
                        app_value=198.0,
                        benchmark_field="price",
                        benchmark_value=200.0,
                        status="match",
                        note="delta=2.00, tolerance=4.00",
                    )
                ],
                diagnostic_root_cause="service_unreachable",
                diagnostic_summary="Health probe also failed, so this looks service-wide.",
                diagnostic_evidence=["service_health probe on /openapi.json returned 599 in 10ms (error)."],
                diagnostic_probes=[
                    DiagnosticProbe(
                        name="service_health",
                        endpoint="/openapi.json",
                        status_code=599,
                        latency_ms=10,
                        outcome="error",
                        note="ConnectError: All connection attempts failed",
                    )
                ],
                response_time_ms=18000,
                slow_threshold_ms=15000,
                slow_response=True,
                verdict=Verdict.FAIL,
                severity=Severity.HIGH,
                issue="Missing freshness.",
                should_have_requested_more_data=True,
                failure_category=["incomplete_data"],
                required_additional_data=["freshness timestamp"],
                recommended_fix=["Add freshness timestamp."],
            )
        ],
    )

    text = render_markdown(run)
    assert "# FaultHunter Report - 2026-04-03" in text
    assert "## Developer Agent Handoff" in text
    assert "## Developer Fix Queue" in text
    assert "| `1` | `decision-aapl` | `GET /decision-terminal` | `fail` | `high` | `service_unreachable` | `18000ms` | `under 15000ms` |" in text
    assert "| `decision-aapl` | `decision_terminal` | `fail` | `high` | `18000ms` | `yes` | `yes` |" in text
    assert "Missing freshness." in text
    assert "Benchmark source: yahoo_finance" in text
    assert "Parity summary: match=1 | missing_in_app=2" in text
    assert "- Root cause label: service_unreachable" in text
    assert "Likely root cause: Health probe also failed, so this looks service-wide." in text
    assert "curl -sS 'http://localhost:8000/decision-terminal?ticker=AAPL'" in text
    assert "Acceptance target: under 15000ms" in text
    assert "| `service_health` | `/openapi.json` | `599` | `10ms` | `error` | ConnectError: All connection attempts failed |" in text
    assert "| `current_price` | `match` | `valuation.current_price_usd` | `198.0` | `200.0` | delta=2.00, tolerance=4.00 |" in text
    assert "Slow responses flagged: `1`" in text
