from __future__ import annotations

import json
from collections import Counter
from urllib.parse import urlencode

from ..models import EvalRun, Finding, Severity, Verdict


_SEVERITY_ORDER = {
    Severity.CRITICAL: 4,
    Severity.HIGH: 3,
    Severity.MEDIUM: 2,
    Severity.LOW: 1,
}

_VERDICT_ORDER = {
    Verdict.FAIL: 3,
    Verdict.WARNING: 2,
    Verdict.PASS: 1,
}


def _priority_key(finding: Finding) -> tuple[int, int, int]:
    return (
        _VERDICT_ORDER.get(finding.verdict, 0),
        _SEVERITY_ORDER.get(finding.severity, 0),
        1 if finding.slow_response else 0,
    )


def _actionable_findings(run: EvalRun) -> list[Finding]:
    findings = [
        finding
        for finding in run.findings
        if finding.verdict != Verdict.PASS or finding.slow_response or finding.should_have_requested_more_data
    ]
    return sorted(findings, key=_priority_key, reverse=True)


def _healthy_findings(run: EvalRun) -> list[Finding]:
    return [finding for finding in run.findings if finding not in _actionable_findings(run)]


def _render_request_payload(method: str, payload: dict) -> str:
    if not payload:
        return "{}"
    if method.upper() == "GET":
        return urlencode(payload)
    return json.dumps(payload, sort_keys=True)


def _render_curl(run: EvalRun, finding: Finding) -> str:
    method = finding.method.upper()
    if method == "GET":
        url = f"{run.target_base_url}{finding.endpoint}"
        if finding.request_payload:
            url = f"{url}?{urlencode(finding.request_payload)}"
        return f"curl -sS '{url}'"
    payload = json.dumps(finding.request_payload, sort_keys=True)
    return (
        f"curl -sS -X {method} '{run.target_base_url}{finding.endpoint}' "
        f"-H 'content-type: application/json' -d '{payload}'"
    )


def _render_developer_prompt(run: EvalRun, actionable: list[Finding]) -> str:
    if not actionable:
        focus = "No actionable findings were produced in this run. Confirm parity and keep the system stable."
    else:
        top = ", ".join(finding.test_id for finding in actionable[:5])
        focus = (
            f"Fix the actionable findings in priority order: {top}. "
            "For each item, address the root cause, rerun the exact repro command from this report, and stop only when the finding clears."
        )

    return "\n".join(
        [
            "You are the TradeTalk developer agent.",
            f"Use this report as the single source of truth for the current evaluation run against {run.target_base_url}.",
            focus,
            "Prioritize `fail` before `warning`, and within the same verdict prioritize higher severity and user-facing recommendation risk.",
            "Do not only silence the symptom. Fix the underlying data, routing, schema, or latency issue described in each finding.",
            "After each fix, rerun the exact endpoint repro command from this report and verify the acceptance target for that finding.",
            "When all actionable findings are resolved, commit and push the changes.",
        ]
    )


