from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..models import EvalRun, ReportKind
from .markdown import render_markdown


def _next_report_path(report_root: Path, run: EvalRun) -> Path:
    dt = datetime.fromisoformat(run.generated_at_utc.replace("Z", "+00:00"))
    year = f"{dt.year:04d}"
    if run.report_kind == ReportKind.DAILY:
        base_dir = report_root / "daily" / year
        stem = dt.strftime("%Y-%m-%d")
    else:
        base_dir = report_root / "manual" / year
        stem = dt.strftime("%Y-%m-%dT%H%M%SZ")

    base_dir.mkdir(parents=True, exist_ok=True)
    candidate = base_dir / f"{stem}.md"
    if not candidate.exists():
        return candidate

    idx = 2
    while True:
        candidate = base_dir / f"{stem}-r{idx}.md"
        if not candidate.exists():
            return candidate
        idx += 1


def write_run_outputs(run: EvalRun, report_root: Path, artifact_root: Path) -> EvalRun:
    report_path = _next_report_path(report_root, run)
    report_path.write_text(render_markdown(run), encoding="utf-8")

    latest_path = report_root / "latest.md"
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(report_path.read_text(encoding="utf-8"), encoding="utf-8")

    artifact_root.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_root / "latest-run.json"
    artifact_path.write_text(json.dumps(run.model_dump(mode="json"), indent=2), encoding="utf-8")

    run.report_path = str(report_path)
    artifact_path.write_text(json.dumps(run.model_dump(mode="json"), indent=2), encoding="utf-8")
    return run
