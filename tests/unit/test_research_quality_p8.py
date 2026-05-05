from __future__ import annotations

import json

from lib import mcp_service
from lib.research_protocol import ResearchSource
from ml_intern import research_tools


def _request(request_id: int, name: str, arguments: dict) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }


def _call_tool(name: str, arguments: dict) -> dict:
    response = mcp_service.handle_request(_request(900, name, arguments))
    assert response is not None
    assert "error" not in response
    result = response["result"]
    return json.loads(result["content"][0]["text"])


def test_cached_search_reports_scope_source_count_and_freshness(tmp_path) -> None:
    def collect() -> list[ResearchSource]:
        return [
            ResearchSource(
                source_type="paper",
                title="Cache Provenance",
                url="https://arxiv.org/abs/2601.00001",
                summary="Cache provenance should be auditable.",
            )
        ]

    first_sources, first_meta = research_tools.cached_search(
        cache_dir=tmp_path / "research-cache",
        namespace="papers",
        query="cache provenance",
        limit=1,
        collect=collect,
    )
    second_sources, second_meta = research_tools.cached_search(
        cache_dir=tmp_path / "research-cache",
        namespace="papers",
        query="cache provenance",
        limit=1,
        collect=collect,
    )

    assert first_sources[0].title == "Cache Provenance"
    assert second_sources[0].title == "Cache Provenance"
    assert first_meta["cache_schema_version"] == "2026-05-03.p8.v1"
    assert second_meta["cache_schema_version"] == "2026-05-03.p8.v1"
    assert first_meta["source_count"] == 1
    assert second_meta["source_count"] == 1
    assert first_meta["freshness_seconds"] == 0
    assert second_meta["freshness_seconds"] >= 0
    assert second_meta["cache_scope"] == {
        "namespace": "papers",
        "query": "cache provenance",
        "limit": 1,
    }


def test_research_task_returns_source_classes_and_citation_trace(monkeypatch) -> None:
    def fake_search_papers(query: str, limit: int = 5):
        del query, limit
        return [
            ResearchSource(
                source_type="paper",
                title="Paper Trace",
                url="https://arxiv.org/abs/2601.00001",
                summary="Paper evidence improves validation bpb.",
                metadata={
                    "provider": {
                        "name": "arxiv",
                        "record_id": "2601.00001",
                        "source_url": "https://arxiv.org/abs/2601.00001",
                    },
                    "pdf_url": "https://arxiv.org/pdf/2601.00001",
                },
            )
        ]

    def fake_search_hf_datasets(query: str, limit: int = 5):
        del query, limit
        return [
            ResearchSource(
                source_type="hf_dataset",
                title="fixture/trace-dataset",
                url="https://huggingface.co/datasets/fixture/trace-dataset",
                summary="Dataset card evidence describes validation splits.",
                metadata={
                    "provider": {
                        "name": "huggingface",
                        "record_id": "fixture/trace-dataset",
                        "source_url": "https://huggingface.co/datasets/fixture/trace-dataset",
                    }
                },
            )
        ]

    def fake_search_github_code(query: str, limit: int = 5):
        del query, limit
        return [
            ResearchSource(
                source_type="github_code",
                title="fixture/repo:train.py",
                url="https://github.com/fixture/repo/blob/main/train.py",
                summary="Code reference shows a compact training loop.",
                metadata={
                    "provider": {
                        "name": "github",
                        "record_id": "fixture/repo:train.py",
                        "source_url": "https://github.com/fixture/repo/blob/main/train.py",
                    }
                },
            )
        ]

    monkeypatch.setattr(research_tools, "search_papers", fake_search_papers)
    monkeypatch.setattr(research_tools, "search_hf_datasets", fake_search_hf_datasets)
    monkeypatch.setattr(research_tools, "search_github_code", fake_search_github_code)

    payload = _call_tool(
        "research_task",
        {
            "objective": "improve validation bpb with traceable evidence",
            "query": "traceable evidence",
            "paper_limit": 1,
            "dataset_limit": 1,
            "github_limit": 1,
            "include_github_code": True,
            "query_fanout": False,
        },
    )

    quality_by_title = {
        source["title"]: source["metadata"]["evidence_quality"]
        for source in payload["sources"]
    }
    source_ids = {source["metadata"]["source_id"] for source in payload["sources"]}

    assert source_ids == {
        "arxiv:2601.00001",
        "huggingface:fixture/trace-dataset",
        "github:fixture/repo:train.py",
    }
    assert quality_by_title["Paper Trace"]["source_class"] == "paper_fulltext_ready"
    assert quality_by_title["fixture/trace-dataset"]["source_class"] == "dataset_card"
    assert quality_by_title["fixture/repo:train.py"]["source_class"] == "code_reference"
    assert payload["evidence_quality"]["source_class_counts"] == {
        "code_reference": 1,
        "dataset_card": 1,
        "paper_fulltext_ready": 1,
    }

    first_citation = payload["evidence_citations"][0]
    assert first_citation["source_trace"] == [
        {
            "evidence": "paper:Paper Trace",
            "source_id": "arxiv:2601.00001",
            "source_type": "paper",
            "provider": "arxiv",
            "url": "https://arxiv.org/abs/2601.00001",
            "query_variant": "traceable evidence",
            "query_reason": "primary",
            "snippet_ids": ["snippet-001"],
        }
    ]
    assert first_citation["snippets"][0]["source_id"] == "arxiv:2601.00001"
    assert first_citation["snippets"][0]["query_variant"] == "traceable evidence"


