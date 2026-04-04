from faulthunter.case_bank import build_case_bank
from faulthunter.evaluation.capture import build_capture
from faulthunter.models import RunProfile
from faulthunter.verifiers.research import _build_parity_checks


def test_decision_terminal_depth_parity_checks_cover_price_and_quality_rows():
    case = build_case_bank(RunProfile.SMOKE)[0]
    capture = build_capture(
        case,
        status_code=200,
        latency_ms=1200,
        payload={
            "generated_at_utc": "2026-04-04T02:40:30.023234+00:00",
            "valuation": {"current_price_usd": 255.92},
            "verdict": {"headline_verdict": "NEUTRAL"},
            "quality": {
                "rows": [
                    {"id": "margin", "value_label": "45.5%"},
                    {"id": "current_ratio", "value_label": "1.25"},
                    {"id": "fcf", "value_label": "$98.0B"},
                ]
            },
        },
    )
    snapshot = {
        "price": 255.5,
        "gross_margins_pct": 44.9,
        "current_ratio": 1.22,
        "free_cashflow": 99_000_000_000.0,
    }

    checks = _build_parity_checks(case, capture, snapshot)

    assert [check.metric for check in checks] == [
        "current_price",
        "gross_margin_pct",
        "current_ratio",
        "free_cashflow",
    ]
    assert checks[0].status == "match"
    assert checks[1].status == "match"
    assert checks[2].status == "match"
    assert checks[3].status == "match"
