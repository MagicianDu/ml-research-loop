from __future__ import annotations

import importlib
import importlib.util
import json
import os
from types import SimpleNamespace
from datetime import datetime, timezone
from typing import Any

from lib.memory_adapters import AdapterStatus, run_async
from lib.research_memory import ResearchMemoryCard


def _adapter_entities(card: ResearchMemoryCard) -> list[dict[str, str]]:
    entities: list[dict[str, str]] = [{"type": "memory_card", "id": card.card_id}]
    entities.extend({"type": "paper", "id": paper_id} for paper_id in card.paper_ids)
    entities.extend({"type": "dataset", "id": dataset} for dataset in card.datasets)
    if card.model_family:
        entities.append({"type": "model", "id": card.model_family})
    if card.metric_name:
        entities.append({"type": "metric", "id": card.metric_name})
    if card.patch_type:
        entities.append({"type": "patch", "id": card.patch_type})
    if card.failure_category:
        entities.append({"type": "failure", "id": card.failure_category})
    entities.extend(
        {"type": "artifact", "id": artifact.name} for artifact in card.artifact_refs
    )
    return entities


def _adapter_relations(card: ResearchMemoryCard) -> list[dict[str, str]]:
    relations: list[dict[str, str]] = []
    card_id = f"memory_card:{card.card_id}"
    for paper_id in card.paper_ids:
        relations.append({
            "subject": card_id,
            "predicate": "SUPPORTS_PAPER",
            "object": f"paper:{paper_id}",
        })
    for dataset in card.datasets:
        relations.append({
            "subject": card_id,
            "predicate": "EVALUATED_ON",
            "object": f"dataset:{dataset}",
        })
    if card.model_family:
        relations.append({
            "subject": card_id,
            "predicate": "USES_MODEL",
            "object": f"model:{card.model_family}",
        })
    if card.metric_name:
        relations.append({
            "subject": card_id,
            "predicate": "REPORTS_METRIC",
            "object": f"metric:{card.metric_name}",
        })
    if card.patch_type:
        relations.append({
            "subject": card_id,
            "predicate": "HAS_PATCH",
            "object": f"patch:{card.patch_type}",
        })
    if card.failure_category:
        relations.append({
            "subject": card_id,
            "predicate": "HAS_FAILURE",
            "object": f"failure:{card.failure_category}",
        })
    for artifact in card.artifact_refs:
        relations.append({
            "subject": card_id,
            "predicate": "HAS_ARTIFACT",
            "object": f"artifact:{artifact.name}",
        })
    return relations


def _env_value(name: str) -> str | None:
    value = os.getenv(name)
    return value if value else None


def _first_env_value(*names: str) -> str | None:
    for name in names:
        value = _env_value(name)
        if value:
            return value
    return None


def _env_int(name: str) -> int | None:
    value = _env_value(name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{name} must be an integer") from None


def _episode_payload(card: ResearchMemoryCard) -> dict[str, Any]:
    return {
        "source": "ml-research-loop.research_memory_card",
        "card": card.to_dict(),
        "entities": _adapter_entities(card),
        "relations": _adapter_relations(card),
        "claim_boundary": card.claim_boundary,
        "official_scores_claimed": card.official_scores_claimed,
    }


def _result_text(item: Any) -> str:
    for attr in ("fact", "text", "summary", "content"):
        value = getattr(item, attr, None)
        if value:
            return str(value)
    if isinstance(item, dict):
        for key in ("fact", "text", "summary", "content"):
            value = item.get(key)
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
            if key not in {"fact", "text", "summary", "content", "score"}
        } | {"raw_type": "dict"}
    metadata: dict[str, Any] = {"raw_type": type(item).__name__}
    for attr in ("uuid", "name", "episodes"):
        value = getattr(item, attr, None)
        if value is not None:
            metadata[attr] = value
    return metadata


async def _close_awaitable(result: Any) -> None:
    if hasattr(result, "__await__"):
        await result


async def _close_owned_graphiti_client(client: Any) -> None:
    for owner_name in ("llm_client", "embedder", "cross_encoder"):
        owner = getattr(client, owner_name, None)
        runtime_client = getattr(owner, "client", None)
        if runtime_client is None:
            continue
        close = getattr(runtime_client, "close", None) or getattr(runtime_client, "aclose", None)
        if close is not None:
            await _close_awaitable(close())

    close_result = client.close()
    await _close_awaitable(close_result)


