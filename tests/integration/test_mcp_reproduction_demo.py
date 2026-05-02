from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_mcp_reproduction_demo_runs(tmp_path: Path) -> None:
    runtime_root = tmp_path / "mcp-runtime"
    env = {
        **os.environ,
        "PYTHONPATH": (
            f"{PROJECT_ROOT}{os.pathsep}"
            f"{PROJECT_ROOT / '.venv' / 'lib' / 'python3.13' / 'site-packages'}"
        ),
        "ML_RESEARCH_LOOP_PYTHON": sys.executable,
        "ML_RESEARCH_LOOP_ALLOWED_ROOTS": str(runtime_root),
    }

    proc = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "mcp_reproduction_demo.py"),
            "--runtime-root",
            str(runtime_root),
            "--json",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
    )

    assert proc.returncode == 0, proc.stdout
    payload = json.loads(proc.stdout)

    assert payload["status"] == "passed"
    assert payload["reproduction"]["readiness"]["status"] == "ready"
    assert payload["grade_report"]["score"] >= 0
    assert payload["grade_report"]["num_leaf_nodes"] == 2
