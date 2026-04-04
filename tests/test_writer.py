from pathlib import Path

from faulthunter.models import EvalRun, ReportKind, RunProfile
from faulthunter.reports.writer import write_run_outputs


def test_write_run_outputs_creates_report_and_latest(tmp_path: Path):
    run = EvalRun(
        run_id="run-1",
        generated_at_utc="2026-04-03T12:30:00+00:00",
        profile=RunProfile.SMOKE,
        report_kind=ReportKind.DAILY,
        target_base_url="http://localhost:8000",
        findings=[],
    )

    updated = write_run_outputs(run, tmp_path / "reports", tmp_path / "artifacts")

    assert updated.report_path is not None
    assert Path(updated.report_path).exists()
    assert (tmp_path / "reports" / "latest.md").exists()
    assert (tmp_path / "artifacts" / "latest-run.json").exists()
