from __future__ import annotations

import importlib.util
import json
from typing import Any

from lib.memory_adapters import AdapterStatus, get_memory_adapter_status
from lib.memory_adapters.cognee_adapter import CogneeMemoryAdapter
from lib.memory_adapters.graphiti_adapter import GraphitiMemoryAdapter
from lib.research_memory import MemoryArtifactRef, MemoryEvidenceRef, ResearchMemoryCard


def _force_missing_optional_dependencies(monkeypatch: Any) -> None:
    def missing_spec(_name: str) -> None:
        return None

    monkeypatch.setattr(importlib.util, "find_spec", missing_spec)


def _memory_card() -> ResearchMemoryCard:
    return ResearchMemoryCard(
        card_id="mem-adapter-test",
        memory_type="procedure",
        task_family="adapter-interface",
        summary="Adapter disabled path should skip writes.",
    )


def _rich_memory_card(tmp_path) -> ResearchMemoryCard:
    artifact = tmp_path / "proof-manifest.json"
    artifact.write_text('{"official_scores_claimed": false}', encoding="utf-8")
    return ResearchMemoryCard(
        card_id="mem-fasttext-arxiv-1607.01759-best-patch",
        memory_type="patch",
        task_family="text-classification",
        summary="fastText AG News bounded client proposal improved local P@1.",
        paper_ids=["arxiv:1607.01759"],
        datasets=["AG News"],
        model_family="fastText",
        metric_name="P@1",
        metric_before=0.75,
        metric_after=0.875,
        patch_type="hyperparameter",
        config={"best_source": "round-001-wordngrams-2"},
        evidence_refs=[
            MemoryEvidenceRef(
                source_id="fasttext-release-proof",
                artifact_path=str(artifact),
                quote="Local release proof bundle; not a leaderboard score.",
            )
        ],
        artifact_refs=[MemoryArtifactRef.from_path("release_manifest", artifact)],
        claim_boundary="local fastText proof only; official_scores_claimed=false",
        tags=["fasttext", "ag-news", "patch"],
    )


def test_memory_adapter_status_reports_optional_disabled_adapters(
    monkeypatch: Any,
) -> None:
    _force_missing_optional_dependencies(monkeypatch)

    statuses = get_memory_adapter_status()

    assert set(statuses) == {"graphiti", "cognee"}
    for status in statuses.values():
        assert isinstance(status, AdapterStatus)
        assert status.name in {"graphiti", "cognee"}
        assert status.enabled is False
        assert status.required is False
        assert isinstance(status.reason, str)
        assert status.reason


def test_graphiti_adapter_is_disabled_and_skips_operations(monkeypatch: Any) -> None:
    _force_missing_optional_dependencies(monkeypatch)
    adapter = GraphitiMemoryAdapter()

    assert adapter.is_available() is False
    assert adapter.search(query="fastText AG News") == []
    assert adapter.upsert(_memory_card()) == {
        "status": "skipped",
        "adapter": "graphiti",
        "reason": adapter.status().reason,
    }


def test_graphiti_adapter_upserts_card_as_structured_episode(tmp_path) -> None:
    class FakeGraphitiClient:
        def __init__(self) -> None:
            self.added: list[dict[str, Any]] = []

        async def add_episode(self, **kwargs: Any) -> dict[str, str]:
            self.added.append(kwargs)
            return {"uuid": "episode-123"}

    client = FakeGraphitiClient()
    adapter = GraphitiMemoryAdapter(client=client)

    result = adapter.upsert(_rich_memory_card(tmp_path))

    assert result["status"] == "indexed"
    assert result["adapter"] == "graphiti"
    assert result["card_id"] == "mem-fasttext-arxiv-1607.01759-best-patch"
    assert client.added
    episode = client.added[0]
    payload = json.loads(episode["episode_body"])
    assert episode["name"] == "research-memory:mem-fasttext-arxiv-1607.01759-best-patch"
    assert episode["source_description"] == "ml-research-loop research memory card"
    assert payload["card"]["card_id"] == "mem-fasttext-arxiv-1607.01759-best-patch"
    assert {"type": "paper", "id": "arxiv:1607.01759"} in payload["entities"]
    assert {"type": "dataset", "id": "AG News"} in payload["entities"]
    assert {"type": "model", "id": "fastText"} in payload["entities"]
    assert {"type": "metric", "id": "P@1"} in payload["entities"]
    assert any(relation["predicate"] == "EVALUATED_ON" for relation in payload["relations"])
    assert any(relation["predicate"] == "HAS_ARTIFACT" for relation in payload["relations"])


def test_graphiti_adapter_search_normalizes_edge_results() -> None:
    class FakeEdge:
        uuid = "edge-123"
        fact = "wordNgrams=2 improved local P@1"
        name = "IMPROVED_METRIC"
        score = 0.91
        episodes = ["episode-123"]

    class FakeGraphitiClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        async def search(self, query: str, **kwargs: Any) -> list[FakeEdge]:
            self.calls.append({"query": query, **kwargs})
            return [FakeEdge()]

    client = FakeGraphitiClient()
    adapter = GraphitiMemoryAdapter(client=client)

    results = adapter.search(query="fastText AG News", limit=2)

    assert client.calls == [{"query": "fastText AG News", "num_results": 2}]
    assert results == [
        {
            "adapter": "graphiti",
            "text": "wordNgrams=2 improved local P@1",
            "score": 0.91,
            "metadata": {
                "uuid": "edge-123",
                "name": "IMPROVED_METRIC",
                "episodes": ["episode-123"],
                "raw_type": "FakeEdge",
            },
        }
    ]


