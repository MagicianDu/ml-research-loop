from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_mcp_client_acceptance_uses_stdio_server_contract() -> None:
    env = {
        **os.environ,
        "PYTHONPATH": (
            f"{PROJECT_ROOT}{os.pathsep}"
            f"{PROJECT_ROOT / '.venv' / 'lib' / 'python3.13' / 'site-packages'}"
        ),
    }

    proc = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "mcp_client_acceptance.py"),
            "--python",
            sys.executable,
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=30,
    )

    assert proc.returncode == 0, proc.stdout
    payload = json.loads(proc.stdout.splitlines()[-1])

    assert payload["status"] == "passed"
    assert payload["server_info"]["name"] == "ml-research-loop"
    assert payload["manifest"]["contract_version"] == "2026-04-30.preview.v1"
    assert payload["manifest"]["schema_versions"]["service_manifest"] == (
        "2026-04-30.preview.v1"
    )
    assert payload["manifest"]["compatibility"]["status"] == "preview"
    assert payload["manifest"]["architecture"] == "hybrid_client_planner_server_executor"
    assert "evidence_quality" in payload["manifest"]["planning_signals"]
    assert "provider_coverage" in payload["manifest"]["planning_signals"]
    assert "research_evidence_gate" in payload["manifest"]["planning_signals"]
    assert "dataset_profile" in payload["manifest"]["planning_signals"]
    assert "code_change_plan" in payload["manifest"]["planning_signals"]
    assert (
        "code_change_plan.next_experiment_plan.proposed_task_patch"
        in payload["manifest"]["planning_signals"]
    )
    assert (
        "code_change_plan.next_experiment_plan.dry_run_validation"
        in payload["manifest"]["planning_signals"]
    )
    assert "planner_actions" in payload["manifest"]["planning_signals"]
    assert set(payload["manifest"]["tool_contracts"]) >= set(
        payload["manifest"]["required_tools"]
    )
    assert payload["missing_required_tools"] == []
