from __future__ import annotations

from lib.research_protocol import (
    ResearchBrief,
    ResearchFinding,
    ResearchHypothesis,
    ResearchSource,
)


def test_research_brief_round_trips_to_json_dict() -> None:
    brief = ResearchBrief(
        objective="reduce val_bpb on TinyStories",
        sources=[
            ResearchSource(
                source_type="paper",
                title="Attention Is All You Need",
                url="https://arxiv.org/abs/1706.03762",
                summary="Transformer attention baseline.",
            )
        ],
        findings=[
            ResearchFinding(
                finding_id="finding-001",
                claim="ALiBi can improve long-context extrapolation.",
                evidence=["paper:alibi"],
                relevance="May improve validation bpb at fixed context budget.",
            )
        ],
        hypotheses=[
            ResearchHypothesis(
                hypothesis_id="hyp-001",
                title="Try ALiBi positional bias",
                rationale="Prior work suggests better length generalization.",
                expected_metric="val_bpb",
                expected_direction="minimize",
                proposed_changes=["replace absolute position embedding with ALiBi"],
                risk_notes=["implementation may slow attention kernel"],
            )
        ],
    )

    restored = ResearchBrief.from_dict(brief.to_dict())

    assert restored.objective == "reduce val_bpb on TinyStories"
    assert restored.sources[0].source_type == "paper"
    assert restored.findings[0].finding_id == "finding-001"
    assert restored.hypotheses[0].hypothesis_id == "hyp-001"
