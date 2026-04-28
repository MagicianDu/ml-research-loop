"""Structured research context shared by ml-intern and autoresearch."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ResearchSource:
    """A source discovered by the ml-intern research layer."""

    source_type: str
    title: str
    url: str
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchSource":
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchFinding:
    """A claim or observation extracted from research sources."""

    finding_id: str
    claim: str
    evidence: list[str] = field(default_factory=list)
    relevance: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchFinding":
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchHypothesis:
    """A research-backed change that autoresearch can validate empirically."""

    hypothesis_id: str
    title: str
    rationale: str
    expected_metric: str
    expected_direction: str
    proposed_changes: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchHypothesis":
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchBrief:
    """The handoff object from ml-intern research into autoresearch validation."""

    objective: str
    sources: list[ResearchSource] = field(default_factory=list)
    findings: list[ResearchFinding] = field(default_factory=list)
    hypotheses: list[ResearchHypothesis] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchBrief":
        return cls(
            objective=data["objective"],
            sources=[ResearchSource.from_dict(item) for item in data.get("sources", [])],
            findings=[ResearchFinding.from_dict(item) for item in data.get("findings", [])],
            hypotheses=[
                ResearchHypothesis.from_dict(item)
                for item in data.get("hypotheses", [])
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "sources": [source.to_dict() for source in self.sources],
            "findings": [finding.to_dict() for finding in self.findings],
            "hypotheses": [hypothesis.to_dict() for hypothesis in self.hypotheses],
        }
