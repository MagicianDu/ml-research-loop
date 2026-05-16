from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lib.memory_adapters import AdapterStatus
from lib.research_memory import ResearchMemoryCard, ResearchMemoryStore


def _write_store(path: Path) -> None:
    ResearchMemoryStore(path).append(
        ResearchMemoryCard(
            card_id="mem-live-smoke",
            memory_type="procedure",
            task_family="live-smoke",
            summary="Live smoke memory card.",
            tags=["live-smoke"],
        )
    )


def test_memory_adapter_live_smoke_skips_when_adapters_are_disabled(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    from scripts import memory_adapter_live_smoke

    store = tmp_path / "memory.jsonl"
    _write_store(store)

    class DisabledAdapter:
        name = "graphiti"

        def status(self) -> AdapterStatus:
            return AdapterStatus(
                name="graphiti",
                enabled=False,
                required=False,
                reason="not configured",
            )

    monkeypatch.setattr(
        memory_adapter_live_smoke,
        "get_memory_adapters",
        lambda adapter_names=None: [DisabledAdapter()],
    )

    payload = memory_adapter_live_smoke.run_live_smoke(
        store=store,
        query="live smoke",
        adapter_names=["graphiti"],
    )

    assert payload["status"] == "skipped"
    assert payload["adapter_statuses"][0]["enabled"] is False
    assert payload["official_scores_claimed"] is False


def test_memory_adapter_live_smoke_syncs_and_searches_enabled_adapters(
    monkeypatch: Any,
    tmp_path: Path,
    capsys: Any,
) -> None:
    from scripts import memory_adapter_live_smoke

    store = tmp_path / "memory.jsonl"
    _write_store(store)

    class EnabledAdapter:
        name = "cognee"

        def status(self) -> AdapterStatus:
            return AdapterStatus(
                name="cognee",
                enabled=True,
                required=False,
                reason="configured",
            )

    monkeypatch.setattr(
        memory_adapter_live_smoke,
        "get_memory_adapters",
        lambda adapter_names=None: [EnabledAdapter()],
    )
    monkeypatch.setattr(
        memory_adapter_live_smoke,
        "sync_cards_to_adapters",
        lambda cards, adapter_names=None: {
            "status": "completed",
            "adapter_names": adapter_names,
            "card_count": len(cards),
            "results": [{"adapter": "cognee", "status": "indexed"}],
        },
    )
    monkeypatch.setattr(
        memory_adapter_live_smoke,
        "search_memory_adapters",
        lambda *, query, limit=10, adapter_names=None: {
            "status": "completed",
            "adapter_names": adapter_names,
            "match_count": 1,
            "results": [{"adapter": "cognee", "text": query, "score": 0.7}],
        },
    )

    payload = memory_adapter_live_smoke.run_live_smoke(
        store=store,
        query="live smoke",
        adapter_names=["cognee"],
        limit=3,
    )
    exit_code = memory_adapter_live_smoke.main([
        "--store",
        str(store),
        "--query",
        "live smoke",
        "--adapter",
        "cognee",
        "--limit",
        "3",
        "--json",
    ])

    printed = json.loads(capsys.readouterr().out)
    assert payload["status"] == "passed"
    assert payload["sync"]["results"][0]["status"] == "indexed"
    assert payload["search"]["results"][0]["adapter"] == "cognee"
    assert exit_code == 0
    assert printed["status"] == "passed"


def test_memory_adapter_live_smoke_fails_when_sync_has_failed_results(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    from scripts import memory_adapter_live_smoke

    store = tmp_path / "memory.jsonl"
    _write_store(store)

    class EnabledAdapter:
        name = "cognee"

        def status(self) -> AdapterStatus:
            return AdapterStatus(
                name="cognee",
                enabled=True,
                required=False,
                reason="configured",
            )

    monkeypatch.setattr(
        memory_adapter_live_smoke,
        "get_memory_adapters",
        lambda adapter_names=None: [EnabledAdapter()],
    )
    monkeypatch.setattr(
        memory_adapter_live_smoke,
        "sync_cards_to_adapters",
        lambda cards, adapter_names=None: {
            "status": "completed",
            "adapter_names": adapter_names,
            "card_count": len(cards),
            "results": [{"adapter": "cognee", "status": "failed", "reason": "timeout"}],
        },
    )
    monkeypatch.setattr(
        memory_adapter_live_smoke,
        "search_memory_adapters",
        lambda *, query, limit=10, adapter_names=None: {
            "status": "completed",
            "adapter_names": adapter_names,
            "match_count": 1,
            "results": [{"adapter": "cognee", "text": query, "score": 0.7}],
        },
    )

    payload = memory_adapter_live_smoke.run_live_smoke(
        store=store,
        query="live smoke",
        adapter_names=["cognee"],
    )

    assert payload["status"] == "failed"
    assert payload["reason"] == "one or more adapter sync operations failed"


def test_memory_adapter_live_smoke_fails_when_sync_has_nested_pipeline_error(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    from scripts import memory_adapter_live_smoke

    store = tmp_path / "memory.jsonl"
    _write_store(store)

    class EnabledAdapter:
        name = "cognee"

        def status(self) -> AdapterStatus:
            return AdapterStatus(
                name="cognee",
                enabled=True,
                required=False,
                reason="configured",
            )

    monkeypatch.setattr(
        memory_adapter_live_smoke,
        "get_memory_adapters",
        lambda adapter_names=None: [EnabledAdapter()],
    )
    monkeypatch.setattr(
        memory_adapter_live_smoke,
        "sync_cards_to_adapters",
        lambda cards, adapter_names=None: {
            "status": "completed",
            "adapter_names": adapter_names,
            "card_count": len(cards),
            "results": [
                {
                    "adapter": "cognee",
                    "status": "indexed",
                    "cognify_result": {
                        "run_info": {"status": "PipelineRunErrored"}
                    },
                }
            ],
        },
    )
    monkeypatch.setattr(
        memory_adapter_live_smoke,
        "search_memory_adapters",
        lambda *, query, limit=10, adapter_names=None: {
            "status": "completed",
            "adapter_names": adapter_names,
            "match_count": 1,
            "results": [{"adapter": "cognee", "text": query, "score": 0.7}],
        },
    )

    payload = memory_adapter_live_smoke.run_live_smoke(
        store=store,
        query="live smoke",
        adapter_names=["cognee"],
    )

    assert payload["status"] == "failed"
    assert payload["reason"] == "one or more adapter sync operations failed"
