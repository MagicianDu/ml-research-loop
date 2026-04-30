"""Fusion workflow helpers for ml-intern research and autoresearch validation."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path
import re
import time
from typing import Any

from lib.research_components import parse_search_region
from lib.research_protocol import (
    ResearchBrief,
    ResearchFinding,
    ResearchHypothesis,
    ResearchSource,
)
from ml_intern import research_tools


PROVIDER_RETRY_POLICY = {
    "max_attempts": 2,
    "backoff_seconds": [0.0, 0.2],
    "retryable_categories": ["rate_limited", "timeout"],
}


def propose_hypotheses(objective: str, sources: list[dict] | None = None) -> dict:
    """Build deterministic first-pass hypotheses from research sources."""
    research_sources = [_source_from_dict(source) for source in sources or []]
    ranked_sources = _rank_for_hypothesis(research_sources)
    findings = derive_findings(objective, ranked_sources)
    source_titles = [
        source.title
        for source in ranked_sources
        if source.title
    ]
    finding_claims = [finding.claim for finding in findings[:3]]
    rationale_parts = []
    if source_titles:
        rationale_parts.append(", ".join(source_titles))
    if finding_claims:
        rationale_parts.append("; ".join(finding_claims))
    rationale_suffix = " | ".join(rationale_parts) if rationale_parts else "no external sources"
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
        sources=research_sources,
        findings=findings,
        hypotheses=[hypothesis],
    )
    return brief.to_dict()


def build_research_context(
    objective: str,
    query: str | None = None,
    paper_limit: int = 3,
    dataset_limit: int = 3,
    github_limit: int = 0,
    include_papers: bool = True,
    include_hf_datasets: bool = True,
    include_github_code: bool = False,
    cache_dir: str | Path | None = None,
    query_fanout: bool = True,
) -> dict[str, Any]:
    """Collect real research sources and turn them into a fusion research brief."""
    effective_query = (query or objective).strip()
    query_plan = build_query_plan(objective=objective, query=effective_query)
    sources: list[ResearchSource] = []
    warnings: list[str] = []
    cache: dict[str, Any] = {}
    diagnostics: dict[str, Any] = {"backends": {}}

    if include_papers:
        sources.extend(
            _collect_source_variants(
                "papers",
                lambda query_variant: research_tools.search_papers(query_variant, limit=paper_limit),
                warnings,
                query_plan=query_plan,
                limit=paper_limit,
                cache=cache,
                cache_dir=cache_dir,
                query_fanout=query_fanout,
                diagnostics=diagnostics,
            )
        )
    if include_hf_datasets:
        sources.extend(
            _collect_source_variants(
                "hf_datasets",
                lambda query_variant: research_tools.search_hf_datasets(query_variant, limit=dataset_limit),
                warnings,
                query_plan=query_plan,
                limit=dataset_limit,
                cache=cache,
                cache_dir=cache_dir,
                query_fanout=query_fanout,
                diagnostics=diagnostics,
            )
        )
    if include_github_code:
        sources.extend(
            _collect_source_variants(
                "github_code",
                lambda query_variant: research_tools.search_github_code(query_variant, limit=github_limit),
                warnings,
                query_plan=query_plan,
                limit=github_limit,
                cache=cache,
                cache_dir=cache_dir,
                query_fanout=query_fanout,
                diagnostics=diagnostics,
            )
        )

    sources = enrich_sources(
        deduplicate_sources(sources),
        objective=objective,
        query=effective_query,
    )
    provider_coverage = provider_coverage_summary(sources)
    source_dicts = [source.to_dict() for source in sources]
    brief = propose_hypotheses(objective, source_dicts)
    findings = [ResearchFinding.from_dict(item) for item in brief.get("findings", [])]
    brief.update({
        "status": "research_context_ready" if not warnings else "research_context_partial",
        "query": effective_query,
        "query_plan": query_plan,
        "warnings": warnings,
        "cache": cache,
        "evidence_quality": evidence_quality_summary(
            sources=sources,
            findings=findings,
            warnings=warnings,
            provider_coverage=provider_coverage,
        ),
        "evidence_citations": build_evidence_citations(
            findings=findings,
            sources=sources,
            objective=objective,
        ),
        "retrieval_diagnostics": finalize_retrieval_diagnostics(
            diagnostics=diagnostics,
            sources=sources,
            warnings=warnings,
        ),
        "provider_coverage": provider_coverage,
        "provider_coverage_gate": provider_coverage_gate(
            sources=sources,
            provider_coverage=provider_coverage,
        ),
        "source_counts": _source_counts(sources),
        "source_rankings": rank_sources(sources),
    })
    return brief


def read_paper_context(identifier: str, objective: str | None = None) -> dict[str, Any]:
    """Read a single paper and return an experiment-ready research brief slice."""
    source = research_tools.read_paper(identifier)
    effective_objective = (objective or source.title or identifier).strip()
    enriched_source = enrich_sources(
        [source],
        objective=effective_objective,
        query=source.title or identifier,
    )[0]
    evidence_snippets = extract_evidence_snippets(
        enriched_source,
        objective=effective_objective,
    )
    brief = propose_hypotheses(effective_objective, [enriched_source.to_dict()])
    return {
        "status": "paper_ready",
        "identifier": identifier,
        "objective": effective_objective,
        "source": enriched_source.to_dict(),
        "evidence_snippets": evidence_snippets,
        "findings": brief["findings"],
        "hypotheses": brief["hypotheses"],
    }


def build_query_plan(objective: str, query: str) -> list[dict[str, str]]:
    """Return deterministic query expansion candidates for auditability."""
    plan = [{"query": query, "reason": "primary"}]
    expanded_terms = sorted(_keywords(f"{objective} {query}"))
    expansion = " ".join(expanded_terms[:8])
    if expansion and expansion != query.lower():
        plan.append({"query": expansion, "reason": "keyword_expansion"})
    return plan


def deduplicate_sources(sources: list[ResearchSource]) -> list[ResearchSource]:
    """Deduplicate sources by URL, falling back to type/title."""
    seen: set[tuple[str, str]] = set()
    unique_sources: list[ResearchSource] = []
    for source in sources:
        keys = _source_keys(source)
        if any(key in seen for key in keys):
            continue
        seen.update(keys)
        unique_sources.append(source)
    return unique_sources


def enrich_sources(
    sources: list[ResearchSource],
    objective: str,
    query: str,
) -> list[ResearchSource]:
    """Attach deterministic relevance metadata while preserving source order."""
    enriched = []
    for source in sources:
        relevance = relevance_score(source, objective=objective, query=query)
        quality = source_evidence_quality(source, relevance)
        enriched.append(ResearchSource(
            source_type=source.source_type,
            title=source.title,
            url=source.url,
            summary=source.summary,
            metadata={
                **source.metadata,
                "relevance_score": relevance,
                "evidence_quality": quality,
            },
        ))
    return enriched


def source_evidence_quality(source: ResearchSource, relevance: float) -> dict[str, Any]:
    """Score whether a source has enough metadata and text to support findings."""
    reasons = []
    score = float(relevance)
    if source.summary.strip():
        score += 2.0
        reasons.append("has_summary")
    else:
        score -= 1.0
        reasons.append("missing_summary")
    if source.url.strip():
        score += 1.0
        reasons.append("has_url")
    else:
        score -= 0.5
        reasons.append("missing_url")
    if _source_provider_name(source):
        score += 1.0
        reasons.append("has_provider")
    else:
        score -= 0.5
        reasons.append("missing_provider")
    if source.source_type == "paper" and source.metadata.get("pdf_url"):
        score += 0.5
        reasons.append("has_pdf")
    if source.metadata.get("sections"):
        score += 1.0
        reasons.append("has_sections")
    return {
        "score": round(score, 3),
        "reasons": reasons,
    }


def evidence_quality_summary(
    sources: list[ResearchSource],
    findings: list[ResearchFinding],
    warnings: list[str],
    provider_coverage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return aggregate evidence quality signals for a research context."""
    coverage = provider_coverage or provider_coverage_summary(sources)
    scores = [
        _source_evidence_quality_score(source)
        for source in sources
    ]
    top_score = max(scores) if scores else 0.0
    evidence_backed = bool(sources and findings and top_score > 0 and not warnings)
    return {
        "evidence_backed": evidence_backed,
        "source_count": len(sources),
        "finding_count": len(findings),
        "warning_count": len(warnings),
        "top_source_score": round(top_score, 3),
        "average_source_score": round(sum(scores) / len(scores), 3) if scores else 0.0,
        "provider_count": int(coverage.get("provider_count") or 0),
        "unknown_provider_source_count": int(coverage.get("unknown_provider_source_count") or 0),
    }


