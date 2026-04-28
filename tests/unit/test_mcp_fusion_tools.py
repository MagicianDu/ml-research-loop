from __future__ import annotations

import json

from lib import mcp_service
from lib.research_protocol import ResearchSource
from ml_intern import research_tools


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


def test_propose_hypotheses_preserves_research_sources() -> None:
    response = mcp_service.handle_request(
        _request(
            3,
            "tools/call",
            {
                "name": "propose_hypotheses",
                "arguments": {
                    "objective": "minimize val_bpb",
                    "sources": [
                        {
                            "source_type": "paper",
                            "title": "ALiBi",
                            "url": "https://arxiv.org/abs/2108.12409",
                            "summary": "Attention with linear biases.",
                        }
                    ],
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])

    assert payload["sources"][0]["source_type"] == "paper"
    assert payload["sources"][0]["title"] == "ALiBi"


def test_research_task_collects_sources_and_generates_hypotheses(monkeypatch) -> None:
    calls: list[tuple[str, str, int]] = []

    def fake_search_papers(query: str, limit: int = 5):
        calls.append(("papers", query, limit))
        return [
            ResearchSource(
                source_type="paper",
                title="Train Short, Test Long",
                url="https://arxiv.org/abs/2108.12409",
                summary="ALiBi improves length extrapolation.",
            )
        ]

    def fake_search_hf_datasets(query: str, limit: int = 5):
        calls.append(("hf_datasets", query, limit))
        return [
            ResearchSource(
                source_type="hf_dataset",
                title="roneneldan/TinyStories",
                url="https://huggingface.co/datasets/roneneldan/TinyStories",
                summary="Synthetic short stories.",
            )
        ]

    def fake_search_github_code(query: str, limit: int = 5):
        calls.append(("github_code", query, limit))
        return [
            ResearchSource(
                source_type="github_code",
                title="karpathy/nanoGPT:train.py",
                url="https://github.com/karpathy/nanoGPT/blob/master/train.py",
                summary="training loop reference",
            )
        ]

    monkeypatch.setattr(research_tools, "search_papers", fake_search_papers)
    monkeypatch.setattr(research_tools, "search_hf_datasets", fake_search_hf_datasets)
    monkeypatch.setattr(research_tools, "search_github_code", fake_search_github_code)

    response = mcp_service.handle_request(
        _request(
            4,
            "tools/call",
            {
                "name": "research_task",
                "arguments": {
                    "objective": "reduce val_bpb on TinyStories",
                    "query": "alibi tiny stories train.py",
                    "paper_limit": 1,
                    "dataset_limit": 1,
                    "github_limit": 1,
                    "include_github_code": True,
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])

    assert payload["status"] == "research_context_ready"
    assert payload["query"] == "alibi tiny stories train.py"
    assert [source["source_type"] for source in payload["sources"]] == [
        "paper",
        "hf_dataset",
        "github_code",
    ]
    assert payload["source_counts"] == {
        "paper": 1,
        "hf_dataset": 1,
        "github_code": 1,
    }
    assert payload["hypotheses"][0]["hypothesis_id"] == "hyp-001"
    assert "Train Short, Test Long" in payload["hypotheses"][0]["rationale"]
    assert calls == [
        ("papers", "alibi tiny stories train.py", 1),
        ("hf_datasets", "alibi tiny stories train.py", 1),
        ("github_code", "alibi tiny stories train.py", 1),
    ]


def test_research_task_returns_partial_context_when_one_backend_fails(monkeypatch) -> None:
    def fake_search_papers(query: str, limit: int = 5):
        del query, limit
        raise RuntimeError("arXiv unavailable")

    def fake_search_hf_datasets(query: str, limit: int = 5):
        del query, limit
        return [
            ResearchSource(
                source_type="hf_dataset",
                title="roneneldan/TinyStories",
                url="https://huggingface.co/datasets/roneneldan/TinyStories",
            )
        ]

    monkeypatch.setattr(research_tools, "search_papers", fake_search_papers)
    monkeypatch.setattr(research_tools, "search_hf_datasets", fake_search_hf_datasets)

    response = mcp_service.handle_request(
        _request(
            5,
            "tools/call",
            {
                "name": "research_task",
                "arguments": {
                    "objective": "reduce val_bpb",
                    "query": "tiny stories",
                    "paper_limit": 1,
                    "dataset_limit": 1,
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])

    assert payload["status"] == "research_context_partial"
    assert payload["sources"][0]["source_type"] == "hf_dataset"
    assert payload["warnings"] == ["papers: arXiv unavailable"]
