"""Fusion workflow helpers for ml-intern research and autoresearch validation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from typing import Any

from lib.research_protocol import ResearchBrief, ResearchHypothesis, ResearchSource
from ml_intern import research_tools


def propose_hypotheses(objective: str, sources: list[dict] | None = None) -> dict:
    """Build deterministic first-pass hypotheses from research sources."""
    research_sources = [_source_from_dict(source) for source in sources or []]
    source_titles = [
        source.title
        for source in research_sources
        if source.title
    ]
    rationale_suffix = ", ".join(source_titles) if source_titles else "no external sources"
    hypothesis = ResearchHypothesis(
        hypothesis_id="hyp-001",
        title=f"Validate research-backed change for {objective}",
        rationale=f"Generated from available research context: {rationale_suffix}",
        expected_metric="val_bpb",
        expected_direction="minimize",
        proposed_changes=["modify one SEARCH REGION parameter before broader code edits"],
        risk_notes=["initial implementation is conservative"],
    )
    brief = ResearchBrief(
        objective=objective,
        sources=research_sources,
        hypotheses=[hypothesis],
    )
    return brief.to_dict()


def build_research_context(
    objective: str,
    query: str | None = None,
    paper_limit: int = 3,
    dataset_limit: int = 3,
    github_limit: int = 0,
    include_papers: bool = True,
    include_hf_datasets: bool = True,
    include_github_code: bool = False,
) -> dict[str, Any]:
    """Collect real research sources and turn them into a fusion research brief."""
    effective_query = (query or objective).strip()
    sources: list[ResearchSource] = []
    warnings: list[str] = []

    if include_papers:
        sources.extend(
            _collect_sources(
                "papers",
                lambda: research_tools.search_papers(effective_query, limit=paper_limit),
                warnings,
            )
        )
    if include_hf_datasets:
        sources.extend(
            _collect_sources(
                "hf_datasets",
                lambda: research_tools.search_hf_datasets(effective_query, limit=dataset_limit),
                warnings,
            )
        )
    if include_github_code:
        sources.extend(
            _collect_sources(
                "github_code",
                lambda: research_tools.search_github_code(effective_query, limit=github_limit),
                warnings,
            )
        )

    source_dicts = [source.to_dict() for source in sources]
    brief = propose_hypotheses(objective, source_dicts)
    brief.update({
        "status": "research_context_ready" if not warnings else "research_context_partial",
        "query": effective_query,
        "warnings": warnings,
        "source_counts": _source_counts(sources),
    })
    return brief


def _collect_sources(
    label: str,
    collect: Callable[[], list[ResearchSource]],
    warnings: list[str],
) -> list[ResearchSource]:
    try:
        return list(collect())
    except Exception as exc:  # noqa: BLE001 - research backends should degrade independently.
        warnings.append(f"{label}: {exc}")
        return []


def _source_counts(sources: list[ResearchSource]) -> dict[str, int]:
    counts = Counter(source.source_type for source in sources)
    return dict(counts)


def _source_from_dict(source: dict[str, Any]) -> ResearchSource:
    return ResearchSource(
        source_type=source.get("source_type", ""),
        title=source.get("title", ""),
        url=source.get("url", ""),
        summary=source.get("summary", ""),
        metadata=source.get("metadata", {}),
    )