def provider_coverage_summary(sources: list[ResearchSource]) -> dict[str, Any]:
    """Summarize how much retrieved evidence came from named providers."""
    provider_groups: dict[str, dict[str, Any]] = {}
    unknown_provider_source_count = 0
    for source in sources:
        provider_name = _source_provider_name(source)
        if not provider_name:
            unknown_provider_source_count += 1
            continue
        group = provider_groups.setdefault(
            provider_name,
            {"source_count": 0, "source_types": set(), "scores": []},
        )
        group["source_count"] += 1
        group["source_types"].add(source.source_type)
        group["scores"].append(_source_evidence_quality_score(source))

    providers: dict[str, Any] = {}
    for provider_name in sorted(provider_groups):
        group = provider_groups[provider_name]
        scores = list(group["scores"])
        providers[provider_name] = {
            "source_count": int(group["source_count"]),
            "source_types": sorted(group["source_types"]),
            "top_evidence_quality_score": round(max(scores), 3) if scores else 0.0,
            "average_evidence_quality_score": (
                round(sum(scores) / len(scores), 3) if scores else 0.0
            ),
        }

    return {
        "provider_count": len(providers),
        "unknown_provider_source_count": unknown_provider_source_count,
        "providers": providers,
    }


def provider_coverage_gate(
    sources: list[ResearchSource],
    provider_coverage: dict[str, Any],
    minimum_provider_count: int = 1,
    minimum_known_provider_ratio: float = 0.5,
) -> dict[str, Any]:
    """Return whether provider attribution is strong enough for evidence-backed planning."""
    total_sources = len(sources)
    unknown_sources = int(provider_coverage.get("unknown_provider_source_count") or 0)
    known_ratio = (
        round((total_sources - unknown_sources) / total_sources, 3)
        if total_sources
        else 0.0
    )
    provider_count = int(provider_coverage.get("provider_count") or 0)
    return {
        "minimum_provider_count": minimum_provider_count,
        "minimum_known_provider_ratio": minimum_known_provider_ratio,
        "known_provider_ratio": known_ratio,
        "met": (
            provider_count >= minimum_provider_count
            and known_ratio >= minimum_known_provider_ratio
        ),
    }


def finalize_retrieval_diagnostics(
    diagnostics: dict[str, Any],
    sources: list[ResearchSource],
    warnings: list[str],
) -> dict[str, Any]:
    """Add aggregate recovery signals to per-backend retrieval diagnostics."""
    provider_coverage = provider_coverage_summary(sources)
    backends = {
        label: value
        for label, value in (diagnostics.get("backends") or {}).items()
        if isinstance(value, dict)
    }
    attempts = [
        attempt
        for backend in backends.values()
        for attempt in _list_payload(backend.get("attempted_queries"))
    ]
    summary = {
        "backend_count": len(backends),
        "attempted_query_count": len(attempts),
        "source_count": len(sources),
        "failed_backend_count": sum(
            1 for backend in backends.values()
            if backend.get("status") == "failed"
        ),
        "empty_backend_count": sum(
            1 for backend in backends.values()
            if backend.get("status") == "empty"
        ),
        "warning_count": len(warnings),
        "used_cache": any(
            isinstance(attempt.get("cache"), dict)
            and bool(attempt["cache"].get("hit"))
            for attempt in attempts
            if isinstance(attempt, dict)
        ),
        "retryable_failure_count": sum(
            1 for attempt in attempts
            if isinstance(attempt.get("error"), dict)
            and bool(attempt["error"].get("retryable"))
        ),
        "rate_limited_backend_count": sum(
            1 for backend in backends.values()
            if any(
                isinstance(attempt.get("error"), dict)
                and attempt["error"].get("category") == "rate_limited"
                for attempt in _list_payload(backend.get("attempted_queries"))
                if isinstance(attempt, dict)
            )
        ),
        "provider_count": int(provider_coverage.get("provider_count") or 0),
        "unknown_provider_source_count": int(
            provider_coverage.get("unknown_provider_source_count") or 0
        ),
    }
    return {
        "backends": backends,
        "summary": summary,
        "provider_coverage": provider_coverage,
        "recommended_recovery": retrieval_recovery_hints(summary),
    }


def retrieval_recovery_hints(summary: dict[str, Any]) -> list[str]:
    """Return deterministic client hints for weak or failed retrieval."""
    hints: list[str] = []
    if int(summary.get("rate_limited_backend_count") or 0) > 0:
        hints.append("wait_for_rate_limit_reset")
    if int(summary.get("failed_backend_count") or 0) > 0:
        hints.append("retry_failed_backends_later")
    if (
        int(summary.get("empty_backend_count") or 0) > 0
        or (
            int(summary.get("source_count") or 0) == 0
            and int(summary.get("rate_limited_backend_count") or 0) == 0
        )
    ):
        hints.append("broaden_query_or_enable_more_sources")
    if hints or int(summary.get("warning_count") or 0) > 0:
        hints.append("keep_cache_dir_for_repeatability")
    return hints


def relevance_score(source: ResearchSource, objective: str, query: str) -> float:
    """Score a source against the research objective and query."""
    terms = _keywords(f"{objective} {query}")
    if not terms:
        return 0.0

    title = source.title.lower()
    summary = source.summary.lower()
    score = 0.0
    for term in terms:
        if term in title:
            score += 3.0
        if term in summary:
            score += 1.0

    if source.source_type == "paper":
        score += 0.3
    elif source.source_type == "hf_dataset":
        score += 0.2
    elif source.source_type == "github_code":
        score += 0.1

    return round(score, 3)


def rank_sources(sources: list[ResearchSource]) -> list[dict[str, Any]]:
    """Return ranked source descriptors without mutating source order."""
    ranked = sorted(
        sources,
        key=lambda source: (
            -float(source.metadata.get("relevance_score", 0.0)),
            source.source_type,
            source.title,
            source.url,
        ),
    )
    return [
        {
            "rank": index,
            "source_type": source.source_type,
            "title": source.title,
            "url": source.url,
            "relevance_score": source.metadata.get("relevance_score", 0.0),
            "provider": _source_provider_name(source),
            "evidence_quality_score": (
                source.metadata.get("evidence_quality", {}).get("score", 0.0)
                if isinstance(source.metadata.get("evidence_quality"), dict)
                else 0.0
            ),
            "evidence": _evidence_label(source),
        }
        for index, source in enumerate(ranked, start=1)
    ]


def _source_provider_name(source: ResearchSource) -> str | None:
    provider = source.metadata.get("provider")
    if isinstance(provider, dict):
        name = provider.get("name")
        return str(name) if name else None
    return None


def _source_evidence_quality_score(source: ResearchSource) -> float:
    quality = source.metadata.get("evidence_quality")
    if not isinstance(quality, dict):
        return 0.0
    try:
        return float(quality.get("score", 0.0))
    except (TypeError, ValueError):
        return 0.0


def derive_findings(objective: str, sources: list[ResearchSource]) -> list[ResearchFinding]:
    """Extract deterministic first-pass findings from research source summaries."""
    findings: list[ResearchFinding] = []
    for index, source in enumerate(sources, start=1):
        claim = _claim_from_source(source)
        if not claim:
            continue
        findings.append(
            ResearchFinding(
                finding_id=f"finding-{index:03d}",
                claim=claim,
                evidence=[_evidence_label(source)],
                relevance=f"Candidate evidence for {objective}",
            )
        )
    return findings


