"""Long-running research case state model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal


ClaimStatus = Literal["unsupported", "supported_local", "blocked", "needs_evidence"]
VALID_CLAIM_STATUSES = frozenset(
    {"unsupported", "supported_local", "blocked", "needs_evidence"}
)
EvidenceStrength = Literal[
    "paper_claim",
    "dataset_card",
    "code_reference",
    "runtime_artifact",
    "weak",
]
VALID_EVIDENCE_STRENGTHS = frozenset(
    {"paper_claim", "dataset_card", "code_reference", "runtime_artifact", "weak"}
)
MilestoneKind = Literal[
    "research",
    "environment",
    "experiment",
    "patch",
    "review",
    "proof_archive",
]
MilestoneStatus = Literal["pending", "passed", "failed", "blocked"]


@dataclass(frozen=True)
class EvidenceRef:
    source_id: str
    artifact_path: str
    quote: str
    strength: EvidenceStrength

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ResearchClaim:
    claim_id: str
    text: str
    status: ClaimStatus
    evidence_refs: list[EvidenceRef] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["evidence_refs"] = [item.to_dict() for item in self.evidence_refs]
        return data


@dataclass(frozen=True)
class ResearchMilestone:
    milestone_id: str
    kind: MilestoneKind
    status: MilestoneStatus
    artifact_path: str | None = None
    metric_name: str | None = None
    metric_value: float | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ResearchCase:
    case_id: str
    objective: str
    claims: list[ResearchClaim] = field(default_factory=list)
    milestones: list[ResearchMilestone] = field(default_factory=list)
    forbidden_claims: list[str] = field(default_factory=list)
    official_scores_claimed: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "objective": self.objective,
            "claims": [item.to_dict() for item in self.claims],
            "milestones": [item.to_dict() for item in self.milestones],
            "forbidden_claims": list(self.forbidden_claims),
            "official_scores_claimed": self.official_scores_claimed,
        }


def serialize_research_case(case: ResearchCase) -> dict[str, object]:
    return case.to_dict()


def summarize_research_case(case: ResearchCase) -> dict[str, object]:
    return {
        "case_id": case.case_id,
        "objective": case.objective,
        "supported_claim_count": sum(
            1 for claim in case.claims if claim.status == "supported_local"
        ),
        "blocked_claim_count": sum(
            1 for claim in case.claims if claim.status == "blocked"
        ),
        "passed_milestone_count": sum(
            1 for item in case.milestones if item.status == "passed"
        ),
        "failed_milestone_count": sum(
            1 for item in case.milestones if item.status == "failed"
        ),
        "official_scores_claimed": bool(case.official_scores_claimed),
        "forbidden_claims": list(case.forbidden_claims),
    }