def test_research_task_distinguishes_weak_and_strong_evidence_classes(monkeypatch) -> None:
    def fake_search_papers(query: str, limit: int = 5):
        del query, limit
        return [
            ResearchSource(
                source_type="paper",
                title="Weak Note",
                url="",
                summary="",
            ),
            ResearchSource(
                source_type="paper",
                title="Strong Paper",
                url="https://arxiv.org/abs/2601.00002",
                summary="Strong paper evidence improves validation bpb.",
                metadata={
                    "provider": {
                        "name": "arxiv",
                        "record_id": "2601.00002",
                        "source_url": "https://arxiv.org/abs/2601.00002",
                    }
                },
            ),
        ]

    monkeypatch.setattr(research_tools, "search_papers", fake_search_papers)
    monkeypatch.setattr(research_tools, "search_hf_datasets", lambda query, limit=5: [])

    payload = _call_tool(
        "research_task",
        {
            "objective": "strong paper evidence validation bpb",
            "query": "weak versus strong evidence",
            "paper_limit": 2,
            "dataset_limit": 0,
            "include_hf_datasets": False,
            "query_fanout": False,
        },
    )

    weak = next(source for source in payload["sources"] if source["title"] == "Weak Note")
    strong = next(source for source in payload["sources"] if source["title"] == "Strong Paper")

    assert weak["metadata"]["evidence_quality"]["source_class"] == "weak_unattributed"
    assert strong["metadata"]["evidence_quality"]["source_class"] == "paper_abstract"
    assert weak["metadata"]["evidence_quality"]["score"] < strong["metadata"]["evidence_quality"]["score"]
    assert payload["provider_coverage"]["unknown_provider_source_count"] == 1


def test_research_task_reports_dedup_cache_and_provider_quality_matrix(
    monkeypatch,
    tmp_path,
) -> None:
    def fake_search_papers(query: str, limit: int = 5):
        del query, limit
        return [
            ResearchSource(
                source_type="paper",
                title="Duplicate Paper",
                url="https://arxiv.org/abs/2601.00003",
                summary="Paper evidence supports byte modeling validation.",
                metadata={
                    "provider": {
                        "name": "arxiv",
                        "record_id": "2601.00003",
                        "source_url": "https://arxiv.org/abs/2601.00003",
                    }
                },
            ),
            ResearchSource(
                source_type="paper",
                title="Duplicate Paper Mirror",
                url="https://arxiv.org/abs/2601.00003",
                summary="Duplicate paper evidence should be collapsed.",
                metadata={
                    "provider": {
                        "name": "arxiv",
                        "record_id": "2601.00003",
                        "source_url": "https://arxiv.org/abs/2601.00003",
                    }
                },
            ),
        ]

    def fake_search_hf_datasets(query: str, limit: int = 5):
        del query, limit
        return [
            ResearchSource(
                source_type="hf_dataset",
                title="fixture/byte-validation",
                url="https://huggingface.co/datasets/fixture/byte-validation",
                summary="Dataset card documents validation splits for byte modeling.",
                metadata={
                    "provider": {
                        "name": "huggingface",
                        "record_id": "fixture/byte-validation",
                        "source_url": "https://huggingface.co/datasets/fixture/byte-validation",
                    }
                },
            )
        ]

    monkeypatch.setattr(research_tools, "search_papers", fake_search_papers)
    monkeypatch.setattr(research_tools, "search_hf_datasets", fake_search_hf_datasets)

    payload = _call_tool(
        "research_task",
        {
            "objective": "validate byte modeling evidence quality",
            "query": "byte modeling evidence quality",
            "paper_limit": 2,
            "dataset_limit": 1,
            "include_github_code": False,
            "query_fanout": False,
            "cache_dir": str(tmp_path / "research-cache"),
        },
    )

    assert [source["title"] for source in payload["sources"]] == [
        "Duplicate Paper",
        "fixture/byte-validation",
    ]
    assert payload["deduplication_report"]["input_source_count"] == 3
    assert payload["deduplication_report"]["unique_source_count"] == 2
    assert payload["deduplication_report"]["duplicate_source_count"] == 1
    assert payload["deduplication_report"]["duplicate_sources"] == [
        {
            "source_type": "paper",
            "title": "Duplicate Paper Mirror",
            "url": "https://arxiv.org/abs/2601.00003",
            "matched_key": "url:https://arxiv.org/abs/2601.00003",
        }
    ]
    assert payload["cache_summary"]["backend_count"] == 2
    assert payload["cache_summary"]["cache_miss_count"] == 2
    assert payload["cache_summary"]["backends"]["papers"]["source_count"] == 2
    assert payload["cache_summary"]["backends"]["hf_datasets"]["source_count"] == 1
    assert payload["provider_quality_matrix"]["providers"]["arxiv"]["source_count"] == 1
    assert payload["provider_quality_matrix"]["providers"]["huggingface"]["source_count"] == 1
    assert payload["provider_quality_matrix"]["source_types"]["paper"]["provider_count"] == 1