def extract_evidence_snippets(
    source: ResearchSource,
    objective: str,
    max_snippets: int = 5,
) -> list[dict[str, Any]]:
    """Extract objective-scored snippets from a source summary or section metadata."""
    sections = _source_sections(source)
    snippets: list[dict[str, Any]] = []
    source_label = _evidence_label(source)
    objective_terms = _keywords(objective)
    for section_name, text in sections:
        for sentence in _sentences(text):
            snippets.append({
                "snippet_id": f"snippet-{len(snippets) + 1:03d}",
                "source": source_label,
                "section": section_name,
                "text": sentence,
                "relevance_score": _snippet_relevance(sentence, objective_terms),
            })
            if len(snippets) >= max_snippets:
                return snippets
    return snippets


def build_evidence_citations(
    findings: list[ResearchFinding],
    sources: list[ResearchSource],
    objective: str,
) -> list[dict[str, Any]]:
    """Tie each finding to concrete source snippets for planner auditability."""
    source_by_label = {_evidence_label(source): source for source in sources}
    citations: list[dict[str, Any]] = []
    for finding in findings:
        snippets: list[dict[str, Any]] = []
        for label in finding.evidence:
            source = source_by_label.get(label)
            if source is None:
                continue
            snippets.extend(extract_evidence_snippets(source, objective=objective, max_snippets=2))
        citations.append({
            "finding_id": finding.finding_id,
            "evidence": list(finding.evidence),
            "snippets": snippets,
        })
    return citations


def review_research_result(
    result_payload: dict[str, Any],
    workspace: str | Path | None = None,
    runtime_root: str | Path | None = None,
) -> dict[str, Any]:
    """Add a deterministic experiment review to a completed autoresearch payload."""
    payload = dict(result_payload)
    research_review = build_research_review(result_payload)
    payload["research_review"] = research_review
    payload["experiment_state"] = build_experiment_state(
        result_payload,
        research_review=research_review,
        workspace=workspace,
        runtime_root=runtime_root,
    )
    return payload


def build_research_review(result_payload: dict[str, Any]) -> dict[str, Any]:
    """Summarize hypothesis outcomes and next actions from experiment records."""
    experiments = _list_payload(result_payload.get("experiments"))
    hypotheses = _list_payload(result_payload.get("hypotheses"))
    best_result = result_payload.get("best_result") if isinstance(result_payload.get("best_result"), dict) else {}

    outcomes = [
        _hypothesis_outcome(hypothesis, experiments)
        for hypothesis in hypotheses
        if isinstance(hypothesis, dict)
    ]

    supported = [outcome for outcome in outcomes if outcome["status"] == "supported"]
    failed_count = sum(1 for experiment in experiments if isinstance(experiment, dict) and experiment.get("error"))
    decision = _review_decision(experiments, supported, failed_count, best_result)
    next_actions = _next_actions(decision, best_result, failed_count)
    recommended_search_space = build_recommended_search_space(
        decision=decision,
        best_result=best_result,
        experiments=experiments,
    )
    experiment_strategy = build_experiment_strategy(
        decision=decision,
        recommended_search_space=recommended_search_space,
        failed_count=failed_count,
    )
    next_task_patch = build_next_task_patch(
        recommended_search_space=recommended_search_space,
        next_actions=next_actions,
        experiment_strategy=experiment_strategy,
    )

    return {
        "decision": decision,
        "hypothesis_outcomes": outcomes,
        "experiment_count": len(experiments),
        "accepted_count": sum(
            1 for experiment in experiments
            if isinstance(experiment, dict) and experiment.get("accepted")
        ),
        "failed_count": failed_count,
        "next_actions": next_actions,
        "recommended_search_space": recommended_search_space,
        "experiment_strategy": experiment_strategy,
        "next_task_patch": next_task_patch,
    }


def build_recommended_search_space(
    decision: str,
    best_result: dict[str, Any],
    experiments: list[Any],
) -> dict[str, Any]:
    """Suggest a next-round search space from the accepted best and rejected params."""
    center_params = best_result.get("params") if isinstance(best_result.get("params"), dict) else {}
    avoid_params = [
        experiment["params"]
        for experiment in experiments
        if (
            isinstance(experiment, dict)
            and not experiment.get("accepted")
            and isinstance(experiment.get("params"), dict)
            and experiment["params"]
        )
    ]
    return {
        "strategy": "local_refinement" if decision == "continue_from_best" else "revise_search_space",
        "center_params": center_params,
        "avoid_params": avoid_params,
        "parameter_hints": _parameter_hints(center_params),
    }


