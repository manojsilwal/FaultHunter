from __future__ import annotations

from fastapi import FastAPI

from .config import load_settings
from .evaluation.runner import run_evaluation
from .models import RunRequest
from .reports.writer import write_run_outputs

app = FastAPI(
    title="FaultHunter",
    version="0.1.0",
    description="Standalone evaluator for TradeTalk surfaces.",
)


@app.get("/healthz")
async def healthz():
    settings = load_settings()
    return {
        "status": "ok",
        "target_base_url": settings.target_base_url,
    }


@app.post("/evaluation/run")
async def evaluation_run(req: RunRequest):
    settings = load_settings()
    target_base_url = (req.target_base_url or settings.target_base_url).rstrip("/")
    run = await run_evaluation(
        profile=req.profile,
        target_base_url=target_base_url,
        report_kind=req.report_kind,
        timeout_s=settings.request_timeout_s,
        repo_root=settings.repo_root,
        browser_probe_enabled=settings.browser_probe_enabled,
        browser_probe_timeout_s=settings.browser_probe_timeout_s,
    )
    run = write_run_outputs(run, settings.report_root, settings.artifact_root)
    return run.model_dump(mode="json")
