from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def run_browser_probe(repo_root: Path, url: str, timeout_s: float = 120.0) -> dict[str, Any] | None:
    script = repo_root / "browser" / "probe.mjs"
    if not script.exists():
        return None

    try:
        proc = subprocess.run(
            ["node", str(script), url],
            cwd=str(repo_root),
            check=True,
            text=True,
            capture_output=True,
            timeout=timeout_s,
        )
    except Exception:
        return None

    try:
        return json.loads(proc.stdout.strip())
    except json.JSONDecodeError:
        return None
