from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_mcp_client_patch_demo_exercises_client_proposal_loop(tmp_path: Path) -> None:
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
            str(PROJECT_ROOT / "scripts" / "mcp_client_patch_demo.py"),
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
    assert payload["tool_chain"] == [
        "research_task",
        "propose_hypotheses",
        "run_hypothesis_experiment",
        "review_research_results",
        "run_client_patch_experiment",
        "review_research_results",
    ]
    assert payload["change_proposal"]["change_type"] == "hyperparam"
    assert payload["change_proposal"]["target"] in (
        payload["initial_review"]["experiment_state"]["current_code"]["search_region"]
    )
    assert payload["client_patch"]["patch_execution"]["mode"] == "task_patch_only"
    assert payload["client_patch"]["patch_execution"]["target"] == (
        payload["change_proposal"]["target"]
    )
    assert payload["client_patch"]["patch_execution"]["task_patch"]["hyperparameter_space"]
    assert payload["client_patch"]["initial_review"]["status"] == "completed"
    assert payload["client_patch"]["final_review"]["status"] == "completed"
    assert payload["client_patch"]["loop_decision"]["decision"] in {"continue", "stop"}
    assert payload["final_review"]["status"] == "completed"
    assert "val_bpb" in payload["final_review"]["experiments"][0]["metrics"]
    assert Path(payload["result_file"]).exists()