def build_next_task_patch(
    recommended_search_space: dict[str, Any],
    next_actions: list[str],
    experiment_strategy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert review output into a run_hypothesis_experiment task_patch."""
    hints = list(next_actions)
    if experiment_strategy:
        mode = experiment_strategy.get("mode")
        if mode:
            hints.append(f"Strategy: {mode}.")
        hints.extend(
            f"Stop condition: {condition}"
            for condition in experiment_strategy.get("stop_conditions", [])
        )
    patch: dict[str, Any] = {
        "program_md_overrides": {
            "hints": hints,
        },
    }
    parameter_hints = recommended_search_space.get("parameter_hints", {})
    avoid_params = recommended_search_space.get("avoid_params", [])
    if parameter_hints:
        patch["hyperparameter_space"] = parameter_hints
    if avoid_params:
        patch["sampling_constraints"] = {
            "avoid_params": recommended_search_space.get("avoid_params", []),
        }
    if experiment_strategy and experiment_strategy.get("recommended_max_experiments"):
        patch["budget"] = {
            "max_experiments": int(experiment_strategy["recommended_max_experiments"]),
        }
    return patch


def build_experiment_strategy(
    decision: str,
    recommended_search_space: dict[str, Any],
    failed_count: int,
) -> dict[str, Any]:
    """Return structured next-run guidance for MCP clients and experiment agents."""
    center_params = recommended_search_space.get("center_params", {})
    avoid_params = recommended_search_space.get("avoid_params", [])
    if decision == "continue_from_best":
        return {
            "mode": "local_refinement",
            "focus_params": list(center_params.keys()),
            "avoid_params_count": len(avoid_params),
            "recommended_max_experiments": 3,
            "stop_conditions": [
                "stop after a locally refined configuration improves the current best metric",
                "stop if all local candidates are rejected or fail",
            ],
        }
    if decision == "debug_failures":
        return {
            "mode": "debug_failures",
            "focus_params": [],
            "avoid_params_count": len(avoid_params),
            "recommended_max_experiments": 1,
            "stop_conditions": [
                f"stop after reproducing and explaining {failed_count} failed experiments",
                "stop before sampling new parameters",
            ],
        }
    if decision == "revise_search_space":
        return {
            "mode": "revise_search_space",
            "focus_params": list(center_params.keys()),
            "avoid_params_count": len(avoid_params),
            "recommended_max_experiments": 2,
            "stop_conditions": [
                "stop after testing a revised hypothesis-backed search space",
                "stop if no experiment improves the current best metric",
            ],
        }
    return {
        "mode": "start_experiment",
        "focus_params": [],
        "avoid_params_count": 0,
        "recommended_max_experiments": 1,
        "stop_conditions": ["stop after the first hypothesis-backed experiment completes"],
    }


def build_experiment_state(
    result_payload: dict[str, Any],
    research_review: dict[str, Any],
    workspace: str | Path | None = None,
    runtime_root: str | Path | None = None,
) -> dict[str, Any]:
    """Build the compact state a Codex/Claude planner needs for the next iteration."""
    task_id = str(result_payload.get("task_id") or "")
    experiments = _list_payload(result_payload.get("experiments"))
    workspace_path = _resolve_workspace_path(
        task_id=task_id,
        workspace=workspace,
        runtime_root=runtime_root,
        experiments=experiments,
    )
    task_payload = _read_task_payload(task_id=task_id, runtime_root=runtime_root)
    current_code = _current_code_state(workspace_path)
    dataset_profile = build_dataset_profile(task_payload, runtime_root=runtime_root)
    failure_summary = _failure_summary(experiments)
    code_change_plan = build_code_change_plan(
        result_payload=result_payload,
        research_review=research_review,
        current_code=current_code,
        dataset_profile=dataset_profile,
        task_payload=task_payload,
    )
    artifacts = _artifact_paths(
        task_id=task_id,
        workspace_path=workspace_path,
        runtime_root=runtime_root,
        result_payload=result_payload,
    )
    research_evidence_gate = build_research_evidence_gate(result_payload)
    return {
        "architecture": "hybrid_client_planner_server_executor",
        "task_id": task_id,
        "status": result_payload.get("status"),
        "best_result": (
            result_payload.get("best_result")
            if isinstance(result_payload.get("best_result"), dict)
            else None
        ),
        "summary": (
            result_payload.get("summary")
            if isinstance(result_payload.get("summary"), dict)
            else {}
        ),
        "recent_experiments": _recent_experiment_summaries(experiments),
        "failure_summary": failure_summary,
        "research_evidence_gate": research_evidence_gate,
        "dataset_profile": dataset_profile,
        "current_code": current_code,
        "code_change_plan": code_change_plan,
        "planner_actions": build_planner_actions(
            task_id=task_id,
            runtime_root=runtime_root,
            workspace_path=workspace_path,
            task_payload=task_payload,
            research_context=(
                result_payload.get("research_context")
                if isinstance(result_payload.get("research_context"), dict)
                else {}
            ),
            research_review=research_review,
            research_evidence_gate=research_evidence_gate,
            failure_summary=failure_summary,
            dataset_profile=dataset_profile,
            code_change_plan=code_change_plan,
            artifacts=artifacts,
        ),
        "artifacts": artifacts,
        "planner_handoff": {
            "client_model_role": "decide_next_code_or_param_change",
            "mcp_server_role": "execute_experiments_and_return_state",
            "recommended_next_tool": _recommended_next_tool(research_review),
            "server_side_llm_tool": "run_ai_autoresearch",
        },
        "next_round": {
            "task_patch": research_review.get("next_task_patch", {}),
            "recommended_search_space": research_review.get("recommended_search_space", {}),
            "experiment_strategy": research_review.get("experiment_strategy", {}),
        },
    }


def build_research_evidence_gate(result_payload: dict[str, Any]) -> dict[str, Any]:
    """Assess whether current research context is usable evidence for planning."""
    research_context = (
        result_payload.get("research_context")
        if isinstance(result_payload.get("research_context"), dict)
        else {}
    )
    sources = _list_payload(research_context.get("sources"))
    findings = _list_payload(research_context.get("findings"))
    warnings = [str(item) for item in _list_payload(research_context.get("warnings"))]
    retrieval_diagnostics = (
        research_context.get("retrieval_diagnostics")
        if isinstance(research_context.get("retrieval_diagnostics"), dict)
        else {}
    )
    retrieval_recovery = [
        str(item)
        for item in _list_payload(retrieval_diagnostics.get("recommended_recovery"))
    ]
    evidence_quality = (
        research_context.get("evidence_quality")
        if isinstance(research_context.get("evidence_quality"), dict)
        else {}
    )
    if "evidence_backed" in evidence_quality:
        evidence_backed = bool(evidence_quality.get("evidence_backed"))
    else:
        evidence_backed = bool(sources and findings and not warnings)
    status = str(
        research_context.get("status")
        or ("research_context_ready" if evidence_backed else "missing")
    )
    gate = {
        "recommended_action": "use_current_context" if evidence_backed else "refresh_research",
        "evidence_backed": evidence_backed,
        "status": status,
        "source_count": len(sources),
        "finding_count": len(findings),
        "warning_count": len(warnings),
        "warnings": warnings,
    }
    if retrieval_recovery:
        gate["retrieval_recovery"] = retrieval_recovery
    return gate


def build_planner_actions(
    task_id: str,
    runtime_root: str | Path | None,
    workspace_path: Path | None,
    task_payload: dict[str, Any],
    research_context: dict[str, Any],
    research_review: dict[str, Any],
    research_evidence_gate: dict[str, Any],
    failure_summary: dict[str, Any],
    dataset_profile: dict[str, Any],
    code_change_plan: dict[str, Any],
    artifacts: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return ordered client-side actions for the next Codex/Claude planning step."""
    actions: list[dict[str, Any]] = []
    if failure_summary.get("failed_count"):
        actions.append({
            "action_id": "inspect-logs",
            "tool": "get_experiment_logs",
            "arguments": _compact_dict({
                "task_id": task_id,
                "runtime_root": str(Path(runtime_root).expanduser().resolve()) if runtime_root else None,
                "workspace": str(workspace_path) if workspace_path else None,
                "tail_lines": 120,
            }),
            "reason": "One or more experiments failed; inspect logs before changing parameters.",
            "requires_client_edit": False,
        })

    if research_evidence_gate.get("recommended_action") == "refresh_research":
        actions.append({
            "action_id": "refresh-research",
            "tool": "research_task",
            "arguments": _research_refresh_arguments(
                task_id=task_id,
                task_payload=task_payload,
                runtime_root=runtime_root,
                research_context=research_context,
            ),
            "reason": _research_refresh_reason(research_evidence_gate),
            "requires_client_edit": False,
        })

    if code_change_plan.get("recommended_action") == "fix_dataset":
        actions.append({
            "action_id": "fix-dataset",
            "tool": None,
            "arguments": _compact_dict({
                "task_config": str(_resolve_task_file(task_id, runtime_root)) if task_id and runtime_root else None,
                "dataset_path": dataset_profile.get("path"),
            }),
            "reason": code_change_plan.get("reason"),
            "requires_client_edit": True,
        })
        return actions

    if code_change_plan.get("recommended_action") == "inspect_code":
        actions.append({
            "action_id": "inspect-code",
            "tool": None,
            "arguments": _compact_dict({
                "train_py": artifacts.get("train_py"),
                "program_md": artifacts.get("program_md"),
            }),
            "reason": code_change_plan.get("reason"),
            "requires_client_edit": True,
        })
        return actions

    if failure_summary.get("failed_count"):
        return actions

    task_file = _resolve_task_file(task_id, runtime_root)
    if task_file:
        actions.append({
            "action_id": "run-next-experiment",
            "tool": "run_hypothesis_experiment",
            "arguments": _compact_dict({
                "task_config": str(task_file),
                "runtime_root": str(Path(runtime_root).expanduser().resolve()) if runtime_root else None,
                "workspace": str(workspace_path) if workspace_path else None,
                "task_patch": research_review.get("next_task_patch", {}),
            }),
            "reason": code_change_plan.get("reason") or "Continue with the recommended next task patch.",
            "requires_client_edit": False,
        })
    return actions


def build_dataset_profile(
    task_payload: dict[str, Any],
    runtime_root: str | Path | None = None,
) -> dict[str, Any]:
    """Summarize the dataset file used by the task for planner decisions."""
    dataset = task_payload.get("dataset") if isinstance(task_payload.get("dataset"), dict) else {}
    name = str(dataset.get("name") or "")
    dataset_type = str(dataset.get("type") or "binary")
    raw_path = str(dataset.get("path") or "")
    resolved_path = _resolve_dataset_path(raw_path, runtime_root)
    risks: list[str] = []
    if not raw_path:
        risks.append("dataset_path_missing")
    if not resolved_path or not resolved_path.exists():
        risks.append(
            "synthetic_fallback"
            if _is_synthetic_fallback_dataset(name=name, raw_path=raw_path)
            else "dataset_file_missing"
        )
        return {
            "name": name,
            "path": str(resolved_path) if resolved_path else raw_path,
            "exists": False,
            "size_bytes": 0,
            "inferred_vocab_size": _int_or_none(dataset.get("vocab_size")),
            "inferred_seq_len": _int_or_none(dataset.get("max_seq_len")),
            "type": dataset_type,
            "risks": risks,
        }

    size_bytes = resolved_path.stat().st_size
    inferred_vocab, inferred_seq_len = _infer_dataset_shape(resolved_path)
    if size_bytes == 0:
        risks.append("dataset_file_empty")
    if inferred_seq_len and size_bytes <= inferred_seq_len:
        risks.append("dataset_too_small_for_sequence_length")
    return {
        "name": name,
        "path": str(resolved_path),
        "exists": True,
        "size_bytes": size_bytes,
        "inferred_vocab_size": inferred_vocab or _int_or_none(dataset.get("vocab_size")),
        "inferred_seq_len": inferred_seq_len or _int_or_none(dataset.get("max_seq_len")),
        "type": dataset_type,
        "risks": risks,
    }


def build_code_change_plan(
    result_payload: dict[str, Any],
    research_review: dict[str, Any],
    current_code: dict[str, Any],
    dataset_profile: dict[str, Any],
    task_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic next-code-change guidance for Codex/Claude planners."""
    search_region = (
        current_code.get("search_region")
        if isinstance(current_code.get("search_region"), dict)
        else {}
    )
    if not search_region:
        return {
            "recommended_action": "inspect_code",
            "target": None,
            "current_value": None,
            "reason": "No SEARCH REGION was found in train.py.",
            "constraints": _code_change_constraints(),
        }
    failure_summary = _failure_summary(_list_payload(result_payload.get("experiments")))
    if failure_summary["failed_count"]:
        return {
            "recommended_action": "debug_before_search",
            "target": None,
            "current_value": None,
            "reason": "One or more experiments failed; inspect logs before changing parameters.",
            "constraints": _code_change_constraints(),
        }
    if not dataset_profile.get("exists"):
        if "synthetic_fallback" not in dataset_profile.get("risks", []):
            return {
                "recommended_action": "fix_dataset",
                "target": None,
                "current_value": None,
                "reason": "Dataset file is missing; fix the task dataset path before tuning.",
                "constraints": _code_change_constraints(),
            }
    if "synthetic_fallback" in dataset_profile.get("risks", []):
        target = _select_change_target(
            search_region=search_region,
            recommended_search_space=research_review.get("recommended_search_space", {}),
        )
        reason = "Synthetic fallback is intentional for this task; continue tuning SEARCH REGION."
        return {
            "recommended_action": "tune_search_region",
            "target": target,
            "current_value": search_region.get(target),
            "reason": reason,
            "constraints": _code_change_constraints(),
            "next_experiment_plan": build_next_experiment_plan(
                target=target,
                search_region=search_region,
                result_payload=result_payload,
                research_review=research_review,
                task_payload=task_payload or {},
                rationale=reason,
            ),
        }

    target = _select_change_target(
        search_region=search_region,
        recommended_search_space=research_review.get("recommended_search_space", {}),
    )
    reason = _code_change_reason(target, research_review)
    return {
        "recommended_action": "tune_search_region",
        "target": target,
        "current_value": search_region.get(target),
        "reason": reason,
        "constraints": _code_change_constraints(),
        "next_experiment_plan": build_next_experiment_plan(
            target=target,
            search_region=search_region,
            result_payload=result_payload,
            research_review=research_review,
            task_payload=task_payload or {},
            rationale=reason,
        ),
    }


def build_next_experiment_plan(
    target: str | None,
    search_region: dict[str, str],
    result_payload: dict[str, Any],
    research_review: dict[str, Any],
    task_payload: dict[str, Any],
    rationale: str,
) -> dict[str, Any] | None:
    """Build a concrete one-parameter next-experiment plan for client planners."""
    if not target:
        return None
    best_result = (
        result_payload.get("best_result")
        if isinstance(result_payload.get("best_result"), dict)
        else {}
    )
    best_params = (
        best_result.get("params")
        if isinstance(best_result.get("params"), dict)
        else {}
    )
    experiment_strategy = (
        research_review.get("experiment_strategy")
        if isinstance(research_review.get("experiment_strategy"), dict)
        else {}
    )
    metric = (
        task_payload.get("metric")
        if isinstance(task_payload.get("metric"), dict)
        else {}
    )
    metric_name = str(metric.get("name") or "val_bpb")
    proposed_task_patch, target_patch_key = build_single_parameter_task_patch(
        target=target,
        research_review=research_review,
    )
    candidate_values = _candidate_values_for_target(
        target=target,
        recommended_search_space=research_review.get("recommended_search_space", {}),
    )
    plan = {
        "mode": experiment_strategy.get("mode") or "one_parameter_edit",
        "metric": {
            "name": metric_name,
            "direction": str(metric.get("direction") or "minimize"),
            "current_best": best_result.get("val"),
        },
        "target_param": target,
        "current_value": search_region.get(target),
        "candidate_values": candidate_values,
        "best_params": best_params,
        "stop_conditions": [
            str(condition)
            for condition in _list_payload(experiment_strategy.get("stop_conditions"))
        ],
        "edit_policy": _code_change_constraints(),
        "diff_preview": build_search_region_diff_preview(
            target=target,
            current_value=search_region.get(target),
            candidate_values=candidate_values,
        ),
        "proposed_task_patch": proposed_task_patch,
        "execution_guardrails": build_patch_execution_guardrails(
            target=target,
            target_patch_key=target_patch_key,
            metric_name=metric_name,
        ),
        "dry_run_validation": build_dry_run_validation(
            target_patch_key=target_patch_key,
            metric_name=metric_name,
        ),
        "rationale": rationale,
    }
    return _compact_dict(plan)


def build_search_region_diff_preview(
    target: str,
    current_value: str | None,
    candidate_values: list[Any],
) -> dict[str, Any]:
    """Return a compact diff-like preview for a one-parameter SEARCH REGION edit."""
    return {
        "scope": "AUTORESEARCH SEARCH REGION",
        "target_param": target,
        "current_line": f"{target} = {current_value}",
        "candidate_lines": [
            f"{target} = {value}"
            for value in candidate_values
        ],
    }


def build_patch_execution_guardrails(
    target: str,
    target_patch_key: str,
    metric_name: str,
) -> dict[str, Any]:
    """Return patch execution steps and rollback guidance for client planners."""
    return {
        "preflight_validation": [
            "confirm train.py contains AUTORESEARCH SEARCH REGION",
            f"confirm only {target} changes in diff preview",
            "confirm task_config exists before applying task_patch",
        ],
        "apply_step": {
            "tool": "run_hypothesis_experiment",
            "mode": "task_patch_only",
            "task_patch_key": target_patch_key,
        },
        "rollback_path": [
            "discard generated hypothesis task config if preflight fails",
            "reuse original task_config and workspace from artifacts",
        ],
        "post_run_review": {
            "tool": "review_research_results",
            "compare_metric": metric_name,
            "decision": "stop_or_continue_from_review",
        },
    }


def build_single_parameter_task_patch(
    target: str,
    research_review: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Return the narrow task_patch for the next one-parameter validation."""
    next_task_patch = (
        research_review.get("next_task_patch")
        if isinstance(research_review.get("next_task_patch"), dict)
        else {}
    )
    hint_key, hint_spec = _target_hint_for_target(
        target=target,
        recommended_search_space=research_review.get("recommended_search_space", {}),
    )
    target_patch_key = hint_key or target.lower()
    patch: dict[str, Any] = {}
    if hint_key and hint_spec:
        patch["hyperparameter_space"] = {hint_key: hint_spec}

    sampling_constraints = next_task_patch.get("sampling_constraints")
    if isinstance(sampling_constraints, dict) and sampling_constraints:
        patch["sampling_constraints"] = sampling_constraints

    budget = next_task_patch.get("budget")
    if isinstance(budget, dict) and budget:
        patch["budget"] = budget

    program_md_overrides = next_task_patch.get("program_md_overrides")
    existing_hints = (
        _list_payload(program_md_overrides.get("hints"))
        if isinstance(program_md_overrides, dict)
        else []
    )
    patch["program_md_overrides"] = {
        "hints": [
            f"Validate {target} only before widening the search space.",
            *[str(hint) for hint in existing_hints],
        ],
    }
    return _compact_dict(patch), target_patch_key


def build_dry_run_validation(target_patch_key: str, metric_name: str) -> dict[str, list[str]]:
    """Return checks a client planner should satisfy around the proposed patch."""
    return {
        "preflight_checks": [
            "confirm task_config exists before calling run_hypothesis_experiment",
            f"confirm task_patch.hyperparameter_space only contains {target_patch_key}",
            "confirm runtime_root/workspace are isolated for this run",
        ],
        "post_run_checks": [
            "call review_research_results after run_hypothesis_experiment",
            f"compare {metric_name} against current_best",
            "stop if configured stop_conditions are met",
        ],
    }


def _resolve_workspace_path(
    task_id: str,
    workspace: str | Path | None,
    runtime_root: str | Path | None,
    experiments: list[Any],
) -> Path | None:
    if workspace:
        return Path(workspace).expanduser().resolve()
    if runtime_root and task_id:
        candidate = Path(runtime_root).expanduser().resolve() / "workdir" / task_id
        if candidate.exists():
            return candidate
    for experiment in reversed(experiments):
        if not isinstance(experiment, dict):
            continue
        snapshot_path = experiment.get("snapshot_path")
        if snapshot_path:
            candidate = Path(str(snapshot_path)).expanduser().resolve()
            if candidate.exists():
                return candidate
    return None


def _read_task_payload(task_id: str, runtime_root: str | Path | None) -> dict[str, Any]:
    if not task_id or not runtime_root:
        return {}
    task_file = Path(runtime_root).expanduser().resolve() / "tasks" / f"{task_id}.json"
    if not task_file.exists():
        hypothesis_file = task_file.with_name(f"{task_id}-hypothesis.json")
        task_file = hypothesis_file if hypothesis_file.exists() else task_file
    if not task_file.exists():
        return {}
    try:
        payload = json.loads(task_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve_task_file(task_id: str, runtime_root: str | Path | None) -> Path | None:
    if not task_id or not runtime_root:
        return None
    tasks_dir = Path(runtime_root).expanduser().resolve() / "tasks"
    task_file = tasks_dir / f"{task_id}.json"
    if task_file.exists():
        return task_file
    hypothesis_file = tasks_dir / f"{task_id}-hypothesis.json"
    if hypothesis_file.exists():
        return hypothesis_file
    return task_file


def _research_refresh_arguments(
    task_id: str,
    task_payload: dict[str, Any],
    runtime_root: str | Path | None,
    research_context: dict[str, Any],
) -> dict[str, Any]:
    objective = str(
        research_context.get("objective")
        or task_payload.get("objective")
        or task_id
    )
    query = str(research_context.get("query") or objective)
    cache_dir = (
        str(Path(runtime_root).expanduser().resolve() / ".research_cache")
        if runtime_root
        else None
    )
    return _compact_dict({
        "objective": objective,
        "query": query,
        "paper_limit": 3,
        "dataset_limit": 3,
        "include_papers": True,
        "include_hf_datasets": True,
        "include_github_code": False,
        "query_fanout": True,
        "cache_dir": cache_dir,
    })


def _research_refresh_reason(research_evidence_gate: dict[str, Any]) -> str:
    recovery = [
        str(item)
        for item in _list_payload(research_evidence_gate.get("retrieval_recovery"))
    ]
    if recovery:
        return (
            "Research context is missing, warning-bearing, or not evidence-backed. "
            f"Recovery hints: {', '.join(recovery)}."
        )
    return "Research context is missing, warning-bearing, or not evidence-backed."


def _resolve_dataset_path(raw_path: str, runtime_root: str | Path | None) -> Path | None:
    if not raw_path:
        return None
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path.resolve()
    if runtime_root:
        candidate = Path(runtime_root).expanduser().resolve() / raw_path
        return candidate.resolve()
    return path.resolve()


def _is_synthetic_fallback_dataset(name: str, raw_path: str) -> bool:
    del raw_path
    return name.strip().lower() == "synthetic"


def _infer_dataset_shape(dataset_path: Path) -> tuple[int | None, int | None]:
    parts = dataset_path.stem.split("_")
    if len(parts) >= 3:
        vocab_size = _int_or_none(parts[-2])
        seq_len = _int_or_none(parts[-1])
        return vocab_size, seq_len
    return None, None


def _int_or_none(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _select_change_target(
    search_region: dict[str, str],
    recommended_search_space: dict[str, Any],
) -> str | None:
    hints = (
        recommended_search_space.get("parameter_hints")
        if isinstance(recommended_search_space.get("parameter_hints"), dict)
        else {}
    )
    for hint_name in hints:
        target = _search_region_target(search_region, str(hint_name))
        if target:
            return target
    for preferred in ("LR", "DEPTH", "DIM", "WINDOW_SIZE", "BATCH_SIZE"):
        if preferred in search_region:
            return preferred
    return next(iter(search_region), None)


def _candidate_values_for_target(
    target: str,
    recommended_search_space: dict[str, Any],
) -> list[Any]:
    _, spec = _target_hint_for_target(
        target=target,
        recommended_search_space=recommended_search_space,
    )
    if not spec:
        return []
    values = spec.get("values")
    if isinstance(values, list):
        return values
    lower = spec.get("min")
    upper = spec.get("max")
    return [value for value in (lower, upper) if value is not None]


def _target_hint_for_target(
    target: str,
    recommended_search_space: dict[str, Any],
) -> tuple[str | None, dict[str, Any]]:
    hints = (
        recommended_search_space.get("parameter_hints")
        if isinstance(recommended_search_space.get("parameter_hints"), dict)
        else {}
    )
    for hint_name, spec in hints.items():
        if hint_name.lower() != target.lower():
            continue
        if not isinstance(spec, dict):
            return str(hint_name), {}
        return str(hint_name), spec
    return None, {}


def _search_region_target(search_region: dict[str, str], name: str) -> str | None:
    normalized = name.lower()
    for target in search_region:
        if target.lower() == normalized:
            return target
    return None


def _code_change_reason(target: str | None, research_review: dict[str, Any]) -> str:
    if not target:
        return "No tunable SEARCH REGION target is available."
    decision = research_review.get("decision")
    if decision == "continue_from_best":
        return f"Continue local refinement by changing {target} around the current best result."
    if decision == "revise_search_space":
        return f"Revise {target} because the previous search did not support the hypothesis."
    return f"Run a conservative one-parameter edit on {target}."


def _code_change_constraints() -> list[str]:
    return [
        "edit only the AUTORESEARCH SEARCH REGION",
        "change one parameter per experiment",
    ]


def _compact_dict(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if value is not None
    }


def _recent_experiment_summaries(
    experiments: list[Any],
    limit: int = 5,
) -> list[dict[str, Any]]:
    recent = [
        experiment
        for experiment in experiments[-limit:]
        if isinstance(experiment, dict)
    ]
    return [
        {
            "experiment_id": experiment.get("experiment_id"),
            "params": (
                experiment.get("params")
                if isinstance(experiment.get("params"), dict)
                else {}
            ),
            "metrics": (
                experiment.get("metrics")
                if isinstance(experiment.get("metrics"), dict)
                else {}
            ),
            "accepted": bool(experiment.get("accepted")),
            "error": experiment.get("error"),
            "hypothesis_id": experiment.get("hypothesis_id"),
            "snapshot_path": experiment.get("snapshot_path"),
        }
        for experiment in recent
    ]


def _failure_summary(experiments: list[Any]) -> dict[str, Any]:
    failed = [
        experiment
        for experiment in experiments
        if isinstance(experiment, dict) and experiment.get("error")
    ]
    return {
        "failed_count": len(failed),
        "recent_errors": [
            {
                "experiment_id": experiment.get("experiment_id"),
                "error": experiment.get("error"),
            }
            for experiment in failed[-3:]
        ],
    }


def _current_code_state(workspace_path: Path | None) -> dict[str, Any]:
    train_py = workspace_path / "train.py" if workspace_path else None
    program_md = workspace_path / "program.md" if workspace_path else None
    train_content = _read_text_if_exists(train_py)
    program_content = _read_text_if_exists(program_md)
    return {
        "train_py": str(train_py) if train_py else None,
        "program_md": str(program_md) if program_md else None,
        "search_region": parse_search_region(train_content) if train_content else {},
        "program_md_excerpt": _excerpt(program_content),
    }


def _artifact_paths(
    task_id: str,
    workspace_path: Path | None,
    runtime_root: str | Path | None,
    result_payload: dict[str, Any],
) -> dict[str, Any]:
    runtime_path = Path(runtime_root).expanduser().resolve() if runtime_root else None
    result_file = result_payload.get("result_file")
    if not result_file and runtime_path and task_id:
        result_file = str(runtime_path / "results" / f"{task_id}.json")
    progress_file = str(runtime_path / "results" / f"{task_id}-progress.json") if runtime_path and task_id else None
    return {
        "runtime_root": str(runtime_path) if runtime_path else None,
        "workspace": str(workspace_path) if workspace_path else None,
        "result_file": result_file,
        "progress_file": progress_file,
        "train_py": str(workspace_path / "train.py") if workspace_path else None,
        "program_md": str(workspace_path / "program.md") if workspace_path else None,
        "logs_dir": str(workspace_path / "logs") if workspace_path else None,
    }


def _recommended_next_tool(research_review: dict[str, Any]) -> str:
    if research_review.get("decision") == "debug_failures":
        return "get_experiment_result"
    return "run_hypothesis_experiment"


def _read_text_if_exists(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _excerpt(text: str, limit: int = 2000) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _collect_sources(
    label: str,
    collect: Callable[[], list[ResearchSource]],
    warnings: list[str],
    cache: dict[str, Any] | None = None,
    cache_dir: str | Path | None = None,
    query: str = "",
    limit: int = 0,
) -> list[ResearchSource]:
    try:
        if cache_dir:
            sources, cache_meta = research_tools.cached_search(
                cache_dir=cache_dir,
                namespace=label,
                query=query,
                limit=limit,
                collect=collect,
            )
            if cache is not None:
                cache[label] = cache_meta
            return list(sources)
        return list(collect())
    except Exception as exc:  # noqa: BLE001 - research backends should degrade independently.
        warnings.append(f"{label}: {exc}")
        return []


def _collect_source_variants(
    label: str,
    collect: Callable[[str], list[ResearchSource]],
    warnings: list[str],
    query_plan: list[dict[str, str]],
    limit: int,
    cache: dict[str, Any] | None = None,
    cache_dir: str | Path | None = None,
    query_fanout: bool = True,
    diagnostics: dict[str, Any] | None = None,
) -> list[ResearchSource]:
    if limit <= 0:
        return []
    collected: list[ResearchSource] = []
    cache_variants: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    variants = query_plan if query_fanout else query_plan[:1]
    for variant in variants:
        query = variant.get("query", "")
        reason = variant.get("reason", "primary")
        variant_cache: dict[str, Any] = {}
        sources, warning, retry_attempts = _collect_sources_with_provider_retries(
            label,
            lambda query=query: collect(query),
            cache=variant_cache,
            cache_dir=cache_dir,
            query=query,
            limit=limit,
        )
        attempt: dict[str, Any] = {
            "query": query,
            "query_reason": reason,
            "source_count": len(sources),
        }
        if label in variant_cache:
            attempt["cache"] = variant_cache[label]
            cache_variants.append({
                **variant_cache[label],
                "query_reason": reason,
            })
        if retry_attempts:
            attempt["retry_attempts"] = retry_attempts
        if warning:
            warnings.append(warning)
            attempt["warning"] = warning
            error = classify_retrieval_warning(label=label, warning=warning)
            if error:
                attempt["error"] = error
        attempts.append(attempt)
        collected.extend(
            _annotate_query_variant(source, query=query, reason=reason)
            for source in sources
        )
        if warning or len(collected) >= limit:
            break
    if diagnostics is not None:
        backend = {
            "status": _retrieval_backend_status(
                source_count=len(collected[:limit]),
                requested_limit=limit,
                attempts=attempts,
            ),
            "requested_limit": int(limit),
            "source_count": len(collected[:limit]),
            "attempted_queries": attempts,
        }
        if any("retry_attempts" in attempt for attempt in attempts):
            backend["provider_retry_policy"] = dict(PROVIDER_RETRY_POLICY)
        diagnostics.setdefault("backends", {})[label] = backend
    if cache is not None and cache_variants:
        if len(cache_variants) == 1:
            cache_meta = dict(cache_variants[0])
            cache_meta.pop("query_reason", None)
            cache[label] = cache_meta
        else:
            cache[label] = {
                "source": "mixed",
                "hit": all(bool(item.get("hit")) for item in cache_variants),
                "variants": cache_variants,
            }
    return collected[:limit]


def _collect_sources_with_provider_retries(
    label: str,
    collect: Callable[[], list[ResearchSource]],
    cache: dict[str, Any] | None = None,
    cache_dir: str | Path | None = None,
    query: str = "",
    limit: int = 0,
) -> tuple[list[ResearchSource], str | None, list[dict[str, Any]]]:
    retry_attempts: list[dict[str, Any]] = []
    max_attempts = int(PROVIDER_RETRY_POLICY["max_attempts"])
    backoff_seconds = list(PROVIDER_RETRY_POLICY["backoff_seconds"])
    last_warning: str | None = None
    for attempt_index in range(max_attempts):
        if attempt_index < len(backoff_seconds) and backoff_seconds[attempt_index] > 0:
            time.sleep(float(backoff_seconds[attempt_index]))
        try:
            if cache_dir:
                sources, cache_meta = research_tools.cached_search(
                    cache_dir=cache_dir,
                    namespace=label,
                    query=query,
                    limit=limit,
                    collect=collect,
                )
                if cache is not None:
                    cache[label] = cache_meta
            else:
                sources = list(collect())
            if retry_attempts:
                retry_attempts.append({
                    "attempt": attempt_index + 1,
                    "status": "ready",
                    "source_count": len(sources),
                })
            return list(sources), None, retry_attempts
        except Exception as exc:  # noqa: BLE001 - research backends degrade independently.
            last_warning = f"{label}: {exc}"
            error = classify_retrieval_warning(label=label, warning=last_warning)
            retry_attempts.append({
                "attempt": attempt_index + 1,
                "status": "failed",
                "error": error or {
                    "category": "unknown",
                    "retryable": False,
                    "recommended_action": "inspect_provider_error",
                    "message": str(exc),
                },
            })
            if not error or not error.get("retryable"):
                break
    return [], last_warning, retry_attempts if len(retry_attempts) > 1 else []


def _retrieval_backend_status(
    source_count: int,
    requested_limit: int,
    attempts: list[dict[str, Any]],
) -> str:
    warning_seen = any("warning" in attempt for attempt in attempts)
    if source_count >= requested_limit:
        return "ready"
    if source_count > 0:
        return "partial"
    if warning_seen:
        return "failed"
    return "empty"


def classify_retrieval_warning(label: str, warning: str) -> dict[str, Any] | None:
    """Classify recognizable provider failures for client recovery planning."""
    prefix = f"{label}: "
    message = warning[len(prefix):] if warning.startswith(prefix) else warning
    normalized = message.lower()
    if "429" in normalized or "rate limit" in normalized or "rate_limited" in normalized:
        return {
            "category": "rate_limited",
            "retryable": True,
            "recommended_action": "retry_after_backoff",
            "message": message,
        }
    if "timeout" in normalized or "timed out" in normalized:
        return {
            "category": "timeout",
            "retryable": True,
            "recommended_action": "retry_with_smaller_limits",
            "message": message,
        }
    if "401" in normalized or "403" in normalized or "unauthorized" in normalized:
        return {
            "category": "auth_or_permission",
            "retryable": False,
            "recommended_action": "check_provider_credentials",
            "message": message,
        }
    return None


def _annotate_query_variant(
    source: ResearchSource,
    query: str,
    reason: str,
) -> ResearchSource:
    return ResearchSource(
        source_type=source.source_type,
        title=source.title,
        url=source.url,
        summary=source.summary,
        metadata={
            **source.metadata,
            "query_variant": query,
            "query_reason": reason,
        },
    )


def _source_counts(sources: list[ResearchSource]) -> dict[str, int]:
    counts = Counter(source.source_type for source in sources)
    return dict(counts)


def _source_from_dict(source: dict[str, Any]) -> ResearchSource:
    return ResearchSource(
        source_type=source.get("source_type", ""),
        title=source.get("title", ""),
        url=source.get("url", ""),
        summary=source.get("summary", ""),
        metadata=source.get("metadata") or {},
    )


def _rank_for_hypothesis(sources: list[ResearchSource]) -> list[ResearchSource]:
    return sorted(
        sources,
        key=lambda source: (
            -float(source.metadata.get("relevance_score", 0.0)),
            source.source_type,
            source.title,
            source.url,
        ),
    )


def _source_key(source: ResearchSource) -> tuple[str, str]:
    return _source_keys(source)[0]


def _source_keys(source: ResearchSource) -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    provider = source.metadata.get("provider") if isinstance(source.metadata, dict) else None
    if isinstance(provider, dict):
        name = str(provider.get("name") or "").strip().lower()
        record_id = str(provider.get("record_id") or "").strip().lower()
        if name and record_id:
            keys.append(("provider_record", f"{name}:{record_id}"))
    if source.url:
        keys.append(("url", source.url.strip().lower()))
    keys.append((source.source_type, source.title.strip().lower()))
    return keys


def _keywords(text: str) -> set[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "for",
        "in",
        "on",
        "or",
        "the",
        "to",
        "with",
    }
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_]+", text.lower())
        if token not in stopwords and len(token) > 2
    }


def _claim_from_source(source: ResearchSource) -> str:
    text = source.summary.strip()
    if not text:
        return ""
    sentence_end = min(
        (position for position in (text.find("."), text.find("!"), text.find("?")) if position >= 0),
        default=-1,
    )
    if sentence_end >= 0:
        return text[:sentence_end + 1].strip()
    return text[:240].strip()


def _source_sections(source: ResearchSource) -> list[tuple[str, str]]:
    sections = source.metadata.get("sections") if isinstance(source.metadata, dict) else None
    if isinstance(sections, list):
        parsed_sections = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            text = str(section.get("text", "")).strip()
            if not text:
                continue
            parsed_sections.append((str(section.get("title") or "section"), text))
        if parsed_sections:
            return parsed_sections
    return [("abstract", source.summary)] if source.summary else []


def _sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text.strip())
        if sentence.strip()
    ]


def _snippet_relevance(sentence: str, objective_terms: set[str]) -> float:
    if not objective_terms:
        return 0.0
    sentence_lower = sentence.lower()
    matches = sum(1 for term in objective_terms if term in sentence_lower)
    return round(float(matches), 3)


def _evidence_label(source: ResearchSource) -> str:
    source_type = source.source_type or "source"
    identifier = source.title or source.url or "untitled"
    return f"{source_type}:{identifier}"


def _list_payload(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _hypothesis_outcome(hypothesis: dict[str, Any], experiments: list[Any]) -> dict[str, Any]:
    hypothesis_id = str(hypothesis.get("hypothesis_id", ""))
    relevant = [
        experiment for experiment in experiments
        if isinstance(experiment, dict) and experiment.get("hypothesis_id") == hypothesis_id
    ]
    accepted = sum(1 for experiment in relevant if experiment.get("accepted"))
    failed = sum(1 for experiment in relevant if experiment.get("error"))
    best = _best_experiment_for_hypothesis(hypothesis, relevant)

    if accepted:
        status = "supported"
    elif failed and failed == len(relevant):
        status = "failed"
    elif relevant:
        status = "not_supported"
    else:
        status = "not_tested"

    return {
        "hypothesis_id": hypothesis_id,
        "title": str(hypothesis.get("title", "")),
        "experiments": len(relevant),
        "accepted": accepted,
        "failed": failed,
        "best_experiment_id": best.get("experiment_id"),
        "best_val": best.get("best_val"),
        "status": status,
    }


def _best_experiment_for_hypothesis(
    hypothesis: dict[str, Any],
    experiments: list[dict[str, Any]],
) -> dict[str, Any]:
    metric_name = str(hypothesis.get("expected_metric") or "val_bpb")
    direction = str(hypothesis.get("expected_direction") or "minimize")
    candidates = []
    for experiment in experiments:
        metrics = experiment.get("metrics") if isinstance(experiment.get("metrics"), dict) else {}
        value = metrics.get(metric_name, metrics.get("val", metrics.get("val_bpb")))
        if isinstance(value, (int, float)):
            candidates.append((float(value), experiment))
    if not candidates:
        return {"experiment_id": None, "best_val": None}

    best_value, best_experiment = (
        min(candidates, key=lambda item: item[0])
        if direction == "minimize"
        else max(candidates, key=lambda item: item[0])
    )
    return {
        "experiment_id": best_experiment.get("experiment_id"),
        "best_val": best_value,
    }


def _review_decision(
    experiments: list[Any],
    supported: list[dict[str, Any]],
    failed_count: int,
    best_result: dict[str, Any],
) -> str:
    if supported and best_result:
        return "continue_from_best"
    if failed_count and failed_count == len(experiments):
        return "debug_failures"
    if experiments:
        return "revise_search_space"
    return "not_started"


def _next_actions(decision: str, best_result: dict[str, Any], failed_count: int) -> list[str]:
    if decision == "continue_from_best":
        experiment_id = best_result.get("experiment_id", "the best experiment")
        return [
            f"Continue locally around best params from {experiment_id}.",
            "Run one narrower follow-up experiment before widening the search space.",
        ]
    if decision == "debug_failures":
        return [
            f"Inspect logs for {failed_count} failed experiments before sampling more params.",
            "Reduce risky hyperparameter ranges or increase experiment_duration_seconds.",
        ]
    if decision == "revise_search_space":
        return [
            "Revise the search space or generate a new hypothesis before continuing.",
            "Use research_task again if current evidence did not produce accepted experiments.",
        ]
    return ["Run at least one hypothesis-backed experiment before reviewing results."]


def _parameter_hints(center_params: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        name: _parameter_hint(name, value)
        for name, value in center_params.items()
    }


def _parameter_hint(name: str, value: Any) -> dict[str, Any]:
    if isinstance(value, int) and not isinstance(value, bool):
        normalized_name = name.lower()
        if normalized_name in {"dim", "hidden_dim", "model_dim", "d_model"}:
            return {
                "type": "choice",
                "values": _unique_sorted_ints([
                    max(4, value // 2),
                    value,
                    value * 2,
                ], multiple_of=4),
            }
        if normalized_name in {"window_size", "context_length", "seq_len", "block_size"}:
            return {
                "type": "choice",
                "values": _unique_sorted_ints([value, value * 2]),
            }
        lower = max(1, value - 1)
        upper = value + 1
        return {"type": "choice", "values": list(range(lower, upper + 1))}
    if isinstance(value, float):
        low = value / 2.0 if value > 0 else value - 1.0
        high = value * 2.0 if value > 0 else value + 1.0
        q = _float_step(value)
        return {
            "type": "q_log_uniform" if value > 0 else "q_uniform",
            "min": round(low, 10),
            "max": round(high, 10),
            "q": q,
        }
    return {"type": "choice", "values": [value]}


def _unique_sorted_ints(values: list[int], multiple_of: int | None = None) -> list[int]:
    normalized = []
    for value in values:
        candidate = int(value)
        if multiple_of:
            candidate = max(multiple_of, round(candidate / multiple_of) * multiple_of)
        if candidate > 0:
            normalized.append(candidate)
    return sorted(set(normalized))


def _float_step(value: float) -> float:
    magnitude = abs(value)
    if magnitude >= 1:
        return 0.1
    if magnitude >= 0.01:
        return 0.001
    if magnitude >= 0.001:
        return 0.0001
    return 0.00001
