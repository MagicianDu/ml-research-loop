from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from lib.research_memory import MemorySuggestion, ResearchMemoryStore


DEFAULT_JSON_NAME = "memory-guided-proposal.json"
DEFAULT_MARKDOWN_NAME = "memory-guided-proposal.md"


def _proposal_from_suggestion(
    suggestion: MemorySuggestion,
    *,
    index: int,
) -> dict[str, Any]:
    return {
        "proposal_id": f"memory-guided-{index:03d}",
        "summary": suggestion.summary,
        "recommended_mcp_tool": suggestion.recommended_mcp_tool,
        "recommended_human_action": suggestion.recommended_human_action,
        "confidence": suggestion.confidence,
        "known_failures": list(suggestion.known_failures),
        "claim_boundary": suggestion.claim_boundary,
        "memory_provenance": list(suggestion.provenance),
        "executes_tool": False,
        "requires_client_review": True,
    }


def _next_step(suggestions: list[MemorySuggestion]) -> dict[str, Any]:
    if not suggestions:
        return {
            "mcp_tool": None,
            "human_action": "add_or_import_relevant_memory_before_planning",
            "executes_tool": False,
        }
    first = suggestions[0]
    return {
        "mcp_tool": first.recommended_mcp_tool,
        "human_action": (
            first.recommended_human_action
            or "review_memory_grounded_proposal_in_client"
        ),
        "executes_tool": False,
    }


def _write_markdown(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Memory-Guided Proposal Handoff",
        "",
        f"- Status: `{payload['status']}`",
        f"- Query: `{payload['query']}`",
        f"- Executes tool: `{payload['executes_tool']}`",
        f"- Official scores claimed: `{payload['official_scores_claimed']}`",
        "",
        "## Recommended Next Step",
        "",
        f"- MCP tool: `{payload['recommended_next_step']['mcp_tool']}`",
        f"- Human action: `{payload['recommended_next_step']['human_action']}`",
        "",
        "## Proposals",
        "",
    ]
    if not payload["proposals"]:
        lines.append("- No memory-backed proposal was generated.")
    for proposal in payload["proposals"]:
        provenance = ", ".join(
            item["card_id"] for item in proposal.get("memory_provenance", [])
        )
        lines.extend(
            [
                f"### {proposal['proposal_id']}",
                "",
                proposal["summary"],
                "",
                f"- Recommended MCP tool: `{proposal['recommended_mcp_tool']}`",
                f"- Claim boundary: {proposal['claim_boundary']}",
                f"- Memory provenance: `{provenance}`",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_memory_guided_proposal(
    *,
    store: str | Path,
    query: str,
    output_dir: str | Path,
    paper_id: str | None = None,
    dataset: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    memory_store = ResearchMemoryStore(store)
    suggestions = memory_store.suggest(
        query=query,
        paper_id=paper_id,
        dataset=dataset,
        limit=limit,
    )
    proposals = [
        _proposal_from_suggestion(suggestion, index=index)
        for index, suggestion in enumerate(suggestions, start=1)
    ]
    memory_provenance = [
        provenance
        for proposal in proposals
        for provenance in proposal.get("memory_provenance", [])
    ]
    json_path = output / DEFAULT_JSON_NAME
    markdown_path = output / DEFAULT_MARKDOWN_NAME
    payload: dict[str, Any] = {
        "status": "completed" if suggestions else "needs_memory",
        "query": query,
        "paper_id": paper_id,
        "dataset": dataset,
        "proposal_count": len(proposals),
        "recommended_next_step": _next_step(suggestions),
        "proposals": proposals,
        "memory_provenance": memory_provenance,
        "executes_tool": False,
        "official_scores_claimed": False,
        "claim_boundary": (
            "memory-assisted proposal handoff only; client must review before "
            "any MCP tool execution"
        ),
        "proposal_file": str(json_path),
        "markdown_file": str(markdown_path),
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_markdown(payload, markdown_path)
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a memory-guided, client-reviewed experiment proposal.",
    )
    parser.add_argument("--store", required=True, help="Research memory JSONL path.")
    parser.add_argument("--query", required=True, help="Search query for memory.")
    parser.add_argument("--output-dir", required=True, help="Output artifact directory.")
    parser.add_argument("--paper-id", default=None, help="Optional paper identifier.")
    parser.add_argument("--dataset", default=None, help="Optional dataset name.")
    parser.add_argument("--limit", type=int, default=5, help="Maximum suggestions.")
    parser.add_argument("--json", action="store_true", help="Print JSON payload.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = build_memory_guided_proposal(
        store=args.store,
        query=args.query,
        output_dir=args.output_dir,
        paper_id=args.paper_id,
        dataset=args.dataset,
        limit=args.limit,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(payload["proposal_file"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
