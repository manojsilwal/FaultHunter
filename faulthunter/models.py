from __future__ import annotations

from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, Field


class RunProfile(str, Enum):
    SMOKE = "smoke"
    DAILY = "daily"
    DEEP = "deep"


class ReportKind(str, Enum):
    MANUAL = "manual"
    DAILY = "daily"


class Verdict(str, Enum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TestCase(BaseModel):
    id: str
    feature: str
    user_question: str
    challenge_type: str
    required_freshness: str
    endpoint: str
    method: str = "GET"
    query: dict[str, Any] = Field(default_factory=dict)
    recommendation_expected: bool = False
    required_fields: list[str] = Field(default_factory=list)
    benchmark_symbol: Optional[str] = None
    parity_field: Optional[str] = None
    browser_probe_url: Optional[str] = None
    slow_latency_ms: int = 10000


class AppCapture(BaseModel):
    endpoint: str
    status_code: int
    latency_ms: int
    summary: str
    recommendation: Optional[str] = None
    confidence: Optional[float] = None
    freshness_timestamp: Optional[str] = None
    available_fields: list[str] = Field(default_factory=list)
    raw_payload: Optional[Union[dict[str, Any], str]] = None


class BenchmarkResult(BaseModel):
    source: str
    summary: str
    evidence: list[str] = Field(default_factory=list)
    reference_price: Optional[float] = None
    reference_symbol: Optional[str] = None
    freshness_timestamp: Optional[str] = None
    browser_probe_url: Optional[str] = None
    browser_probe_excerpt: Optional[str] = None
    unavailable_reason: Optional[str] = None


class Finding(BaseModel):
    test_id: str
    feature: str
    user_question: str
    app_answer_summary: str
    benchmark_summary: str
    benchmark_source: str = ""
    benchmark_evidence: list[str] = Field(default_factory=list)
    response_time_ms: int = 0
    slow_threshold_ms: int = 0
    slow_response: bool = False
    verdict: Verdict
    severity: Severity
    failure_category: list[str] = Field(default_factory=list)
    issue: str
    should_have_requested_more_data: bool = False
    required_additional_data: list[str] = Field(default_factory=list)
    recommended_fix: list[str] = Field(default_factory=list)


class EvalRun(BaseModel):
    run_id: str
    generated_at_utc: str
    profile: RunProfile
    report_kind: ReportKind
    target_base_url: str
    findings: list[Finding] = Field(default_factory=list)
    report_path: Optional[str] = None


class RunRequest(BaseModel):
    profile: RunProfile = RunProfile.SMOKE
    report_kind: ReportKind = ReportKind.MANUAL
    target_base_url: Optional[str] = None
