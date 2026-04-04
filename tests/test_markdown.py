from faulthunter.models import EvalRun, Finding, ReportKind, RunProfile, Severity, Verdict
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
                user_question="Should I buy AAPL today?",
                app_answer_summary="Decision Terminal says BUY.",
                benchmark_summary="Need same-day price and freshness.",
                benchmark_source="yahoo_finance",
                benchmark_evidence=["AAPL reference price: 200.00 USD"],
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
    assert "| `decision-aapl` | `decision_terminal` | `fail` | `high` | `18000ms` | `yes` | `yes` |" in text
    assert "Missing freshness." in text
    assert "Benchmark source: yahoo_finance" in text
    assert "Slow responses flagged: `1`" in text
