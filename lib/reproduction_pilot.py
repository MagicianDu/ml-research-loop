"""Selection gate helpers for real-paper reproduction pilots."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import time
from typing import Any

from lib.environment_probe import probe_research_environment
from lib.research_case import EvidenceRef, ResearchCase, ResearchClaim, ResearchMilestone


DEFAULT_RESOURCE_BUDGET_MINUTES = 15
FORBIDDEN_REPRODUCTION_CLAIMS = [
    "official benchmark score",
    "full SOTA reproduction",
    "official leaderboard result",
]
REQUIRED_PROOF_ARTIFACTS = {
    "paper_selection_report": "paper-selection-report.json",
    "research_case": "research-case.json",
    "environment_probe": "environment-probe.json",
    "dataset_provenance": "dataset-provenance.json",
    "baseline_metrics": "baseline-metrics.json",
    "ablation_metrics": "ablation-metrics.json",
    "experiment_summary": "experiment-summary.json",
    "run_log": "run-log.txt",
    "client_handoff": "client-handoff.json",
    "client_routing_patch": "client-routing-patch.json",
    "patched_metrics": "patched-metrics.json",
    "iteration_comparison": "iteration-comparison.json",
    "human_review_report": "human-review-report.json",
}
VALID_REVIEW_DECISIONS = {
    "approved_with_limitations",
    "needs_more_evidence",
    "rejected",
}


@dataclass(frozen=True)
class PaperCandidate:
    """A bounded paper candidate before it enters a reproduction pilot."""

    paper_id: str
    title: str
    arxiv_url: str
    task: str
    metric: str
    dataset_plan: str
    algorithm_plan: str
    resource_budget_minutes: int
    target_claim: str
    official_scores_claimed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PaperSelectionReport:
    """Decision artifact for the paper-selection gate."""

    paper_id: str
    title: str
    arxiv_url: str
    task: str
    target_claim: str
    target_metric: str
    dataset_plan: str
    algorithm_plan: str
    resource_budget_minutes: int
    decision: str
    reject_reasons: list[str]
    official_scores_claimed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PilotRunConfig:
    """Local execution constraints for a real-paper reproduction pilot."""

    case_id: str
    data_path: Path
    output_dir: Path
    max_runtime_seconds: int
    required_commands: tuple[str, ...] = ("python3",)


@dataclass(frozen=True)
class PilotEnvironmentReport:
    """Readiness report for a bounded pilot run."""

    status: str
    case_id: str
    data_path: str
    output_dir: str
    python_version: str
    max_runtime_seconds: int
    data_exists: bool
    data_valid: bool
    output_dir_writable: bool
    missing_commands: list[str]
    package_status: dict[str, str]
    secret_risk_files: list[str]
    blockers: list[str]
    repair_plan: list[dict[str, Any]]
    official_scores_claimed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PilotExperimentResult:
    """Artifacts and metric summary for a bounded local pilot experiment."""

    status: str
    case_id: str
    metric_name: str
    baseline_metric: float
    ablation_metric: float
    sample_count: int
    substitute_data: bool
    artifacts: dict[str, Path]
    official_scores_claimed: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["artifacts"] = {
            role: str(path) for role, path in self.artifacts.items()
        }
        return payload


def evaluate_paper_candidate(
    candidate: PaperCandidate,
    *,
    default_budget_minutes: int = DEFAULT_RESOURCE_BUDGET_MINUTES,
) -> PaperSelectionReport:
    """Evaluate whether a paper candidate can enter the bounded pilot."""
    reject_reasons: list[str] = []

    if not candidate.arxiv_url.strip():
        reject_reasons.append("missing_arxiv_url")
    if not candidate.task.strip():
        reject_reasons.append("missing_task")
    if not candidate.metric.strip():
        reject_reasons.append("missing_metric")
    if not candidate.dataset_plan.strip():
        reject_reasons.append("missing_dataset_plan")
    if not candidate.target_claim.strip():
        reject_reasons.append("missing_target_claim")
    if not candidate.algorithm_plan.strip():
        reject_reasons.append("missing_algorithm_plan")
    if candidate.official_scores_claimed:
        reject_reasons.append("official_scores_claimed_not_allowed")

    budget_reasons: list[str] = []
    if candidate.resource_budget_minutes > default_budget_minutes:
        budget_reasons.append("resource_budget_exceeds_default_limit")

    if reject_reasons:
        return _build_report(candidate, decision="rejected", reject_reasons=reject_reasons)
    if budget_reasons:
        return _build_report(
            candidate,
            decision="requires_override",
            reject_reasons=budget_reasons,
        )
    return _build_report(candidate, decision="accepted_for_pilot", reject_reasons=[])


def reject_candidate(candidate: PaperCandidate, reasons: list[str]) -> PaperSelectionReport:
    """Build an explicit rejection report while preserving candidate metadata."""
    return _build_report(candidate, decision="rejected", reject_reasons=list(reasons))


def build_research_case_from_selection(
    report: PaperSelectionReport,
    *,
    selection_artifact_path: Path,
) -> ResearchCase:
    """Convert an accepted selection report into a long-running ResearchCase."""
    case_slug = _slugify(report.paper_id)
    title_slug = _slugify(report.title.split(":", maxsplit=1)[0]) or "paper"
    selection_artifact = selection_artifact_path.as_posix()
    return ResearchCase(
        case_id=f"real-paper-pilot-{case_slug}",
        objective=(
            f"Reproduce one bounded claim from {report.title}: "
            f"{report.target_claim}. Task: {report.task}. Metric: {report.target_metric}."
        ),
        claims=[
            ResearchClaim(
                claim_id=f"claim-{title_slug}-bounded",
                text=report.target_claim,
                status="needs_evidence",
                evidence_refs=[
                    EvidenceRef(
                        source_id=report.paper_id,
                        artifact_path=report.arxiv_url,
                        quote=report.title,
                        strength="paper_claim",
                    ),
                    EvidenceRef(
                        source_id="paper-selection-report",
                        artifact_path=selection_artifact,
                        quote="accepted bounded pilot with official_scores_claimed=false",
                        strength="runtime_artifact",
                    ),
                ],
            )
        ],
        milestones=[
            ResearchMilestone(
                milestone_id="selection-gate",
                kind="research",
                status="passed" if report.decision == "accepted_for_pilot" else "blocked",
                artifact_path=selection_artifact,
                metric_name=report.target_metric,
            )
        ],
        forbidden_claims=list(FORBIDDEN_REPRODUCTION_CLAIMS),
        official_scores_claimed=False,
    )


def write_research_case(case: ResearchCase, output_dir: Path) -> Path:
    """Persist a ResearchCase JSON artifact and return its path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    case_path = output_dir / "research-case.json"
    case_path.write_text(
        json.dumps(case.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return case_path


def write_fixture_dataset(data_path: Path) -> Path:
    """Write a deterministic substitute dataset for the bounded MemFlow pilot."""
    records = [
        {
            "id": "q1",
            "intent": "definition",
            "question": "What does the memory system orchestrate?",
            "memories": [
                {
                    "intent": "definition",
                    "text": "MemFlow-shaped agents orchestrate memory by intent.",
                    "relevant": True,
                },
                {
                    "intent": "limitation",
                    "text": "This local pilot does not claim official benchmark results.",
                    "relevant": False,
                },
            ],
        },
        {
            "id": "q2",
            "intent": "limitation",
            "question": "What claim boundary must be preserved?",
            "memories": [
                {
                    "intent": "definition",
                    "text": "The agent has a memory router.",
                    "relevant": False,
                },
                {
                    "intent": "limitation",
                    "text": "Local substitute data must not be reported as SOTA.",
                    "relevant": True,
                },
            ],
        },
        {
            "id": "q3",
            "intent": "metric",
            "question": "Which artifact records measured progress?",
            "memories": [
                {
                    "intent": "metric",
                    "text": "Metrics are written to JSON artifacts for review.",
                    "relevant": True,
                },
                {
                    "intent": "definition",
                    "text": "Intent labels describe the local routing task.",
                    "relevant": False,
                },
            ],
        },
        {
            "id": "q4",
            "intent": "repair",
            "question": "What should happen when data is missing?",
            "memories": [
                {
                    "intent": "metric",
                    "text": "The metric direction is higher_is_better.",
                    "relevant": False,
                },
                {
                    "intent": "repair",
                    "text": "The environment probe should report a repair plan.",
                    "relevant": True,
                },
            ],
        },
    ]
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    return data_path


def write_public_memflow_slice(data_path: Path) -> Path:
    """Write a tiny public-source-derived MemFlow pilot slice.

    The records are paraphrased from public arXiv metadata/abstract-level
    descriptions and intentionally avoid storing verbatim paper text.
    """
    source = {
        "kind": "public_arxiv_metadata",
        "url": "https://arxiv.org/abs/2605.03312",
        "paper_id": "arxiv:2605.03312",
        "paper_title": (
            "MemFlow: Intent-Driven Memory Orchestration for Small Language Model Agents"
        ),
        "verbatim_excerpt": False,
    }
    records = [
        {
            "id": "public-q1",
            "intent": "profile",
            "question": "Which memory tier should answer a stable user profile query?",
            "source": source,
            "memories": [
                {
                    "intent": "scratchpad",
                    "text": "Recent scratchpad notes are useful for short-lived dialogue state.",
                    "relevant": False,
                },
                {
                    "intent": "profile",
                    "text": "Stable user preferences belong in profile-oriented memory.",
                    "relevant": True,
                },
            ],
        },
        {
            "id": "public-q2",
            "intent": "targeted_retrieval",
            "question": "Which tier should serve a focused evidence lookup?",
            "source": source,
            "memories": [
                {
                    "intent": "profile",
                    "text": "Profile memory stores durable user traits.",
                    "relevant": False,
                },
                {
                    "intent": "targeted_retrieval",
                    "text": "Targeted retrieval should fetch compact task-relevant context.",
                    "relevant": True,
                },
            ],
        },
        {
            "id": "public-q3",
            "intent": "deep_reasoning",
            "question": "Which tier should support a multi-step reasoning request?",
            "source": source,
            "memories": [
                {
                    "intent": "deep_reasoning",
                    "text": "Deep reasoning memory can keep broader context for harder tasks.",
                    "relevant": True,
                },
                {
                    "intent": "scratchpad",
                    "text": "Scratchpad memory captures transient intermediate notes.",
                    "relevant": False,
                },
            ],
        },
        {
            "id": "public-q4",
            "intent": "scratchpad",
            "question": "Which tier should hold temporary working notes?",
            "source": source,
            "memories": [
                {
                    "intent": "targeted_retrieval",
                    "text": "Targeted retrieval searches for compact external evidence.",
                    "relevant": False,
                },
                {
                    "intent": "scratchpad",
                    "text": "Scratchpad memory should hold temporary working state.",
                    "relevant": True,
                },
            ],
        },
    ]
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    return data_path


def run_bounded_pilot_experiment(
    config: PilotRunConfig,
    *,
    target_claim: str,
    metric_name: str,
    substitute_data: bool,
) -> PilotExperimentResult:
    """Run a deterministic baseline and intent-routing ablation."""
    start_time = time.monotonic()
    records = _load_fixture_records(config.data_path)
    output_dir = config.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline_predictions = [_select_baseline_memory(record) for record in records]
    ablation_predictions = [_select_intent_memory(record) for record in records]
    baseline_metric = _selection_accuracy(baseline_predictions)
    ablation_metric = _selection_accuracy(ablation_predictions)
    duration_seconds = round(time.monotonic() - start_time, 6)

    baseline_path = output_dir / "baseline-metrics.json"
    ablation_path = output_dir / "ablation-metrics.json"
    summary_path = output_dir / "experiment-summary.json"
    log_path = output_dir / "run-log.txt"
    handoff_path = output_dir / "client-handoff.json"
    provenance_path = output_dir / "dataset-provenance.json"
    data_kind = _data_kind(substitute_data)

    common_metric_payload = {
        "case_id": config.case_id,
        "metric_name": metric_name,
        "metric_direction": "higher_is_better",
        "sample_count": len(records),
        "substitute_data": substitute_data,
        "data_kind": data_kind,
        "official_scores_claimed": False,
    }
    _write_json(
        baseline_path,
        {
            **common_metric_payload,
            "run_kind": "baseline",
            "metric_value": baseline_metric,
            "method": "select_first_memory",
        },
    )
    _write_json(
        ablation_path,
        {
            **common_metric_payload,
            "run_kind": "intent_routing_ablation",
            "metric_value": ablation_metric,
            "method": "select_memory_matching_intent",
        },
    )
    delta = round(ablation_metric - baseline_metric, 6)
    decision = "continue" if delta > 0 else "review_failure"
    _write_json(
        summary_path,
        {
            "status": "completed",
            "case_id": config.case_id,
            "target_claim": target_claim,
            "metric_name": metric_name,
            "metric_before": baseline_metric,
            "metric_after": ablation_metric,
            "delta": delta,
            "decision": decision,
            "duration_seconds": duration_seconds,
            "substitute_data": substitute_data,
            "data_kind": data_kind,
            "official_scores_claimed": False,
        },
    )
    _write_json(
        provenance_path,
        _build_dataset_provenance(
            records=records,
            data_path=config.data_path,
            substitute_data=substitute_data,
        ),
    )
    log_path.write_text(
        "\n".join(
            [
                "real-paper reproduction pilot bounded run",
                f"case_id={config.case_id}",
                f"metric_name={metric_name}",
                f"baseline={baseline_metric}",
                f"ablation={ablation_metric}",
                f"substitute_data={str(substitute_data).lower()}",
                f"data_kind={data_kind}",
                "official_scores_claimed=false",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        handoff_path,
        {
            "case_summary": {
                "case_id": config.case_id,
                "status": "baseline_completed",
                "substitute_data": substitute_data,
                "data_kind": data_kind,
                "official_scores_claimed": False,
            },
            "target_claim": target_claim,
            "metric_before": baseline_metric,
            "metric_after": ablation_metric,
            "failure_or_gap": _handoff_gap(delta, substitute_data),
            "allowed_patch_scope": _allowed_patch_scope(substitute_data),
            "suggested_next_actions": [
                "validate on a larger public dataset slice",
                "try a second routing heuristic under the same metric",
                "stop if the next run cannot improve evidence quality",
            ],
            "stop_rules": [
                "stop if data remains substitute-only for public claims",
                "stop if metric regresses twice under the same budget",
                "stop before claiming official benchmark or SOTA performance",
            ],
            "official_scores_claimed": False,
        },
    )

    return PilotExperimentResult(
        status="completed",
        case_id=config.case_id,
        metric_name=metric_name,
        baseline_metric=baseline_metric,
        ablation_metric=ablation_metric,
        sample_count=len(records),
        substitute_data=substitute_data,
        artifacts={
            "baseline_metrics": baseline_path,
            "ablation_metrics": ablation_path,
            "experiment_summary": summary_path,
            "run_log": log_path,
            "client_handoff": handoff_path,
            "dataset_provenance": provenance_path,
        },
        official_scores_claimed=False,
    )


def run_guarded_pilot_iteration(
    config: PilotRunConfig,
    *,
    target_claim: str,
    metric_name: str,
    substitute_data: bool,
) -> dict[str, Any]:
    """Apply a bounded client-style routing config patch and compare metrics."""
    output_dir = config.output_dir.expanduser().resolve()
    baseline_path = output_dir / "baseline-metrics.json"
    if not baseline_path.exists():
        return {
            "status": "blocked",
            "blockers": ["missing_baseline_metrics"],
            "official_scores_claimed": False,
        }

    baseline_payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    records = _load_fixture_records(config.data_path)
    patch_path = output_dir / "client-routing-patch.json"
    patched_metrics_path = output_dir / "patched-metrics.json"
    comparison_path = output_dir / "iteration-comparison.json"

    patch_payload = {
        "case_id": config.case_id,
        "patch_kind": "routing_config",
        "patch_source": "client_handoff",
        "allowed_patch_scope": ["routing heuristic configuration"],
        "config_before": {"routing_method": "select_first_memory"},
        "config_after": {"routing_method": "select_memory_matching_intent"},
        "patch_applied": True,
        "substitute_data": substitute_data,
        "data_kind": _data_kind(substitute_data),
        "official_scores_claimed": False,
    }
    _write_json(patch_path, patch_payload)

    patched_predictions = [_select_intent_memory(record) for record in records]
    patched_metric = _selection_accuracy(patched_predictions)
    metric_before = float(baseline_payload["metric_value"])
    delta = round(patched_metric - metric_before, 6)
    decision = "continue" if delta > 0 else "stop"
    why = (
        _iteration_success_reason(substitute_data)
        if delta > 0
        else "The guarded routing-config patch did not improve the local metric."
    )
    next_recommended_action = (
        _iteration_next_action(substitute_data)
        if delta > 0
        else "Stop this patch path and inspect failure diagnostics before another iteration."
    )

    patched_payload = {
        "case_id": config.case_id,
        "metric_name": metric_name,
        "metric_direction": "higher_is_better",
        "run_kind": "guarded_routing_config_patch",
        "metric_value": patched_metric,
        "sample_count": len(records),
        "patch_artifact": str(patch_path),
        "substitute_data": substitute_data,
        "data_kind": _data_kind(substitute_data),
        "official_scores_claimed": False,
    }
    _write_json(patched_metrics_path, patched_payload)

    comparison = {
        "status": "completed",
        "case_id": config.case_id,
        "target_claim": target_claim,
        "metric_name": metric_name,
        "metric_before": metric_before,
        "metric_after": patched_metric,
        "delta": delta,
        "decision": decision,
        "why": why,
        "next_recommended_action": next_recommended_action,
        "patch_artifact": str(patch_path),
        "patched_metrics": str(patched_metrics_path),
        "substitute_data": substitute_data,
        "data_kind": _data_kind(substitute_data),
        "official_scores_claimed": False,
    }
    _write_json(comparison_path, comparison)
    return comparison


def write_human_review_report(
    *,
    output_dir: Path,
    paper_id: str,
    claim: str,
    reviewer: str,
    decision: str,
) -> Path:
    """Write an operator-review artifact for the bounded real-paper pilot."""
    if decision not in VALID_REVIEW_DECISIONS:
        allowed = ", ".join(sorted(VALID_REVIEW_DECISIONS))
        raise ValueError(f"invalid review decision: {decision}; expected one of {allowed}")
    resolved_output_dir = output_dir.expanduser().resolve()
    required_paths = {
        "dataset_provenance": resolved_output_dir / "dataset-provenance.json",
        "experiment_summary": resolved_output_dir / "experiment-summary.json",
        "iteration_comparison": resolved_output_dir / "iteration-comparison.json",
    }
    missing = [
        role
        for role, path in required_paths.items()
        if not path.is_file()
    ]
    if missing:
        raise FileNotFoundError(f"missing review inputs: {', '.join(missing)}")

    provenance = _read_json(required_paths["dataset_provenance"])
    summary = _read_json(required_paths["experiment_summary"])
    iteration = _read_json(required_paths["iteration_comparison"])
    substitute_data = bool(iteration.get("substitute_data"))
    data_kind = _data_kind(substitute_data)
    official_claims_ok = not any(
        bool(payload.get("official_scores_claimed"))
        for payload in [provenance, summary, iteration]
    )
    checklist = [
        {
            "item": "all_required_artifacts_present",
            "status": "passed",
        },
        {
            "item": "official_scores_claimed_false",
            "status": "passed" if official_claims_ok else "failed",
        },
        {
            "item": "claim_strength_limited",
            "status": "passed"
            if data_kind in {"local_public_data", "local_substitute_data"}
            else "failed",
        },
        {
            "item": "dataset_provenance_recorded",
            "status": "passed" if provenance.get("source_kind") else "failed",
        },
        {
            "item": "full_reproduction_claim_blocked",
            "status": "passed",
        },
    ]
    blocked_public_claims = [
        "official benchmark score",
        "full paper reproduction",
        "SOTA or leaderboard performance",
    ]
    approved_public_claims = []
    if decision == "approved_with_limitations":
        approved_public_claims.append(
            "bounded real-paper pilot with auditable local public-slice artifacts"
            if not substitute_data
            else "bounded real-paper pilot with auditable local substitute-data artifacts"
        )

    report = {
        "schema_version": "2026-05-13.real-paper-human-review.v1",
        "review_method": "operator_artifact_review",
        "reviewer": reviewer,
        "review_status": decision,
        "case_id": iteration["case_id"],
        "paper_id": paper_id,
        "claim": claim,
        "claim_strength": data_kind,
        "metric_summary": {
            "metric_name": iteration["metric_name"],
            "metric_before": iteration["metric_before"],
            "metric_after": iteration["metric_after"],
            "delta": iteration["delta"],
            "substitute_data": substitute_data,
            "data_kind": data_kind,
        },
        "checklist": checklist,
        "limitations_acknowledged": _proof_limitations(substitute_data),
        "approved_public_claims": approved_public_claims,
        "blocked_public_claims": blocked_public_claims,
        "human_review_required_for_stronger_claims": True,
        "official_scores_claimed": False,
    }
    report_path = resolved_output_dir / "human-review-report.json"
    _write_json(report_path, report)
    return report_path


def write_pilot_proof_archive(
    *,
    output_dir: Path,
    proof_dir: Path,
    paper_id: str,
    claim: str,
    commands: list[str],
) -> dict[str, Any]:
    """Archive a completed real-paper pilot with hashes and claim boundaries."""
    resolved_output_dir = output_dir.expanduser().resolve()
    resolved_proof_dir = proof_dir.expanduser().resolve()
    missing = [
        file_name
        for file_name in REQUIRED_PROOF_ARTIFACTS.values()
        if not (resolved_output_dir / file_name).is_file()
    ]
    if missing:
        return {
            "status": "blocked",
            "blockers": ["missing_required_artifacts"],
            "missing_artifacts": missing,
            "official_scores_claimed": False,
        }

    artifacts_dir = resolved_proof_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    archived_artifacts: list[dict[str, Any]] = []
    for role, file_name in REQUIRED_PROOF_ARTIFACTS.items():
        source_path = resolved_output_dir / file_name
        archive_path = artifacts_dir / file_name
        _copy_sanitized_artifact(
            source_path,
            archive_path,
            redacted_prefix=resolved_output_dir,
        )
        archived_artifacts.append(
            {
                "role": role,
                "source_path": source_path.relative_to(resolved_output_dir).as_posix(),
                "archive_path": archive_path.relative_to(resolved_proof_dir).as_posix(),
                "sha256": _sha256_file(archive_path),
                "size_bytes": archive_path.stat().st_size,
            }
        )

    selection = _read_json(resolved_output_dir / "paper-selection-report.json")
    environment = _read_json(resolved_output_dir / "environment-probe.json")
    iteration = _read_json(resolved_output_dir / "iteration-comparison.json")
    summary = _read_json(resolved_output_dir / "experiment-summary.json")
    review = _read_json(resolved_output_dir / "human-review-report.json")
    substitute_data = bool(iteration.get("substitute_data"))
    manifest = {
        "case_id": iteration["case_id"],
        "paper_id": paper_id,
        "paper_title": selection.get("title"),
        "claim": claim,
        "claim_strength": _data_kind(substitute_data),
        "official_scores_claimed": False,
        "artifacts": archived_artifacts,
        "artifact_sha256": {
            item["role"]: item["sha256"] for item in archived_artifacts
        },
        "commands": commands,
        "environment": {
            "python_version": environment.get("python_version"),
            "package_status": environment.get("package_status", {}),
            "data_valid": environment.get("data_valid"),
            "max_runtime_seconds": environment.get("max_runtime_seconds"),
        },
        "metric_summary": {
            "metric_name": iteration["metric_name"],
            "metric_before": iteration["metric_before"],
            "metric_after": iteration["metric_after"],
            "delta": iteration["delta"],
            "decision": iteration["decision"],
            "baseline_decision": summary.get("decision"),
            "substitute_data": substitute_data,
            "data_kind": _data_kind(substitute_data),
        },
        "limitations": _proof_limitations(substitute_data),
        "review_status": review.get("review_status", "review_missing"),
        "review": {
            "review_method": review.get("review_method"),
            "reviewer": review.get("reviewer"),
            "human_review_required_for_stronger_claims": bool(
                review.get("human_review_required_for_stronger_claims", True)
            ),
        },
    }
    manifest_path = resolved_proof_dir / "proof-manifest.json"
    _write_json(manifest_path, manifest)
    return {
        "status": "completed",
        "proof_manifest": str(manifest_path),
        "artifact_count": len(archived_artifacts),
        "official_scores_claimed": False,
    }


def write_pilot_evidence_indexes(
    *,
    manifest_path: Path,
    evidence_dir: Path,
) -> dict[str, Path]:
    """Write public evidence indexes for the real-paper pilot proof."""
    manifest = _read_json(manifest_path)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    pilot_index_path = evidence_dir / "real-paper-pilot-index.json"
    claims_map_path = evidence_dir / "public-claims-map.json"
    repo_root = evidence_dir.resolve().parents[1]
    evidence_path = _display_path(manifest_path, repo_root)
    pilot_index = {
        "schema_version": "2026-05-13.real-paper-pilot.v1",
        "official_scores_claimed": False,
        "entries": [
            {
                "case_id": manifest["case_id"],
                "paper_id": manifest["paper_id"],
                "claim": manifest["claim"],
                "claim_strength": manifest["claim_strength"],
                "proof_manifest": evidence_path,
                "metric_summary": manifest["metric_summary"],
                "limitations": manifest["limitations"],
                "review_status": manifest["review_status"],
                "official_scores_claimed": False,
            }
        ],
    }
    public_claim = (
        "ML Research Loop can execute a bounded real-paper pilot "
        "with auditable local public-slice artifacts."
        if manifest["claim_strength"] == "local_public_data"
        else "ML Research Loop can execute a bounded real-paper pilot "
        "with auditable local artifacts."
    )
    claim_boundary = (
        "local public-data slice proof only; not an official score"
        if manifest["claim_strength"] == "local_public_data"
        else "local substitute-data proof only; not an official score"
    )
    claim_id = (
        "real-paper-pilot-public-slice-proof"
        if manifest["claim_strength"] == "local_public_data"
        else "real-paper-pilot-local-proof"
    )
    allowed_public_claim = manifest.get("review_status") == "approved_with_limitations"
    public_claims_map = {
        "schema_version": "2026-05-13.public-claims.v1",
        "official_scores_claimed": False,
        "public_claims": [
            {
                "claim_id": claim_id,
                "public_claim": public_claim,
                "proof_matrix_entry": "Real paper pilot",
                "evidence": evidence_path,
                "claim_boundary": claim_boundary,
            }
        ],
        "claims": [
            {
                "public_claim": public_claim,
                "public_claim_status": (
                    "allowed_with_boundary"
                    if allowed_public_claim
                    else "blocked_pending_review"
                ),
                "evidence": evidence_path,
                "boundary": claim_boundary,
            },
            {
                "public_claim": (
                    "ML Research Loop reproduced the full MemFlow paper or achieved "
                    "official benchmark/SOTA results."
                ),
                "public_claim_status": "blocked",
                "evidence": evidence_path,
                "boundary": "blocked by claim boundary and proof limitations",
            },
        ],
    }
    _write_json(pilot_index_path, pilot_index)
    _write_json(claims_map_path, public_claims_map)
    return {
        "pilot_index": pilot_index_path,
        "public_claims_map": claims_map_path,
    }


def probe_pilot_environment(config: PilotRunConfig) -> PilotEnvironmentReport:
    """Probe local readiness without reading secret file contents."""
    output_dir = config.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    data_path = config.data_path.expanduser()
    resolved_data_path = data_path.resolve() if data_path.exists() else data_path

    workspace_report = probe_research_environment(
        workspace=output_dir,
        required_files=[],
        required_commands=list(config.required_commands),
    )
    blockers: list[str] = []
    repair_plan = list(workspace_report["repair_plan"])

    data_exists = data_path.exists()
    data_valid = False
    if not data_exists:
        blockers.append("dataset_missing")
        repair_plan.append(
            {
                "kind": "create_or_mount_dataset",
                "path": str(resolved_data_path),
                "message": (
                    "Create the pilot dataset, mount a public dataset slice, "
                    "or mark the run as substitute_data=true."
                ),
            }
        )
    else:
        dataset_blockers, dataset_repair_plan = _validate_pilot_dataset(data_path)
        blockers.extend(dataset_blockers)
        repair_plan.extend(dataset_repair_plan)
        data_valid = not dataset_blockers

    output_dir_writable = _is_writable_directory(output_dir)
    if not output_dir_writable:
        blockers.append("output_dir_not_writable")
        repair_plan.append(
            {
                "kind": "fix_output_dir_permissions",
                "path": str(output_dir),
                "message": "Make the pilot output directory writable.",
            }
        )

    if config.max_runtime_seconds <= 0:
        blockers.append("invalid_runtime_budget")
        repair_plan.append(
            {
                "kind": "fix_runtime_budget",
                "message": "Use a positive max_runtime_seconds value.",
            }
        )

    missing_commands = list(workspace_report["missing_commands"])
    blockers.extend(f"missing_command:{command}" for command in missing_commands)
    package_status = _probe_package_status(["pytest", "lib.research_case"])

    status = "blocked" if blockers else "ready"
    return PilotEnvironmentReport(
        status=status,
        case_id=config.case_id,
        data_path=str(resolved_data_path),
        output_dir=str(output_dir),
        python_version=sys.version.split()[0],
        max_runtime_seconds=config.max_runtime_seconds,
        data_exists=data_exists,
        data_valid=data_valid,
        output_dir_writable=output_dir_writable,
        missing_commands=missing_commands,
        package_status=package_status,
        secret_risk_files=list(workspace_report["secret_risk_files"]),
        blockers=blockers,
        repair_plan=repair_plan,
        official_scores_claimed=False,
    )


def _build_report(
    candidate: PaperCandidate,
    *,
    decision: str,
    reject_reasons: list[str],
) -> PaperSelectionReport:
    return PaperSelectionReport(
        paper_id=candidate.paper_id,
        title=candidate.title,
        arxiv_url=candidate.arxiv_url,
        task=candidate.task,
        target_claim=candidate.target_claim,
        target_metric=candidate.metric,
        dataset_plan=candidate.dataset_plan,
        algorithm_plan=candidate.algorithm_plan,
        resource_budget_minutes=candidate.resource_budget_minutes,
        decision=decision,
        reject_reasons=reject_reasons,
        official_scores_claimed=candidate.official_scores_claimed,
    )


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "paper"


def _is_writable_directory(path: Path) -> bool:
    probe_path = path / ".write-probe"
    try:
        probe_path.write_text("ok\n", encoding="utf-8")
        probe_path.unlink()
    except OSError:
        return False
    return True


def _probe_package_status(module_names: list[str]) -> dict[str, str]:
    return {
        module_name: "available"
        if importlib.util.find_spec(module_name) is not None
        else "missing"
        for module_name in module_names
    }


def _load_fixture_records(data_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in data_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    if not records:
        raise ValueError(f"pilot dataset is empty: {data_path}")
    return records


def _data_kind(substitute_data: bool) -> str:
    return "local_substitute_data" if substitute_data else "local_public_data"


def _build_dataset_provenance(
    *,
    records: list[dict[str, Any]],
    data_path: Path,
    substitute_data: bool,
) -> dict[str, Any]:
    sources = [
        record.get("source")
        for record in records
        if isinstance(record.get("source"), dict)
    ]
    first_source = sources[0] if sources else {}
    source_url = first_source.get("url") if isinstance(first_source, dict) else None
    source_kind = (
        first_source.get("kind")
        if isinstance(first_source, dict)
        else None
    )
    return {
        "schema_version": "2026-05-13.real-paper-dataset-provenance.v1",
        "data_kind": _data_kind(substitute_data),
        "substitute_data": substitute_data,
        "data_path": data_path.name,
        "sample_count": len(records),
        "source_kind": source_kind or "local_fixture",
        "source_url": source_url,
        "source_record_count": len(sources),
        "verbatim_excerpt": any(
            bool(source.get("verbatim_excerpt"))
            for source in sources
            if isinstance(source, dict)
        ),
        "official_scores_claimed": False,
        "limitations": _proof_limitations(substitute_data),
    }


def _allowed_patch_scope(substitute_data: bool) -> list[str]:
    data_scope = "fixture dataset records" if substitute_data else "public mini-slice records"
    return [data_scope, "routing heuristic configuration"]


def _handoff_gap(delta: float, substitute_data: bool) -> str:
    if delta <= 0:
        return "Ablation did not improve the local metric."
    if substitute_data:
        return (
            "Ablation improved the local substitute-data metric; next step is "
            "to validate on a less synthetic public slice."
        )
    return (
        "Ablation improved the local public mini-slice metric; next step is "
        "to validate on a larger public slice before broader claims."
    )


def _iteration_success_reason(substitute_data: bool) -> str:
    if substitute_data:
        return "The guarded routing-config patch improved the local substitute-data metric."
    return "The guarded routing-config patch improved the local public mini-slice metric."


def _iteration_next_action(substitute_data: bool) -> str:
    if substitute_data:
        return "Validate the same routing patch on a public dataset slice before any public claim."
    return (
        "Scale the same routing patch to a larger public slice or official debug harness "
        "before any stronger claim."
    )


def _proof_limitations(substitute_data: bool) -> list[str]:
    data_limitation = (
        "fixture-backed substitute data; not an official benchmark result"
        if substitute_data
        else "curated public mini-slice derived from arXiv metadata; not an official benchmark result"
    )
    return [
        data_limitation,
        "single bounded claim only; not a full paper reproduction",
        "local deterministic routing heuristic; no external judge or official scorer",
    ]


def _validate_pilot_dataset(data_path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    blockers: list[str] = []
    repair_plan: list[dict[str, Any]] = []
    try:
        records = _load_fixture_records(data_path)
    except json.JSONDecodeError:
        blockers.append("dataset_malformed_jsonl")
        repair_plan.append(
            {
                "kind": "fix_dataset_format",
                "path": str(data_path),
                "message": "Use newline-delimited JSON records for the pilot dataset.",
            }
        )
        return blockers, repair_plan
    except ValueError:
        blockers.append("dataset_empty")
        repair_plan.append(
            {
                "kind": "add_dataset_records",
                "path": str(data_path),
                "message": "Add at least one pilot JSONL record.",
            }
        )
        return blockers, repair_plan

    if not all(_record_has_required_fields(record) for record in records):
        blockers.append("dataset_missing_required_fields")
        repair_plan.append(
            {
                "kind": "fix_dataset_schema",
                "path": str(data_path),
                "message": (
                    "Each pilot record must include id, intent, and a non-empty "
                    "memories list whose items include intent and relevant."
                ),
            }
        )
    return blockers, repair_plan


def _record_has_required_fields(record: dict[str, Any]) -> bool:
    memories = record.get("memories")
    if not record.get("id") or not record.get("intent") or not isinstance(memories, list):
        return False
    if not memories:
        return False
    return all(
        isinstance(memory, dict)
        and "intent" in memory
        and "relevant" in memory
        for memory in memories
    )


def _select_baseline_memory(record: dict[str, Any]) -> dict[str, Any]:
    return dict(record["memories"][0])


def _select_intent_memory(record: dict[str, Any]) -> dict[str, Any]:
    intent = record["intent"]
    for memory in record["memories"]:
        if memory["intent"] == intent:
            return dict(memory)
    return _select_baseline_memory(record)


def _selection_accuracy(predictions: list[dict[str, Any]]) -> float:
    correct = sum(1 for prediction in predictions if prediction.get("relevant") is True)
    return round(correct / len(predictions), 6)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path, root: Path) -> str:
    resolved_path = path.expanduser().resolve()
    try:
        return resolved_path.relative_to(root.expanduser().resolve()).as_posix()
    except ValueError:
        return resolved_path.name


def _copy_sanitized_artifact(
    source_path: Path,
    archive_path: Path,
    *,
    redacted_prefix: Path,
) -> None:
    try:
        text = source_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        shutil.copy2(source_path, archive_path)
        return
    sanitized = text.replace(str(redacted_prefix), ".")
    archive_path.write_text(sanitized, encoding="utf-8")
