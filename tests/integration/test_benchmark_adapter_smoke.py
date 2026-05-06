from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_benchmark_adapter_smoke_runs_both_compatibility_demos(tmp_path: Path) -> None:
    runtime_root = tmp_path / "benchmark-runtime"
    env = {
        **os.environ,
        "PYTHONPATH": (
            f"{PROJECT_ROOT}{os.pathsep}"
            f"{PROJECT_ROOT / '.venv' / 'lib' / 'python3.13' / 'site-packages'}"
        ),
        "ML_RESEARCH_LOOP_PYTHON": sys.executable,
    }

    proc = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "benchmark_adapter_smoke.py"),
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
    payload = json.loads(proc.stdout.splitlines()[-1])

    assert payload["status"] == "passed"
    assert payload["official_scores_claimed"] is False
    assert [item["name"] for item in payload["results"]] == [
        "mle_bench",
        "paperbench",
    ]
    assert payload["results"][0]["status"] == "completed"
    assert payload["results"][0]["official_mle_bench"] is False
    assert Path(payload["results"][0]["benchmark_report_path"]).exists()
    assert payload["results"][1]["status"] == "passed"
    assert payload["results"][1]["official_paperbench"] is False
    assert payload["results"][1]["grading_score"] > 0
    assert Path(payload["results"][1]["benchmark_report_path"]).exists()
