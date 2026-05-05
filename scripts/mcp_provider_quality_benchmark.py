#!/usr/bin/env python3
"""Run deterministic MCP provider-quality benchmarks."""

from __future__ import annotations

import argparse
import contextlib
import json
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from lib import mcp_service
from lib.research_protocol import ResearchSource
from ml_intern import research_tools


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MCP provider-quality benchmark pack")
    parser.add_argument("--runtime-root", type=Path, default=None)
    parser.add_argument(
        "--mode",
        choices=["fixture", "live"],
        default="fixture",
        help="Use fixture providers for release gates, or live providers for manual checks.",
    )
    return parser.parse_args()


def make_runtime_root(runtime_root: Path | None) -> Path:
    root = runtime_root or PROJECT_ROOT / ".demo_runs" / f"mcp-provider-{uuid.uuid4().hex[:8]}"
    root = root.expanduser().resolve()
    (root / "research-cache").mkdir(parents=True, exist_ok=True)
    return root


def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    response = mcp_service.handle_request({
        "jsonrpc": "2.0",
        "id": name,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })
    if response is None:
        raise RuntimeError(f"No MCP response for tool: {name}")
    if "error" in response:
        raise RuntimeError(response["error"]["message"])
    result = response["result"]
    payload = json.loads(result["content"][0]["text"])
    if result.get("isError"):
        raise RuntimeError(json.dumps(payload, ensure_ascii=False))
    return payload


@contextlib.contextmanager
def fixture_providers() -> Iterator[None]:
    original_papers = research_tools.search_papers
    original_datasets = research_tools.search_hf_datasets
    original_github_code = research_tools.search_github_code

    def fake_papers(query: str, limit: int = 5, **_: Any) -> list[ResearchSource]:
        del limit
        return [
            ResearchSource(
                source_type="paper",
                title="Fixture Transformer Scaling For Byte Modeling",
                url="https://arxiv.org/abs/2601.00001",
                summary=(
                    "A controlled paper fixture about transformer byte modeling, "
                    f"queried with {query}."
                ),
                metadata={
                    "provider": {
                        "name": "arxiv",
                        "record_id": "2601.00001",
                        "source_url": "https://arxiv.org/abs/2601.00001",
                    }
                },
            )
        ]

    def fake_datasets(query: str, limit: int = 5, **_: Any) -> list[ResearchSource]:
        del limit
        return [
            ResearchSource(
                source_type="hf_dataset",
                title="fixture/byte-modeling-corpus",
                url="https://huggingface.co/datasets/fixture/byte-modeling-corpus",
                summary=(
                    "A controlled dataset fixture with byte-token modeling metadata, "
                    f"queried with {query}."
                ),
                metadata={
                    "dataset_id": "fixture/byte-modeling-corpus",
                    "provider": {
                        "name": "huggingface",
                        "record_id": "fixture/byte-modeling-corpus",
                        "source_url": "https://huggingface.co/datasets/fixture/byte-modeling-corpus",
                    },
                },
            )
        ]

    def fake_github_code(query: str, limit: int = 5, **_: Any) -> list[ResearchSource]:
        del limit
        return [
            ResearchSource(
                source_type="github_code",
                title="fixture/byte-modeling:train.py",
                url="https://github.com/fixture/byte-modeling/blob/main/train.py",
                summary=(
                    "A controlled code fixture with a byte-modeling training loop, "
                    f"queried with {query}."
                ),
                metadata={
                    "repository": "fixture/byte-modeling",
                    "path": "train.py",
                    "provider": {
                        "name": "github",
                        "record_id": "fixture/byte-modeling:train.py",
                        "source_url": "https://github.com/fixture/byte-modeling/blob/main/train.py",
                    },
                },
            )
        ]

    research_tools.search_papers = fake_papers
    research_tools.search_hf_datasets = fake_datasets
    research_tools.search_github_code = fake_github_code
    try:
        yield
    finally:
        research_tools.search_papers = original_papers
        research_tools.search_hf_datasets = original_datasets
        research_tools.search_github_code = original_github_code


