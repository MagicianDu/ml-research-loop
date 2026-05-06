from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import pytest

from lib import mcp_service


def _request(request_id: int, method: str, params: dict | None = None) -> dict:
    request = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        request["params"] = params
    return request


@pytest.fixture(autouse=True)
def allow_tmp_execution_roots(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("ML_RESEARCH_LOOP_ALLOWED_ROOTS", str(tmp_path))


def test_initialize_returns_server_capabilities() -> None:
    response = mcp_service.handle_request(
        _request(1, "initialize", {"protocolVersion": "2024-11-05"})
    )

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert response["result"]["serverInfo"] == {
        "name": "ml-research-loop",
        "version": "0.1.0",
    }
    assert response["result"]["capabilities"] == {"tools": {}}


def test_tools_list_exposes_research_loop_tools() -> None:
    response = mcp_service.handle_request(_request(2, "tools/list"))

    tool_names = {tool["name"] for tool in response["result"]["tools"]}
    assert {
        "run_fresh_demo",
        "run_autoresearch",
        "run_ai_autoresearch",
        "get_service_manifest",
        "get_experiment_status",
        "get_experiment_result",
        "get_experiment_logs",
        "run_client_patch_experiment",
        "apply_client_code_patch",
        "run_next_experiment_from_review",
    }.issubset(tool_names)
    research_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "research_task"
    )
    assert research_tool["inputSchema"]["properties"]["query_fanout"] == {
        "type": "boolean",
        "default": True,
        "description": "Use query_plan variants when a backend returns too few sources.",
    }


def test_ping_returns_empty_result() -> None:
    response = mcp_service.handle_request(_request(5, "ping"))

    assert response == {"jsonrpc": "2.0", "id": 5, "result": {}}


def test_tools_call_wraps_json_payload_as_text_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        mcp_service.TOOL_HANDLERS,
        "run_fresh_demo",
        lambda arguments: {"status": "completed", "runtime_root": arguments["runtime_root"]},
    )

    response = mcp_service.handle_request(
        _request(
            3,
            "tools/call",
            {
                "name": "run_fresh_demo",
                "arguments": {"runtime_root": "/tmp/ml-loop-demo"},
            },
        )
    )

    assert response["id"] == 3
    assert response["result"]["content"][0]["type"] == "text"
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload == {"status": "completed", "runtime_root": "/tmp/ml-loop-demo"}


def test_initialized_notification_returns_no_response() -> None:
    assert mcp_service.handle_request(
        {"jsonrpc": "2.0", "method": "notifications/initialized"}
    ) is None


def test_unknown_tool_returns_tool_error_content() -> None:
    response = mcp_service.handle_request(
        _request(4, "tools/call", {"name": "missing_tool", "arguments": {}})
    )

    assert response["id"] == 4
    assert response["result"]["isError"] is True
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["error"] == "Unknown MCP tool: missing_tool"


def test_autoresearch_timeout_is_unbounded_without_explicit_mcp_budget() -> None:
    assert mcp_service.subprocess_timeout(
        arguments={},
        experiment_duration=300,
        default_experiments=None,
    ) is None


def test_timeout_scales_with_explicit_experiment_count() -> None:
    assert mcp_service.subprocess_timeout(
        arguments={"max_experiments": 3},
        experiment_duration=300,
        default_experiments=None,
    ) == 990


def test_run_ai_autoresearch_tool_uses_mock_provider(monkeypatch, tmp_path) -> None:
    task_config = tmp_path / "task.json"
    task_config.write_text("{}", encoding="utf-8")
    result_file = tmp_path / "result.json"
    result_file.write_text('{"task_id": "ai-task", "status": "completed"}', encoding="utf-8")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=(
                f"RESULT_FILE={result_file}\n"
                "STATUS=completed\n"
                "BEST_VAL=0.42\n"
                "EXPERIMENTS=1\n"
            ),
        )

    monkeypatch.setattr(mcp_service, "run_mcp_subprocess", fake_run)

    payload = mcp_service.run_ai_autoresearch_tool({
        "task_config": str(task_config),
        "workspace": str(tmp_path / "workdir"),
        "runtime_root": str(tmp_path),
        "llm_provider": "mock",
        "mock_response": {
            "change_type": "hyperparam",
            "target": "DEPTH",
            "current_value": "1",
            "proposed_value": "2",
            "reason": "test",
            "confidence": 0.9,
        },
        "max_experiments": 1,
        "experiment_duration": 5,
    })

    assert payload["status"] == "completed"
    assert payload["result"]["task_id"] == "ai-task"
    assert str(mcp_service.PROJECT_ROOT / "scripts" / "ai_autoresearch_run.py") in captured["cmd"]
    assert "--mock" in captured["cmd"]
    assert "--mock-response" in captured["cmd"]
    assert "--workspace" in captured["cmd"]


def test_run_ai_autoresearch_tool_passes_real_provider_selection(monkeypatch, tmp_path) -> None:
    task_config = tmp_path / "task.json"
    task_config.write_text("{}", encoding="utf-8")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout="STATUS=completed\nEXPERIMENTS=0\n",
        )

    monkeypatch.setattr(mcp_service, "run_mcp_subprocess", fake_run)

    payload = mcp_service.run_ai_autoresearch_tool({
        "task_config": str(task_config),
        "runtime_root": str(tmp_path),
        "llm_provider": "openai",
        "llm_model": "gpt-5.5",
        "max_experiments": 1,
        "experiment_duration": 5,
    })

    assert payload["status"] == "completed"
    assert "--mock" not in captured["cmd"]
    assert "--llm-provider" in captured["cmd"]
    assert "--llm-model" in captured["cmd"]
    assert "openai" in captured["cmd"]
    assert "gpt-5.5" in captured["cmd"]


