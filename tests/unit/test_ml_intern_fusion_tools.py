from __future__ import annotations

import json

from lib.research_protocol import ResearchSource
from ml_intern import research_tools
from ml_intern.tools.run_autoresearch import (
    ProposeHypothesesTool,
    ResearchTaskTool,
    ReviewResearchResultsTool,
    RunHypothesisExperimentTool,
)


def test_fusion_tool_names_match_mcp_names() -> None:
    assert ResearchTaskTool().name == "research_task"
    assert ProposeHypothesesTool().name == "propose_hypotheses"
    assert RunHypothesisExperimentTool().name == "run_hypothesis_experiment"
    assert ReviewResearchResultsTool().name == "review_research_results"


def test_research_task_tool_collects_sources(monkeypatch) -> None:
    def fake_search_papers(query: str, limit: int = 5):
        assert query == "alibi"
        assert limit == 1
        return [
            ResearchSource(
                source_type="paper",
                title="ALiBi",
                url="https://arxiv.org/abs/2108.12409",
                summary="Attention with linear biases.",
            )
        ]

    def fake_search_hf_datasets(query: str, limit: int = 5):
        assert query == "alibi"
        assert limit == 1
        return []

    monkeypatch.setattr(research_tools, "search_papers", fake_search_papers)
    monkeypatch.setattr(research_tools, "search_hf_datasets", fake_search_hf_datasets)

    payload = json.loads(
        ResearchTaskTool().forward(
            objective="reduce val_bpb",
            query="alibi",
            paper_limit=1,
            dataset_limit=1,
        )
    )

    assert payload["sources"][0]["title"] == "ALiBi"
    assert payload["hypotheses"][0]["hypothesis_id"] == "hyp-001"
