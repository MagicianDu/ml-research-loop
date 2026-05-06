from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_paperbench_adapter_demo_runs_end_to_end(tmp_path: Path) -> None:
    runtime_root = tmp_path / "paperbench-runtime"
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
            str(PROJECT_ROOT / "scripts" / "paperbench_adapter_demo.py"),
            "--runtime-root",
            str(runtime_root),
            "--json",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
    )

    assert proc.returncode == 0, proc.stdout
    payload = json.loads(proc.stdout)

    assert payload["status"] == "passed"
    assert payload["official_paperbench"] is False
    assert payload["paper_id"] == "mlrl-debug-paper"
    assert payload["agent_rollout"]["status"] == "completed"
    assert payload["reproduction"]["status"] == "completed"
    assert payload["grading"]["status"] == "completed"
    assert payload["grading"]["score"] > 0
    assert Path(payload["submission_dir"]).exists()
    assert Path(payload["reproduction_report_path"]).exists()
    assert Path(payload["grade_report_path"]).exists()
    assert Path(payload["benchmark_report_path"]).exists()

    grade_report = json.loads(
        Path(payload["grade_report_path"]).read_text(encoding="utf-8")
    )
    assert grade_report["score"] > 0
    assert grade_report["num_leaf_nodes"] == 3
