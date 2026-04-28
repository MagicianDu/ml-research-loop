from __future__ import annotations

from ml_intern.research_tools import normalize_dataset_result, normalize_paper_result


def test_normalize_paper_result_preserves_source_type() -> None:
    result = normalize_paper_result({
        "title": "ALiBi",
        "url": "https://arxiv.org/abs/2108.12409",
        "summary": "Linear biases for attention.",
    })

    assert result.source_type == "paper"
    assert result.title == "ALiBi"
    assert result.url.endswith("2108.12409")


def test_normalize_dataset_result_preserves_hf_dataset_id() -> None:
    result = normalize_dataset_result({
        "id": "roneneldan/TinyStories",
        "description": "Synthetic short stories.",
    })

    assert result.source_type == "hf_dataset"
    assert result.title == "roneneldan/TinyStories"
    assert result.metadata["dataset_id"] == "roneneldan/TinyStories"
