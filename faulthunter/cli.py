from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .config import load_settings
from .models import ReportKind, RunProfile
from .evaluation.runner import run_evaluation
from .reports.writer import write_run_outputs
from .spec_catalog import DEFAULT_SPEC_RELATIVE, emit_feature_spec


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run FaultHunter against a TradeTalk target.")
    parser.add_argument("--profile", choices=[p.value for p in RunProfile], default=RunProfile.SMOKE.value)
    parser.add_argument("--report-kind", choices=[k.value for k in ReportKind], default=ReportKind.MANUAL.value)
    parser.add_argument("--target-base-url", default=None)
    parser.add_argument(
        "--emit-feature-spec",
        metavar="PATH",
        nargs="?",
        const=str(DEFAULT_SPEC_RELATIVE),
        default=None,
        help=(
            "Write specs/FEATURE_TEST_SPEC.md auto-catalog from case_bank.py and exit. "
            "Optional PATH; default: specs/FEATURE_TEST_SPEC.md (relative to repo root)."
        ),
    )
    return parser.parse_args()


async def _run() -> None:
    args = parse_args()
    settings = load_settings()
    if args.emit_feature_spec is not None:
        raw = Path(args.emit_feature_spec)
        path = raw if raw.is_absolute() else (settings.repo_root / raw)
        emit_feature_spec(path)
        print(path)
        return
    target_base_url = (args.target_base_url or settings.target_base_url).rstrip("/")
    run = await run_evaluation(
        profile=RunProfile(args.profile),
        target_base_url=target_base_url,
        report_kind=ReportKind(args.report_kind),
        timeout_s=settings.request_timeout_s,
        repo_root=settings.repo_root,
        browser_probe_enabled=settings.browser_probe_enabled,
        browser_probe_timeout_s=settings.browser_probe_timeout_s,
    )
    run = write_run_outputs(run, settings.report_root, settings.artifact_root)
    print(run.report_path)


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
