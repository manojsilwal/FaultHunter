from __future__ import annotations

from dataclasses import dataclass, field

from ..models import AppCapture, DiagnosticProbe, Finding, TestCase


@dataclass
class DiagnosticResult:
    root_cause: str = ""
    summary: str = ""
    evidence: list[str] = field(default_factory=list)
    probes: list[DiagnosticProbe] = field(default_factory=list)


def _probe_sentence(probe: DiagnosticProbe) -> str:
    return (
        f"{probe.name} probe on {probe.endpoint} returned {probe.status_code} "
        f"in {probe.latency_ms}ms ({probe.outcome})."
    )


def _diagnose_failure(capture: AppCapture, health_probe: DiagnosticProbe) -> DiagnosticResult:
    error_text = f"{capture.error_type or ''} {capture.error_detail or ''} {capture.summary}".lower()
    evidence = [_probe_sentence(health_probe)]

    if "connect" in error_text or "connection attempts failed" in error_text or "could not connect" in error_text:
        if health_probe.status_code == 599:
            return DiagnosticResult(
                root_cause="service_unreachable",
                summary="The endpoint failed because the TradeTalk service itself was not reachable during the health probe.",
                evidence=evidence + [
                    "The same host failed a lightweight service-health probe, so this looks like a process or listener issue rather than a single broken route."
                ],
                probes=[health_probe],
            )
        return DiagnosticResult(
            root_cause="route_specific_connectivity_issue",
            summary="The endpoint failed to connect, but the service-health probe stayed up, so this looks route-specific or intermittent.",
            evidence=evidence,
            probes=[health_probe],
        )

    if "timeout" in error_text:
        if health_probe.status_code == 599 or health_probe.latency_ms > 3000:
            return DiagnosticResult(
                root_cause="service_wide_timeout",
                summary="The endpoint timed out and the health probe was also unhealthy or very slow, pointing to service-wide degradation.",
                evidence=evidence,
                probes=[health_probe],
            )
        return DiagnosticResult(
            root_cause="endpoint_timeout",
            summary="The endpoint timed out even though the service-health probe stayed responsive, which points to route-specific heavy work or a hung dependency.",
            evidence=evidence,
            probes=[health_probe],
        )

    if capture.status_code in {400, 422}:
        return DiagnosticResult(
            root_cause="request_contract_failure",
            summary="The endpoint was reachable, but it rejected the request shape or validation contract.",
            evidence=evidence,
            probes=[health_probe],
        )

    if capture.status_code >= 500:
        if health_probe.status_code == 599:
            return DiagnosticResult(
                root_cause="service_instability",
                summary="The endpoint failed with a server-side error and the health probe also failed, so the service looks broadly unstable.",
                evidence=evidence,
                probes=[health_probe],
            )
        return DiagnosticResult(
            root_cause="endpoint_server_error",
            summary="The service stayed up on a lightweight probe, so this looks like a route-specific backend exception rather than a full outage.",
            evidence=evidence,
            probes=[health_probe],
        )

    return DiagnosticResult(
        root_cause="unknown_failure",
        summary="The endpoint failed, and FaultHunter could not narrow the issue beyond the current transport and health probes.",
        evidence=evidence,
        probes=[health_probe],
    )


def _diagnose_slow_response(
    case: TestCase,
    capture: AppCapture,
    health_probe: DiagnosticProbe,
    replay_capture: AppCapture,
) -> DiagnosticResult:
    evidence = [
        f"Initial latency was {capture.latency_ms}ms against a {case.slow_latency_ms}ms threshold.",
        _probe_sentence(health_probe),
        (
            f"Replay of {case.endpoint} completed in {replay_capture.latency_ms}ms "
            f"with status {replay_capture.status_code}."
        ),
    ]

    if replay_capture.status_code >= 400:
        return DiagnosticResult(
            root_cause="slow_then_failed",
            summary="The endpoint was slow on the first pass and failed on replay, which points to instability rather than simple slowness.",
            evidence=evidence,
            probes=[health_probe],
        )

    if health_probe.status_code == 599 or health_probe.latency_ms > 3000:
        return DiagnosticResult(
            root_cause="service_wide_latency",
            summary="The endpoint was slow and the service-health probe was also degraded, so the slowness looks broader than this route alone.",
            evidence=evidence,
            probes=[health_probe],
        )

    if replay_capture.latency_ms <= case.slow_latency_ms:
        return DiagnosticResult(
            root_cause="cold_cache_or_warmup",
            summary="The replay fell back under the threshold while the service-health probe stayed healthy, which suggests a cold-cache or warm-up delay.",
            evidence=evidence,
            probes=[health_probe],
        )

    return DiagnosticResult(
        root_cause="endpoint_specific_latency",
        summary="The health probe stayed healthy, but the replay remained slow, which points to endpoint-specific compute or retrieval cost.",
        evidence=evidence,
        probes=[health_probe],
    )


async def analyze_case_diagnostics(case: TestCase, capture: AppCapture, finding: Finding, target) -> DiagnosticResult:
    needs_diagnostics = capture.status_code >= 400 or finding.slow_response
    if not needs_diagnostics:
        return DiagnosticResult()

    health_probe = await target.probe("/openapi.json", name="service_health")

    if capture.status_code >= 400:
        return _diagnose_failure(capture, health_probe)

    replay_capture = await target.execute(case)
    return _diagnose_slow_response(case, capture, health_probe, replay_capture)