def test_graphiti_adapter_reads_optional_runtime_model_env(monkeypatch: Any) -> None:
    monkeypatch.setenv("ML_RESEARCH_LOOP_GRAPHITI_LLM_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.setenv("ML_RESEARCH_LOOP_GRAPHITI_LLM_API_KEY", "local-key")
    monkeypatch.setenv("ML_RESEARCH_LOOP_GRAPHITI_LLM_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setenv("ML_RESEARCH_LOOP_GRAPHITI_LLM_SMALL_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setenv(
        "ML_RESEARCH_LOOP_GRAPHITI_EMBEDDING_MODEL",
        "text-embedding-nomic-embed-text-v1.5",
    )
    monkeypatch.setenv("ML_RESEARCH_LOOP_GRAPHITI_EMBEDDING_DIM", "768")

    adapter = GraphitiMemoryAdapter(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="password",
    )

    assert adapter._uses_custom_runtime_clients() is True
    assert adapter.llm_base_url == "http://127.0.0.1:1234/v1"
    assert adapter.llm_api_key == "local-key"
    assert adapter.llm_model == "openai/gpt-oss-20b"
    assert adapter.llm_small_model == "openai/gpt-oss-20b"
    assert adapter.embedding_model == "text-embedding-nomic-embed-text-v1.5"
    assert adapter.embedding_dim == 768


def test_graphiti_adapter_passes_runtime_clients_to_graphiti(monkeypatch: Any) -> None:
    class FakeGraphiti:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

    adapter = GraphitiMemoryAdapter(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="password",
    )
    monkeypatch.setattr(adapter, "_load_graphiti", lambda: (FakeGraphiti, "json"))
    monkeypatch.setattr(
        adapter,
        "_build_graphiti_runtime_clients",
        lambda: {"llm_client": "llm", "embedder": "embedder", "cross_encoder": "reranker"},
    )

    client, should_close = adapter._configured_client()

    assert should_close is True
    assert client.args == ("bolt://localhost:7687", "neo4j", "password")
    assert client.kwargs == {
        "llm_client": "llm",
        "embedder": "embedder",
        "cross_encoder": "reranker",
    }


def test_cognee_adapter_is_disabled_and_skips_operations(monkeypatch: Any) -> None:
    _force_missing_optional_dependencies(monkeypatch)
    adapter = CogneeMemoryAdapter()

    assert adapter.is_available() is False
    assert adapter.search(query="fastText AG News") == []
    assert adapter.upsert(_memory_card()) == {
        "status": "skipped",
        "adapter": "cognee",
        "reason": adapter.status().reason,
    }


def test_cognee_adapter_adds_cognifies_and_searches_chunks(tmp_path) -> None:
    class FakeSearchType:
        CHUNKS = "CHUNKS"

    class FakeCogneeModule:
        SearchType = FakeSearchType

        def __init__(self) -> None:
            self.add_calls: list[dict[str, Any]] = []
            self.cognify_calls: list[dict[str, Any]] = []
            self.search_calls: list[dict[str, Any]] = []

        async def add(self, **kwargs: Any) -> dict[str, str]:
            self.add_calls.append(kwargs)
            return {"pipeline_run_id": "add-123"}

        async def cognify(self, **kwargs: Any) -> dict[str, str]:
            self.cognify_calls.append(kwargs)
            return {"pipeline_run_id": "cognify-123"}

        async def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
            self.search_calls.append({"query": query, **kwargs})
            return [
                {
                    "text": "release proof bundle mentions local P@1",
                    "score": 0.82,
                    "source": "release-proof-manifest.json",
                }
            ]

    module = FakeCogneeModule()
    adapter = CogneeMemoryAdapter(
        cognee_module=module,
        dataset_name="ml-research-loop-test",
        cognify_after_upsert=True,
    )

    upsert = adapter.upsert(_rich_memory_card(tmp_path))
    search_results = adapter.search(query="release proof", limit=2)

    assert upsert["status"] == "indexed"
    assert module.add_calls
    assert module.add_calls[0]["dataset_name"] == "ml-research-loop-test"
    assert "fastText AG News" in module.add_calls[0]["data"]
    assert module.cognify_calls == [{"datasets": ["ml-research-loop-test"]}]
    assert module.search_calls == [
        {
            "query": "release proof",
            "query_type": "CHUNKS",
            "datasets": ["ml-research-loop-test"],
            "top_k": 2,
        }
    ]
    assert search_results == [
        {
            "adapter": "cognee",
            "text": "release proof bundle mentions local P@1",
            "score": 0.82,
            "metadata": {
                "source": "release-proof-manifest.json",
                "raw_type": "dict",
            },
        }
    ]
