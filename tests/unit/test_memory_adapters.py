from __future__ import annotations

import importlib.util
from typing import Any

from lib.memory_adapters import AdapterStatus, get_memory_adapter_status
from lib.memory_adapters.cognee_adapter import CogneeMemoryAdapter
from lib.memory_adapters.graphiti_adapter import GraphitiMemoryAdapter
from lib.research_memory import ResearchMemoryCard


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
