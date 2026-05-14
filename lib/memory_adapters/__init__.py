from __future__ import annotations

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


def get_memory_adapter_status() -> dict[str, AdapterStatus]:
    from lib.memory_adapters.cognee_adapter import CogneeMemoryAdapter
    from lib.memory_adapters.graphiti_adapter import GraphitiMemoryAdapter

    adapters: list[MemoryAdapter] = [
        GraphitiMemoryAdapter(),
        CogneeMemoryAdapter(),
    ]
    return {adapter.name: adapter.status() for adapter in adapters}


__all__ = [
    "AdapterStatus",
    "MemoryAdapter",
    "get_memory_adapter_status",
]