@contextlib.contextmanager
def rate_limited_backend(source_label: str) -> Iterator[None]:
    original_papers = research_tools.search_papers
    original_datasets = research_tools.search_hf_datasets
    original_github_code = research_tools.search_github_code

    def raise_429(*_: Any, **__: Any) -> list[ResearchSource]:
        raise RuntimeError("HTTP Error 429: Unknown Error")

    if source_label == "papers":
        research_tools.search_papers = raise_429
    elif source_label == "hf_datasets":
        research_tools.search_hf_datasets = raise_429
    elif source_label == "github_code":
        research_tools.search_github_code = raise_429
    else:
        raise ValueError(f"Unsupported source label: {source_label}")
    try:
        yield
    finally:
        research_tools.search_papers = original_papers
        research_tools.search_hf_datasets = original_datasets
        research_tools.search_github_code = original_github_code


def run_benchmark(
    runtime_root: Path,
    *,
    name: str,
    objective: str,
    query: str,
    source_label: str,
) -> dict[str, Any]:
    cache_dir = runtime_root / "research-cache" / name
    arguments = {
        "objective": objective,
        "query": query,
        "paper_limit": 1 if source_label == "papers" else 0,
        "dataset_limit": 1 if source_label == "hf_datasets" else 0,
        "github_limit": 1 if source_label == "github_code" else 0,
        "include_papers": source_label == "papers",
        "include_hf_datasets": source_label == "hf_datasets",
        "include_github_code": source_label == "github_code",
        "query_fanout": False,
        "cache_dir": str(cache_dir),
    }
    first_payload = call_tool("research_task", arguments)
    cached_payload = call_tool("research_task", arguments)
    with rate_limited_backend(source_label):
        rate_limit_payload = call_tool(
            "research_task",
            {
                **arguments,
                "query": f"{query} rate limit probe",
                "cache_dir": str(runtime_root / "rate-limit-cache" / name),
            },
        )

    first_cache = first_payload.get("cache", {}).get(source_label, {})
    second_cache = cached_payload.get("cache", {}).get(source_label, {})
    rate_limit_diagnostics = rate_limit_payload["retrieval_diagnostics"]
    return {
        "name": name,
        "source_label": source_label,
        "query": query,
        "status": cached_payload.get("status"),
        "provider_counts": cached_payload["provider_coverage"],
        "cache": {
            "first_hit": bool(first_cache.get("hit")),
            "second_hit": bool(second_cache.get("hit")),
            "cache_file": second_cache.get("cache_file"),
        },
        "retrieval_diagnostics": cached_payload["retrieval_diagnostics"],
        "rate_limit_diagnostics": rate_limit_diagnostics,
        "deduplication_report": cached_payload.get("deduplication_report", {}),
        "cache_summary": cached_payload.get("cache_summary", {}),
        "provider_quality_matrix": cached_payload.get("provider_quality_matrix", {}),
        "recovery_hints": rate_limit_diagnostics["recommended_recovery"],
        "evidence_citations": cached_payload["evidence_citations"],
        "source_rankings": cached_payload["source_rankings"],
    }


def main() -> int:
    args = parse_args()
    runtime_root = make_runtime_root(args.runtime_root)
    benchmark_specs = [
        {
            "name": "paper-heavy",
            "objective": "find paper-backed transformer changes for byte modeling",
            "query": "byte transformer architecture ablation",
            "source_label": "papers",
        },
        {
            "name": "dataset-heavy",
            "objective": "find dataset-backed byte modeling benchmarks",
            "query": "byte language modeling dataset",
            "source_label": "hf_datasets",
        },
        {
            "name": "code-heavy",
            "objective": "find code-backed byte modeling training loop patterns",
            "query": "byte language modeling train.py",
            "source_label": "github_code",
        },
    ]
    provider_context = fixture_providers() if args.mode == "fixture" else contextlib.nullcontext()
    with provider_context:
        benchmarks = [
            run_benchmark(runtime_root, **spec)
            for spec in benchmark_specs
        ]

    payload = {
        "status": "completed" if _benchmarks_passed(benchmarks) else "failed",
        "mode": args.mode,
        "runtime_root": str(runtime_root),
        "benchmarks": benchmarks,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "completed" else 1


def _benchmarks_passed(benchmarks: list[dict[str, Any]]) -> bool:
    return all(
        benchmark.get("provider_counts", {}).get("provider_count", 0) >= 1
        and benchmark.get("cache", {}).get("second_hit") is True
        and benchmark.get("rate_limit_diagnostics", {})
            .get("summary", {})
            .get("rate_limited_backend_count") == 1
        and bool(benchmark.get("evidence_citations"))
        for benchmark in benchmarks
    )


if __name__ == "__main__":
    raise SystemExit(main())
