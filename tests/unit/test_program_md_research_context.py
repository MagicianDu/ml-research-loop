from __future__ import annotations

from lib.research_protocol import ResearchBrief, ResearchHypothesis, ResearchSource
from lib.task_protocol import (
    BaseCodeConfig,
    BudgetConfig,
    DatasetConfig,
    HyperparamSpace,
    MetricConfig,
    MetricDirection,
    TaskDefinition,
)
from scripts.generate_program_md import generate_program_md


def test_program_md_includes_research_sources_and_hypotheses() -> None:
    brief = ResearchBrief(
        objective="minimize val_bpb",
        sources=[
            ResearchSource(
                source_type="paper",
                title="ALiBi",
                url="https://arxiv.org/abs/2108.12409",
                summary="Attention with linear biases.",
            )
        ],
        hypotheses=[
            ResearchHypothesis(
                hypothesis_id="hyp-001",
                title="Try ALiBi",
                rationale="May improve long-context validation.",
                expected_metric="val_bpb",
                expected_direction="minimize",
                proposed_changes=["add ALiBi attention bias"],
            )
        ],
    )
    task = TaskDefinition(
        task_id="research-demo",
        objective="minimize val_bpb",
        dataset=DatasetConfig(name="tiny", path="data.bin"),
        metric=MetricConfig(name="val_bpb", direction=MetricDirection.MINIMIZE),
        hyperparameter_space={"depth": HyperparamSpace(type="choice", values=[1])},
        budget=BudgetConfig(max_experiments=1),
        base_code=BaseCodeConfig(train_py_url="file://train.py", prepare_py_url="file://prepare.py"),
        research_context=brief.to_dict(),
        hypotheses=[brief.hypotheses[0].to_dict()],
    )

    program = generate_program_md(task)

    assert "## Research Context" in program
    assert "ALiBi" in program
    assert "hyp-001" in program
    assert "add ALiBi attention bias" in program