def _render_fix_queue(run: EvalRun, actionable: list[Finding]) -> list[str]:
    lines = [
        "## Developer Fix Queue",
        "",
        "| Priority | Test | Endpoint | Verdict | Severity | Root Cause | Latency | Target |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for idx, finding in enumerate(actionable, start=1):
        target = "clear finding"
        if finding.slow_response:
            target = f"under {finding.slow_threshold_ms}ms"
        elif finding.should_have_requested_more_data:
            target = "return enough evidence or explicitly defer"
        lines.append(
            f"| `{idx}` | `{finding.test_id}` | `{finding.method} {finding.endpoint}` | "
            f"`{finding.verdict.value}` | `{finding.severity.value}` | "
            f"`{finding.diagnostic_root_cause or 'none'}` | `{finding.response_time_ms}ms` | `{target}` |"
        )
    if len(lines) == 4:
        lines.append("| `0` | `none` | `n/a` | `pass` | `low` | `none` | `0ms` | `monitor` |")
    lines.append("")
    return lines


def _render_summary(run: EvalRun) -> list[str]:
    counts = Counter(f.verdict for f in run.findings)
    slow_count = sum(1 for f in run.findings if f.slow_response)
    actionable = _actionable_findings(run)
    lines = [
        f"# FaultHunter Report - {run.generated_at_utc[:10]}",
        "",
        f"- Run ID: `{run.run_id}`",
        f"- Profile: `{run.profile.value}`",
        f"- Target: `{run.target_base_url}`",
        f"- Findings: pass={counts.get(Verdict.PASS, 0)} warning={counts.get(Verdict.WARNING, 0)} fail={counts.get(Verdict.FAIL, 0)}",
        f"- Slow responses flagged: `{slow_count}`",
        f"- Actionable findings: `{len(actionable)}`",
        "",
        "## Developer Agent Handoff",
        "",
        "```text",
        _render_developer_prompt(run, actionable),
        "```",
        "",
    ]
    lines.extend(_render_fix_queue(run, actionable))
    lines.extend(
        [
            "## Run Summary",
            "",
            "| Test | Feature | Verdict | Severity | Latency | Slow | More Data Needed |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for finding in run.findings:
        needs_more = "yes" if finding.should_have_requested_more_data else "no"
        slow = "yes" if finding.slow_response else "no"
        lines.append(
            f"| `{finding.test_id}` | `{finding.feature}` | `{finding.verdict.value}` | "
            f"`{finding.severity.value}` | `{finding.response_time_ms}ms` | `{slow}` | `{needs_more}` |"
        )
    lines.append("")
    return lines


def _render_diagnostic_probes(finding: Finding) -> list[str]:
    if not finding.diagnostic_probes:
        return []
    lines = [
        "| Probe | Endpoint | Status | Latency | Outcome | Note |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for probe in finding.diagnostic_probes:
        lines.append(
            f"| `{probe.name}` | `{probe.endpoint}` | `{probe.status_code}` | "
            f"`{probe.latency_ms}ms` | `{probe.outcome}` | {probe.note or 'none'} |"
        )
    lines.append("")
    return lines


def _render_parity_checks(finding: Finding) -> list[str]:
    if not finding.parity_checks:
        return []
    lines = [
        "| Metric | Status | App Field | App Value | Yahoo Value | Note |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for check in finding.parity_checks:
        lines.append(
            f"| `{check.metric}` | `{check.status}` | `{check.app_field or 'n/a'}` | "
            f"`{check.app_value if check.app_value is not None else 'n/a'}` | "
            f"`{check.benchmark_value if check.benchmark_value is not None else 'n/a'}` | "
            f"{check.note or 'none'} |"
        )
    lines.append("")
    return lines


def _render_finding(run: EvalRun, finding: Finding, *, priority: int | None = None) -> list[str]:
    priority_label = f"P{priority}" if priority is not None else "info"
    lines = [
        f"### {priority_label} - {finding.test_id} - {finding.feature}",
        "",
        f"- Endpoint: `{finding.method} {finding.endpoint}`",
        f"- User question: {finding.user_question}",
        f"- Why this matters: {finding.issue}",
        f"- Likely root cause: {finding.diagnostic_summary or finding.diagnostic_root_cause or 'none'}",
        f"- App answer: {finding.app_answer_summary}",
        f"- Benchmark: {finding.benchmark_summary}",
        f"- Benchmark source: {finding.benchmark_source or 'n/a'}",
        f"- Benchmark evidence: {', '.join(finding.benchmark_evidence) if finding.benchmark_evidence else 'none'}",
        f"- Parity summary: {finding.parity_summary or 'none'}",
        f"- Response time: `{finding.response_time_ms}ms`",
        f"- Slow threshold: `{finding.slow_threshold_ms}ms`",
        f"- Verdict: `{finding.verdict.value}`",
        f"- Severity: `{finding.severity.value}`",
        f"- Failure categories: {', '.join(finding.failure_category) if finding.failure_category else 'none'}",
        f"- Required additional data: {', '.join(finding.required_additional_data) if finding.required_additional_data else 'none'}",
        f"- Recommended fix: {'; '.join(finding.recommended_fix) if finding.recommended_fix else 'none'}",
        "",
        "**Reproduce**",
        "",
        "```bash",
        _render_curl(run, finding),
        "```",
        "",
        f"- Request payload: `{_render_request_payload(finding.method, finding.request_payload)}`",
        f"- Acceptance target: {'under ' + str(finding.slow_threshold_ms) + 'ms' if finding.slow_response else ('return enough evidence or defer safely' if finding.should_have_requested_more_data else 'clear the finding on rerun')}",
        "",
    ]
    if finding.diagnostic_root_cause or finding.diagnostic_evidence:
        lines.extend(
            [
                "**Diagnostics**",
                "",
                f"- Root cause label: {finding.diagnostic_root_cause or 'none'}",
                f"- Diagnostic evidence: {', '.join(finding.diagnostic_evidence) if finding.diagnostic_evidence else 'none'}",
                "",
            ]
        )
        lines.extend(_render_diagnostic_probes(finding))
    if finding.parity_checks:
        lines.extend(["**Parity Checks**", ""])
        lines.extend(_render_parity_checks(finding))
    return lines


def render_markdown(run: EvalRun) -> str:
    actionable = _actionable_findings(run)
    healthy = _healthy_findings(run)
    lines = _render_summary(run)
    lines.extend(["## Actionable Findings", ""])
    if not actionable:
        lines.extend(["No actionable findings in this run.", ""])
    else:
        for idx, finding in enumerate(actionable, start=1):
            lines.extend(_render_finding(run, finding, priority=idx))

    lines.extend(["## Healthy Findings", ""])
    if not healthy:
        lines.extend(["No fully healthy findings in this run.", ""])
    else:
        for finding in healthy:
            lines.extend(_render_finding(run, finding))

    return "\n".join(lines).strip() + "\n"
