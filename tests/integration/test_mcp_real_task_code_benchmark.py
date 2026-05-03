from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_mcp_real_task_code_benchmark_applies_review_planned_patch(tmp_path: Path) -> None:
    env = {
        **os.environ,
        "PYTHONPATH": (
            f"{PROJECT_ROOT}{os.pathsep}"
            f"{PROJECT_ROOT / '.venv' / 'lib' / 'python3.13' / 'site-packages'}"
        ),
        "ML_RESEARCH_LOOP_PYTHON": sys.executable,
        "ML_RESEARCH_LOOP_ALLOWED_ROOTS": str(tmp_path / "mcp-runtime"),
    }

    proc = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "mcp_real_task_code_benchmark.py"),
            "--runtime-root",
            str(tmp_path / "mcp-runtime"),
            "--max-experiments",
            "1",
            "--experiment-duration",
            "30",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=180,
    )

    assert proc.returncode == 0, proc.stdout
    payload = json.loads(proc.stdout.splitlines()[-1])

    assert payload["status"] == "completed"
    assert payload["data_source"] == "real_file"
    assert payload["run_budget"] == {
        "max_experiments": 1,
        "experiment_duration_seconds": 30,
    }
    assert payload["patch_planning"]["source"] == "code_change_plan.next_experiment_plan"
    assert payload["code_patch"]["status"] == "applied"
    assert payload["code_patch"]["patch_execution"]["mode"] == "workspace_unified_diff"
    assert payload["code_patch"]["patch_execution"]["changed_files"] == ["program.md", "train.py"]
    assert payload["code_patch"]["patch_execution"]["test_check"]["status"] == "passed"
    assert payload["code_patch"]["post_patch_review"]["status"] == "completed"
    assert payload["code_patch"]["loop_decision"]["reason_category"] in {
        "metric_improved",
        "metric_not_improved",
    }
    assert payload["post_patch_review"]["status"] == "completed"
    state = payload["post_patch_review"]["experiment_state"]
    assert state["dataset_profile"]["exists"] is True
    assert state["dataset_profile"]["risks"] == []
    assert state["code_change_plan"]["next_experiment_plan"]["proposed_task_patch"]
    target = payload["patch_planning"]["target"]
    assert state["current_code"]["search_region"][target] == payload["patch_planning"]["proposed_value"]
