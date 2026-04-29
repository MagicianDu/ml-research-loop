from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_mcp_multi_round_demo_uses_review_patch_for_second_round(tmp_path: Path) -> None:
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
            str(PROJECT_ROOT / "scripts" / "mcp_multi_round_demo.py"),
            "--runtime-root",
            str(tmp_path / "mcp-runtime"),
            "--rounds",
            "2",
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
    assert payload["round_count"] == 2
    assert payload["tool_chain"] == [
        "research_task",
        "propose_hypotheses",
        "run_hypothesis_experiment",
        "review_research_results",
        "run_hypothesis_experiment",
        "review_research_results",
    ]
    first_round, second_round = payload["rounds"]
    assert first_round["task_id"] == "mcp-multi-round-r1"
    assert second_round["task_id"] == "mcp-multi-round-r2"
    assert second_round["input_task_patch"] == (
        first_round["review"]["experiment_state"]["next_round"]["task_patch"]
    )
    assert second_round["patched_task"]["program_md_overrides"]["hints"]
    assert second_round["patched_task"]["hyperparameter_space"] == (
        first_round["review"]["experiment_state"]["next_round"]["task_patch"]["hyperparameter_space"]
    )
    assert "val_bpb" in second_round["review"]["experiments"][0]["metrics"]
    assert second_round["review"]["experiment_state"]["planner_handoff"]["recommended_next_tool"] == (
        "run_hypothesis_experiment"
    )
    assert Path(second_round["result_file"]).exists()
