from __future__ import annotations

import importlib.util
from typing import Any

from lib.memory_adapters import AdapterStatus
from lib.research_memory import ResearchMemoryCard


class CogneeMemoryAdapter:
    name = "cognee"
    required = False
    dependency_modules = ("cognee",)

    def _available_dependency(self) -> str | None:
        for module_name in self.dependency_modules:
            try:
                if importlib.util.find_spec(module_name) is not None:
                    return module_name
            except (ImportError, ValueError):
                continue
        return None

    def status(self) -> AdapterStatus:
        dependency = self._available_dependency()
        if dependency is None:
            return AdapterStatus(
                name=self.name,
                enabled=False,
                required=self.required,
                reason="optional dependency missing: install cognee to enable the cognee adapter",
            )
        return AdapterStatus(
            name=self.name,
            enabled=True,
            required=self.required,
            reason=f"optional dependency '{dependency}' is importable",
        )

    def is_available(self) -> bool:
        return self.status().enabled

    def search(self, *, query: str, limit: int = 10) -> list[dict[str, Any]]:
        if not self.is_available():
            return []
        return []

    def upsert(self, card: ResearchMemoryCard) -> dict[str, Any]:
        status = self.status()
        if not status.enabled:
            return {
                "status": "skipped",
                "adapter": self.name,
                "reason": status.reason,
            }
        return {
            "status": "skipped",
            "adapter": self.name,
            "reason": "cognee adapter interface is available but not configured",
        }
