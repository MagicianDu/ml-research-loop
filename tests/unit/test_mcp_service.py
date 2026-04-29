from __future__ import annotations

import json
import subprocess

import pytest

from lib import mcp_service


def _request(request_id: int, method: str, params: dict | None = None) -> dict:
    request = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        request["params"] = params
    return request


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
    }.issubset(tool_names)


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

    monkeypatch.setattr(mcp_service.subprocess, "run", fake_run)

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

    monkeypatch.setattr(mcp_service.subprocess, "run", fake_run)

    payload = mcp_service.run_ai_autoresearch_tool({
        "task_config": str(task_config),
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


def test_get_service_manifest_returns_client_contract() -> None:
    payload = mcp_service.get_service_manifest_tool({})

    assert payload["architecture"] == "hybrid_client_planner_server_executor"
    assert payload["product_status"] == "preview"
    assert "Codex/Claude" in payload["client_model_role"]
    assert payload["server_side_llm"]["tool"] == "run_ai_autoresearch"
    assert payload["recommended_workflows"][0]["tools"][0] == "research_task"
    assert "run_hypothesis_experiment" in payload["required_tools"]
    assert payload["planning_signals"] == [
        "cache",
        "evidence_quality",
        "source_rankings",
        "research_evidence_gate",
        "dataset_profile",
        "code_change_plan",
        "planner_actions",
        "next_round.task_patch",
    ]


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
