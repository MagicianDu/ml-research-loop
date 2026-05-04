from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from scripts import mcp_client_acceptance


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
    assert payload["manifest"]["execution_sandbox"]["status"] == "enforced"
    assert payload["compatibility_check"]["status"] == "compatible"
    assert payload["compatibility_check"]["expected_contract_version"] == (
        "2026-04-30.preview.v1"
    )
    assert payload["compatibility_check"]["migration_required"] is False
    assert (
        payload["manifest"]["execution_sandbox"]["allowed_roots_env"]
        == "ML_RESEARCH_LOOP_ALLOWED_ROOTS"
    )
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
    assert payload["manifest"]["recommended_skills"] == [
        "ml-research-loop-planner",
        "ml-research-loop-reproduction",
        "ml-research-loop-experiment-optimizer",
        "ml-research-loop-operator",
    ]
    assert set(payload["manifest"]["skill_contracts"]) == set(
        payload["manifest"]["recommended_skills"]
    )
    assert payload["compatibility_check"]["missing_skill_contracts"] == []
    assert payload["compatibility_check"]["skill_contract_mismatches"] == []
    assert payload["missing_required_tools"] == []


def test_client_acceptance_compatibility_reports_contract_mismatch() -> None:
    manifest = {
        "contract_version": "2099-01-01.preview.v9",
        "schema_versions": {
            "service_manifest": "2099-01-01.preview.v9",
            "tool_inputs": "2099-01-01.preview.v9",
            "tool_outputs": "2099-01-01.preview.v9",
            "runtime_artifacts": "2099-01-01.preview.v9",
        },
        "required_tools": ["research_task"],
        "tool_contracts": {
            "research_task": {
                "input_schema_version": "2099-01-01.preview.v9",
                "output_schema_version": "2099-01-01.preview.v9",
            }
        },
    }

    report = mcp_client_acceptance.check_manifest_compatibility(
        manifest=manifest,
        tool_names=["research_task"],
        expected_contract_version="2026-04-30.preview.v1",
    )

    assert report["status"] == "incompatible"
    assert report["migration_required"] is True
    assert report["actual_contract_version"] == "2099-01-01.preview.v9"
    assert report["schema_mismatches"] == [
        {
            "schema": "service_manifest",
            "expected": "2026-04-30.preview.v1",
            "actual": "2099-01-01.preview.v9",
        },
        {
            "schema": "tool_inputs",
            "expected": "2026-04-30.preview.v1",
            "actual": "2099-01-01.preview.v9",
        },
        {
            "schema": "tool_outputs",
            "expected": "2026-04-30.preview.v1",
            "actual": "2099-01-01.preview.v9",
        },
        {
            "schema": "runtime_artifacts",
            "expected": "2026-04-30.preview.v1",
            "actual": "2099-01-01.preview.v9",
        },
    ]
    assert any("contract_version" in hint for hint in report["migration_hints"])


def test_client_acceptance_compatibility_reports_missing_tool_contract() -> None:
    manifest = {
        "contract_version": "2026-04-30.preview.v1",
        "schema_versions": {
            "service_manifest": "2026-04-30.preview.v1",
            "tool_inputs": "2026-04-30.preview.v1",
            "tool_outputs": "2026-04-30.preview.v1",
            "runtime_artifacts": "2026-04-30.preview.v1",
        },
        "required_tools": ["research_task", "run_hypothesis_experiment"],
        "tool_contracts": {
            "research_task": {
                "input_schema_version": "2026-04-30.preview.v1",
                "output_schema_version": "2026-04-30.preview.v1",
            }
        },
    }

    report = mcp_client_acceptance.check_manifest_compatibility(
        manifest=manifest,
        tool_names=["research_task"],
        expected_contract_version="2026-04-30.preview.v1",
    )

    assert report["status"] == "incompatible"
    assert report["missing_required_tools"] == ["run_hypothesis_experiment"]
    assert report["missing_tool_contracts"] == ["run_hypothesis_experiment"]
    assert report["migration_required"] is True
    assert any("missing required MCP tools" in hint for hint in report["migration_hints"])


def test_client_acceptance_compatibility_reports_skill_contract_mismatch() -> None:
    manifest = {
        "contract_version": "2026-04-30.preview.v1",
        "schema_versions": {
            "service_manifest": "2026-04-30.preview.v1",
            "tool_inputs": "2026-04-30.preview.v1",
            "tool_outputs": "2026-04-30.preview.v1",
            "runtime_artifacts": "2026-04-30.preview.v1",
        },
        "required_tools": ["get_service_manifest"],
        "tool_contracts": {
            "get_service_manifest": {
                "input_schema_version": "2026-04-30.preview.v1",
                "output_schema_version": "2026-04-30.preview.v1",
            }
        },
        "recommended_skills": [
            "ml-research-loop-planner",
            "ml-research-loop-operator",
        ],
        "skill_contracts": {
            "ml-research-loop-planner": {
                "contract_version": "2099-01-01.preview.v9",
            }
        },
    }

    report = mcp_client_acceptance.check_manifest_compatibility(
        manifest=manifest,
        tool_names=["get_service_manifest"],
        expected_contract_version="2026-04-30.preview.v1",
    )

    assert report["status"] == "incompatible"
    assert report["missing_skill_contracts"] == ["ml-research-loop-operator"]
    assert report["skill_contract_mismatches"] == [
        {
            "skill": "ml-research-loop-planner",
            "field": "contract_version",
            "expected": "2026-04-30.preview.v1",
            "actual": "2099-01-01.preview.v9",
        }
    ]
    assert report["migration_required"] is True
    assert any("skill contract" in hint for hint in report["migration_hints"])
