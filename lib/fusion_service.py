"""Fusion workflow helpers for ml-intern research and autoresearch validation."""

from __future__ import annotations

from lib.research_protocol import ResearchBrief, ResearchHypothesis


def propose_hypotheses(objective: str, sources: list[dict] | None = None) -> dict:
    """Build deterministic first-pass hypotheses from research sources."""
    source_titles = [
        source.get("title", "")
        for source in sources or []
        if source.get("title")
    ]
    rationale_suffix = ", ".join(source_titles) if source_titles else "no external sources"
    hypothesis = ResearchHypothesis(
        hypothesis_id="hyp-001",
        title=f"Validate research-backed change for {objective}",
        rationale=f"Generated from available research context: {rationale_suffix}",
        expected_metric="val_bpb",
        expected_direction="minimize",
        proposed_changes=["modify one SEARCH REGION parameter before broader code edits"],
        risk_notes=["initial implementation is conservative"],
    )
    brief = ResearchBrief(
        objective=objective,
        hypotheses=[hypothesis],
    )
    return brief.to_dict()
