# FaultHunter

FaultHunter is a standalone evaluator for TradeTalk. It probes TradeTalk's public
API surfaces, judges whether the app had enough data to answer safely, and writes
daily Markdown reports back into this repo.

Each report is now designed as a single-file developer handoff: one Markdown file
contains the prioritized fix queue, exact repro commands, likely root-cause notes,
acceptance targets, and the supporting parity/diagnostic evidence.

Daily runs intentionally update exactly one repo report file for that day:
`reports/daily/YYYY/YYYY-MM-DD.md`.

## What ships in this first slice

- FastAPI service for manual evaluation runs
- CLI runner for local and scheduled execution
- Seeded case bank for core TradeTalk features
- TradeTalk HTTP target adapter
- Heuristic sufficiency judge focused on stale/incomplete-data failures
- Yahoo-backed parity depth checks for price and available market/fundamental metrics
- One-level-deeper diagnostics for slow or failed endpoints, including service-health probes and replay-based latency analysis
- Markdown report generation under `reports/`
- GitHub Actions workflow that can generate, artifact, and commit daily reports
- Playwright browser probe scaffold for targeted evidence capture

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
npm install
python -m faulthunter.cli --profile smoke --report-kind manual --target-base-url http://localhost:8000
PYTHONPATH=. pytest
```

To use the browser probe locally:

```bash
npm run browser:install
node browser/probe.mjs https://finance.yahoo.com/quote/AAPL
```

The scheduled GitHub Action enables browser probes automatically for the daily
run and still updates exactly one report file per day:
`reports/daily/YYYY/YYYY-MM-DD.md`.

## Environment

- `TRADETALK_BASE_URL` default target URL
- `FAULTHUNTER_REPORT_ROOT` default `./reports`
- `FAULTHUNTER_ARTIFACT_ROOT` default `./artifacts`
- `FAULTHUNTER_TIMEOUT_S` default `90`
- `FAULTHUNTER_BROWSER_PROBE=1` to attach browser evidence when supported

## Run the API

```bash
uvicorn faulthunter.main:app --reload --port 8010
```
