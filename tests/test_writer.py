from pathlib import Path

from faulthunter.models import EvalRun, ReportKind, RunProfile
from faulthunter.reports.writer import write_run_outputs


def test_write_run_outputs_creates_report_and_latest(tmp_path: Path):
    run = EvalRun(
        run_id="run-1",
        generated_at_utc="2026-04-03T12:30:00+00:00",
        profile=RunProfile.SMOKE,
        report_kind=ReportKind.MANUAL,
        target_base_url="http://localhost:8000",
        findings=[],
    )

    updated = write_run_outputs(run, tmp_path / "reports", tmp_path / "artifacts")

    assert updated.report_path is not None
    assert Path(updated.report_path).exists()
    assert (tmp_path / "reports" / "latest.md").exists()
    assert (tmp_path / "artifacts" / "latest-run.json").exists()


def test_daily_write_updates_single_daily_file_without_latest(tmp_path: Path):
    run = EvalRun(
        run_id="run-2",
        generated_at_utc="2026-04-03T22:00:00+00:00",
        profile=RunProfile.DAILY,
        report_kind=ReportKind.DAILY,
        target_base_url="http://localhost:8000",
        findings=[],
    )

    updated = write_run_outputs(run, tmp_path / "reports", tmp_path / "artifacts")

    expected = tmp_path / "reports" / "daily" / "2026" / "2026-04-03.md"
    assert Path(updated.report_path) == expected
    assert expected.exists()
    assert not (tmp_path / "reports" / "latest.md").exists()


def test_daily_write_overwrites_same_file_for_same_day(tmp_path: Path):
    reports_root = tmp_path / "reports"
    artifacts_root = tmp_path / "artifacts"
    first_run = EvalRun(
        run_id="run-3",
        generated_at_utc="2026-04-03T10:00:00+00:00",
        profile=RunProfile.DAILY,
        report_kind=ReportKind.DAILY,
        target_base_url="http://localhost:8000",
        findings=[],
    )
    second_run = EvalRun(
        run_id="run-4",
        generated_at_utc="2026-04-03T22:30:00+00:00",
        profile=RunProfile.DAILY,
        report_kind=ReportKind.DAILY,
        target_base_url="http://localhost:8000",
        findings=[],
    )

    first = write_run_outputs(first_run, reports_root, artifacts_root)
    second = write_run_outputs(second_run, reports_root, artifacts_root)

    assert first.report_path == second.report_path
    report_path = Path(second.report_path)
    assert report_path.read_text(encoding="utf-8").startswith("# FaultHunter Report - 2026-04-03")
    assert "run-4" in report_path.read_text(encoding="utf-8")
