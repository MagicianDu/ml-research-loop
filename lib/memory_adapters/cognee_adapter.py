from __future__ import annotations

import importlib
import importlib.util
import json
import os
from typing import Any

from lib.memory_adapters import AdapterStatus, run_async
from lib.research_memory import ResearchMemoryCard


def _card_document(card: ResearchMemoryCard) -> str:
    evidence = [
        {
            "source_id": item.source_id,
            "artifact_path": item.artifact_path,
            "quote": item.quote,
            "strength": item.strength,
            "url": item.url,
        }
        for item in card.evidence_refs
    ]
    artifacts = [
        {
            "name": item.name,
            "path": item.path,
            "sha256": item.sha256,
            "artifact_type": item.artifact_type,
        }
        for item in card.artifact_refs
    ]
    payload = {
        "card": card.to_dict(),
        "evidence_refs": evidence,
        "artifact_refs": artifacts,
    }
    return "\n".join([
        f"Research memory card: {card.card_id}",
        f"Summary: {card.summary}",
        f"Task family: {card.task_family}",
        f"Papers: {', '.join(card.paper_ids)}",
        f"Datasets: {', '.join(card.datasets)}",
        f"Model: {card.model_family or ''}",
        f"Metric: {card.metric_name or ''}",
        f"Claim boundary: {card.claim_boundary}",
        "JSON:",
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
    ])


def _result_text(item: Any) -> str:
    if isinstance(item, dict):
        for key in ("text", "chunk", "content", "summary"):
            value = item.get(key)
            if value:
                return str(value)
    for attr in ("text", "chunk", "content", "summary"):
        value = getattr(item, attr, None)
        if value:
            return str(value)
    return str(item)


def _result_score(item: Any) -> float | None:
    value = item.get("score") if isinstance(item, dict) else getattr(item, "score", None)
    return float(value) if value is not None else None


def _result_metadata(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return {
            key: value
            for key, value in item.items()
            if key not in {"text", "chunk", "content", "summary", "score"}
        } | {"raw_type": "dict"}
    metadata: dict[str, Any] = {"raw_type": type(item).__name__}
    for attr in ("source", "metadata", "id"):
        value = getattr(item, attr, None)
        if value is not None:
            metadata[attr] = value
    return metadata


class CogneeMemoryAdapter:
    name = "cognee"
    required = False
    dependency_modules = ("cognee",)

    def __init__(
        self,
        *,
        cognee_module: Any | None = None,
        dataset_name: str | None = None,
        cognify_after_upsert: bool = True,
        search_type: str = "CHUNKS",
    ) -> None:
        self.cognee_module = cognee_module
        self.dataset_name = (
            dataset_name
            or os.getenv("ML_RESEARCH_LOOP_COGNEE_DATASET")
            or "ml_research_loop_memory"
        )
        self.cognify_after_upsert = cognify_after_upsert
        self.search_type = search_type

    def _available_dependency(self) -> str | None:
        for module_name in self.dependency_modules:
            try:
                if importlib.util.find_spec(module_name) is not None:
                    return module_name
            except (ImportError, ValueError):
                continue
        return None

    def status(self) -> AdapterStatus:
        if self.cognee_module is not None:
            return AdapterStatus(
                name=self.name,
                enabled=True,
                required=self.required,
                reason="injected cognee module configured",
            )
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

    def _module(self) -> Any:
        if self.cognee_module is not None:
            return self.cognee_module
        dependency = self._available_dependency()
        if dependency is None:
            raise RuntimeError("cognee dependency is not importable")
        return importlib.import_module(dependency)

    def _query_type(self, module: Any) -> Any:
        search_type = getattr(module, "SearchType", None)
        if search_type is not None:
            return getattr(search_type, self.search_type, self.search_type)
        return self.search_type

    def search(self, *, query: str, limit: int = 10) -> list[dict[str, Any]]:
        if not self.is_available():
            return []
        return run_async(self.async_search(query=query, limit=limit))

    async def async_search(self, *, query: str, limit: int = 10) -> list[dict[str, Any]]:
        module = self._module()
        query_type = self._query_type(module)
        try:
            raw_results = await module.search(
                query,
                query_type=query_type,
                datasets=[self.dataset_name],
                top_k=limit,
            )
        except TypeError:
            try:
                raw_results = await module.search(query, query_type=query_type)
            except TypeError:
                raw_results = await module.search(query)
        results = list(raw_results or [])[:limit]
        return [
            {
                "adapter": self.name,
                "text": _result_text(item),
                "score": _result_score(item),
                "metadata": _result_metadata(item),
            }
            for item in results
        ]

    def upsert(self, card: ResearchMemoryCard) -> dict[str, Any]:
        status = self.status()
        if not status.enabled:
            return {
                "status": "skipped",
                "adapter": self.name,
                "reason": status.reason,
            }
        return run_async(self.async_upsert(card))

    async def async_upsert(self, card: ResearchMemoryCard) -> dict[str, Any]:
        module = self._module()
        add_result = await module.add(
            data=_card_document(card),
            dataset_name=self.dataset_name,
        )
        cognify_result = None
        if self.cognify_after_upsert:
            cognify_result = await module.cognify(datasets=[self.dataset_name])
        return {
            "status": "indexed",
            "adapter": self.name,
            "card_id": card.card_id,
            "dataset_name": self.dataset_name,
            "cognified": self.cognify_after_upsert,
            "add_result": add_result,
            "cognify_result": cognify_result,
        }
