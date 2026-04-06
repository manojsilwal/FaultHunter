from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    target_base_url: str
    report_root: Path
    artifact_root: Path
    request_timeout_s: float
    browser_probe_enabled: bool
    browser_probe_timeout_s: float


def load_settings() -> Settings:
    repo_root = _repo_root()
    return Settings(
        repo_root=repo_root,
        # Default matches TradeTalk Vite dev server (port 5173) with API proxied to FastAPI :8000.
        # See tradetalkapp frontend/vite.config.js — run backend + `npm run dev` in frontend/.
        target_base_url=os.environ.get("TRADETALK_BASE_URL", "http://127.0.0.1:5173").rstrip("/"),
        report_root=Path(os.environ.get("FAULTHUNTER_REPORT_ROOT", repo_root / "reports")).resolve(),
        artifact_root=Path(os.environ.get("FAULTHUNTER_ARTIFACT_ROOT", repo_root / "artifacts")).resolve(),
        request_timeout_s=float(os.environ.get("FAULTHUNTER_TIMEOUT_S", "90")),
        browser_probe_enabled=os.environ.get("FAULTHUNTER_BROWSER_PROBE", "0").strip().lower() in {"1", "true", "yes"},
        browser_probe_timeout_s=float(os.environ.get("FAULTHUNTER_BROWSER_PROBE_TIMEOUT_S", "120")),
    )