class GraphitiMemoryAdapter:
    name = "graphiti"
    required = False
    dependency_modules = ("graphiti_core", "graphiti")

    def __init__(
        self,
        *,
        client: Any | None = None,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        episode_type_json: Any | None = None,
        llm_api_key: str | None = None,
        llm_base_url: str | None = None,
        llm_model: str | None = None,
        llm_small_model: str | None = None,
        embedding_api_key: str | None = None,
        embedding_base_url: str | None = None,
        embedding_model: str | None = None,
        embedding_dim: int | None = None,
        llm_structured_output: str | None = None,
    ) -> None:
        self.client = client
        self.uri = uri or os.getenv("ML_RESEARCH_LOOP_GRAPHITI_URI")
        self.user = user or os.getenv("ML_RESEARCH_LOOP_GRAPHITI_USER")
        self.password = password or os.getenv("ML_RESEARCH_LOOP_GRAPHITI_PASSWORD")
        self.episode_type_json = episode_type_json
        self.llm_api_key = llm_api_key or _first_env_value(
            "ML_RESEARCH_LOOP_GRAPHITI_LLM_API_KEY",
            "OPENAI_API_KEY",
        )
        self.llm_base_url = llm_base_url or _first_env_value(
            "ML_RESEARCH_LOOP_GRAPHITI_LLM_BASE_URL",
            "OPENAI_BASE_URL",
        )
        self.llm_model = llm_model or _env_value("ML_RESEARCH_LOOP_GRAPHITI_LLM_MODEL")
        self.llm_small_model = llm_small_model or _env_value(
            "ML_RESEARCH_LOOP_GRAPHITI_LLM_SMALL_MODEL"
        )
        self.embedding_api_key = embedding_api_key or _first_env_value(
            "ML_RESEARCH_LOOP_GRAPHITI_EMBEDDING_API_KEY",
            "OPENAI_API_KEY",
        )
        self.embedding_base_url = embedding_base_url or _first_env_value(
            "ML_RESEARCH_LOOP_GRAPHITI_EMBEDDING_BASE_URL",
            "OPENAI_BASE_URL",
        )
        self.embedding_model = embedding_model or _env_value(
            "ML_RESEARCH_LOOP_GRAPHITI_EMBEDDING_MODEL"
        )
        self.embedding_dim = embedding_dim or _env_int(
            "ML_RESEARCH_LOOP_GRAPHITI_EMBEDDING_DIM"
        )
        self.llm_structured_output = (
            llm_structured_output
            or _env_value("ML_RESEARCH_LOOP_GRAPHITI_LLM_STRUCTURED_OUTPUT")
            or "responses_parse"
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
        if self.client is not None:
            return AdapterStatus(
                name=self.name,
                enabled=True,
                required=self.required,
                reason="injected graphiti client configured",
            )
        dependency = self._available_dependency()
        if dependency is None:
            return AdapterStatus(
                name=self.name,
                enabled=False,
                required=self.required,
                reason=(
                    "optional dependency missing: install graphiti_core or graphiti "
                    "to enable the graphiti adapter"
                ),
            )
        if not all([self.uri, self.user, self.password]):
            return AdapterStatus(
                name=self.name,
                enabled=False,
                required=self.required,
                reason=(
                    "graphiti dependency is importable but "
                    "ML_RESEARCH_LOOP_GRAPHITI_URI/USER/PASSWORD are not fully set"
                ),
            )
        return AdapterStatus(
            name=self.name,
            enabled=True,
            required=self.required,
            reason=f"optional dependency '{dependency}' is importable and configured",
        )

    def is_available(self) -> bool:
        return self.status().enabled

    def _load_graphiti(self) -> tuple[Any, Any]:
        dependency = self._available_dependency()
        if dependency is None:
            raise RuntimeError("Graphiti dependency is not importable")
        graphiti_module = importlib.import_module(dependency)
        graphiti_cls = getattr(graphiti_module, "Graphiti")
        try:
            nodes_module = importlib.import_module(f"{dependency}.nodes")
            episode_type = getattr(getattr(nodes_module, "EpisodeType"), "json")
        except (ImportError, AttributeError):
            episode_type = "json"
        return graphiti_cls, episode_type

    def _uses_custom_runtime_clients(self) -> bool:
        return any([
            self.llm_api_key,
            self.llm_base_url,
            self.llm_model,
            self.llm_small_model,
            self.embedding_api_key,
            self.embedding_base_url,
            self.embedding_model,
            self.embedding_dim,
            self.llm_structured_output != "responses_parse",
        ])

    def _build_graphiti_runtime_clients(self) -> dict[str, Any]:
        if not self._uses_custom_runtime_clients():
            return {}

        from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
        from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
        from graphiti_core.llm_client.config import LLMConfig
        from graphiti_core.llm_client.openai_client import OpenAIClient

        class ChatJsonSchemaOpenAIClient(OpenAIClient):
            async def _create_structured_completion(
                self,
                model: str,
                messages: list[Any],
                temperature: float | None,
                max_tokens: int,
                response_model: type[Any],
                reasoning: str | None = None,
                verbosity: str | None = None,
            ) -> Any:
                del reasoning, verbosity
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": response_model.__name__,
                            "schema": response_model.model_json_schema(),
                            "strict": True,
                        },
                    },
                )
                usage = getattr(response, "usage", None)
                return SimpleNamespace(
                    output_text=response.choices[0].message.content or "{}",
                    usage=SimpleNamespace(
                        input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
                        output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
                    ),
                )

            async def _create_completion(
                self,
                model: str,
                messages: list[Any],
                temperature: float | None,
                max_tokens: int,
                response_model: type[Any] | None = None,
                reasoning: str | None = None,
                verbosity: str | None = None,
            ) -> Any:
                del response_model, reasoning, verbosity
                return await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "text"},
                )

        llm_config = LLMConfig(
            api_key=self.llm_api_key,
            base_url=self.llm_base_url,
            model=self.llm_model,
            small_model=self.llm_small_model,
        )
        llm_client_cls = (
            ChatJsonSchemaOpenAIClient
            if self.llm_structured_output == "chat_json_schema"
            else OpenAIClient
        )
        embedding_config: dict[str, Any] = {
            "api_key": self.embedding_api_key,
            "base_url": self.embedding_base_url,
        }
        if self.embedding_model:
            embedding_config["embedding_model"] = self.embedding_model
        if self.embedding_dim:
            embedding_config["embedding_dim"] = self.embedding_dim

        return {
            "llm_client": llm_client_cls(config=llm_config),
            "embedder": OpenAIEmbedder(config=OpenAIEmbedderConfig(**embedding_config)),
            "cross_encoder": OpenAIRerankerClient(config=llm_config),
        }

    def _configured_client(self) -> tuple[Any, bool]:
        if self.client is not None:
            return self.client, False
        graphiti_cls, episode_type = self._load_graphiti()
        self.episode_type_json = self.episode_type_json or episode_type
        runtime_clients = self._build_graphiti_runtime_clients()
        return graphiti_cls(self.uri, self.user, self.password, **runtime_clients), True

    def search(self, *, query: str, limit: int = 10) -> list[dict[str, Any]]:
        if not self.is_available():
            return []
        return run_async(self.async_search(query=query, limit=limit))

    async def async_search(self, *, query: str, limit: int = 10) -> list[dict[str, Any]]:
        client, should_close = self._configured_client()
        try:
            try:
                raw_results = await client.search(query, num_results=limit)
            except TypeError:
                raw_results = await client.search(query)
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
        finally:
            if should_close and hasattr(client, "close"):
                await _close_owned_graphiti_client(client)

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
        client, should_close = self._configured_client()
        try:
            graphiti_cls_episode_type = self.episode_type_json
            if graphiti_cls_episode_type is None:
                try:
                    _, graphiti_cls_episode_type = self._load_graphiti()
                except RuntimeError:
                    graphiti_cls_episode_type = "json"
            payload = _episode_payload(card)
            await client.add_episode(
                name=f"research-memory:{card.card_id}",
                episode_body=json.dumps(payload, ensure_ascii=False, sort_keys=True),
                source=graphiti_cls_episode_type,
                source_description="ml-research-loop research memory card",
                reference_time=datetime.now(timezone.utc),
                previous_episode_uuids=[],
            )
            return {
                "status": "indexed",
                "adapter": self.name,
                "card_id": card.card_id,
                "entity_count": len(payload["entities"]),
                "relation_count": len(payload["relations"]),
            }
        finally:
            if should_close and hasattr(client, "close"):
                await _close_owned_graphiti_client(client)
