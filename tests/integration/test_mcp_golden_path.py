from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_mcp_golden_path_runs_research_to_review(tmp_path: Path) -> None:
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
            str(PROJECT_ROOT / "scripts" / "mcp_golden_path.py"),
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
        timeout=120,
    )

    assert proc.returncode == 0, proc.stdout
    payload = json.loads(proc.stdout.splitlines()[-1])

    assert payload["status"] == "completed"
    assert payload["tool_chain"] == [
        "research_task",
        "propose_hypotheses",
        "run_hypothesis_experiment",
        "review_research_results",
    ]
    assert payload["research_context"]["sources"][0]["title"] == "Attention Is All You Need"
    assert payload["review"]["hypotheses"][0]["hypothesis_id"] == "hyp-001"
    assert payload["review"]["experiments"][0]["hypothesis_id"] == "hyp-001"
    assert payload["review"]["experiment_state"]["planner_handoff"]["recommended_next_tool"] == (
        "run_hypothesis_experiment"
    )
    assert payload["review"]["experiment_state"]["current_code"]["search_region"]
    assert Path(payload["result_file"]).exists()
