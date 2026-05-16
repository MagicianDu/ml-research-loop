from __future__ import annotations

import asyncio
import importlib
import importlib.util
import os
from typing import Any

from lib.memory_adapters import AdapterStatus, run_async
from lib.research_memory import ResearchMemoryCard


RESEARCH_MEMORY_GRAPH_PROMPT = """
You extract a compact knowledge graph from one ml-research-loop ResearchMemoryCard.

Only use facts explicitly present in the card. Do not invent placeholders, question marks,
ellipsis-only values, fake paper IDs, fake metrics, or unsupported relationships.

Use these node types when present: ResearchMemoryCard, Paper, Dataset, Model, Metric,
Patch, Failure, Evidence, Artifact, ClaimBoundary, Config.

Use clear human-readable node IDs from the input text. Preserve exact identifiers such as
arxiv IDs, dataset names, model names, metric names, card IDs, artifact names, and source IDs.

Use these relationship names when supported by the input: supports_paper, evaluated_on,
uses_model, reports_metric, has_patch, has_failure, has_evidence, has_artifact,
has_claim_boundary, has_config.

Keep the graph small and precise. Prefer omitting uncertain facts over guessing.
"""


def _card_document(card: ResearchMemoryCard) -> str:
    lines = [
        f"Research memory card: {card.card_id}",
        f"Memory type: {card.memory_type}",
        f"Summary: {card.summary}",
        f"Task family: {card.task_family}",
        f"Papers: {_join(card.paper_ids)}",
        f"Datasets: {_join(card.datasets)}",
        f"Model: {card.model_family or 'unknown'}",
        (
            "Metric: "
            f"{card.metric_name or 'unknown'} "
            f"before={_value(card.metric_before)} "
            f"after={_value(card.metric_after)}"
        ),
        f"Patch type: {card.patch_type or 'none'}",
        f"Failure category: {card.failure_category or 'none'}",
        f"Claim boundary: {card.claim_boundary}",
        f"Official scores claimed: {str(card.official_scores_claimed).lower()}",
        f"Tags: {_join(card.tags)}",
    ]
    if card.config:
        config_facts = ", ".join(
            f"{key}={_value(value)}" for key, value in sorted(card.config.items())
        )
        lines.append(f"Config: {config_facts}")
    for item in card.evidence_refs:
        lines.append(
            "Evidence: "
            f"source_id={item.source_id}; "
            f"strength={item.strength}; "
            f"artifact_path={item.artifact_path or 'none'}; "
            f"url={item.url or 'none'}; "
            f"quote={item.quote or 'none'}"
        )
    for item in card.artifact_refs:
        lines.append(
            "Artifact: "
            f"name={item.name}; "
            f"path={item.path}; "
            f"type={item.artifact_type}; "
            f"sha256={item.sha256}"
        )
    return "\n".join(lines)


def _join(values: list[str]) -> str:
    return ", ".join(values) if values else "none"


def _value(value: Any) -> str:
    if value is None:
        return "none"
    return str(value)


def _env_float(name: str) -> float | None:
    value = os.getenv(name)
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"{name} must be a number") from None


def _env_int(name: str) -> int | None:
    value = os.getenv(name)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{name} must be an integer") from None


async def _await_with_timeout(awaitable: Any, *, timeout: float, operation: str) -> Any:
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout)
    except TimeoutError:
        raise TimeoutError(f"cognee {operation} timed out after {timeout:g}s") from None


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


