"""ml-intern research tool adapters for fusion workflows."""

from __future__ import annotations

from lib.research_protocol import ResearchSource


def normalize_paper_result(data: dict) -> ResearchSource:
    """Normalize a paper search/read result into a research source."""
    return ResearchSource(
        source_type="paper",
        title=data.get("title", ""),
        url=data.get("url", ""),
        summary=data.get("summary", data.get("abstract", "")),
        metadata={
            key: value
            for key, value in data.items()
            if key not in {"title", "url", "summary", "abstract"}
        },
    )


def normalize_dataset_result(data: dict) -> ResearchSource:
    """Normalize a Hugging Face dataset result into a research source."""
    dataset_id = data.get("id", data.get("dataset_id", ""))
    return ResearchSource(
        source_type="hf_dataset",
        title=dataset_id,
        url=f"https://huggingface.co/datasets/{dataset_id}" if dataset_id else "",
        summary=data.get("description", ""),
        metadata={"dataset_id": dataset_id},
    )


def search_papers(query: str, limit: int = 5) -> list[ResearchSource]:
    """Search papers and return normalized sources.

    The first fusion slice keeps this deterministic. Network-backed providers can
    plug in behind this function without changing the protocol.
    """
    return []


def search_hf_datasets(query: str, limit: int = 5) -> list[ResearchSource]:
    """Search Hugging Face datasets and return normalized sources."""
    return []


def search_github_code(query: str, limit: int = 5) -> list[ResearchSource]:
    """Search GitHub code and return normalized sources."""
    return []
