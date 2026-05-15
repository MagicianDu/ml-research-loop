"""Optional live smoke for configured Graphiti/cognee memory adapters."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from lib.memory_adapters import (
    get_memory_adapters,
    search_memory_adapters,
    sync_cards_to_adapters,
)
from lib.research_memory import ResearchMemoryStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument(
        "--adapter",
        action="append",
        choices=["graphiti", "cognee"],
        help="Optional adapter to smoke. Can be provided multiple times.",
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="Print JSON payload")
    return parser


def _adapter_statuses(adapter_names: list[str] | None) -> list[dict[str, Any]]:
    return [asdict(adapter.status()) for adapter in get_memory_adapters(adapter_names)]


def run_live_smoke(
    *,
    store: str | Path,
    query: str,
    adapter_names: list[str] | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    memory_store = ResearchMemoryStore(store)
    cards = memory_store.list_cards()
    statuses = _adapter_statuses(adapter_names)
    enabled_names = [status["name"] for status in statuses if status["enabled"]]
    base_payload: dict[str, Any] = {
        "store": str(store),
        "query": query,
        "card_count": len(cards),
        "adapter_statuses": statuses,
        "official_scores_claimed": False,
    }
    if not cards:
        return {
            **base_payload,
            "status": "skipped",
            "reason": "memory store contains no cards to sync",
        }
    if not enabled_names:
        return {
            **base_payload,
            "status": "skipped",
            "reason": "no requested memory adapters are enabled",
        }
    try:
        sync_payload = sync_cards_to_adapters(cards, adapter_names=enabled_names)
        search_payload = search_memory_adapters(
            query=query,
            limit=limit,
            adapter_names=enabled_names,
        )
    except Exception as exc:  # pragma: no cover - exercised by real external backends.
        return {
            **base_payload,
            "status": "failed",
            "reason": str(exc),
            "enabled_adapters": enabled_names,
        }
    status = "passed" if search_payload.get("match_count", 0) > 0 else "failed"
    return {
        **base_payload,
        "status": status,
        "enabled_adapters": enabled_names,
        "sync": sync_payload,
        "search": search_payload,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_live_smoke(
        store=args.store,
        query=args.query,
        adapter_names=args.adapter,
        limit=args.limit,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["status"] in {"passed", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