def test_run_autoresearch_rejects_task_config_outside_allowed_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    monkeypatch.setenv("ML_RESEARCH_LOOP_ALLOWED_ROOTS", str(runtime_root))
    outside_root = tmp_path / "outside"
    outside_root.mkdir()
    task_config = outside_root / "task.json"
    task_config.write_text("{}", encoding="utf-8")

    response = mcp_service.handle_request(
        _request(
            6,
            "tools/call",
            {
                "name": "run_autoresearch",
                "arguments": {
                    "task_config": str(task_config),
                    "runtime_root": str(runtime_root),
                    "experiment_duration": 5,
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])
    assert response["result"]["isError"] is True
    assert payload["status"] == "failed"
    assert payload["field"] == "task_config"
    assert payload["security_policy"]["allowed_roots_env"] == "ML_RESEARCH_LOOP_ALLOWED_ROOTS"


def test_run_autoresearch_rejects_workspace_outside_runtime_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("ML_RESEARCH_LOOP_ALLOWED_ROOTS", str(runtime_root))
    task_dir = runtime_root / "tasks"
    task_dir.mkdir(parents=True)
    task_config = task_dir / "task.json"
    task_config.write_text("{}", encoding="utf-8")
    outside_workspace = tmp_path / "outside-workspace"

    response = mcp_service.handle_request(
        _request(
            7,
            "tools/call",
            {
                "name": "run_autoresearch",
                "arguments": {
                    "task_config": str(task_config),
                    "runtime_root": str(runtime_root),
                    "workspace": str(outside_workspace),
                    "experiment_duration": 5,
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])
    assert response["result"]["isError"] is True
    assert payload["status"] == "failed"
    assert payload["field"] == "workspace"
    assert "runtime_root" in payload["error"]


def test_run_autoresearch_allows_execution_paths_inside_allowed_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("ML_RESEARCH_LOOP_ALLOWED_ROOTS", str(runtime_root))
    task_dir = runtime_root / "tasks"
    result_dir = runtime_root / "results"
    workspace = runtime_root / "workdir" / "safe-task"
    task_dir.mkdir(parents=True)
    result_dir.mkdir()
    task_config = task_dir / "safe-task.json"
    result_file = result_dir / "safe-task.json"
    task_config.write_text("{}", encoding="utf-8")
    result_file.write_text('{"task_id": "safe-task", "status": "completed"}', encoding="utf-8")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=f"RESULT_FILE={result_file}\nSTATUS=completed\nEXPERIMENTS=0\n",
        )

    monkeypatch.setattr(mcp_service, "run_mcp_subprocess", fake_run)

    payload = mcp_service.run_autoresearch_tool({
        "task_config": str(task_config),
        "runtime_root": str(runtime_root),
        "workspace": str(workspace),
        "experiment_duration": 5,
    })

    assert payload["status"] == "completed"
    assert captured["kwargs"]["env"]["ML_RESEARCH_LOOP_ROOT"] == str(runtime_root)
    assert str(task_config) in captured["cmd"]
    assert str(workspace) in captured["cmd"]


def test_run_autoresearch_reports_execution_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("ML_RESEARCH_LOOP_ALLOWED_ROOTS", str(runtime_root))
    task_dir = runtime_root / "tasks"
    result_dir = runtime_root / "results"
    workspace = runtime_root / "workdir" / "metadata-task"
    task_dir.mkdir(parents=True)
    result_dir.mkdir()
    task_config = task_dir / "metadata-task.json"
    result_file = result_dir / "metadata-task.json"
    task_config.write_text('{"task_id": "metadata-task"}', encoding="utf-8")
    result_file.write_text(
        '{"task_id": "metadata-task", "status": "completed"}',
        encoding="utf-8",
    )

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=f"RESULT_FILE={result_file}\nSTATUS=completed\nEXPERIMENTS=0\n",
        )

    monkeypatch.setattr(mcp_service, "run_mcp_subprocess", fake_run)

    payload = mcp_service.run_autoresearch_tool({
        "task_config": str(task_config),
        "runtime_root": str(runtime_root),
        "workspace": str(workspace),
        "python": sys.executable,
        "max_experiments": 1,
        "experiment_duration": 5,
    })

    metadata = payload["execution_metadata"]
    assert metadata["wall_time_seconds"] >= 0
    assert metadata["python_executable"] == sys.executable
    assert metadata["timeout_policy"]["subprocess_timeout_seconds"] == 120
    assert metadata["timeout_policy"]["experiment_duration_seconds"] == 5
    assert metadata["timeout_policy"]["max_experiments"] == 1
    assert metadata["execution_sandbox"]["status"] == "enforced"
    assert str(runtime_root) in metadata["sandbox_roots"]
    assert metadata["artifact_retention"]["runtime_root"] == str(runtime_root)
    assert metadata["artifact_retention"]["task_file"] == str(task_config)
    assert metadata["artifact_retention"]["result_file"] == str(result_file)
    assert metadata["artifact_retention"]["workspace"] == str(workspace)


def test_run_mcp_subprocess_reports_startup_failure(tmp_path) -> None:
    missing_binary = tmp_path / "missing-python"

    with pytest.raises(mcp_service.MCPToolError) as exc_info:
        mcp_service.run_mcp_subprocess(
            [str(missing_binary), "-c", "print('never')"],
            cwd=tmp_path,
            env=dict(os.environ),
            timeout_seconds=5,
        )

    assert exc_info.value.payload["status"] == "failed"
    assert exc_info.value.payload["error_type"] == "startup_failed"
    assert str(missing_binary) in exc_info.value.payload["error"]


def test_run_mcp_subprocess_reports_timeout_and_kills_process(tmp_path) -> None:
    sentinel = tmp_path / "child-survived.txt"
    command = [
        sys.executable,
        "-c",
        (
            "import pathlib,subprocess,sys,time;"
            f"sentinel={str(sentinel)!r};"
            "subprocess.Popen([sys.executable,'-c',"
            "'import pathlib,time; time.sleep(2); pathlib.Path(%r).write_text(\"alive\")' % sentinel]);"
            "time.sleep(20)"
        ),
    ]

    with pytest.raises(mcp_service.MCPToolError) as exc_info:
        mcp_service.run_mcp_subprocess(
            command,
            cwd=tmp_path,
            env=dict(os.environ),
            timeout_seconds=1,
        )

    assert exc_info.value.payload["status"] == "failed"
    assert exc_info.value.payload["error_type"] == "timeout"
    assert exc_info.value.payload["timeout_seconds"] == 1
    time.sleep(2.5)
    assert not sentinel.exists()


def test_get_service_manifest_returns_client_contract() -> None:
    payload = mcp_service.get_service_manifest_tool({})

    assert payload["contract_version"] == "2026-04-30.preview.v1"
    assert payload["schema_versions"] == {
        "service_manifest": "2026-04-30.preview.v1",
        "tool_inputs": "2026-04-30.preview.v1",
        "tool_outputs": "2026-04-30.preview.v1",
        "runtime_artifacts": "2026-04-30.preview.v1",
    }
    assert payload["compatibility"] == {
        "status": "preview",
        "breaking_changes": "allowed only with a contract_version change",
        "client_requirement": "check contract_version before planning automated loops",
    }
    assert payload["architecture"] == "hybrid_client_planner_server_executor"
    assert payload["product_status"] == "preview"
    assert payload["execution_sandbox"] == {
        "status": "enforced",
        "allowed_roots_env": "ML_RESEARCH_LOOP_ALLOWED_ROOTS",
        "default_allowed_roots": ["project_root", "ML_RESEARCH_LOOP_ROOT"],
        "rules": [
            "execution task_config/runtime_root/workspace paths must be inside allowed roots",
            "workspace must stay inside runtime_root when both are provided",
        ],
    }
    assert "Codex/Claude" in payload["client_model_role"]
    assert payload["server_side_llm"]["tool"] == "run_ai_autoresearch"
    assert payload["benchmark_adapters"]["status"] == "compatibility_ready"
    assert payload["benchmark_adapters"]["official_scores_claimed"] is False
    assert [adapter["name"] for adapter in payload["benchmark_adapters"]["adapters"]] == [
        "mle_bench",
        "paperbench",
    ]
    assert payload["benchmark_harness_probe"]["read_only"] is True
    assert payload["benchmark_harness_probe"]["official_scores_claimed"] is False
    assert [harness["name"] for harness in payload["benchmark_harness_probe"]["harnesses"]] == [
        "mle_bench",
        "paperbench",
    ]
    assert payload["recommended_workflows"][0]["tools"][0] == "research_task"
    assert "run_hypothesis_experiment" in payload["required_tools"]
    assert "run_client_patch_experiment" in payload["required_tools"]
    assert "apply_client_code_patch" in payload["required_tools"]
    assert "run_next_experiment_from_review" in payload["required_tools"]
    assert payload["planning_signals"] == [
        "cache",
        "cache.cache_scope",
        "cache.freshness_seconds",
        "evidence_quality",
        "evidence_quality.source_class_counts",
        "evidence_citations.source_trace",
        "source.metadata.source_id",
        "deduplication_report",
        "cache_summary",
        "provider_quality_matrix",
        "provider_coverage",
        "source_rankings",
        "retrieval_diagnostics",
        "research_evidence_gate",
        "dataset_profile",
        "experiment_tree",
        "loop_policy",
        "failure_diagnostics",
        "metric_stop_policy",
        "reproduction.readiness",
        "execution_metadata",
        "code_change_plan",
        "code_change_plan.next_experiment_plan",
        "code_change_plan.next_experiment_plan.proposed_task_patch",
        "code_change_plan.next_experiment_plan.dry_run_validation",
        "code_change_plan.next_experiment_plan.diff_preview",
        "code_change_plan.next_experiment_plan.execution_guardrails",
        "run_next_experiment_from_review.final_review",
        "run_next_experiment_from_review.loop_decision",
        "run_client_patch_experiment.patch_execution",
        "run_client_patch_experiment.loop_decision",
        "apply_client_code_patch.patch_execution",
        "apply_client_code_patch.post_patch_review",
        "apply_client_code_patch.loop_decision",
        "benchmark_adapters",
        "benchmark_adapters.adapters",
        "benchmark_adapters.combined_smoke",
        "benchmark_harness_probe",
        "planner_actions",
        "next_round.task_patch",
    ]
    assert set(payload["tool_contracts"]) == set(payload["required_tools"])
    assert any("mcp_auto_next_demo.py" in item for item in payload["acceptance_commands"])
    assert any("mcp_provider_quality_benchmark.py" in item for item in payload["acceptance_commands"])
    assert any("mcp_real_task_code_benchmark.py" in item for item in payload["acceptance_commands"])
    assert any("benchmark_adapter_smoke.py" in item for item in payload["acceptance_commands"])
    assert any("benchmark_harness_probe.py" in item for item in payload["acceptance_commands"])
    assert "wall_time_seconds" in payload["execution_metadata_contract"]["required_fields"]
    assert "subprocess_timeout_seconds" in payload["execution_metadata_contract"]["timeout_policy_fields"]
    assert payload["skill_package"]["status"] == "repo_local"
    assert payload["skill_package"]["install_command"] == "ml-loop init-skills"
    assert payload["recommended_skills"] == [
        "ml-research-loop-planner",
        "ml-research-loop-reproduction",
        "ml-research-loop-experiment-optimizer",
        "ml-research-loop-operator",
    ]
    assert set(payload["skill_contracts"]) == set(payload["recommended_skills"])
    planner_contract = payload["skill_contracts"]["ml-research-loop-planner"]
    assert planner_contract["contract_version"] == "2026-04-30.preview.v1"
    assert planner_contract["path"] == "skills/ml-research-loop-planner/SKILL.md"
    assert planner_contract["client_role"] == "workflow_planner"
    assert "get_service_manifest" in planner_contract["required_tools"]
    assert "review_research_results" in planner_contract["required_tools"]
    assert "research_evidence_gate" in planner_contract["planning_signals"]
    assert "human_confirmation" in planner_contract["safety_rules"]
    for tool_name, contract in payload["tool_contracts"].items():
        assert contract["input_schema_version"] == "2026-04-30.preview.v1"
        assert contract["output_schema_version"] == "2026-04-30.preview.v1"
        assert contract["stability"] == "preview"
        assert contract["description"]


def test_manifest_reports_fit_first_upstream_patterns() -> None:
    payload = mcp_service.get_service_manifest_tool({})

    assert payload["upstream_patterns"] == {
        "aide": {
            "integration_mode": "architecture_pattern",
            "enabled_features": ["experiment_tree", "best_node_tracking", "loop_policy"],
            "direct_dependency": False,
        },
        "paperbench": {
            "integration_mode": "architecture_pattern",
            "enabled_features": ["reproduction_spec", "rubric_grade_report"],
            "direct_dependency": False,
        },
    }


def test_get_experiment_logs_returns_recent_log_tail(tmp_path) -> None:
    workspace = tmp_path / "workdir" / "log-task"
    logs_dir = workspace / "logs"
    logs_dir.mkdir(parents=True)
    (logs_dir / "exp-001.log").write_text(
        "\n".join(f"line {index}" for index in range(1, 8)),
        encoding="utf-8",
    )

    payload = mcp_service.get_experiment_logs_tool({
        "task_id": "log-task",
        "workspace": str(workspace),
        "tail_lines": 3,
    })

    assert payload["task_id"] == "log-task"
    assert payload["log_count"] == 1
    assert payload["logs"][0]["file"].endswith("exp-001.log")
    assert payload["logs"][0]["tail"] == "line 5\nline 6\nline 7"


def test_get_experiment_logs_caps_tail_lines(tmp_path) -> None:
    workspace = tmp_path / "workdir" / "log-task"
    logs_dir = workspace / "logs"
    logs_dir.mkdir(parents=True)
    (logs_dir / "exp-001.log").write_text(
        "\n".join(f"line {index}" for index in range(1, 602)),
        encoding="utf-8",
    )

    payload = mcp_service.get_experiment_logs_tool({
        "task_id": "log-task",
        "workspace": str(workspace),
        "tail_lines": 1000,
    })

    assert len(payload["logs"][0]["tail"].splitlines()) == 500
    assert payload["logs"][0]["tail"].splitlines()[0] == "line 102"


def test_run_next_experiment_from_review_can_include_final_review_and_loop_decision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    task_file = tmp_path / "tasks" / "loop-task.json"
    task_file.parent.mkdir()
    task_file.write_text("{}", encoding="utf-8")
    reviews = [
        {
            "experiment_state": {
                "best_result": {"val": 1.0},
                "code_change_plan": {
                    "next_experiment_plan": {
                        "metric": {"name": "val_bpb", "direction": "minimize"},
                        "proposed_task_patch": {
                            "hyperparameter_space": {
                                "depth": {"type": "choice", "values": [1, 2]},
                            }
                        },
                    }
                },
                "planner_actions": [
                    {
                        "tool": "run_hypothesis_experiment",
                        "arguments": {
                            "task_config": str(task_file),
                            "runtime_root": str(tmp_path),
                        },
                    }
                ],
            }
        },
        {
            "experiment_state": {
                "best_result": {"val": 0.8},
                "code_change_plan": {
                    "next_experiment_plan": {
                        "metric": {"name": "val_bpb", "direction": "minimize"},
                    }
                },
            }
        },
    ]

    def fake_review(arguments: dict) -> dict:
        del arguments
        return reviews.pop(0)

    monkeypatch.setattr(mcp_service, "review_research_results_tool", fake_review)
    monkeypatch.setattr(
        mcp_service,
        "run_hypothesis_experiment_tool",
        lambda arguments: {"status": "completed", "arguments": arguments},
    )

    payload = mcp_service.run_next_experiment_from_review_tool({
        "task_id": "loop-task",
        "runtime_root": str(tmp_path),
        "include_final_review": True,
    })

    assert payload["status"] == "completed"
    assert payload["final_review"]["experiment_state"]["best_result"]["val"] == 0.8
    assert payload["loop_decision"] == {
        "decision": "continue",
        "reason": "best metric improved; continue with the next reviewed patch",
        "reason_category": "metric_improved",
        "recommended_next_action": "continue_with_reviewed_patch",
        "metric": "val_bpb",
        "metric_direction": "minimize",
        "previous_best": 1.0,
        "current_best": 0.8,
        "improved": True,
    }


def test_build_loop_decision_stops_on_final_reproduction_blocker() -> None:
    decision = mcp_service.build_loop_decision(
        initial_review={
            "experiment_state": {
                "best_result": {"val": 1.0},
                "code_change_plan": {
                    "next_experiment_plan": {
                        "metric": {"name": "val_bpb", "direction": "minimize"},
                    }
                },
            }
        },
        final_review={
            "experiment_state": {
                "best_result": {"val": 0.8},
                "loop_policy": {
                    "decision": "stop",
                    "reason_category": "reproduction_blocked",
                    "recommended_next_action": "fix_reproduction_requirements",
                    "reason": "Reproduction required files are missing or invalid.",
                    "stop_reason": "Stop before running more experiments.",
                },
                "code_change_plan": {
                    "next_experiment_plan": {
                        "metric": {"name": "val_bpb", "direction": "minimize"},
                    }
                },
            }
        },
    )

    assert decision["decision"] == "stop"
    assert decision["reason_category"] == "reproduction_blocked"
    assert decision["recommended_next_action"] == "fix_reproduction_requirements"
    assert decision["improved"] is True


def test_run_next_experiment_from_review_reports_execution_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    task_file = tmp_path / "tasks" / "loop-task.json"
    task_file.parent.mkdir()
    task_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        mcp_service,
        "review_research_results_tool",
        lambda arguments: {
            "experiment_state": {
                "planner_actions": [
                    {
                        "tool": "run_hypothesis_experiment",
                        "arguments": {
                            "task_config": str(task_file),
                            "runtime_root": str(tmp_path),
                        },
                    }
                ],
                "code_change_plan": {
                    "next_experiment_plan": {
                        "proposed_task_patch": {"budget": {"max_experiments": 1}},
                    }
                },
            }
        },
    )
    monkeypatch.setattr(
        mcp_service,
        "run_hypothesis_experiment_tool",
        lambda arguments: {"status": "completed", "arguments": arguments},
    )

    payload = mcp_service.run_next_experiment_from_review_tool({
        "task_id": "loop-task",
        "runtime_root": str(tmp_path),
        "max_experiments": 1,
        "experiment_duration": 5,
        "python": sys.executable,
    })

    metadata = payload["execution_metadata"]
    assert metadata["wall_time_seconds"] >= 0
    assert metadata["python_executable"] == sys.executable
    assert metadata["timeout_policy"]["experiment_duration_seconds"] == 5
    assert metadata["timeout_policy"]["max_experiments"] == 1
    assert metadata["artifact_retention"]["runtime_root"] == str(tmp_path)


def test_run_client_patch_experiment_validates_patch_and_runs_review_loop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    runtime_root = tmp_path / "runtime"
    task_file = runtime_root / "tasks" / "client-task.json"
    workspace = runtime_root / "workdir" / "client-task"
    task_file.parent.mkdir(parents=True)
    workspace.mkdir(parents=True)
    task_file.write_text(
        json.dumps({
            "task_id": "client-task",
            "objective": "minimize val_bpb",
            "metric": {"name": "val_bpb", "direction": "minimize"},
            "hyperparameter_space": {},
        }),
        encoding="utf-8",
    )
    (workspace / "train.py").write_text(
        "\n".join([
            "print('before')",
            "# ======= AUTORESEARCH SEARCH REGION START =======",
            "DEPTH = 1",
            "# ======= AUTORESEARCH SEARCH REGION END =======",
        ]),
        encoding="utf-8",
    )
    captured: dict = {}

    def fake_run(arguments: dict) -> dict:
        captured["run_arguments"] = arguments
        return {
            "status": "completed",
            "result": {
                "task_id": "client-task",
                "best_result": {"val": 0.7},
            },
        }

    reviews = [
        {
            "experiment_state": {
                "best_result": {"val": 0.8},
                "code_change_plan": {
                    "next_experiment_plan": {
                        "metric": {"name": "val_bpb", "direction": "minimize"},
                    },
                },
            }
        },
        {
            "experiment_state": {
                "best_result": {"val": 0.6},
                "code_change_plan": {
                    "next_experiment_plan": {
                        "metric": {"name": "val_bpb", "direction": "minimize"},
                    },
                },
            }
        },
    ]

    def fake_review(arguments: dict) -> dict:
        captured["review_arguments"] = arguments
        return reviews.pop(0)

    monkeypatch.setattr(mcp_service, "run_hypothesis_experiment_tool", fake_run)
    monkeypatch.setattr(mcp_service, "review_research_results_tool", fake_review)

    payload = mcp_service.run_client_patch_experiment_tool({
        "task_config": str(task_file),
        "runtime_root": str(runtime_root),
        "workspace": str(workspace),
        "change_proposal": {
            "change_type": "hyperparam",
            "target": "DEPTH",
            "current_value": "1",
            "proposed_value": "2",
            "reason": "validate a slightly deeper model",
            "confidence": 0.8,
        },
        "max_experiments": 1,
        "experiment_duration": 5,
        "include_final_review": True,
    })

    assert payload["status"] == "completed"
    assert payload["patch_execution"]["status"] == "validated"
    assert payload["patch_execution"]["target"] == "DEPTH"
    assert payload["patch_execution"]["task_patch"] == {
        "hyperparameter_space": {"depth": {"type": "choice", "values": [2]}},
        "program_md_overrides": {
            "hints": ["Client proposal DEPTH: 1 -> 2. Reason: validate a slightly deeper model"],
        },
    }
    assert payload["patch_execution"]["diff_preview"]["before"] == "DEPTH = 1"
    assert payload["patch_execution"]["diff_preview"]["after"] == "DEPTH = 2"
    assert captured["run_arguments"]["task_patch"] == payload["patch_execution"]["task_patch"]
    assert captured["run_arguments"]["max_experiments"] == 1
    assert captured["review_arguments"]["task_id"] == "client-task"
    assert payload["initial_review"]["experiment_state"]["best_result"]["val"] == 0.8
    assert payload["final_review"]["experiment_state"]["best_result"]["val"] == 0.6
    assert payload["loop_decision"]["decision"] == "continue"


def test_run_client_patch_experiment_reports_execution_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    runtime_root = tmp_path / "runtime"
    task_file = runtime_root / "tasks" / "client-task.json"
    workspace = runtime_root / "workdir" / "client-task"
    task_file.parent.mkdir(parents=True)
    workspace.mkdir(parents=True)
    task_file.write_text('{"task_id": "client-task"}', encoding="utf-8")
    (workspace / "train.py").write_text(
        "\n".join([
            "# ======= AUTORESEARCH SEARCH REGION START =======",
            "DEPTH = 1",
            "# ======= AUTORESEARCH SEARCH REGION END =======",
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        mcp_service,
        "run_hypothesis_experiment_tool",
        lambda arguments: {"status": "completed", "result": {"task_id": "client-task"}},
    )

    payload = mcp_service.run_client_patch_experiment_tool({
        "task_config": str(task_file),
        "runtime_root": str(runtime_root),
        "workspace": str(workspace),
        "python": sys.executable,
        "change_proposal": {
            "change_type": "hyperparam",
            "target": "DEPTH",
            "current_value": "1",
            "proposed_value": "2",
            "reason": "validate a slightly deeper model",
        },
        "max_experiments": 1,
        "experiment_duration": 5,
    })

    metadata = payload["execution_metadata"]
    assert metadata["python_executable"] == sys.executable
    assert metadata["timeout_policy"]["experiment_duration_seconds"] == 5
    assert metadata["artifact_retention"]["runtime_root"] == str(runtime_root)
    assert metadata["artifact_retention"]["workspace"] == str(workspace)


def test_run_client_patch_experiment_rejects_stale_current_value(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    task_file = runtime_root / "tasks" / "client-task.json"
    workspace = runtime_root / "workdir" / "client-task"
    task_file.parent.mkdir(parents=True)
    workspace.mkdir(parents=True)
    task_file.write_text('{"task_id": "client-task"}', encoding="utf-8")
    (workspace / "train.py").write_text(
        "\n".join([
            "# ======= AUTORESEARCH SEARCH REGION START =======",
            "DEPTH = 1",
            "# ======= AUTORESEARCH SEARCH REGION END =======",
        ]),
        encoding="utf-8",
    )

    with pytest.raises(mcp_service.MCPToolError) as exc_info:
        mcp_service.run_client_patch_experiment_tool({
            "task_config": str(task_file),
            "runtime_root": str(runtime_root),
            "workspace": str(workspace),
            "change_proposal": {
                "change_type": "hyperparam",
                "target": "DEPTH",
                "current_value": "4",
                "proposed_value": "2",
                "reason": "stale client state",
            },
        })

    assert exc_info.value.payload["status"] == "failed"
    assert exc_info.value.payload["error_type"] == "stale_patch"
    assert exc_info.value.payload["actual_value"] == "1"


def test_run_client_patch_experiment_rejects_unknown_search_region_target(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    task_file = runtime_root / "tasks" / "client-task.json"
    workspace = runtime_root / "workdir" / "client-task"
    task_file.parent.mkdir(parents=True)
    workspace.mkdir(parents=True)
    task_file.write_text('{"task_id": "client-task"}', encoding="utf-8")
    (workspace / "train.py").write_text(
        "\n".join([
            "# ======= AUTORESEARCH SEARCH REGION START =======",
            "DEPTH = 1",
            "# ======= AUTORESEARCH SEARCH REGION END =======",
        ]),
        encoding="utf-8",
    )

    with pytest.raises(mcp_service.MCPToolError) as exc_info:
        mcp_service.run_client_patch_experiment_tool({
            "task_config": str(task_file),
            "runtime_root": str(runtime_root),
            "workspace": str(workspace),
            "change_proposal": {
                "change_type": "hyperparam",
                "target": "DROPOUT",
                "current_value": "0.1",
                "proposed_value": "0.2",
                "reason": "not in current SEARCH REGION",
            },
        })

    assert exc_info.value.payload["status"] == "failed"
    assert exc_info.value.payload["error_type"] == "invalid_patch_target"
    assert exc_info.value.payload["available_targets"] == ["DEPTH"]


def test_run_client_patch_experiment_rejects_invalid_confidence(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    task_file = runtime_root / "tasks" / "client-task.json"
    workspace = runtime_root / "workdir" / "client-task"
    task_file.parent.mkdir(parents=True)
    workspace.mkdir(parents=True)
    task_file.write_text('{"task_id": "client-task"}', encoding="utf-8")
    (workspace / "train.py").write_text(
        "\n".join([
            "# ======= AUTORESEARCH SEARCH REGION START =======",
            "DEPTH = 1",
            "# ======= AUTORESEARCH SEARCH REGION END =======",
        ]),
        encoding="utf-8",
    )

    with pytest.raises(mcp_service.MCPToolError) as exc_info:
        mcp_service.run_client_patch_experiment_tool({
            "task_config": str(task_file),
            "runtime_root": str(runtime_root),
            "workspace": str(workspace),
            "change_proposal": {
                "change_type": "hyperparam",
                "target": "DEPTH",
                "current_value": "1",
                "proposed_value": "2",
                "reason": "bad confidence",
                "confidence": "high",
            },
        })

    assert exc_info.value.payload["status"] == "failed"
    assert exc_info.value.payload["error_type"] == "invalid_patch_confidence"


def test_apply_client_code_patch_applies_workspace_patch_and_checks_syntax(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = runtime_root / "workdir" / "patch-task"
    workspace.mkdir(parents=True)
    train_py = workspace / "train.py"
    train_py.write_text("VALUE = 1\nprint(VALUE)\n", encoding="utf-8")

    payload = mcp_service.apply_client_code_patch_tool({
        "runtime_root": str(runtime_root),
        "workspace": str(workspace),
        "patch": "\n".join([
            "--- a/train.py",
            "+++ b/train.py",
            "@@ -1,2 +1,2 @@",
            "-VALUE = 1",
            "+VALUE = 2",
            " print(VALUE)",
            "",
        ]),
        "test_command": [sys.executable, "-m", "py_compile", "train.py"],
    })

    assert payload["status"] == "applied"
    assert payload["patch_execution"]["mode"] == "workspace_unified_diff"
    assert payload["patch_execution"]["changed_files"] == ["train.py"]
    assert payload["patch_execution"]["preflight"]["status"] == "passed"
    assert payload["patch_execution"]["syntax_check"]["status"] == "passed"
    assert payload["patch_execution"]["test_check"]["status"] == "passed"
    assert payload["patch_execution"]["rollback"]["performed"] is False
    assert train_py.read_text(encoding="utf-8") == "VALUE = 2\nprint(VALUE)\n"


def test_apply_client_code_patch_handles_multi_file_patch_and_post_review(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = runtime_root / "workdir" / "patch-task"
    workspace.mkdir(parents=True)
    train_py = workspace / "train.py"
    helper_py = workspace / "helper.py"
    train_py.write_text(
        "from helper import scale\nVALUE = scale(1)\nprint(VALUE)\n",
        encoding="utf-8",
    )
    helper_py.write_text("def scale(value):\n    return value\n", encoding="utf-8")
    captured: dict = {}

    def fake_review(arguments: dict) -> dict:
        captured["review_arguments"] = arguments
        return {
            "status": "completed",
            "experiment_state": {
                "best_result": {"val": 0.5},
                "code_change_plan": {
                    "next_experiment_plan": {
                        "metric": {"name": "val_bpb", "direction": "minimize"},
                    }
                },
            },
        }

    monkeypatch.setattr(mcp_service, "review_research_results_tool", fake_review)

    payload = mcp_service.apply_client_code_patch_tool({
        "runtime_root": str(runtime_root),
        "workspace": str(workspace),
        "task_id": "patch-task",
        "patch": "\n".join([
            "--- a/train.py",
            "+++ b/train.py",
            "@@ -1,3 +1,3 @@",
            " from helper import scale",
            "-VALUE = scale(1)",
            "+VALUE = scale(2)",
            " print(VALUE)",
            "--- a/helper.py",
            "+++ b/helper.py",
            "@@ -1,2 +1,2 @@",
            " def scale(value):",
            "-    return value",
            "+    return value * 2",
            "",
        ]),
        "allowed_files": ["train.py", "helper.py"],
        "test_command": [sys.executable, "-m", "py_compile", "train.py", "helper.py"],
        "include_post_patch_review": True,
        "initial_review": {
            "experiment_state": {
                "best_result": {"val": 1.0},
                "code_change_plan": {
                    "next_experiment_plan": {
                        "metric": {"name": "val_bpb", "direction": "minimize"},
                    }
                },
            }
        },
    })

    assert payload["status"] == "applied"
    assert payload["patch_execution"]["changed_files"] == ["helper.py", "train.py"]
    assert payload["patch_execution"]["syntax_check"]["checked_files"] == ["helper.py", "train.py"]
    assert payload["patch_execution"]["test_check"]["status"] == "passed"
    assert payload["post_patch_review"]["status"] == "completed"
    assert payload["loop_decision"]["decision"] == "continue"
    assert payload["loop_decision"]["reason_category"] == "metric_improved"
    assert captured["review_arguments"] == {
        "task_id": "patch-task",
        "runtime_root": str(runtime_root),
        "workspace": str(workspace),
    }
    assert train_py.read_text(encoding="utf-8") == "from helper import scale\nVALUE = scale(2)\nprint(VALUE)\n"
    assert helper_py.read_text(encoding="utf-8") == "def scale(value):\n    return value * 2\n"


def test_apply_client_code_patch_reports_execution_metadata(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = runtime_root / "workdir" / "patch-task"
    workspace.mkdir(parents=True)
    train_py = workspace / "train.py"
    train_py.write_text("VALUE = 1\nprint(VALUE)\n", encoding="utf-8")

    payload = mcp_service.apply_client_code_patch_tool({
        "runtime_root": str(runtime_root),
        "workspace": str(workspace),
        "patch": "\n".join([
            "--- a/train.py",
            "+++ b/train.py",
            "@@ -1,2 +1,2 @@",
            "-VALUE = 1",
            "+VALUE = 2",
            " print(VALUE)",
            "",
        ]),
        "test_command": [sys.executable, "-m", "py_compile", "train.py"],
        "test_timeout_seconds": 12,
    })

    metadata = payload["execution_metadata"]
    assert metadata["wall_time_seconds"] >= 0
    assert metadata["timeout_policy"]["test_timeout_seconds"] == 12
    assert metadata["artifact_retention"]["runtime_root"] == str(runtime_root)
    assert metadata["artifact_retention"]["workspace"] == str(workspace)


def test_apply_client_code_patch_rolls_back_on_syntax_error(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = runtime_root / "workdir" / "patch-task"
    workspace.mkdir(parents=True)
    train_py = workspace / "train.py"
    original_text = "VALUE = 1\nprint(VALUE)\n"
    train_py.write_text(original_text, encoding="utf-8")

    with pytest.raises(mcp_service.MCPToolError) as exc_info:
        mcp_service.apply_client_code_patch_tool({
            "runtime_root": str(runtime_root),
            "workspace": str(workspace),
            "patch": "\n".join([
                "--- a/train.py",
                "+++ b/train.py",
                "@@ -1,2 +1,2 @@",
                "-VALUE = 1",
                "+VALUE =",
                " print(VALUE)",
                "",
            ]),
        })

    assert exc_info.value.payload["status"] == "failed"
    assert exc_info.value.payload["error_type"] == "syntax_check_failed"
    assert exc_info.value.payload["patch_execution"]["rollback"]["performed"] is True
    assert train_py.read_text(encoding="utf-8") == original_text


def test_apply_client_code_patch_rolls_back_on_test_command_failure(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = runtime_root / "workdir" / "patch-task"
    workspace.mkdir(parents=True)
    train_py = workspace / "train.py"
    original_text = "VALUE = 1\nprint(VALUE)\n"
    train_py.write_text(original_text, encoding="utf-8")

    with pytest.raises(mcp_service.MCPToolError) as exc_info:
        mcp_service.apply_client_code_patch_tool({
            "runtime_root": str(runtime_root),
            "workspace": str(workspace),
            "patch": "\n".join([
                "--- a/train.py",
                "+++ b/train.py",
                "@@ -1,2 +1,2 @@",
                "-VALUE = 1",
                "+VALUE = 2",
                " print(VALUE)",
                "",
            ]),
            "test_command": [sys.executable, "-c", "raise SystemExit(7)"],
        })

    assert exc_info.value.payload["status"] == "failed"
    assert exc_info.value.payload["error_type"] == "test_check_failed"
    assert exc_info.value.payload["patch_execution"]["test_check"]["returncode"] == 7
    assert exc_info.value.payload["patch_execution"]["rollback"]["performed"] is True
    assert train_py.read_text(encoding="utf-8") == original_text


def test_apply_client_code_patch_rejects_path_escape(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = runtime_root / "workdir" / "patch-task"
    workspace.mkdir(parents=True)

    with pytest.raises(mcp_service.MCPToolError) as exc_info:
        mcp_service.apply_client_code_patch_tool({
            "runtime_root": str(runtime_root),
            "workspace": str(workspace),
            "patch": "\n".join([
                "--- a/../outside.py",
                "+++ b/../outside.py",
                "@@ -1 +1 @@",
                "-VALUE = 1",
                "+VALUE = 2",
                "",
            ]),
        })

    assert exc_info.value.payload["status"] == "failed"
    assert exc_info.value.payload["error_type"] == "unsafe_patch_path"
    assert exc_info.value.payload["patch_execution"]["rollback"]["performed"] is False


def test_runtime_artifact_tools_list_archive_and_clean_task_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("ML_RESEARCH_LOOP_ALLOWED_ROOTS", str(runtime_root))
    task_file = runtime_root / "tasks" / "demo.json"
    result_file = runtime_root / "results" / "demo.json"
    progress_file = runtime_root / "results" / "demo-progress.json"
    workspace = runtime_root / "workdir" / "demo"
    task_file.parent.mkdir(parents=True)
    result_file.parent.mkdir(parents=True)
    workspace.mkdir(parents=True)
    task_file.write_text("{}", encoding="utf-8")
    result_file.write_text("{}", encoding="utf-8")
    progress_file.write_text("{}", encoding="utf-8")
    (workspace / "train.py").write_text("print('demo')\n", encoding="utf-8")

    listed = mcp_service.list_runtime_artifacts_tool({"runtime_root": str(runtime_root)})

    assert listed["task_ids"] == ["demo"]
    assert listed["artifacts"]["tasks"]["file_count"] == 1
    assert listed["artifacts"]["results"]["file_count"] == 2
    assert listed["artifacts"]["workdir"]["file_count"] == 1

    archived = mcp_service.archive_runtime_artifacts_tool({
        "runtime_root": str(runtime_root),
        "task_id": "demo",
    })

    assert archived["status"] == "archived"
    assert archived["task_id"] == "demo"
    assert archived["archived_count"] == 3
    assert not task_file.exists()
    assert not result_file.exists()
    assert not workspace.exists()
    assert (runtime_root / "archive").exists()

    new_task_file = runtime_root / "tasks" / "demo.json"
    new_task_file.parent.mkdir(parents=True, exist_ok=True)
    new_task_file.write_text("{}", encoding="utf-8")
    cleaned = mcp_service.clean_runtime_artifacts_tool({
        "runtime_root": str(runtime_root),
        "task_id": "demo",
        "confirm": True,
    })

    assert cleaned["status"] == "cleaned"
    assert cleaned["deleted_count"] == 1
    assert not new_task_file.exists()


def test_clean_runtime_artifacts_requires_confirm(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()

    with pytest.raises(mcp_service.MCPToolError) as exc_info:
        mcp_service.clean_runtime_artifacts_tool({
            "runtime_root": str(runtime_root),
            "task_id": "demo",
        })

    assert exc_info.value.payload["status"] == "failed"
    assert "confirm" in exc_info.value.payload["error"]
