from __future__ import annotations

from collections import Counter

from ..models import EvalRun, Verdict


def render_markdown(run: EvalRun) -> str:
    counts = Counter(f.verdict for f in run.findings)
    slow_count = sum(1 for f in run.findings if f.slow_response)
    lines = [
        f"# FaultHunter Report - {run.generated_at_utc[:10]}",
        "",
        f"- Run ID: `{run.run_id}`",
        f"- Profile: `{run.profile.value}`",
        f"- Target: `{run.target_base_url}`",
        f"- Findings: pass={counts.get(Verdict.PASS, 0)} warning={counts.get(Verdict.WARNING, 0)} fail={counts.get(Verdict.FAIL, 0)}",
        f"- Slow responses flagged: `{slow_count}`",
        "",
        "## Summary",
        "",
        "| Test | Feature | Verdict | Severity | Latency | Slow | More Data Needed |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]

    for finding in run.findings:
        needs_more = "yes" if finding.should_have_requested_more_data else "no"
        slow = "yes" if finding.slow_response else "no"
        lines.append(
            f"| `{finding.test_id}` | `{finding.feature}` | `{finding.verdict.value}` | "
            f"`{finding.severity.value}` | `{finding.response_time_ms}ms` | `{slow}` | `{needs_more}` |"
        )

    lines.extend(["", "## Findings", ""])

    for finding in run.findings:
        lines.extend(
            [
                f"### {finding.test_id} - {finding.feature}",
                "",
                f"- Question: {finding.user_question}",
                f"- App answer: {finding.app_answer_summary}",
                f"- Benchmark: {finding.benchmark_summary}",
                f"- Benchmark source: {finding.benchmark_source or 'n/a'}",
                f"- Benchmark evidence: {', '.join(finding.benchmark_evidence) if finding.benchmark_evidence else 'none'}",
                f"- Response time: `{finding.response_time_ms}ms`",
                f"- Slow response threshold: `{finding.slow_threshold_ms}ms`",
                f"- Slow response flagged: {'yes' if finding.slow_response else 'no'}",
                f"- Verdict: `{finding.verdict.value}`",
                f"- Severity: `{finding.severity.value}`",
                f"- Issue: {finding.issue}",
                f"- Failure categories: {', '.join(finding.failure_category) if finding.failure_category else 'none'}",
                f"- Should have requested more data: {'yes' if finding.should_have_requested_more_data else 'no'}",
                f"- Required additional data: {', '.join(finding.required_additional_data) if finding.required_additional_data else 'none'}",
                f"- Recommended fix: {'; '.join(finding.recommended_fix) if finding.recommended_fix else 'none'}",
                "",
            ]
        )

    return "\n".join(lines).strip() + "\n"