def _is_low_quality_text(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if stripped in {"...", "…", "???", "???"}:
        return True
    if "??" in stripped:
        return True
    if stripped.count("…") >= 2:
        return True
    if len(stripped) < 12 and any(marker in stripped for marker in ("?", "…", "...")):
        return True
    return False


def _failure_payload(
    *,
    operation: str,
    reason: str,
    card_id: str | None = None,
    dataset_name: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "failed",
        "adapter": "cognee",
        "operation": operation,
        "reason": reason,
    }
    if card_id is not None:
        payload["card_id"] = card_id
    if dataset_name is not None:
        payload["dataset_name"] = dataset_name
    return payload


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_json_safe(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _json_safe(model_dump(mode="json"))
        except TypeError:
            return _json_safe(model_dump())
    return str(value)


def _is_failure_status(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.lower()
    return any(marker in normalized for marker in ("failed", "errored", "error"))


def _contains_failed_status(value: Any) -> bool:
    safe_value = _json_safe(value)
    if isinstance(safe_value, dict):
        for key, item in safe_value.items():
            if str(key).lower() == "status" and _is_failure_status(item):
                return True
            if _contains_failed_status(item):
                return True
        return False
    if isinstance(safe_value, list):
        return any(_contains_failed_status(item) for item in safe_value)
    return False


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
        operation_timeout_seconds: float | None = None,
        graph_prompt: str | None = None,
        chunks_per_batch: int | None = None,
    ) -> None:
        self.cognee_module = cognee_module
        self.dataset_name = (
            dataset_name
            or os.getenv("ML_RESEARCH_LOOP_COGNEE_DATASET")
            or "ml_research_loop_memory"
        )
        self.cognify_after_upsert = cognify_after_upsert
        self.search_type = search_type
        self.operation_timeout_seconds = (
            operation_timeout_seconds
            or _env_float("ML_RESEARCH_LOOP_COGNEE_TIMEOUT_SECONDS")
            or 180.0
        )
        self.graph_prompt = (
            graph_prompt
            or os.getenv("ML_RESEARCH_LOOP_COGNEE_GRAPH_PROMPT")
            or RESEARCH_MEMORY_GRAPH_PROMPT
        )
        self.chunks_per_batch = (
            chunks_per_batch
            or _env_int("ML_RESEARCH_LOOP_COGNEE_CHUNKS_PER_BATCH")
            or 1
        )

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
            raw_results = await _await_with_timeout(
                module.search(
                    query,
                    query_type=query_type,
                    datasets=[self.dataset_name],
                    top_k=limit,
                ),
                timeout=self.operation_timeout_seconds,
                operation="search",
            )
        except TypeError:
            try:
                raw_results = await _await_with_timeout(
                    module.search(query, query_type=query_type),
                    timeout=self.operation_timeout_seconds,
                    operation="search",
                )
            except TypeError:
                raw_results = await _await_with_timeout(
                    module.search(query),
                    timeout=self.operation_timeout_seconds,
                    operation="search",
                )
        except Exception:
            return []
        normalized_results: list[dict[str, Any]] = []
        for item in list(raw_results or []):
            text = _result_text(item)
            if _is_low_quality_text(text):
                continue
            normalized_results.append({
                "adapter": self.name,
                "text": text,
                "score": _result_score(item),
                "metadata": _result_metadata(item),
            })
            if len(normalized_results) == limit:
                break
        return normalized_results

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
        try:
            add_result = await _await_with_timeout(
                module.add(
                    data=_card_document(card),
                    dataset_name=self.dataset_name,
                ),
                timeout=self.operation_timeout_seconds,
                operation="add",
            )
        except Exception as exc:
            return _failure_payload(
                operation="add",
                reason=str(exc),
                card_id=card.card_id,
                dataset_name=self.dataset_name,
            )
        cognify_result = None
        if self.cognify_after_upsert:
            try:
                cognify_result = await _await_with_timeout(
                    module.cognify(
                        datasets=[self.dataset_name],
                        custom_prompt=self.graph_prompt,
                        chunks_per_batch=self.chunks_per_batch,
                    ),
                    timeout=self.operation_timeout_seconds,
                    operation="cognify",
                )
            except Exception as exc:
                return {
                    **_failure_payload(
                        operation="cognify",
                        reason=str(exc),
                        card_id=card.card_id,
                        dataset_name=self.dataset_name,
                    ),
                    "add_result": _json_safe(add_result),
                }
            safe_cognify_result = _json_safe(cognify_result)
            if _contains_failed_status(safe_cognify_result):
                return {
                    **_failure_payload(
                        operation="cognify",
                        reason="cognee cognify returned a failed pipeline status",
                        card_id=card.card_id,
                        dataset_name=self.dataset_name,
                    ),
                    "add_result": _json_safe(add_result),
                    "cognify_result": safe_cognify_result,
                }
        return {
            "status": "indexed",
            "adapter": self.name,
            "card_id": card.card_id,
            "dataset_name": self.dataset_name,
            "cognified": self.cognify_after_upsert,
            "add_result": _json_safe(add_result),
            "cognify_result": _json_safe(cognify_result),
        }
