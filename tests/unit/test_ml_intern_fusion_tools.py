from __future__ import annotations

import json

from lib.task_protocol import TaskResult, TaskStatus
from lib.research_protocol import ResearchSource
from ml_intern import research_tools
from ml_intern.tools.run_autoresearch import (
    ProposeHypothesesTool,
    ResearchTaskTool,
    ReviewResearchResultsTool,
    RunAutoresearchTool,
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
    assert payload["findings"][0]["evidence"] == ["paper:ALiBi"]


def test_run_autoresearch_tool_passes_program_guidance(monkeypatch) -> None:
    captured = {}

    def fake_create_autoresearch_task(**kwargs):
        captured.update(kwargs)
        return kwargs["task_id"]

    monkeypatch.setattr(
        "ml_intern.tools.run_autoresearch.create_autoresearch_task",
        fake_create_autoresearch_task,
    )

    payload = json.loads(
        RunAutoresearchTool().forward(
            objective="minimize val_bpb",
            dataset_path="data.bin",
            focus_areas=["local refinement"],
            forbidden_changes=["do not edit prepare.py"],
            hints=["Continue from exp-002."],
            task_id="guided-task",
        )
    )

    assert payload["task_id"] == "guided-task"
    assert captured["focus_areas"] == ["local refinement"]
    assert captured["forbidden_changes"] == ["do not edit prepare.py"]
    assert captured["hints"] == ["Continue from exp-002."]


def test_review_research_results_tool_adds_research_review(monkeypatch) -> None:
    class FakeManager:
        def get_result(self, task_id: str):
            assert task_id == "demo"
            return TaskResult(
                task_id="demo",
                status=TaskStatus.COMPLETED,
                best_result={"experiment_id": "exp-001", "val": 0.42},
                hypotheses=[
                    {
                        "hypothesis_id": "hyp-001",
                        "title": "Try safer learning rate",
                        "expected_metric": "val_bpb",
                        "expected_direction": "minimize",
                    }
                ],
                experiments=[
                    {
                        "experiment_id": "exp-001",
                        "hypothesis_id": "hyp-001",
                        "metrics": {"val_bpb": 0.42},
                        "accepted": True,
                    }
                ],
            )

    monkeypatch.setattr("ml_intern.tools.run_autoresearch.AutoResearchManager", FakeManager)

    payload = json.loads(ReviewResearchResultsTool().forward("demo"))

    assert payload["research_review"]["decision"] == "continue_from_best"
    assert payload["research_review"]["hypothesis_outcomes"][0]["status"] == "supported"
