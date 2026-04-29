"""Fusion workflow helpers for ml-intern research and autoresearch validation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from pathlib import Path
import re
from typing import Any

from lib.research_components import parse_search_region
from lib.research_protocol import (
    ResearchBrief,
    ResearchFinding,
    ResearchHypothesis,
    ResearchSource,
)
from ml_intern import research_tools


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
) -> dict[str, Any]:
    """Collect real research sources and turn them into a fusion research brief."""
    effective_query = (query or objective).strip()
    query_plan = build_query_plan(objective=objective, query=effective_query)
    sources: list[ResearchSource] = []
    warnings: list[str] = []

    if include_papers:
        sources.extend(
            _collect_sources(
                "papers",
                lambda: research_tools.search_papers(effective_query, limit=paper_limit),
                warnings,
            )
        )
    if include_hf_datasets:
        sources.extend(
            _collect_sources(
                "hf_datasets",
                lambda: research_tools.search_hf_datasets(effective_query, limit=dataset_limit),
                warnings,
            )
        )
    if include_github_code:
        sources.extend(
            _collect_sources(
                "github_code",
                lambda: research_tools.search_github_code(effective_query, limit=github_limit),
                warnings,
            )
        )

    sources = enrich_sources(
        deduplicate_sources(sources),
        objective=objective,
        query=effective_query,
    )
    source_dicts = [source.to_dict() for source in sources]
    brief = propose_hypotheses(objective, source_dicts)
    brief.update({
        "status": "research_context_ready" if not warnings else "research_context_partial",
        "query": effective_query,
        "query_plan": query_plan,
        "warnings": warnings,
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
        key = _source_key(source)
        if key in seen:
            continue
        seen.add(key)
        unique_sources.append(source)
    return unique_sources


def enrich_sources(
    sources: list[ResearchSource],
    objective: str,
    query: str,
) -> list[ResearchSource]:
    """Attach deterministic relevance metadata while preserving source order."""
    return [
        ResearchSource(
            source_type=source.source_type,
            title=source.title,
            url=source.url,
            summary=source.summary,
            metadata={
                **source.metadata,
                "relevance_score": relevance_score(source, objective=objective, query=query),
            },
        )
        for source in sources
    ]


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
            "evidence": _evidence_label(source),
        }
        for index, source in enumerate(ranked, start=1)
    ]


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
        "failure_summary": _failure_summary(experiments),
        "current_code": _current_code_state(workspace_path),
        "artifacts": _artifact_paths(
            task_id=task_id,
            workspace_path=workspace_path,
            runtime_root=runtime_root,
            result_payload=result_payload,
        ),
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
) -> list[ResearchSource]:
    try:
        return list(collect())
    except Exception as exc:  # noqa: BLE001 - research backends should degrade independently.
        warnings.append(f"{label}: {exc}")
        return []


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
    if source.url:
        return ("url", source.url.strip().lower())
    return (source.source_type, source.title.strip().lower())


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
        name: _parameter_hint(value)
        for name, value in center_params.items()
    }


def _parameter_hint(value: Any) -> dict[str, Any]:
    if isinstance(value, int) and not isinstance(value, bool):
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


def _float_step(value: float) -> float:
    magnitude = abs(value)
    if magnitude >= 1:
        return 0.1
    if magnitude >= 0.01:
        return 0.001
    if magnitude >= 0.001:
        return 0.0001
    return 0.00001
