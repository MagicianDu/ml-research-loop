from __future__ import annotations

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
