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
    assert payload["recommended_workflows"][0]["tools"][0] == "research_task"
    assert "run_hypothesis_experiment" in payload["required_tools"]
    assert "run_next_experiment_from_review" in payload["required_tools"]
    assert payload["planning_signals"] == [
        "cache",
        "evidence_quality",
        "provider_coverage",
        "source_rankings",
        "retrieval_diagnostics",
        "research_evidence_gate",
        "dataset_profile",
        "code_change_plan",
        "code_change_plan.next_experiment_plan",
        "code_change_plan.next_experiment_plan.proposed_task_patch",
        "code_change_plan.next_experiment_plan.dry_run_validation",
        "code_change_plan.next_experiment_plan.diff_preview",
        "code_change_plan.next_experiment_plan.execution_guardrails",
        "run_next_experiment_from_review.final_review",
        "run_next_experiment_from_review.loop_decision",
        "planner_actions",
        "next_round.task_patch",
    ]
    assert set(payload["tool_contracts"]) == set(payload["required_tools"])
    assert any("mcp_auto_next_demo.py" in item for item in payload["acceptance_commands"])
    for tool_name, contract in payload["tool_contracts"].items():
        assert contract["input_schema_version"] == "2026-04-30.preview.v1"
        assert contract["output_schema_version"] == "2026-04-30.preview.v1"
        assert contract["stability"] == "preview"
        assert contract["description"]


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
        "metric": "val_bpb",
        "metric_direction": "minimize",
        "previous_best": 1.0,
        "current_best": 0.8,
        "improved": True,
    }


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
