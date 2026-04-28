from __future__ import annotations

import json

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
        "get_experiment_status",
        "get_experiment_result",
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
