from lib.research_case import (
    EvidenceRef,
    ResearchCase,
    ResearchClaim,
    ResearchMilestone,
    summarize_research_case,
)


def test_research_case_summarizes_claims_evidence_and_milestones() -> None:
    case = ResearchCase(
        case_id="case-memflow-mini",
        objective="Reproduce one bounded MemFlow claim",
        claims=[
            ResearchClaim(
                claim_id="claim-routing",
                text="Intent routing improves evidence selection",
                status="supported_local",
                evidence_refs=[
                    EvidenceRef(
                        source_id="paper-1",
                        artifact_path="docs/evidence/memflow.md",
                        quote="intent-driven memory orchestration",
                        strength="paper_claim",
                    )
                ],
            )
        ],
        milestones=[
            ResearchMilestone(
                milestone_id="exp-001",
                kind="experiment",
                status="passed",
                artifact_path=".demo_runs/case/metrics.json",
                metric_name="answer_accuracy",
                metric_value=0.57,
            )
        ],
        forbidden_claims=["official benchmark score"],
    )

    summary = summarize_research_case(case)

    assert summary["case_id"] == "case-memflow-mini"
    assert summary["supported_claim_count"] == 1
    assert summary["passed_milestone_count"] == 1
    assert summary["official_scores_claimed"] is False
    assert summary["forbidden_claims"] == ["official benchmark score"]
