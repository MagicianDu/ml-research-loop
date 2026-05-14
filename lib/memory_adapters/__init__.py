from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

from lib.research_memory import ResearchMemoryCard


@dataclass(frozen=True)
class AdapterStatus:
    name: str
    enabled: bool
    required: bool
    reason: str


class MemoryAdapter(Protocol):
    name: str

    def status(self) -> AdapterStatus:
        ...

    def is_available(self) -> bool:
        ...

    def search(self, *, query: str, limit: int = 10) -> list[dict[str, Any]]:
        ...

    def upsert(self, card: ResearchMemoryCard) -> dict[str, Any]:
        ...


def run_async(awaitable: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    if hasattr(awaitable, "close"):
        awaitable.close()
    raise RuntimeError("memory adapter sync methods cannot run inside an active event loop")


def get_memory_adapters(adapter_names: list[str] | None = None) -> list[MemoryAdapter]:
    from lib.memory_adapters.cognee_adapter import CogneeMemoryAdapter
    from lib.memory_adapters.graphiti_adapter import GraphitiMemoryAdapter

    registry: dict[str, MemoryAdapter] = {
        "graphiti": GraphitiMemoryAdapter(),
        "cognee": CogneeMemoryAdapter(),
    }
    if adapter_names:
        unknown = sorted(set(adapter_names) - set(registry))
        if unknown:
            raise ValueError(f"unknown memory adapter(s): {', '.join(unknown)}")
        return [registry[name] for name in adapter_names]
    return list(registry.values())


def get_memory_adapter_status() -> dict[str, AdapterStatus]:
    adapters = get_memory_adapters()
    return {adapter.name: adapter.status() for adapter in adapters}


def sync_cards_to_adapters(
    cards: list[ResearchMemoryCard],
    adapter_names: list[str] | None = None,
) -> dict[str, Any]:
    adapters = get_memory_adapters(adapter_names)
    results: list[dict[str, Any]] = []
    for adapter in adapters:
        for card in cards:
            results.append(adapter.upsert(card))
    return {
        "status": "completed",
        "adapter_names": [adapter.name for adapter in adapters],
        "card_count": len(cards),
        "results": results,
    }


def search_memory_adapters(
    *,
    query: str,
    limit: int = 10,
    adapter_names: list[str] | None = None,
) -> dict[str, Any]:
    adapters = get_memory_adapters(adapter_names)
    results: list[dict[str, Any]] = []
    for adapter in adapters:
        results.extend(adapter.search(query=query, limit=limit))
    limited_results = results[:limit]
    return {
        "status": "completed",
        "adapter_names": [adapter.name for adapter in adapters],
        "match_count": len(limited_results),
        "results": limited_results,
    }


__all__ = [
    "AdapterStatus",
    "MemoryAdapter",
    "get_memory_adapters",
    "get_memory_adapter_status",
    "run_async",
    "search_memory_adapters",
    "sync_cards_to_adapters",
]
