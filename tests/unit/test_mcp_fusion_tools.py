from __future__ import annotations

import json

from lib import mcp_service


def _request(request_id: int, method: str, params: dict | None = None) -> dict:
    request = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        request["params"] = params
    return request


def test_mcp_lists_fusion_tools() -> None:
    response = mcp_service.handle_request(_request(1, "tools/list"))
    names = {tool["name"] for tool in response["result"]["tools"]}

    assert {
        "research_task",
        "propose_hypotheses",
        "run_hypothesis_experiment",
        "review_research_results",
    }.issubset(names)


def test_propose_hypotheses_returns_research_brief() -> None:
    response = mcp_service.handle_request(
        _request(
            2,
            "tools/call",
            {
                "name": "propose_hypotheses",
                "arguments": {
                    "objective": "minimize val_bpb",
                    "sources": [{"title": "ALiBi", "source_type": "paper"}],
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])

    assert payload["objective"] == "minimize val_bpb"
    assert payload["hypotheses"][0]["hypothesis_id"] == "hyp-001"
    assert "ALiBi" in payload["hypotheses"][0]["rationale"]
