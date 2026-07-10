from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from html.parser import HTMLParser
import hashlib
import inspect
import importlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import types
from typing import Any, Callable
import urllib.error
import urllib.parse
import urllib.request

from lib.benchmarks.smol_worldcup import (
    FetchedResource,
    _build_model_messages,
    build_smol_worldcup_model_eval,
    build_smol_worldcup_prompt_leakage_audit,
    openai_compatible_chat_completion,
)
from lib.proposal_contract import validate_client_proposal
from lib.research_memory import (
    MemoryArtifactRef,
    MemoryEvidenceRef,
    ResearchMemoryCard,
)


FAILURE_RECORD_SCHEMA_VERSION = "2026-06-02.failure-record.v1"
PROPOSAL_OUTCOME_SCHEMA_VERSION = "2026-06-02.proposal-outcome.v1"
PROPOSAL_PATTERN_MEMORY_SCHEMA_VERSION = "2026-06-02.proposal-pattern-memory.v1"
PROPOSAL_PATTERN_RETRIEVAL_SCHEMA_VERSION = "2026-06-02.proposal-pattern-retrieval.v1"
FAILURE_DRIVEN_CONTEXT_SCHEMA_VERSION = "2026-06-02.failure-driven-context.v1"
FAILURE_DRIVEN_GENERATION_SCHEMA_VERSION = "2026-06-02.failure-driven-generation.v1"
FAILURE_DRIVEN_RANKING_SCHEMA_VERSION = "2026-06-02.failure-driven-ranking.v1"
FAILURE_DRIVEN_HANDOFF_SCHEMA_VERSION = "2026-06-02.failure-driven-handoff.v1"
FAILURE_DRIVEN_TEMPLATE_SCHEMA_VERSION = "2026-06-02.failure-driven-client-templates.v1"
FAILURE_DRIVEN_MEMORY_BRIDGE_SCHEMA_VERSION = "2026-06-02.failure-driven-memory-bridge.v1"
PROPOSAL_EFFECTIVENESS_SCHEMA_VERSION = "2026-06-02.proposal-effectiveness.v1"
CP_BENCH_EFFECTIVENESS_BUNDLE_SCHEMA_VERSION = "2026-06-02.cp-bench-proposal-effectiveness-bundle.v1"
FASTTEXT_EFFECTIVENESS_BUNDLE_SCHEMA_VERSION = "2026-06-02.fasttext-proposal-effectiveness-bundle.v1"
SMOL_WORLDCUP_EFFECTIVENESS_BUNDLE_SCHEMA_VERSION = (
    "2026-06-02.smol-worldcup-proposal-effectiveness-bundle.v1"
)
SMOL_WORLDCUP_RESULT_ANALYSIS_SCHEMA_VERSION = (
    "2026-06-27.smol-worldcup-result-analysis.v1"
)
SMOL_WORLDCUP_CONFIDENCE_VARIANCE_GATE_SCHEMA_VERSION = (
    "2026-06-27.smol-worldcup-confidence-variance-gate.v1"
)
SMOL_WORLDCUP_CACHED_CONFIDENCE_SCORING_GATE_SCHEMA_VERSION = (
    "2026-06-27.smol-worldcup-cached-confidence-scoring-gate.v1"
)
REAL_PAPER_EFFECTIVENESS_BUNDLE_SCHEMA_VERSION = (
    "2026-06-02.real-paper-proposal-effectiveness-bundle.v1"
)
CROSS_TASK_EFFECTIVENESS_SUMMARY_SCHEMA_VERSION = "2026-06-02.cross-task-proposal-effectiveness-summary.v1"
PROPOSAL_EFFECTIVENESS_CLAIM_AUDIT_SCHEMA_VERSION = (
    "2026-06-02.proposal-effectiveness-claim-audit.v1"
)
MIXED_SIGNAL_EFFECTIVENESS_AUDIT_SCHEMA_VERSION = (
    "2026-06-02.mixed-signal-proposal-effectiveness-audit.v1"
)
PROMPT_MODULE_SPEC_SCHEMA_VERSION = "2026-06-04.prompt-module-spec.v1"
SMOL_WORLDCUP_PROMOTION_GATE_SCHEMA_VERSION = (
    "2026-06-02.smol-worldcup-promotion-gate.v1"
)
SMOL_WORLDCUP_CANARY_FAILURE_SLICE_AUDIT_SCHEMA_VERSION = (
    "2026-06-02.smol-worldcup-canary-failure-slice-audit.v1"
)
SMOL_WORLDCUP_CANARY_CONTROL_ARM_HANDOFF_SCHEMA_VERSION = (
    "2026-06-02.smol-worldcup-canary-control-arm-handoff.v1"
)
SMOL_WORLDCUP_CANARY_CONTROL_ARM_EXECUTION_BUNDLE_SCHEMA_VERSION = (
    "2026-06-02.smol-worldcup-canary-control-arm-execution-bundle.v1"
)
SMOL_WORLDCUP_PROMOTION_GATE_REFRESH_SCHEMA_VERSION = (
    "2026-06-02.smol-worldcup-promotion-gate-refresh.v1"
)
SLICE_EVAL_MATRIX_SCHEMA_VERSION = "2026-06-04.slice-eval-matrix.v1"
SLICE_GATE_DECISION_SCHEMA_VERSION = "2026-06-04.slice-gate-decision.v1"
SLICE_VARIANCE_GATE_DECISION_SCHEMA_VERSION = (
    "2026-06-05.slice-variance-gate-decision.v1"
)
PAIRED_REPEAT_MANIFEST_SCHEMA_VERSION = "2026-06-05.paired-repeat-manifest.v1"
GATE_POLICY_INPUT_SCHEMA_VERSION = "2026-06-05.gate-policy-input.v1"
GATE_POLICY_DECISION_SCHEMA_VERSION = "2026-06-05.gate-policy-decision.v1"
GATE_POLICY_COMPOSITION_SCHEMA_VERSION = (
    "2026-06-05.gate-policy-composition.v1"
)
GATE_POLICY_GRAPH_SCHEMA_VERSION = "2026-06-05.gate-policy-graph.v1"
GATE_POLICY_GRAPH_DECISION_SCHEMA_VERSION = (
    "2026-06-05.gate-policy-graph-decision.v1"
)
SLICE_REPAIR_CONTEXT_SCHEMA_VERSION = "2026-06-04.slice-repair-context.v1"
SLICE_PATCH_CANDIDATE_SCHEMA_VERSION = "2026-06-04.slice-patch-candidate.v1"
SLICE_PATCH_CANDIDATES_SCHEMA_VERSION = "2026-06-04.slice-patch-candidates.v1"
SLICE_PATCH_MATERIALIZATION_SCHEMA_VERSION = (
    "2026-06-04.slice-patch-materialization.v1"
)
PROMPT_PROFILE_REGISTRATION_PLAN_SCHEMA_VERSION = (
    "2026-06-05.prompt-profile-registration-plan.v1"
)
PROMPT_PROFILE_REGISTRATION_SCHEMA_VERSION = (
    "2026-06-05.prompt-profile-registration.v1"
)
SLICE_PATCH_OUTCOME_SCHEMA_VERSION = "2026-06-05.slice-patch-outcome.v1"
SLICE_OPTIMIZER_SELECTION_SCHEMA_VERSION = (
    "2026-06-05.slice-optimizer-selection.v1"
)
OPTIMIZER_GATE_RUN_SCHEMA_VERSION = "2026-06-05.optimizer-gate-run.v1"
OPTIMIZER_RUNTIME_PROBE_SCHEMA_VERSION = "2026-06-05.optimizer-runtime-probe.v1"
OPTIMIZER_PACKAGE_RUNTIME_BENEFIT_AUDIT_SCHEMA_VERSION = (
    "2026-06-16.optimizer-package-runtime-benefit-audit.v1"
)
METHOD_PROPOSAL_GENERATION_TRACE_SCHEMA_VERSION = (
    "2026-06-16.method-proposal-generation-trace.v1"
)
METHOD_SEARCH_STUDY_SCHEMA_VERSION = "2026-06-19.method-search-study.v1"
METHOD_SEARCH_TRIAL_SCHEMA_VERSION = "2026-06-19.method-search-trial.v1"
METHOD_SEARCH_ASK_SCHEMA_VERSION = "2026-06-19.method-search-ask.v1"
METHOD_SEARCH_TELL_SCHEMA_VERSION = "2026-06-19.method-search-tell.v1"
GATE_FEEDBACK_MEMORY_SCHEMA_VERSION = "2026-06-19.gate-feedback-memory.v1"
GATE_FEEDBACK_MEMORY_STORE_SCHEMA_VERSION = (
    "2026-06-24.gate-feedback-memory-store.v1"
)
MULTI_OPTIMIZER_CANDIDATE_RACE_SCHEMA_VERSION = (
    "2026-06-25.multi-optimizer-candidate-race.v1"
)
MULTI_OPTIMIZER_CANDIDATE_RACE_RUN_SCHEMA_VERSION = (
    "2026-06-25.multi-optimizer-candidate-race-run.v1"
)
METHOD_SEARCH_TRAJECTORY_SCHEMA_VERSION = (
    "2026-06-27.method-search-trajectory.v1"
)
REAL_BENCHMARK_READINESS_RUN_SCHEMA_VERSION = (
    "2026-06-27.real-benchmark-readiness-run.v1"
)
DEFAULT_MULTI_OPTIMIZER_SOURCES: tuple[str, ...] = (
    "llm",
    "optuna",
    "textgrad",
    "dspy",
    "heuristic",
)
HEXAGON_GUIDED_LLM_SAMPLER_SCHEMA_VERSION = (
    "2026-06-19.hexagon-guided-llm-sampler.v1"
)
OPTUNA_SAMPLER_ADAPTER_SCHEMA_VERSION = (
    "2026-06-24.optuna-sampler-adapter.v1"
)
OPTUNA_STORAGE_ADAPTER_SCHEMA_VERSION = (
    "2026-06-24.optuna-storage-adapter.v1"
)
OPTUNA_DASHBOARD_EXPORT_SCHEMA_VERSION = (
    "2026-06-24.optuna-dashboard-export.v1"
)
OPTIMIZER_GATE_EXECUTION_PLAN_SCHEMA_VERSION = (
    "2026-06-05.optimizer-gate-execution-plan.v1"
)
OPTIMIZER_GATE_EXECUTION_PREFLIGHT_SCHEMA_VERSION = (
    "2026-06-05.optimizer-gate-execution-preflight.v1"
)
REGISTERED_PROFILE_EXECUTION_BUNDLE_SCHEMA_VERSION = (
    "2026-06-05.registered-profile-execution-bundle.v1"
)
REGISTERED_PROFILE_GATE_DECISION_SCHEMA_VERSION = (
    "2026-06-05.registered-profile-gate-decision.v1"
)
REGISTERED_PROFILE_EXECUTION_RUN_SCHEMA_VERSION = (
    "2026-06-05.registered-profile-execution-run.v1"
)
REGISTERED_PROFILE_CANARY_PREFLIGHT_SCHEMA_VERSION = (
    "2026-06-06.registered-profile-canary-preflight.v1"
)
REGISTERED_PROFILE_CANARY_EXECUTION_SCHEMA_VERSION = (
    "2026-06-06.registered-profile-canary-execution.v1"
)
REGISTERED_PROFILE_CANARY_RESULT_GATE_SCHEMA_VERSION = (
    "2026-06-06.registered-profile-canary-result-gate.v1"
)
REGISTERED_PROFILE_OUTCOME_SCHEDULE_SCHEMA_VERSION = (
    "2026-06-06.registered-profile-outcome-schedule.v1"
)
OPTIMIZER_GATE_SCHEDULER_PLAN_SCHEMA_VERSION = (
    "2026-06-07.optimizer-gate-scheduler-plan.v1"
)
OPTIMIZER_GATE_SCHEDULER_ACTION_SCHEMA_VERSION = (
    "2026-06-07.optimizer-gate-scheduler-action.v1"
)
OPTIMIZER_GATE_SCHEDULER_LOOP_SCHEMA_VERSION = (
    "2026-06-07.optimizer-gate-scheduler-loop.v1"
)
OPTIMIZER_GATE_SCHEDULER_HANDOFF_SCHEMA_VERSION = (
    "2026-06-07.optimizer-gate-scheduler-handoff.v1"
)
OPTIMIZER_GATE_CANARY_RUNNER_BUNDLE_SCHEMA_VERSION = (
    "2026-06-11.optimizer-gate-canary-runner-bundle.v1"
)
OPTIMIZER_GATE_CANARY_RUNNER_EXECUTION_SCHEMA_VERSION = (
    "2026-06-11.optimizer-gate-canary-runner-execution.v1"
)
OPTIMIZER_GATE_PROMOTION_REVIEW_QUEUE_SCHEMA_VERSION = (
    "2026-06-11.optimizer-gate-promotion-review-queue.v1"
)
OPTIMIZER_GATE_HUMAN_PROMOTION_APPROVAL_SCHEMA_VERSION = (
    "2026-06-15.optimizer-gate-human-promotion-approval.v1"
)
OPTIMIZER_GATE_LOCAL_PROMOTION_ACTION_SCHEMA_VERSION = (
    "2026-06-15.optimizer-gate-local-promotion-action.v1"
)
LOCAL_PROFILE_REGISTRY_SCHEMA_VERSION = "2026-06-16.local-profile-registry.v1"
OPTIMIZER_GATE_LOCAL_PROMOTION_ROLLBACK_SCHEMA_VERSION = (
    "2026-06-16.optimizer-gate-local-promotion-rollback.v1"
)
OPTIMIZER_GATE_EXTERNAL_SUBMISSION_ACTION_SCHEMA_VERSION = (
    "2026-06-16.optimizer-gate-external-submission-action.v1"
)
OPTIMIZER_GATE_OFFICIAL_SUBMISSION_SCHEMA_VERSION = (
    "2026-06-16.optimizer-gate-official-submission.v1"
)
OPTIMIZER_GATE_PUBLIC_RESULT_FETCH_SCHEMA_VERSION = (
    "2026-06-16.optimizer-gate-public-result-fetch.v1"
)
OPTIMIZER_GATE_PUBLIC_RESULT_VERIFIER_SCHEMA_VERSION = (
    "2026-06-16.optimizer-gate-public-result-verifier.v1"
)
OPTIMIZER_GATE_OFFICIAL_CLAIM_SCHEMA_VERSION = (
    "2026-06-16.optimizer-gate-official-claim.v1"
)
OPTIMIZER_GATE_EXECUTABLE_LOOP_SCHEMA_VERSION = (
    "2026-06-16.optimizer-gate-executable-loop.v1"
)
MODEL_RUNTIME_PREFLIGHT_SCHEMA_VERSION = "2026-06-06.model-runtime-preflight.v1"
OPTIMIZER_GATE_SYSTEM_SPEC_SCHEMA_VERSION = (
    "2026-06-05.optimizer-gate-system-spec.v1"
)
OPTIMIZER_GATE_PLUGIN_MANIFEST_SCHEMA_VERSION = (
    "2026-06-05.optimizer-gate-plugin-manifest.v1"
)
DEFAULT_TEXTGRAD_OPTIMIZER_MODEL = "qwen/qwen3-8b"
DEFAULT_TEXTGRAD_OPTIMIZER_BASE_URL = "http://127.0.0.1:1234/v1"
KNOWN_FAILURE_TYPES = {
    "metric_regression",
    "no_improvement",
    "canary_not_confirmed",
    "holdout_not_confirmed",
    "runtime_error",
    "timeout",
    "invalid_patch",
    "scope_too_broad",
    "leakage_risk",
    "cost_too_high",
}
DEFAULT_IDEA_HEXAGON_OPERATORS: tuple[dict[str, str], ...] = (
    {
        "operator_id": "extend_dimension",
        "label": "add a new dimension of X",
        "alias": "extend",
    },
    {
        "operator_id": "combine",
        "label": "combine X with a different idea or method",
        "alias": "fusion",
    },
    {
        "operator_id": "adapt",
        "label": "find a new application or context for X",
        "alias": "application",
    },
    {
        "operator_id": "substitute_tool",
        "label": "replace the tool, substrate, or runtime around X",
        "alias": "tool",
    },
    {
        "operator_id": "increment",
        "label": "make a bounded next-step improvement to X",
        "alias": "improve",
    },
    {
        "operator_id": "invert",
        "label": "reverse an assumption or search from the opposite direction",
        "alias": "reverse",
    },
)
_METHOD_SEARCH_REQUIRED_PROPOSAL_FIELDS: tuple[str, ...] = (
    "operator_id",
    "why_this_operator_applies",
    "hypothesis",
    "change_surface",
    "expected_effect",
    "risk",
    "cheapest_validation",
    "rollback_or_stop_condition",
)


@dataclass(frozen=True)
class OptimizerAdapter:
    name: str
    adapter_type: str
    runtime_status: str
    provider: str
    candidate_surface: str
    candidate_schema: str
    supports_execute_optimizer: bool
    executes_tool_default: bool
    executes_experiment: bool
    module_scope: str
    capabilities: tuple[str, ...]
    default_model: str | None = None
    default_base_url: str | None = None
    runtime_entrypoint: dict[str, Any] | None = None
    source: str = "builtin"
    plugin_id: str | None = None

    def to_manifest(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "source": self.source,
            "adapter_type": self.adapter_type,
            "runtime_status": self.runtime_status,
            "provider": self.provider,
            "candidate_surface": self.candidate_surface,
            "candidate_schema": self.candidate_schema,
            "supports_execute_optimizer": self.supports_execute_optimizer,
            "executes_tool_default": self.executes_tool_default,
            "executes_experiment": self.executes_experiment,
            "module_scope": self.module_scope,
            "capabilities": list(self.capabilities),
        }
        if self.default_model:
            payload["default_model"] = self.default_model
        if self.default_base_url:
            payload["default_base_url"] = self.default_base_url
        if self.runtime_entrypoint:
            payload["runtime_entrypoint"] = dict(self.runtime_entrypoint)
        if self.plugin_id:
            payload["plugin_id"] = self.plugin_id
        return payload

    def runtime(
        self,
        *,
        execute_optimizer: bool,
        optimizer_model: str | None,
        optimizer_base_url: str | None,
        optimizer_timeout_seconds: int,
        optimizer_temperature: float,
        optimizer_max_tokens: int,
    ) -> dict[str, Any]:
        return _slice_optimizer_runtime(
            optimizer=self.name,
            execute_optimizer=execute_optimizer,
            optimizer_model=optimizer_model,
            optimizer_base_url=optimizer_base_url,
            optimizer_timeout_seconds=optimizer_timeout_seconds,
            optimizer_temperature=optimizer_temperature,
            optimizer_max_tokens=optimizer_max_tokens,
            supports_execute_optimizer=self.supports_execute_optimizer,
            default_model=self.default_model,
            default_base_url=self.default_base_url,
            runtime_entrypoint=self.runtime_entrypoint,
        )


@dataclass(frozen=True)
class GatePolicy:
    policy_id: str
    function: str
    decision_schema: str
    required_inputs: tuple[str, ...]
    blocks_on: tuple[str, ...]
    decision_outputs: tuple[str, ...]
    canary_allowed_when: str
    executes_experiment: bool
    underlying_decision_schema: str | None = None
    input_schema: str | None = None
    default_min_repeats: int | None = None
    source: str = "builtin"
    plugin_id: str | None = None

    def to_manifest(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "policy_id": self.policy_id,
            "source": self.source,
            "function": self.function,
            "decision_schema": self.decision_schema,
            "required_inputs": list(self.required_inputs),
            "blocks_on": list(self.blocks_on),
            "decision_outputs": list(self.decision_outputs),
            "canary_allowed_when": self.canary_allowed_when,
            "executes_experiment": self.executes_experiment,
        }
        if self.underlying_decision_schema:
            payload["underlying_decision_schema"] = self.underlying_decision_schema
            payload["schema_version"] = self.underlying_decision_schema
        else:
            payload["schema_version"] = self.decision_schema
        if self.input_schema:
            payload["input_schema"] = self.input_schema
        if self.default_min_repeats is not None:
            payload["default_min_repeats"] = self.default_min_repeats
        if self.plugin_id:
            payload["plugin_id"] = self.plugin_id
        return payload

    def evaluate(
        self,
        *,
        gate_input: dict[str, Any],
        gate_input_ref: str = "inline",
    ) -> dict[str, Any]:
        if self.policy_id == "slice-dev-hard-gate":
            decision = evaluate_slice_gate(
                slice_matrix=_slice_dev_gate_input_without_quality_blockers(gate_input)
            )
        elif self.policy_id in {
            "min-improvement-gate",
            "min-quality-gate",
            "target-smoke-success-gate",
        }:
            decision = _evaluate_quality_gate_policy(
                policy_id=self.policy_id,
                gate_input=gate_input,
            )
        else:
            raise ValueError(
                f"gate policy {self.policy_id} cannot evaluate a single gate input"
            )
        return _gate_policy_decision_payload(
            policy=self,
            decision=decision,
            gate_input_ref=gate_input_ref,
        )


@dataclass(frozen=True)
class BenchmarkAdapter:
    benchmark_id: str
    task_family: str
    runner_function: str
    supported_splits: tuple[str, ...]
    required_artifacts: tuple[str, ...]
    planned_execution_stages: tuple[str, ...]
    gate_outputs: tuple[str, ...]
    executes_experiment: bool
    source: str = "builtin"

    def to_manifest(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "source": self.source,
            "task_family": self.task_family,
            "runner_function": self.runner_function,
            "supported_splits": list(self.supported_splits),
            "required_artifacts": list(self.required_artifacts),
            "planned_execution_stages": list(self.planned_execution_stages),
            "gate_outputs": list(self.gate_outputs),
            "executes_experiment": self.executes_experiment,
        }


def resolve_optimizer_adapter(
    name: str,
    *,
    plugin_manifests: list[dict[str, Any] | str | Path] | None = None,
) -> OptimizerAdapter:
    adapter_name = _string_value(name) or "manual-template"
    registry = {
        item.name: item
        for item in _optimizer_adapter_registry_objects(plugin_manifests=plugin_manifests)
    }
    adapter = registry.get(adapter_name)
    if adapter is None:
        raise ValueError(f"unsupported optimizer adapter: {adapter_name}")
    return adapter


def resolve_gate_policy(
    policy_id: str,
    *,
    plugin_manifests: list[dict[str, Any] | str | Path] | None = None,
) -> GatePolicy:
    normalized_policy_id = _string_value(policy_id) or "slice-dev-hard-gate"
    registry = {
        item.policy_id: item
        for item in _gate_policy_registry_objects(plugin_manifests=plugin_manifests)
    }
    policy = registry.get(normalized_policy_id)
    if policy is None:
        raise ValueError(f"unsupported gate policy: {normalized_policy_id}")
    return policy


def resolve_benchmark_adapter(benchmark_id: str) -> BenchmarkAdapter:
    normalized_benchmark_id = _string_value(benchmark_id) or "smol_worldcup"
    registry = {
        item.benchmark_id: item
        for item in _benchmark_adapter_registry_objects()
    }
    adapter = registry.get(normalized_benchmark_id)
    if adapter is None:
        raise ValueError(f"unsupported benchmark adapter: {normalized_benchmark_id}")
    return adapter


def load_optimizer_gate_plugin_manifest(
    plugin_manifest: dict[str, Any] | str | Path,
    *,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Load a non-executing optimizer/gate plugin manifest."""
    manifest_payload, manifest_path = _load_object(plugin_manifest)
    payload = _normalize_optimizer_gate_plugin_manifest(
        manifest_payload,
        manifest_ref=str(manifest_path) if manifest_path is not None else "inline",
    )
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def extract_failure_records(
    source_artifact: dict[str, Any] | str | Path,
    *,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    payload, source_path = _load_object(source_artifact)
    records = _extract_failure_records_from_payload(payload, source_path=source_path)
    result = {
        "status": "completed",
        "record_count": len(records),
        "records": records,
        "executes_tool": False,
        "official_scores_claimed": False,
        "claim_boundary": "local failure extraction only; not public proof",
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        _write_jsonl(records, output)
        result["output_path"] = str(output)
    return result


def record_proposal_outcome(
    *,
    proposal: dict[str, Any] | str | Path,
    evaluation: dict[str, Any] | str | Path,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    proposal_payload, proposal_path = _load_object(proposal)
    evaluation_payload, evaluation_path = _load_object(evaluation)
    proposal_id = _string_value(proposal_payload.get("proposal_id")) or "unknown-proposal"
    metric_delta = _metric_delta_map(evaluation_payload)
    rollback_reasons = _string_list(evaluation_payload.get("rollback_reasons"))
    failure_labels = _outcome_failure_labels(
        evaluation_payload,
        metric_delta,
        evaluation_split=(
            _evaluation_split_from_evaluation(evaluation_payload)
            or _proposal_evaluation_split(proposal_payload)
        ),
    )
    accepted = _accepted(metric_delta, rollback_reasons)
    regression = any(value < 0 for value in metric_delta.values())
    artifact_refs = []
    if proposal_path is not None:
        artifact_refs.append({"name": "proposal", "path": str(proposal_path)})
    if evaluation_path is not None:
        artifact_refs.append({"name": "evaluation", "path": str(evaluation_path)})

    payload = {
        "status": "completed",
        "schema_version": PROPOSAL_OUTCOME_SCHEMA_VERSION,
        "outcome_id": f"{proposal_id}-outcome",
        "proposal_id": proposal_id,
        "proposal_type": _string_value(proposal_payload.get("proposal_type")) or "failure_fix",
        "based_on_failures": _string_list(proposal_payload.get("based_on_failures")),
        "change_surface": _string_value(proposal_payload.get("change_surface")),
        "target_scope": _string_value(proposal_payload.get("target_scope")),
        "executed": True,
        "accepted": accepted,
        "metric_delta": metric_delta,
        "regression": regression,
        "rollback_triggered": bool(rollback_reasons),
        "rollback_reasons": rollback_reasons,
        "failure_labels": failure_labels,
        "outcome_summary": _outcome_summary(
            proposal_id=proposal_id,
            accepted=accepted,
            regression=regression,
            rollback_reasons=rollback_reasons,
            metric_delta=metric_delta,
        ),
        "artifact_refs": artifact_refs + _artifact_refs_from_evaluation(evaluation_payload),
        "claim_boundary": "local proposal outcome only; not public proof",
        "official_scores_claimed": False,
        "executes_tool": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        payload["output_path"] = str(output)
    return payload


def build_proposal_pattern_memory(
    outcomes: list[dict[str, Any]] | str | Path,
    *,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    outcome_items = _load_outcome_items(outcomes)
    groups: dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]] = {}
    for item in outcome_items:
        proposal_type = _string_value(item.get("proposal_type")) or "failure_fix"
        failure_types = _pattern_failure_types(item)
        groups.setdefault((proposal_type, failure_types), []).append(item)

    patterns = [
        _pattern_from_group(proposal_type=key[0], failure_types=list(key[1]), items=items)
        for key, items in sorted(groups.items(), key=lambda entry: (entry[0][0], entry[0][1]))
    ]
    payload = {
        "status": "completed",
        "pattern_count": len(patterns),
        "patterns": patterns,
        "executes_tool": False,
        "official_scores_claimed": False,
        "claim_boundary": "local proposal pattern memory only; not public proof",
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        _write_jsonl(patterns, output)
        payload["output_path"] = str(output)
    return payload


def _pattern_failure_types(item: dict[str, Any]) -> tuple[str, ...]:
    observed = [
        _normalize_failure_type(label)
        for label in _string_list(item.get("failure_labels"))
        if _normalize_failure_type(label)
    ]
    if observed:
        return tuple(sorted(set(observed)))
    source_failures = [
        _normalize_failure_type(label)
        for label in _string_list(item.get("based_on_failures"))
        if _normalize_failure_type(label)
    ]
    if source_failures:
        return tuple(sorted(set(source_failures)))
    return ("unspecified",)


def retrieve_proposal_patterns(
    *,
    pattern_memory: list[dict[str, Any]] | str | Path,
    failure_type: str | None = None,
    proposal_type: str | None = None,
    task_family: str | None = None,
    metric_name: str | None = None,
    limit: int = 10,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    patterns = _load_pattern_memory(pattern_memory)
    query = {
        "failure_type": failure_type,
        "proposal_type": proposal_type,
        "task_family": task_family,
        "metric_name": metric_name,
    }
    matches = []
    for pattern in patterns:
        scored = _pattern_match(pattern=pattern, query=query)
        if scored is not None:
            matches.append(scored)
    matches.sort(
        key=lambda item: (
            -float(item["score"]),
            -float(item["pattern"].get("historical_success_rate", 0.0)),
            str(item["pattern"].get("pattern_id", "")),
        )
    )
    payload = {
        "status": "completed",
        "schema_version": PROPOSAL_PATTERN_RETRIEVAL_SCHEMA_VERSION,
        "query": {key: value for key, value in query.items() if value},
        "match_count": len(matches),
        "matches": matches[: max(1, limit)],
        "claim_boundary": "local proposal pattern retrieval only; not public proof",
        "executes_tool": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def build_prompt_module_spec(
    *,
    profile_id: str,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build the default Smol WorldCup prompt-module specification."""
    if not profile_id:
        raise ValueError("profile_id is required")
    payload = {
        "status": "completed",
        "schema_version": PROMPT_MODULE_SPEC_SCHEMA_VERSION,
        "profile_id": profile_id,
        "task_family": "smol_worldcup_prompt_routing",
        "modules": _default_smol_prompt_modules(),
        "module_routing": _default_smol_module_routing(),
        "protected_global_contracts": [
            "official_scores_claimed must remain false",
            "do not introduce leaderboard or hidden-test claims",
            "keep one module and one section per slice patch",
        ],
        "claim_boundary": "local prompt module specification only",
        "executes_tool": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def build_slice_eval_matrix(
    *,
    baseline_report: dict[str, Any] | str | Path,
    candidate_report: dict[str, Any] | str | Path,
    candidate_evaluation: dict[str, Any] | str | Path | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Compare score-breakdown slices between baseline and candidate reports."""
    baseline_payload, baseline_path = _load_object(baseline_report)
    candidate_payload, candidate_path = _load_object(candidate_report)
    evaluation_payload: dict[str, Any] = {}
    evaluation_path: Path | None = None
    if candidate_evaluation is not None:
        evaluation_payload, evaluation_path = _load_object(candidate_evaluation)
    split = (
        _slice_report_split(evaluation_payload)
        or _slice_report_split(candidate_payload)
        or _slice_report_split(baseline_payload)
        or "unknown"
    )
    baseline_breakdown = _slice_score_breakdown(baseline_payload)
    candidate_breakdown = _slice_score_breakdown(candidate_payload)
    slices = _slice_rows_from_breakdowns(
        baseline_breakdown=baseline_breakdown,
        candidate_breakdown=candidate_breakdown,
        split=split,
    )
    metric_delta = _slice_metric_delta(
        baseline_payload=baseline_payload,
        candidate_payload=candidate_payload,
        evaluation_payload=evaluation_payload,
    )
    hard_blockers = [
        f"{metric_name}_delta_lt_0"
        for metric_name, delta in sorted(metric_delta.items())
        if delta < 0
    ]
    if any(item["gate"] == "blocked" for item in slices):
        hard_blockers.append("slice_regression")
    payload = {
        "status": "completed",
        "schema_version": SLICE_EVAL_MATRIX_SCHEMA_VERSION,
        "task_family": _slice_task_family(
            baseline_payload,
            candidate_payload,
            evaluation_payload,
        ),
        "baseline_ref": str(baseline_path) if baseline_path is not None else "inline",
        "candidate_ref": str(candidate_path) if candidate_path is not None else "inline",
        "candidate_evaluation_ref": (
            str(evaluation_path) if evaluation_path is not None else None
        ),
        "split": split,
        "metric_delta": metric_delta,
        "slices": slices,
        "hard_blockers": sorted(set(hard_blockers)),
        "claim_boundary": "local slice regression matrix only",
        "executes_tool": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def build_gate_policy_input(
    *,
    metric_table: list[dict[str, Any]] | dict[str, Any] | str | Path,
    slice_table: list[dict[str, Any]] | dict[str, Any] | str | Path,
    policy_id: str = "slice-dev-hard-gate",
    task_family: str = "generic_gate_policy",
    split: str = "dev",
    quality_constraints: dict[str, Any] | str | Path | None = None,
    execution_quality: dict[str, Any] | str | Path | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a benchmark-agnostic gate input from metric and slice tables."""
    metric_rows, metric_path = _load_table_rows(metric_table)
    slice_rows, slice_path = _load_table_rows(slice_table)
    normalized_split = _string_value(split) or "unknown"
    metric_delta = _metric_delta_from_table_rows(metric_rows)
    slices = _slice_rows_from_table_rows(
        rows=slice_rows,
        split=normalized_split,
    )
    quality_constraints_payload = _load_optional_object_payload(quality_constraints)
    execution_quality_payload = _load_optional_object_payload(execution_quality)
    hard_blockers = [
        f"{metric_name}_delta_lt_0"
        for metric_name, delta in sorted(metric_delta.items())
        if delta < 0
    ]
    if any(item.get("gate") == "blocked" for item in slices):
        hard_blockers.append("slice_regression")
    quality_checks = _gate_quality_checks(
        metric_delta=metric_delta,
        slices=slices,
        quality_constraints=quality_constraints_payload,
        execution_quality=execution_quality_payload,
    )
    hard_blockers.extend(_string_list(quality_checks.get("hard_blockers")))
    payload = {
        "status": "completed",
        "schema_version": GATE_POLICY_INPUT_SCHEMA_VERSION,
        "policy_id": policy_id,
        "task_family": task_family,
        "split": normalized_split,
        "metric_delta": metric_delta,
        "slices": slices,
        "quality_constraints": quality_checks["constraints"],
        "quality_checks": quality_checks,
        "hard_blockers": sorted(set(hard_blockers)),
        "source_tables": {
            "metric_table_ref": str(metric_path) if metric_path is not None else "inline",
            "slice_table_ref": str(slice_path) if slice_path is not None else "inline",
        },
        "claim_boundary": "benchmark-agnostic gate policy input only",
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    if execution_quality_payload is not None:
        payload["execution_quality"] = execution_quality_payload
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def evaluate_gate_policy(
    *,
    gate_input: dict[str, Any] | str | Path,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Evaluate a benchmark-agnostic gate policy input."""
    gate_payload, gate_input_path = _load_object(gate_input)
    policy_id = _string_value(gate_payload.get("policy_id")) or "slice-dev-hard-gate"
    policy = resolve_gate_policy(policy_id)
    payload = policy.evaluate(
        gate_input=gate_payload,
        gate_input_ref=str(gate_input_path) if gate_input_path is not None else "inline",
    )
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def build_gate_policy_composition(
    *,
    decisions: list[dict[str, Any] | str | Path],
    composition_id: str = "optimizer-gate-hard-composition",
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Compose gate policy decisions into one hard-gate result."""
    if not decisions:
        raise ValueError("decisions is required")
    loaded: list[dict[str, Any]] = []
    decision_refs: list[str] = []
    for item in decisions:
        decision, decision_path = _load_object(item)
        loaded.append(decision)
        decision_refs.append(str(decision_path) if decision_path is not None else "inline")

    policy_results = [
        _gate_policy_composition_result(decision=decision, decision_ref=decision_ref)
        for decision, decision_ref in zip(loaded, decision_refs)
    ]
    blocking_policies = [
        _string_value(result.get("policy_id")) or "unknown-policy"
        for result in policy_results
        if result.get("blocking") is True
    ]
    hard_blockers = _dedupe_strings([
        blocker
        for decision in loaded
        for blocker in _string_list(decision.get("hard_blockers"))
    ])
    stable_repair_targets = [
        target
        for decision in loaded
        for target in _dict_list(decision.get("stable_repair_targets"))
    ]
    statuses = [
        _string_value(result.get("status")) or "unknown"
        for result in policy_results
    ]
    if "needs_paired_repeat" in statuses:
        status = "needs_paired_repeat"
    elif blocking_policies:
        status = "blocked"
    elif "variance_review_required" in statuses:
        status = "review_required"
    elif all(bool(result.get("canary_allowed")) for result in policy_results):
        status = "passed_for_canary"
    else:
        status = "blocked"
    canary_allowed = status == "passed_for_canary"
    payload = {
        "status": status,
        "schema_version": GATE_POLICY_COMPOSITION_SCHEMA_VERSION,
        "composition_id": _string_value(composition_id) or "optimizer-gate-hard-composition",
        "decision_refs": decision_refs,
        "policy_results": policy_results,
        "blocking_policies": blocking_policies,
        "hard_blockers": hard_blockers,
        "stable_repair_targets": stable_repair_targets[:5],
        "gate": {
            "decision_count": len(policy_results),
            "passed_decision_count": sum(
                1 for result in policy_results if result.get("canary_allowed") is True
            ),
            "canary_allowed": canary_allowed,
            "promotion_ready": False,
        },
        "recommended_next_action": _gate_policy_composition_next_action(status),
        "claim_boundary": "local gate policy composition only; not an executed gate run",
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def build_gate_policy_graph(
    *,
    graph_id: str = "optimizer-gate-policy-graph",
    required_policies: list[str] | None = None,
    optional_policies: list[str] | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a configurable non-executing gate policy graph."""
    hard_gate_policy_ids = _dedupe_strings(required_policies or [])
    optional_policy_ids = [
        policy_id
        for policy_id in _dedupe_strings(optional_policies or [])
        if policy_id not in hard_gate_policy_ids
    ]
    if not hard_gate_policy_ids:
        hard_gate_policy_ids = [
            *_registered_profile_required_gate_policy_ids(),
            "paired-repeat-variance-gate",
        ]
    nodes = [
        _gate_policy_graph_node(policy_id=policy_id, required=True)
        for policy_id in hard_gate_policy_ids
    ] + [
        _gate_policy_graph_node(policy_id=policy_id, required=False)
        for policy_id in optional_policy_ids
    ]
    payload = {
        "status": "completed",
        "schema_version": GATE_POLICY_GRAPH_SCHEMA_VERSION,
        "graph_id": _string_value(graph_id) or "optimizer-gate-policy-graph",
        "composition_mode": "all_required_must_pass",
        "nodes": nodes,
        "hard_gate_policy_ids": hard_gate_policy_ids,
        "optional_policy_ids": optional_policy_ids,
        "claim_boundary": "non-executing gate policy graph only",
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def evaluate_gate_policy_graph(
    *,
    policy_graph: dict[str, Any] | str | Path,
    decisions: list[dict[str, Any] | str | Path],
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Evaluate gate decisions through a configurable hard/optional policy graph."""
    graph_payload, graph_path = _load_object(policy_graph)
    if not decisions:
        raise ValueError("decisions is required")
    hard_gate_policy_ids = _string_list(graph_payload.get("hard_gate_policy_ids"))
    optional_policy_ids = _string_list(graph_payload.get("optional_policy_ids"))
    if not hard_gate_policy_ids:
        raise ValueError("policy_graph hard_gate_policy_ids is required")

    loaded: list[dict[str, Any]] = []
    decision_refs: list[str] = []
    for item in decisions:
        decision, decision_path = _load_object(item)
        loaded.append(decision)
        decision_refs.append(str(decision_path) if decision_path is not None else "inline")

    policy_results = []
    blocking_policies: list[str] = []
    advisory_blocking_policies: list[str] = []
    hard_blockers: list[str] = []
    advisory_blockers: list[str] = []
    missing_required_policies = [
        policy_id
        for policy_id in hard_gate_policy_ids
        if policy_id not in {_gate_policy_id_from_decision(decision) for decision in loaded}
    ]
    for decision, decision_ref in zip(loaded, decision_refs):
        result = _gate_policy_composition_result(
            decision=decision,
            decision_ref=decision_ref,
        )
        policy_id = _string_value(result.get("policy_id")) or "unknown-policy"
        node_role = (
            "required"
            if policy_id in hard_gate_policy_ids
            else "optional"
            if policy_id in optional_policy_ids
            else "unmapped"
        )
        result["node_role"] = node_role
        policy_results.append(result)
        if result.get("blocking") is not True:
            continue
        blockers = _string_list(result.get("hard_blockers"))
        if node_role == "required":
            blocking_policies.append(policy_id)
            hard_blockers.extend(blockers)
        else:
            advisory_blocking_policies.append(policy_id)
            advisory_blockers.extend(blockers)

    if missing_required_policies:
        status = "missing_required_decision"
        hard_blockers.extend(
            [f"missing_required_policy:{policy_id}" for policy_id in missing_required_policies]
        )
    elif blocking_policies:
        status = "blocked"
    elif advisory_blocking_policies:
        status = "passed_with_advisory_blockers"
    else:
        status = "passed_for_canary"
    canary_allowed = status == "passed_for_canary"
    payload = {
        "status": status,
        "schema_version": GATE_POLICY_GRAPH_DECISION_SCHEMA_VERSION,
        "graph_id": _string_value(graph_payload.get("graph_id")) or "unknown-graph",
        "policy_graph_ref": str(graph_path) if graph_path is not None else "inline",
        "policy_results": policy_results,
        "blocking_policies": _dedupe_strings(blocking_policies),
        "advisory_blocking_policies": _dedupe_strings(advisory_blocking_policies),
        "missing_required_policies": missing_required_policies,
        "hard_blockers": _dedupe_strings(hard_blockers),
        "advisory_blockers": _dedupe_strings(advisory_blockers),
        "gate": {
            "decision_count": len(policy_results),
            "required_policy_count": len(hard_gate_policy_ids),
            "optional_policy_count": len(optional_policy_ids),
            "canary_allowed": canary_allowed,
            "promotion_ready": False,
        },
        "recommended_next_action": _gate_policy_graph_next_action(status),
        "claim_boundary": "local gate policy graph decision only; not an executed gate run",
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def evaluate_slice_gate(
    *,
    slice_matrix: dict[str, Any] | str | Path | None = None,
    baseline_report: dict[str, Any] | str | Path | None = None,
    candidate_report: dict[str, Any] | str | Path | None = None,
    candidate_evaluation: dict[str, Any] | str | Path | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Evaluate whether a slice-local patch may proceed to the next split."""
    if slice_matrix is None:
        if baseline_report is None or candidate_report is None:
            raise ValueError("slice_matrix or baseline_report and candidate_report are required")
        matrix = build_slice_eval_matrix(
            baseline_report=baseline_report,
            candidate_report=candidate_report,
            candidate_evaluation=candidate_evaluation,
        )
    else:
        matrix, _ = _load_object(slice_matrix)
    split = _string_value(matrix.get("split")) or "unknown"
    metric_delta = {
        str(key): float(value)
        for key, value in (matrix.get("metric_delta") or {}).items()
        if _is_plain_number(value)
    }
    hard_blockers = set(_string_list(matrix.get("hard_blockers")))
    hard_blockers.update(
        f"{metric_name}_delta_lt_0"
        for metric_name, delta in metric_delta.items()
        if delta < 0
    )
    regressions = _slice_regression_rows(matrix.get("slices"))
    top_slices = regressions
    if not top_slices and hard_blockers:
        top_slices = _slice_candidate_watch_rows(matrix.get("slices"))
    if regressions:
        hard_blockers.add("slice_regression")
    dev_passed = split != "dev" or not hard_blockers
    canary_allowed = dev_passed and split == "dev"
    payload = {
        "status": "passed_for_canary" if canary_allowed else "blocked",
        "schema_version": SLICE_GATE_DECISION_SCHEMA_VERSION,
        "split": split,
        "metric_delta": {key: round(value, 6) for key, value in metric_delta.items()},
        "gate": {
            "dev_passed": dev_passed,
            "canary_allowed": canary_allowed,
            "promotion_ready": False,
        },
        "hard_blockers": sorted(hard_blockers),
        "top_regression_slices": top_slices[:5],
        "slice_regressions": regressions,
        "quality_checks": (
            matrix.get("quality_checks")
            if isinstance(matrix.get("quality_checks"), dict)
            else {}
        ),
        "claim_boundary": "local slice gate decision only",
        "executes_tool": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def build_paired_repeat_manifest(
    *,
    slice_matrices: list[dict[str, Any] | str | Path],
    task_family: str = "generic_paired_repeat",
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Bundle paired repeat slice matrices into an auditable gate input."""
    if not slice_matrices:
        raise ValueError("slice_matrices is required")
    loaded: list[dict[str, Any]] = []
    matrix_refs: list[str] = []
    for item in slice_matrices:
        matrix, matrix_path = _load_object(item)
        loaded.append(matrix)
        matrix_refs.append(str(matrix_path) if matrix_path is not None else "inline")

    split_values = [_string_value(matrix.get("split")) or "unknown" for matrix in loaded]
    baseline_refs = [
        _string_value(matrix.get("baseline_ref")) or "unknown"
        for matrix in loaded
    ]
    candidate_refs = [
        _string_value(matrix.get("candidate_ref")) or "unknown"
        for matrix in loaded
    ]
    split = split_values[0] if split_values else "unknown"
    baseline_ref = baseline_refs[0] if baseline_refs else "unknown"
    candidate_ref = candidate_refs[0] if candidate_refs else "unknown"
    same_split = all(value == split for value in split_values)
    same_baseline_ref = all(value == baseline_ref for value in baseline_refs)
    same_candidate_ref = all(value == candidate_ref for value in candidate_refs)
    hard_blockers = []
    if not same_split:
        hard_blockers.append("mixed_split")
    if not same_baseline_ref:
        hard_blockers.append("mixed_baseline_ref")
    if not same_candidate_ref:
        hard_blockers.append("mixed_candidate_ref")

    repeats = [
        {
            "repeat_id": f"repeat-{index}",
            "matrix_ref": matrix_ref,
            "split": _string_value(matrix.get("split")) or "unknown",
            "baseline_ref": _string_value(matrix.get("baseline_ref")) or "unknown",
            "candidate_ref": _string_value(matrix.get("candidate_ref")) or "unknown",
            "metric_delta": {
                str(key): round(float(value), 6)
                for key, value in (matrix.get("metric_delta") or {}).items()
                if _is_plain_number(value)
            },
            "slice_count": len(matrix.get("slices") or [])
            if isinstance(matrix.get("slices"), list)
            else 0,
        }
        for index, (matrix, matrix_ref) in enumerate(zip(loaded, matrix_refs), start=1)
    ]
    payload = {
        "status": "completed" if not hard_blockers else "needs_review",
        "schema_version": PAIRED_REPEAT_MANIFEST_SCHEMA_VERSION,
        "task_family": _string_value(task_family) or "generic_paired_repeat",
        "split": split,
        "baseline_ref": baseline_ref,
        "candidate_ref": candidate_ref,
        "repeat_count": len(loaded),
        "matrix_refs": matrix_refs,
        "repeats": repeats,
        "slice_matrices": loaded,
        "consistency": {
            "same_split": same_split,
            "same_baseline_ref": same_baseline_ref,
            "same_candidate_ref": same_candidate_ref,
        },
        "hard_blockers": hard_blockers,
        "claim_boundary": "local paired-repeat manifest only",
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def evaluate_slice_variance_gate(
    *,
    slice_matrices: list[dict[str, Any] | str | Path] | None = None,
    paired_repeat_manifest: dict[str, Any] | str | Path | None = None,
    min_repeats: int = 2,
    regression_delta_threshold: float = -1.0,
    stable_support_ratio: float = 1.0,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Classify slice regressions across paired repeats without executing runs."""
    if not slice_matrices and paired_repeat_manifest is None:
        raise ValueError("slice_matrices or paired_repeat_manifest is required")
    min_repeats = max(1, int(min_repeats))
    stable_support_ratio = min(1.0, max(0.0, float(stable_support_ratio)))
    regression_delta_threshold = -abs(float(regression_delta_threshold))
    manifest_ref: str | None = None
    manifest_blockers: list[str] = []
    if paired_repeat_manifest is not None:
        manifest, manifest_path = _load_object(paired_repeat_manifest)
        loaded, matrix_refs = _slice_matrices_from_paired_repeat_manifest(manifest)
        manifest_ref = str(manifest_path) if manifest_path is not None else "inline"
        manifest_blockers = _string_list(manifest.get("hard_blockers"))
    else:
        loaded = []
        matrix_refs = []
        for item in slice_matrices or []:
            matrix, matrix_path = _load_object(item)
            loaded.append(matrix)
            matrix_refs.append(str(matrix_path) if matrix_path is not None else "inline")

    split_values = [
        _string_value(matrix.get("split")) or "unknown"
        for matrix in loaded
    ]
    split = split_values[0] if split_values else "unknown"
    repeat_count = len(loaded)
    hard_blockers: set[str] = set()
    hard_blockers.update(manifest_blockers)
    if any(value != split for value in split_values):
        hard_blockers.add("mixed_split")
    if repeat_count < min_repeats:
        hard_blockers.add("insufficient_repeats")

    slice_stability = _slice_variance_rows(
        matrices=loaded,
        repeat_count=repeat_count,
        min_repeats=min_repeats,
        regression_delta_threshold=regression_delta_threshold,
        stable_support_ratio=stable_support_ratio,
    )
    stable_repair_targets = [
        row
        for row in slice_stability
        if row.get("classification") == "stable_regression"
    ]
    variance_suspects = [
        row
        for row in slice_stability
        if row.get("classification") == "variance_suspect"
    ]
    metric_stability = _metric_variance_rows(
        matrices=loaded,
        repeat_count=repeat_count,
        min_repeats=min_repeats,
        regression_delta_threshold=regression_delta_threshold,
        stable_support_ratio=stable_support_ratio,
    )
    stable_metric_regressions = [
        row
        for row in metric_stability
        if row.get("classification") == "stable_regression"
    ]
    if stable_repair_targets:
        hard_blockers.add("stable_slice_regression")
    if stable_metric_regressions:
        hard_blockers.add("stable_metric_regression")
    if variance_suspects and repeat_count >= min_repeats:
        hard_blockers.add("unstable_slice_regression")

    if repeat_count < min_repeats:
        status = "needs_paired_repeat"
    elif stable_repair_targets or stable_metric_regressions:
        status = "blocked"
    elif variance_suspects:
        status = "variance_review_required"
    elif hard_blockers:
        status = "blocked"
    else:
        status = "passed_for_canary"
    canary_allowed = status == "passed_for_canary" and split == "dev"
    payload = {
        "status": status,
        "schema_version": SLICE_VARIANCE_GATE_DECISION_SCHEMA_VERSION,
        "split": split,
        "matrix_refs": matrix_refs,
        "paired_repeat_manifest_ref": manifest_ref,
        "gate": {
            "repeat_count": repeat_count,
            "min_repeats": min_repeats,
            "paired_repeat_required": repeat_count < min_repeats,
            "regression_delta_threshold": round(regression_delta_threshold, 6),
            "stable_support_ratio": stable_support_ratio,
            "dev_passed": canary_allowed,
            "canary_allowed": canary_allowed,
            "promotion_ready": False,
        },
        "hard_blockers": sorted(hard_blockers),
        "metric_stability": metric_stability,
        "slice_stability": slice_stability,
        "stable_repair_targets": stable_repair_targets[:5],
        "recommended_next_actions": _slice_variance_next_actions(
            status=status,
            stable_targets=stable_repair_targets,
        ),
        "claim_boundary": "local paired-repeat variance gate only",
        "executes_tool": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def build_slice_repair_context(
    *,
    slice_matrix: dict[str, Any] | str | Path,
    prompt_modules: dict[str, Any] | str | Path,
    pattern_memory: list[dict[str, Any]] | str | Path | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a planner context that limits repair to one module section."""
    matrix, matrix_path = _load_object(slice_matrix)
    modules_payload, modules_path = _load_object(prompt_modules)
    patterns = _load_pattern_memory(pattern_memory)
    regressions = _slice_regression_rows(matrix.get("slices"))
    target = regressions[0] if regressions else {}
    target_slice = _string_value(target.get("slice_name")) or _slice_name_from_key(
        _string_value(target.get("slice_key"))
    )
    module = _slice_module_for_target(modules_payload, target_slice)
    contract = _slice_patch_contract(
        target=target,
        target_slice=target_slice,
        module=module,
    )
    payload = {
        "status": "ready_for_slice_patch" if contract else "needs_slice_regression",
        "schema_version": SLICE_REPAIR_CONTEXT_SCHEMA_VERSION,
        "slice_matrix_ref": str(matrix_path) if matrix_path is not None else "inline",
        "prompt_modules_ref": str(modules_path) if modules_path is not None else "inline",
        "target_regression_slice": target,
        "matched_pattern_count": len(patterns),
        "recommended_patch_contract": contract,
        "planner_constraints": [
            "one module per patch",
            "one section per patch",
            "prompt_profile is disallowed in first-stage slice repair",
            "candidate must pass evaluate_slice_gate before canary",
        ],
        "claim_boundary": "local slice repair planning only",
        "executes_tool": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def generate_slice_patch_candidates(
    *,
    context: dict[str, Any] | str | Path,
    optimizer: str = "manual-template",
    optimizer_gate_plugin_manifests: list[dict[str, Any] | str | Path] | None = None,
    max_candidates: int = 1,
    execute_optimizer: bool = False,
    optimizer_model: str | None = None,
    optimizer_base_url: str | None = None,
    optimizer_api_key: str | None = None,
    optimizer_timeout_seconds: int = 30,
    optimizer_temperature: float = 0.0,
    optimizer_max_tokens: int = 512,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Generate section-local patch candidates without running evaluation."""
    adapter = resolve_optimizer_adapter(
        optimizer,
        plugin_manifests=optimizer_gate_plugin_manifests,
    )
    context_payload, context_path = _load_object(context)
    contract = (
        context_payload.get("recommended_patch_contract")
        if isinstance(context_payload.get("recommended_patch_contract"), dict)
        else {}
    )
    candidates: list[dict[str, Any]] = []
    optimizer_runtime = adapter.runtime(
        execute_optimizer=execute_optimizer,
        optimizer_model=optimizer_model,
        optimizer_base_url=optimizer_base_url,
        optimizer_timeout_seconds=optimizer_timeout_seconds,
        optimizer_temperature=optimizer_temperature,
        optimizer_max_tokens=optimizer_max_tokens,
    )
    optimizer_error: dict[str, str] | None = None
    if contract:
        count = max(1, max_candidates)
        try:
            if adapter.supports_execute_optimizer and not execute_optimizer:
                count = 0
            for index in range(1, count + 1):
                if adapter.name == "textgrad-openai-compatible" and execute_optimizer:
                    candidates.append(
                        _textgrad_openai_compatible_candidate(
                            contract=contract,
                            index=index,
                            optimizer_model=optimizer_runtime["model"],
                            optimizer_base_url=optimizer_runtime["base_url"],
                            optimizer_api_key=optimizer_api_key,
                            optimizer_timeout_seconds=optimizer_timeout_seconds,
                            optimizer_temperature=optimizer_temperature,
                            optimizer_max_tokens=optimizer_max_tokens,
                        )
                    )
                elif _adapter_uses_openai_compatible_runtime(adapter) and execute_optimizer:
                    candidates.append(
                        _openai_compatible_optimizer_candidate(
                            contract=contract,
                            index=index,
                            optimizer=adapter.name,
                            candidate_strategy="plugin_openai_compatible",
                            optimizer_model=optimizer_runtime["model"],
                            optimizer_base_url=optimizer_runtime["base_url"],
                            optimizer_api_key=_optimizer_runtime_api_key(
                                adapter=adapter,
                                optimizer_api_key=optimizer_api_key,
                            ),
                            optimizer_timeout_seconds=optimizer_timeout_seconds,
                            optimizer_temperature=optimizer_temperature,
                            optimizer_max_tokens=optimizer_max_tokens,
                        )
                    )
                elif _adapter_uses_subprocess_json_runtime(adapter) and execute_optimizer:
                    candidates.append(
                        _subprocess_json_optimizer_candidate(
                            contract=contract,
                            index=index,
                            optimizer=adapter.name,
                            command=_subprocess_json_runtime_command(adapter),
                            optimizer_timeout_seconds=optimizer_timeout_seconds,
                        )
                    )
                elif _adapter_uses_python_package_runtime(adapter) and execute_optimizer:
                    candidate, runtime_update, runtime_error = (
                        _python_package_optimizer_candidate(
                            contract=contract,
                            index=index,
                            optimizer=adapter.name,
                            adapter=adapter,
                            optimizer_timeout_seconds=optimizer_timeout_seconds,
                        )
                    )
                    optimizer_runtime.update(runtime_update)
                    if runtime_error is not None:
                        optimizer_error = runtime_error
                        break
                    if candidate is not None:
                        candidates.append(candidate)
                elif adapter.supports_execute_optimizer and execute_optimizer:
                    optimizer_runtime["status"] = "unsupported"
                    optimizer_runtime["executed"] = False
                    optimizer_error = {
                        "type": "UnsupportedOptimizerRuntime",
                        "message": (
                            f"optimizer adapter {adapter.name} has no implemented "
                            "candidate generation wrapper"
                        ),
                    }
                    break
                else:
                    candidates.append(
                        _manual_slice_patch_candidate(
                            contract=contract,
                            optimizer=adapter.name,
                            index=index,
                        )
                    )
        except (OSError, ValueError, subprocess.TimeoutExpired, urllib.error.URLError) as exc:
            candidates = []
            optimizer_runtime["status"] = "failed"
            optimizer_error = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
    status = "completed" if candidates else "needs_repair_context"
    if optimizer_error is not None:
        if optimizer_error.get("type") == "OptimizerRuntimeNotReady":
            status = "optimizer_runtime_not_ready"
        elif optimizer_error.get("type") == "UnsupportedOptimizerRuntime":
            status = "optimizer_runtime_unsupported"
        else:
            status = "optimizer_failed"
    elif contract and adapter.supports_execute_optimizer and not execute_optimizer:
        status = "needs_optimizer_execution"
    if candidates and optimizer_runtime.get("status") == "configured":
        optimizer_runtime["status"] = "executed"
    payload = {
        "status": status,
        "schema_version": SLICE_PATCH_CANDIDATES_SCHEMA_VERSION,
        "context_ref": str(context_path) if context_path is not None else "inline",
        "optimizer": adapter.name,
        "optimizer_adapter": {
            "registry_ref": f"optimizer_adapter:{adapter.name}",
            "adapter_type": adapter.adapter_type,
            "runtime_status": adapter.runtime_status,
            "candidate_schema": adapter.candidate_schema,
            "module_scope": adapter.module_scope,
        },
        "optimizer_runtime": optimizer_runtime,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "claim_boundary": "local slice patch candidates only",
        "executes_tool": bool(optimizer_runtime.get("executed")),
        "executes_optimizer_runtime": bool(
            optimizer_runtime.get("executed")
            and adapter.supports_execute_optimizer
            and optimizer_runtime.get("provider") != "deterministic-local"
        ),
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    if optimizer_error is not None:
        payload["optimizer_error"] = optimizer_error
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def probe_optimizer_runtime(
    *,
    optimizer: str = "manual-template",
    optimizer_gate_plugin_manifests: list[dict[str, Any] | str | Path] | None = None,
    execute_probe: bool = False,
    optimizer_model: str | None = None,
    optimizer_base_url: str | None = None,
    optimizer_timeout_seconds: int = 30,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Probe optimizer runtime readiness without running benchmark evaluation."""
    adapter = resolve_optimizer_adapter(
        optimizer,
        plugin_manifests=optimizer_gate_plugin_manifests,
    )
    runtime = adapter.runtime(
        execute_optimizer=execute_probe,
        optimizer_model=optimizer_model,
        optimizer_base_url=optimizer_base_url,
        optimizer_timeout_seconds=optimizer_timeout_seconds,
        optimizer_temperature=0.0,
        optimizer_max_tokens=1,
    )
    status = "not_required"
    runtime_ready = True
    probe_result: dict[str, Any] = {}
    probe_error: dict[str, str] | None = None

    if adapter.supports_execute_optimizer:
        runtime_ready = False
        status = "probe_not_executed"
        if execute_probe:
            if _adapter_uses_subprocess_json_runtime(adapter):
                try:
                    probe_response = _call_subprocess_json_optimizer(
                        command=_subprocess_json_runtime_command(adapter),
                        payload={
                            "task": "probe_optimizer_runtime",
                            "optimizer": adapter.name,
                            "strict_output": {
                                "format": "json_object",
                                "required_fields": ["status", "runtime_ready"],
                            },
                            "claim_boundary": "optimizer runtime readiness probe only",
                            "official_scores_claimed": False,
                        },
                        timeout_seconds=optimizer_timeout_seconds,
                    )
                    probe_result = probe_response["payload"]
                    runtime_ready = bool(probe_result.get("runtime_ready", False))
                    status = (
                        _string_value(probe_result.get("status"))
                        or ("ready" if runtime_ready else "not_ready")
                    )
                    runtime["status"] = "executed"
                    runtime["executed"] = True
                    probe_result.setdefault(
                        "response_id",
                        _response_id(probe_response.get("raw_response")),
                    )
                except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                    status = "probe_failed"
                    runtime_ready = False
                    runtime["status"] = "failed"
                    probe_error = {
                        "type": type(exc).__name__,
                        "message": str(exc),
                    }
            elif _adapter_uses_openai_compatible_runtime(adapter):
                status = "configured"
                runtime_ready = True
            elif _adapter_uses_python_package_runtime(adapter):
                probe_result = _probe_python_package_runtime(adapter)
                runtime_ready = bool(probe_result.get("runtime_ready", False))
                status = (
                    _string_value(probe_result.get("status"))
                    or ("ready" if runtime_ready else "not_ready")
                )
                runtime["status"] = "executed"
                runtime["executed"] = True
            else:
                status = "unsupported_probe_runtime"
                runtime_ready = False
    recommended_next_action = _optimizer_runtime_probe_next_action(
        status=status,
        runtime_ready=runtime_ready,
        execute_probe=execute_probe,
    )
    payload = {
        "status": status,
        "schema_version": OPTIMIZER_RUNTIME_PROBE_SCHEMA_VERSION,
        "optimizer": {
            "name": adapter.name,
            "registry_ref": f"optimizer_adapter:{adapter.name}",
            "adapter_type": adapter.adapter_type,
            "runtime_status": adapter.runtime_status,
            "supports_execute_optimizer": adapter.supports_execute_optimizer,
        },
        "runtime": runtime,
        "runtime_ready": runtime_ready,
        "probe_result": probe_result,
        "recommended_next_action": recommended_next_action,
        "claim_boundary": "optimizer runtime readiness probe only; not a benchmark run",
        "executes_tool": bool(execute_probe and adapter.supports_execute_optimizer),
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    if probe_error is not None:
        payload["probe_error"] = probe_error
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def build_optimizer_package_runtime_benefit_audit(
    *,
    optimizer_runtime_probe: dict[str, Any] | str | Path,
    slice_patch_candidates: dict[str, Any] | str | Path | None = None,
    gate_decision: dict[str, Any] | str | Path | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Bind package runtime readiness, candidate generation, and local gate benefit."""
    probe_payload, probe_path = _load_object(optimizer_runtime_probe)
    candidates_payload: dict[str, Any] | None = None
    candidates_path: Path | None = None
    if slice_patch_candidates is not None:
        candidates_payload, candidates_path = _load_object(slice_patch_candidates)
    gate_payload: dict[str, Any] | None = None
    gate_path: Path | None = None
    if gate_decision is not None:
        gate_payload, gate_path = _load_object(gate_decision)

    probe_result = (
        probe_payload.get("probe_result")
        if isinstance(probe_payload.get("probe_result"), dict)
        else {}
    )
    optimizer_payload = (
        probe_payload.get("optimizer")
        if isinstance(probe_payload.get("optimizer"), dict)
        else {}
    )
    optimizer_name = (
        _string_value(optimizer_payload.get("name"))
        or (
            _string_value(candidates_payload.get("optimizer"))
            if isinstance(candidates_payload, dict)
            else None
        )
        or "unknown_optimizer"
    )
    runtime_ready = bool(probe_payload.get("runtime_ready", False))
    candidate_count = (
        int(candidates_payload.get("candidate_count", 0) or 0)
        if isinstance(candidates_payload, dict)
        else 0
    )
    candidate_generated = (
        isinstance(candidates_payload, dict)
        and _string_value(candidates_payload.get("status")) == "completed"
        and candidate_count > 0
    )
    gate_evidence_present = isinstance(gate_payload, dict)
    metric_delta = _metric_delta_map(gate_payload or {})
    metric_delta_positive = any(value > 0 for value in metric_delta.values())
    gate = gate_payload.get("gate") if isinstance(gate_payload, dict) else {}
    gate_canary_allowed = (
        bool(gate.get("canary_allowed", False)) if isinstance(gate, dict) else False
    )
    gate_hard_blockers = (
        _string_list(gate_payload.get("hard_blockers"))
        if isinstance(gate_payload, dict)
        else []
    )
    benefit_verified = (
        runtime_ready
        and candidate_generated
        and gate_evidence_present
        and metric_delta_positive
        and gate_canary_allowed
        and not gate_hard_blockers
    )
    hard_blockers: list[str] = []
    if not runtime_ready:
        hard_blockers.append("runtime_not_ready")
    if runtime_ready and not candidate_generated:
        hard_blockers.append("candidate_not_generated")
    if runtime_ready and candidate_generated and not gate_evidence_present:
        hard_blockers.append("gate_evidence_missing")
    if (
        runtime_ready
        and candidate_generated
        and gate_evidence_present
        and not metric_delta_positive
    ):
        hard_blockers.append("metric_delta_not_positive")
    if (
        runtime_ready
        and candidate_generated
        and gate_evidence_present
        and metric_delta_positive
        and not gate_canary_allowed
    ):
        hard_blockers.append("gate_not_passed_for_canary")
    hard_blockers.extend(gate_hard_blockers)
    hard_blockers = _dedupe_strings(hard_blockers)
    if benefit_verified:
        status = "benefit_verified"
    elif not runtime_ready:
        status = "blocked_runtime_not_ready"
    elif not candidate_generated:
        status = "blocked_candidate_not_generated"
    elif not gate_evidence_present:
        status = "candidate_generated_without_gate_evidence"
    else:
        status = "benefit_not_verified"

    artifact_refs = []
    if probe_path is not None:
        artifact_refs.append({"name": "optimizer_runtime_probe", "path": str(probe_path)})
    if candidates_path is not None:
        artifact_refs.append({"name": "slice_patch_candidates", "path": str(candidates_path)})
    if gate_path is not None:
        artifact_refs.append({"name": "gate_decision", "path": str(gate_path)})
    payload = {
        "status": status,
        "schema_version": OPTIMIZER_PACKAGE_RUNTIME_BENEFIT_AUDIT_SCHEMA_VERSION,
        "optimizer": optimizer_name,
        "package_runtime": {
            "package_import": _string_value(probe_result.get("package_import")),
            "package_name": _string_value(probe_result.get("package_name")),
            "package_version": _string_value(probe_result.get("package_version")),
            "runtime_ready": runtime_ready,
            "api": {
                key: value
                for key, value in probe_result.items()
                if key.endswith("_api") and isinstance(value, dict)
            },
        },
        "candidate_summary": {
            "candidate_count": candidate_count,
            "candidate_generated": candidate_generated,
            "candidate_status": (
                _string_value(candidates_payload.get("status"))
                if isinstance(candidates_payload, dict)
                else None
            ),
        },
        "metric_delta": metric_delta,
        "gate": {
            "runtime_ready": runtime_ready,
            "candidate_generated": candidate_generated,
            "gate_evidence_present": gate_evidence_present,
            "metric_delta_positive": metric_delta_positive,
            "gate_canary_allowed": gate_canary_allowed,
            "benefit_verified": benefit_verified,
        },
        "hard_blockers": hard_blockers,
        "artifact_refs": artifact_refs,
        "claim_boundary": (
            "package runtime benefit audit only; benefit requires runtime readiness, "
            "candidate generation, and local gate evidence with positive metric delta"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def build_method_proposal_generation_trace(
    *,
    generation_context: dict[str, Any] | str | Path,
    generation_run: dict[str, Any] | str | Path,
    reasoning_trace: dict[str, Any] | str | Path,
    proposals: list[dict[str, Any]] | dict[str, Any] | str | Path,
    ranking_decisions: list[dict[str, Any]] | dict[str, Any] | str | Path,
    selected_proposal_ids: list[str] | None = None,
    execution_links: list[dict[str, Any]] | dict[str, Any] | str | Path | None = None,
    gate_results: list[dict[str, Any]] | dict[str, Any] | str | Path | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Record a full method-proposal search trace without executing experiments."""
    context_payload, context_path = _load_object(generation_context)
    run_payload, run_path = _load_object(generation_run)
    reasoning_payload, reasoning_path = _load_object(reasoning_trace)
    proposal_items, proposals_path = _load_method_trace_items(
        proposals,
        list_keys=("proposals", "candidate_pool", "candidates", "ranked_proposals"),
    )
    ranking_items, ranking_path = _load_method_trace_items(
        ranking_decisions,
        list_keys=("decisions", "ranking_decisions", "ranked_proposals"),
    )
    execution_items: list[dict[str, Any]] = []
    execution_path: Path | None = None
    if execution_links is not None:
        execution_items, execution_path = _load_method_trace_items(
            execution_links,
            list_keys=("execution_links", "links", "artifacts"),
        )
    gate_items: list[dict[str, Any]] = []
    gate_path: Path | None = None
    if gate_results is not None:
        gate_items, gate_path = _load_method_trace_items(
            gate_results,
            list_keys=("gate_results", "results", "validation_links"),
        )

    candidate_pool = _method_trace_candidate_pool(proposal_items)
    ranking_trace = _method_trace_ranking_trace(ranking_items)
    normalized_selected_ids = _method_trace_selected_ids(
        selected_proposal_ids=selected_proposal_ids,
        ranking_decisions=ranking_trace["decisions"],
    )
    selected_set = set(normalized_selected_ids)
    selected_proposals = [
        proposal
        for proposal in candidate_pool
        if proposal["proposal_id"] in selected_set
    ]
    pruned_proposals = [
        _method_trace_pruned_proposal(
            proposal=proposal,
            ranking_decisions=ranking_trace["decisions"],
        )
        for proposal in candidate_pool
        if proposal["proposal_id"] not in selected_set
    ]
    validation_links = _method_trace_validation_links(
        execution_links=execution_items,
        gate_results=gate_items,
    )
    artifact_refs = _method_trace_artifact_refs(
        {
            "generation_context": context_path,
            "generation_run": run_path,
            "reasoning_trace": reasoning_path,
            "proposals": proposals_path,
            "ranking_decisions": ranking_path,
            "execution_links": execution_path,
            "gate_results": gate_path,
        }
    )
    payload = {
        "status": "completed" if candidate_pool else "needs_proposals",
        "schema_version": METHOD_PROPOSAL_GENERATION_TRACE_SCHEMA_VERSION,
        "generation_context": _method_trace_generation_context(context_payload),
        "generation_run": _method_trace_generation_run(run_payload),
        "reasoning_trace": _method_trace_reasoning_trace(reasoning_payload),
        "candidate_pool": candidate_pool,
        "proposal_count": len(candidate_pool),
        "ranking_trace": ranking_trace,
        "selected_proposals": selected_proposals,
        "selected_proposal_count": len(selected_proposals),
        "pruned_proposals": pruned_proposals,
        "pruned_proposal_count": len(pruned_proposals),
        "validation_links": validation_links,
        "learning_updates": _method_trace_learning_updates(
            candidate_pool=candidate_pool,
            gate_results=gate_items,
        ),
        "artifact_refs": artifact_refs,
        "recommended_next_action": (
            "validate_selected_proposals"
            if selected_proposals
            else "rank_and_select_proposals"
        ),
        "claim_boundary": (
            "method proposal generation trace only; not proof of improvement"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def build_method_search_study(
    *,
    study_name: str,
    objective: str,
    direction: str = "maximize",
    operators: list[str | dict[str, Any]] | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Create an Optuna-style method-search study without importing Optuna."""
    if not study_name:
        raise ValueError("study_name is required")
    if not objective:
        raise ValueError("objective is required")
    operator_taxonomy = _method_search_operator_taxonomy(operators)
    operator_weights = {
        item["operator_id"]: 1.0 for item in operator_taxonomy["operators"]
    }
    gate_feedback_memory = build_gate_feedback_memory(
        gate_results=[],
        operators=[item["operator_id"] for item in operator_taxonomy["operators"]],
    )
    payload = {
        "status": "active",
        "schema_version": METHOD_SEARCH_STUDY_SCHEMA_VERSION,
        "study_name": study_name,
        "objective": objective,
        "direction": direction,
        "optuna_compatibility": {
            "object_model": "Study/Trial",
            "supports_ask_tell": True,
            "trial_states": ["COMPLETE", "PRUNED", "FAIL", "WAITING"],
            "sampler_protocol": "ask produces WAITING trials; tell records gate score",
            "pruner_protocol": "gate hard blockers map to PRUNED trials",
            "reserved_adapters": [
                "OptunaSamplerAdapter",
                "OptunaStorageAdapter",
                "OptunaDashboardExport",
            ],
            "optuna_package_integrated_as_main_path": False,
        },
        "sampler": {
            "sampler_name": "HexagonGuidedLLMSampler",
            "operator_taxonomy": operator_taxonomy,
            "rule_only_round_robin": False,
            "gate_feedback_required": True,
        },
        "storage": {
            "storage_adapter": "artifact_json",
            "reserved_adapter": "OptunaStorageAdapter",
        },
        "pruner": {
            "pruner_name": "GateFeedbackPruner",
            "hard_blockers_prune_trial": True,
            "reserved_adapter": "OptunaPrunerAdapter",
        },
        "trials": [],
        "trial_count": 0,
        "best_trial": None,
        "sampler_state": {
            "operator_weights": operator_weights,
            "gate_feedback_memory": gate_feedback_memory,
            "last_sampler_output": None,
            "last_direction_change": {
                "reason": "new study has no gate feedback yet",
                "upweighted_operator_ids": [],
                "downweighted_operator_ids": [],
            },
        },
        "claim_boundary": {
            "evidence_scope": "local_gate_only",
            "llm_may_claim_improvement": False,
            "official_scores_claimed": False,
        },
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    _method_search_write_payload(payload, output_path=output_path, overwrite=overwrite)
    return payload


def build_gate_feedback_memory(
    *,
    gate_results: list[dict[str, Any]] | dict[str, Any] | str | Path | None = None,
    operators: list[str | dict[str, Any]] | None = None,
    near_pass_threshold: float = 0.7,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Turn gate outcomes into sampler feedback without claiming improvement."""
    operator_taxonomy = _method_search_operator_taxonomy(operators)
    operator_ids = [item["operator_id"] for item in operator_taxonomy["operators"]]
    operator_weights = {operator_id: 1.0 for operator_id in operator_ids}
    result_items, gate_results_path = _method_search_load_items(
        gate_results,
        list_keys=("gate_results", "results", "validation_links", "outcomes"),
    )
    operator_feedback: list[dict[str, Any]] = []
    blocked_patterns: list[dict[str, Any]] = []
    promoted_patterns: list[dict[str, Any]] = []

    for index, gate_result in enumerate(result_items, start=1):
        operator_id = _method_search_gate_operator_id(gate_result)
        if operator_id not in operator_weights:
            operator_weights[operator_id] = 1.0
        proposal_id = (
            _string_value(gate_result.get("proposal_id"))
            or _string_value(gate_result.get("patch_id"))
            or f"proposal-{index:03d}"
        )
        status = (
            _string_value(gate_result.get("status"))
            or _string_value(gate_result.get("gate_status"))
            or "unknown"
        )
        score = _method_search_gate_score(gate_result)
        hard_blockers = _method_search_hard_blockers(gate_result)
        passed = _method_search_gate_passed(gate_result, hard_blockers=hard_blockers)
        near_pass = (
            not hard_blockers
            and not passed
            and (
                status in {"near_pass", "near-passed", "near_passed"}
                or score >= near_pass_threshold
            )
        )
        feedback = {
            "proposal_id": proposal_id,
            "operator_id": operator_id,
            "status": status,
            "score": score,
            "hard_blockers": hard_blockers,
            "gate_passed": passed,
            "near_pass": near_pass,
            "official_scores_claimed": False,
        }
        if hard_blockers:
            operator_weights[operator_id] = round(
                max(0.05, operator_weights[operator_id] * 0.5),
                4,
            )
            blocked_patterns.append({
                "proposal_id": proposal_id,
                "operator_id": operator_id,
                "hard_blockers": hard_blockers,
                "weight_update": "downweighted",
            })
            feedback["weight_update"] = "downweighted"
        elif passed:
            operator_weights[operator_id] = round(operator_weights[operator_id] + 0.75, 4)
            promoted_patterns.append({
                "proposal_id": proposal_id,
                "operator_id": operator_id,
                "status": status,
                "weight_update": "upweighted",
            })
            feedback["weight_update"] = "upweighted"
        elif near_pass:
            operator_weights[operator_id] = round(operator_weights[operator_id] + 0.35, 4)
            promoted_patterns.append({
                "proposal_id": proposal_id,
                "operator_id": operator_id,
                "status": status,
                "weight_update": "upweighted_near_pass",
            })
            feedback["weight_update"] = "upweighted_near_pass"
        else:
            feedback["weight_update"] = "unchanged"
        operator_feedback.append(feedback)

    payload = {
        "status": "ready",
        "schema_version": GATE_FEEDBACK_MEMORY_SCHEMA_VERSION,
        "operator_taxonomy": operator_taxonomy,
        "operator_weights": operator_weights,
        "operator_feedback": operator_feedback,
        "blocked_patterns": blocked_patterns,
        "promoted_patterns": promoted_patterns,
        "feedback_policy": {
            "hard_block_downweights_operator_pattern": True,
            "gate_pass_or_near_pass_upweights_operator_pattern": True,
            "near_pass_threshold": near_pass_threshold,
            "llm_can_self_report_improvement": False,
        },
        "artifact_refs": (
            [{"name": "gate_results", "path": str(gate_results_path)}]
            if gate_results_path is not None
            else []
        ),
        "recommended_operator_shift": _method_search_operator_shift(operator_weights),
        "claim_boundary": {
            "evidence_scope": "local_gate_only",
            "llm_may_claim_improvement": False,
            "official_scores_claimed": False,
        },
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    _method_search_write_payload(payload, output_path=output_path, overwrite=overwrite)
    return payload


def sample_hexagon_guided_llm_proposals(
    *,
    objective: str,
    operators: list[str | dict[str, Any]] | None = None,
    gate_feedback_memory: dict[str, Any] | str | Path | None = None,
    llm_proposals: list[dict[str, Any]] | dict[str, Any] | str | Path | None = None,
    model: str = "llm-method-search",
    execute_llm: bool = False,
    llm_base_url: str = DEFAULT_TEXTGRAD_OPTIMIZER_BASE_URL,
    llm_provider: str = "openai-compatible",
    llm_api_key_env: str | None = None,
    llm_temperature: float = 0.2,
    llm_max_tokens: int = 1600,
    llm_timeout_seconds: int = 60,
    llm_completion_fn: Callable[..., dict[str, Any]] | None = None,
    max_selected: int = 1,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Sample LLM proposals under Idea Hexagon operators and gate feedback."""
    if not objective:
        raise ValueError("objective is required")
    operator_taxonomy = _method_search_operator_taxonomy(operators)
    operator_ids = [item["operator_id"] for item in operator_taxonomy["operators"]]
    memory_payload = _method_search_feedback_memory_payload(
        gate_feedback_memory=gate_feedback_memory,
        operator_ids=operator_ids,
    )
    operator_weights = dict(memory_payload.get("operator_weights") or {})
    for operator_id in operator_ids:
        operator_weights.setdefault(operator_id, 1.0)
    proposal_items, proposals_path = _method_search_load_items(
        llm_proposals,
        list_keys=("proposals", "candidate_pool", "candidates", "ranked_proposals"),
    )
    llm_input_mode = "provided_llm_output" if proposals_path is None else "artifact"
    if not proposal_items and execute_llm:
        proposal_items = _method_search_generate_llm_proposals(
            objective=objective,
            operator_taxonomy=operator_taxonomy,
            gate_feedback_memory=memory_payload,
            model=model,
            base_url=llm_base_url,
            provider=llm_provider,
            api_key_env=llm_api_key_env,
            temperature=llm_temperature,
            max_tokens=llm_max_tokens,
            timeout_seconds=llm_timeout_seconds,
            completion_fn=llm_completion_fn,
        )
        llm_input_mode = "live_llm"
    if not proposal_items:
        proposal_items = [
            _method_search_placeholder_llm_proposal(
                operator_id=operator_ids[0] if operator_ids else "combine",
                objective=objective,
            )
        ]
        llm_input_mode = "placeholder_no_llm_output"
    normalized_proposals = [
        _method_search_normalize_llm_proposal(
            proposal=proposal,
            index=index,
            operator_ids=operator_ids,
        )
        for index, proposal in enumerate(proposal_items, start=1)
    ]
    ranked_proposals = sorted(
        normalized_proposals,
        key=lambda proposal: (
            -float(operator_weights.get(str(proposal["operator_id"]), 1.0)),
            int(proposal["_input_order"]),
        ),
    )
    selected_proposals = ranked_proposals[: max(0, max_selected)]
    selected_ids = [str(proposal["proposal_id"]) for proposal in selected_proposals]
    ranking_decisions = _method_search_ranking_decisions(
        ranked_proposals=ranked_proposals,
        selected_ids=set(selected_ids),
        operator_weights=operator_weights,
    )
    output_proposals = [
        {key: value for key, value in proposal.items() if key != "_input_order"}
        for proposal in ranked_proposals
    ]
    payload = {
        "status": "completed" if output_proposals else "needs_llm_proposals",
        "schema_version": HEXAGON_GUIDED_LLM_SAMPLER_SCHEMA_VERSION,
        "sampler_name": "HexagonGuidedLLMSampler",
        "objective": objective,
        "operator_taxonomy": operator_taxonomy,
        "operator_weights": operator_weights,
        "selected_operator_ids": [
            str(proposal["operator_id"]) for proposal in selected_proposals
        ],
        "selected_proposal_ids": selected_ids,
        "proposals": output_proposals,
        "ranking_decisions": ranking_decisions,
        "reasoning_trace": _method_search_sampler_reasoning_trace(
            proposals=selected_proposals,
            operator_weights=operator_weights,
        ),
        "llm_generation": {
            "uses_llm": True,
            "model": model,
            "input_mode": llm_input_mode,
            "proposal_artifact_ref": str(proposals_path) if proposals_path else "inline",
            "base_url": llm_base_url if execute_llm else None,
            "provider": llm_provider if execute_llm else None,
            "required_fields": list(_METHOD_SEARCH_REQUIRED_PROPOSAL_FIELDS),
            "llm_may_claim_improvement": False,
        },
        "gate_feedback_memory": {
            "schema_version": memory_payload.get("schema_version"),
            "operator_feedback_count": len(
                memory_payload.get("operator_feedback")
                if isinstance(memory_payload.get("operator_feedback"), list)
                else []
            ),
            "blocked_patterns": memory_payload.get("blocked_patterns") or [],
            "promoted_patterns": memory_payload.get("promoted_patterns") or [],
            "recommended_operator_shift": memory_payload.get(
                "recommended_operator_shift"
            ),
        },
        "rule_only_round_robin": False,
        "claim_boundary": {
            "evidence_scope": "local_gate_only",
            "llm_may_claim_improvement": False,
            "official_scores_claimed": False,
        },
        "executes_tool": True,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    _method_search_write_payload(payload, output_path=output_path, overwrite=overwrite)
    return payload


def ask_method_search_trial(
    *,
    study: dict[str, Any] | str | Path,
    objective: str | None = None,
    operators: list[str | dict[str, Any]] | None = None,
    llm_proposals: list[dict[str, Any]] | dict[str, Any] | str | Path | None = None,
    gate_feedback_memory: dict[str, Any] | str | Path | None = None,
    gate_feedback_memory_store: dict[str, Any] | str | Path | None = None,
    model: str = "llm-method-search",
    execute_llm: bool = False,
    llm_base_url: str = DEFAULT_TEXTGRAD_OPTIMIZER_BASE_URL,
    llm_provider: str = "openai-compatible",
    llm_api_key_env: str | None = None,
    llm_temperature: float = 0.2,
    llm_max_tokens: int = 1600,
    llm_timeout_seconds: int = 60,
    llm_completion_fn: Callable[..., dict[str, Any]] | None = None,
    adapter: str = "llm-method-search",
    slice_id: str = "unspecified",
    patch_scope: str = "unspecified",
    budget: dict[str, Any] | None = None,
    max_trials: int = 1,
    output_dir: str | Path | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Optuna-style ask: sample proposals and return WAITING trials."""
    study_payload, study_path = _load_object(study)
    resolved_objective = objective or _string_value(study_payload.get("objective"))
    if not resolved_objective:
        raise ValueError("objective is required")
    output_root = Path(output_dir) if output_dir is not None else None
    if output_root is not None:
        output_root.mkdir(parents=True, exist_ok=True)
    memory_payload = _method_search_feedback_memory_payload(
        gate_feedback_memory=(
            gate_feedback_memory
            if gate_feedback_memory is not None
            else _method_search_latest_memory_from_store(gate_feedback_memory_store)
        ),
        operator_ids=_method_search_operator_ids_from_study(study_payload, operators),
        study=study_payload,
    )
    feedback_store_path = _method_search_feedback_store_path(gate_feedback_memory_store)
    sampler_output_path = (
        output_root / "hexagon-guided-llm-sampler.json"
        if output_root is not None
        else None
    )
    sampler_output = sample_hexagon_guided_llm_proposals(
        objective=resolved_objective,
        operators=operators or _method_search_operator_ids_from_study(study_payload, None),
        gate_feedback_memory=memory_payload,
        llm_proposals=llm_proposals,
        model=model,
        execute_llm=execute_llm,
        llm_base_url=llm_base_url,
        llm_provider=llm_provider,
        llm_api_key_env=llm_api_key_env,
        llm_temperature=llm_temperature,
        llm_max_tokens=llm_max_tokens,
        llm_timeout_seconds=llm_timeout_seconds,
        llm_completion_fn=llm_completion_fn,
        max_selected=max_trials,
        output_path=sampler_output_path,
        overwrite=overwrite,
    )
    trace_output_path = (
        output_root / "method-proposal-generation-trace.json"
        if output_root is not None
        else None
    )
    trace_payload = build_method_proposal_generation_trace(
        generation_context={
            "task_family": _string_value(study_payload.get("study_name")) or "method_search",
            "objective": resolved_objective,
            "operators": sampler_output["selected_operator_ids"],
            "constraints": [
                "LLM proposals do not claim improvement",
                "gate outcome decides trial value",
                "official_scores_claimed remains false",
            ],
            "evidence_scope": "local_gate_only",
        },
        generation_run={
            "generator": "HexagonGuidedLLMSampler",
            "model": model,
            "adapter": adapter,
            "rule_only_round_robin": False,
            "uses_llm": True,
        },
        reasoning_trace=sampler_output["reasoning_trace"],
        proposals=sampler_output["proposals"],
        ranking_decisions=sampler_output["ranking_decisions"],
        selected_proposal_ids=sampler_output["selected_proposal_ids"],
        output_path=trace_output_path,
        overwrite=overwrite,
    )
    updated_study = _json_clone(study_payload)
    existing_trials = [
        item for item in updated_study.get("trials", []) if isinstance(item, dict)
    ]
    new_trials = [
        _method_search_build_trial(
            proposal=proposal,
            trial_number=len(existing_trials) + index,
            adapter=adapter,
            slice_id=slice_id,
            patch_scope=patch_scope,
            model=model,
            budget=budget or {},
            trace_payload=trace_payload,
            sampler_output=sampler_output,
        )
        for index, proposal in enumerate(
            _method_search_selected_sampler_proposals(sampler_output),
            start=1,
        )
    ]
    updated_study["trials"] = existing_trials + new_trials
    updated_study["trial_count"] = len(updated_study["trials"])
    updated_study.setdefault("sampler_state", {})
    updated_study["sampler_state"]["last_sampler_output"] = {
        "schema_version": sampler_output["schema_version"],
        "selected_operator_ids": sampler_output["selected_operator_ids"],
        "selected_proposal_ids": sampler_output["selected_proposal_ids"],
        "operator_weights": sampler_output["operator_weights"],
    }
    updated_study["sampler_state"]["gate_feedback_memory"] = memory_payload
    if feedback_store_path is not None:
        updated_study["sampler_state"]["feedback_store_ref"] = str(feedback_store_path)
    updated_study["official_scores_claimed"] = False
    artifact_refs = _method_search_artifact_refs(
        study_path=study_path,
        sampler_output=sampler_output,
        trace_payload=trace_payload,
    )
    payload = {
        "status": "waiting_for_gate_feedback" if new_trials else "no_trial_sampled",
        "schema_version": METHOD_SEARCH_ASK_SCHEMA_VERSION,
        "study": updated_study,
        "trials": new_trials,
        "sampler": sampler_output,
        "method_proposal_generation_trace": trace_payload,
        "artifact_refs": artifact_refs,
        "claim_boundary": {
            "evidence_scope": "local_gate_only",
            "llm_may_claim_improvement": False,
            "official_scores_claimed": False,
        },
        "executes_tool": True,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    if output_path is None and output_root is not None:
        output_path = output_root / "method-search-ask.json"
    _method_search_write_payload(payload, output_path=output_path, overwrite=overwrite)
    return payload


def tell_method_search_trial(
    *,
    study: dict[str, Any] | str | Path,
    trial: dict[str, Any] | str | Path,
    gate_result: dict[str, Any] | str | Path,
    feedback_store_path: str | Path | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Optuna-style tell: consume a gate result and update trial/study state."""
    study_payload, study_path = _load_object(study)
    trial_payload, trial_path = _load_object(trial)
    gate_payload, gate_path = _load_object(gate_result)
    score = _method_search_gate_score(gate_payload)
    hard_blockers = _method_search_hard_blockers(gate_payload)
    passed = _method_search_gate_passed(gate_payload, hard_blockers=hard_blockers)
    state = _method_search_trial_state(
        gate_payload=gate_payload,
        hard_blockers=hard_blockers,
        passed=passed,
    )
    updated_trial = _json_clone(trial_payload)
    updated_trial["state"] = state
    updated_trial["value"] = score
    updated_trial["user_attrs"] = _json_clone(
        updated_trial.get("user_attrs")
        if isinstance(updated_trial.get("user_attrs"), dict)
        else {}
    )
    updated_trial["user_attrs"]["hard_blockers"] = hard_blockers
    updated_trial["user_attrs"]["gate_result"] = _method_search_gate_result_summary(
        gate_payload=gate_payload,
        gate_path=gate_path,
        state=state,
        score=score,
        hard_blockers=hard_blockers,
    )
    updated_trial["user_attrs"].setdefault("claim_boundary", {})
    updated_trial["user_attrs"]["claim_boundary"].update({
        "evidence_scope": "local_gate_only",
        "llm_may_claim_improvement": False,
        "official_scores_claimed": False,
    })
    updated_trial["official_scores_claimed"] = False

    updated_study = _json_clone(study_payload)
    trials = [
        item for item in updated_study.get("trials", []) if isinstance(item, dict)
    ]
    replaced = False
    for index, existing in enumerate(trials):
        if _method_search_same_trial(existing, updated_trial):
            trials[index] = updated_trial
            replaced = True
            break
    if not replaced:
        trials.append(updated_trial)
    updated_study["trials"] = trials
    updated_study["trial_count"] = len(trials)
    memory = build_gate_feedback_memory(
        gate_results=_method_search_gate_results_from_trials(trials),
        operators=_method_search_operator_ids_from_study(updated_study, None),
    )
    updated_study.setdefault("sampler_state", {})
    before_weights = _method_search_existing_operator_weights(study_payload)
    after_weights = memory["operator_weights"]
    updated_study["sampler_state"]["gate_feedback_memory"] = memory
    updated_study["sampler_state"]["operator_weights"] = after_weights
    updated_study["sampler_state"]["last_direction_change"] = (
        _method_search_direction_change(before_weights, after_weights)
    )
    updated_study["best_trial"] = _method_search_best_trial(trials)
    updated_study["official_scores_claimed"] = False
    feedback_store = None
    if feedback_store_path is not None:
        feedback_store = persist_gate_feedback_memory_store(
            gate_feedback_memory=memory,
            study=updated_study,
            trial=updated_trial,
            gate_result=gate_payload,
            output_path=feedback_store_path,
        )
        updated_study["sampler_state"]["feedback_store_ref"] = str(feedback_store_path)
    payload = {
        "status": "study_updated",
        "schema_version": METHOD_SEARCH_TELL_SCHEMA_VERSION,
        "study": updated_study,
        "trial": updated_trial,
        "gate_feedback_memory": memory,
        "feedback_store": feedback_store,
        "acceptance_answers": _method_search_acceptance_answers(
            study=updated_study,
            trial=updated_trial,
            gate_result=gate_payload,
            memory=memory,
        ),
        "artifact_refs": _method_search_artifact_refs(
            study_path=study_path,
            trial_path=trial_path,
            gate_path=gate_path,
        ),
        "claim_boundary": {
            "evidence_scope": "local_gate_only",
            "llm_may_claim_improvement": False,
            "official_scores_claimed": False,
        },
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    _method_search_write_payload(payload, output_path=output_path, overwrite=overwrite)
    return payload


def build_multi_optimizer_candidate_race(
    *,
    race_name: str,
    objective: str,
    candidate_sources: list[dict[str, Any]] | dict[str, Any] | str | Path,
    gate_results: list[dict[str, Any]] | dict[str, Any] | str | Path,
    operators: list[str | dict[str, Any]] | None = None,
    direction: str = "maximize",
    model: str = "multi-optimizer-candidate-race",
    adapter: str = "multi-optimizer-candidate-race",
    slice_id: str = "multi_optimizer_race",
    patch_scope: str = "multi_optimizer_candidate",
    budget: dict[str, Any] | None = None,
    output_dir: str | Path | None = None,
    feedback_store_path: str | Path | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run multiple optimizer proposal sources through one MethodSearch gate ledger."""
    if not race_name:
        raise ValueError("race_name is required")
    if not objective:
        raise ValueError("objective is required")
    source_rows, candidate_pool, candidate_sources_path = (
        _multi_optimizer_candidate_sources(candidate_sources)
    )
    if not candidate_pool:
        raise ValueError("candidate_sources must contain at least one proposal")
    gate_items, gate_results_path = _method_search_load_items(
        gate_results,
        list_keys=("gate_results", "results", "validation_links", "outcomes"),
    )
    gate_by_proposal_id = {
        str(item["proposal_id"]): item
        for item in gate_items
        if isinstance(item, dict) and _string_value(item.get("proposal_id"))
    }
    output_root = Path(output_dir) if output_dir is not None else None
    if output_root is not None:
        output_root.mkdir(parents=True, exist_ok=True)
    race_budget = budget or {
        "candidate_count": len(candidate_pool),
        "optimizer_source_count": len(source_rows),
    }
    study_output_path = output_root / "method-search-study.json" if output_root else None
    proposals_output_path = (
        output_root / "multi-optimizer-proposals.json" if output_root else None
    )
    ask_output_path = output_root / "method-search-ask.json" if output_root else None
    ask_output_dir = output_root / "ask" if output_root else None
    gates_dir = output_root / "gate-results" if output_root else None
    tell_dir = output_root / "tell" if output_root else None
    if gates_dir is not None:
        gates_dir.mkdir(parents=True, exist_ok=True)
    if tell_dir is not None:
        tell_dir.mkdir(parents=True, exist_ok=True)
    if proposals_output_path is not None:
        _method_search_write_payload(
            {"proposals": candidate_pool},
            output_path=proposals_output_path,
            overwrite=overwrite,
        )

    study = build_method_search_study(
        study_name=race_name,
        objective=objective,
        direction=direction,
        operators=operators,
        output_path=study_output_path,
        overwrite=overwrite,
    )
    ask_payload = ask_method_search_trial(
        study=study,
        objective=objective,
        operators=operators,
        llm_proposals=proposals_output_path or {"proposals": candidate_pool},
        model=model,
        adapter=adapter,
        slice_id=slice_id,
        patch_scope=patch_scope,
        budget=race_budget,
        max_trials=len(candidate_pool),
        output_dir=ask_output_dir,
        output_path=ask_output_path,
        overwrite=overwrite,
    )

    candidate_by_id = {
        str(candidate["proposal_id"]): candidate for candidate in candidate_pool
    }
    current_study = ask_payload["study"]
    tell_results: list[dict[str, Any]] = []
    missing_gate_proposal_ids: list[str] = []
    for trial in ask_payload["trials"]:
        if not isinstance(trial, dict):
            continue
        proposal_id = str(trial.get("proposal_id"))
        gate_payload = gate_by_proposal_id.get(proposal_id)
        if gate_payload is None:
            missing_gate_proposal_ids.append(proposal_id)
            continue
        gate_payload = dict(gate_payload)
        gate_payload.setdefault("proposal_id", proposal_id)
        gate_payload.setdefault(
            "operator_id",
            trial.get("params", {}).get("operator")
            if isinstance(trial.get("params"), dict)
            else None,
        )
        gate_payload["official_scores_claimed"] = False
        gate_output_path = gates_dir / f"{proposal_id}.json" if gates_dir else None
        if gate_output_path is not None:
            _method_search_write_payload(
                gate_payload,
                output_path=gate_output_path,
                overwrite=overwrite,
            )
        tell_output_path = tell_dir / f"{proposal_id}.json" if tell_dir else None
        tell_payload = tell_method_search_trial(
            study=current_study,
            trial=trial,
            gate_result=gate_output_path or gate_payload,
            feedback_store_path=feedback_store_path,
            output_path=tell_output_path,
            overwrite=overwrite,
        )
        current_study = tell_payload["study"]
        tell_results.append(tell_payload)

    gate_feedback_memory = (
        current_study.get("sampler_state", {}).get("gate_feedback_memory", {})
        if isinstance(current_study.get("sampler_state"), dict)
        else {}
    )
    winner = _multi_optimizer_race_winner(
        study=current_study,
        candidates=candidate_by_id,
        direction=direction,
    )
    payload = {
        "status": (
            "completed"
            if not missing_gate_proposal_ids
            else "waiting_for_gate_feedback"
        ),
        "schema_version": MULTI_OPTIMIZER_CANDIDATE_RACE_SCHEMA_VERSION,
        "race_name": race_name,
        "objective": objective,
        "direction": direction,
        "source_count": len(source_rows),
        "candidate_count": len(candidate_pool),
        "candidate_sources": source_rows,
        "candidate_pool": candidate_pool,
        "gate_result_count": len(gate_items),
        "missing_gate_proposal_ids": missing_gate_proposal_ids,
        "winner": winner,
        "study": current_study,
        "ask": ask_payload,
        "tell_results": tell_results,
        "trials": current_study.get("trials", []),
        "gate_feedback_memory": gate_feedback_memory,
        "acceptance_answers": _multi_optimizer_race_acceptance_answers(
            candidate_sources=source_rows,
            candidate_pool=candidate_pool,
            winner=winner,
            study=current_study,
            missing_gate_proposal_ids=missing_gate_proposal_ids,
        ),
        "artifact_refs": _method_search_artifact_refs(
            candidate_sources_path=candidate_sources_path,
            gate_results_path=gate_results_path,
            study_path=study_output_path,
            proposals_path=proposals_output_path,
            ask_path=ask_output_path,
            feedback_store_path=Path(feedback_store_path)
            if feedback_store_path is not None
            else None,
        ),
        "claim_boundary": {
            "evidence_scope": "local_gate_only",
            "llm_may_claim_improvement": False,
            "official_scores_claimed": False,
        },
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    _method_search_write_payload(payload, output_path=output_path, overwrite=overwrite)
    return payload


def run_multi_optimizer_candidate_race(
    *,
    race_name: str,
    objective: str,
    context: dict[str, Any] | str | Path,
    gate_results: list[dict[str, Any]] | dict[str, Any] | str | Path,
    mode: str = "optimization-run",
    optimizer_sources: list[str] | None = None,
    operators: list[str | dict[str, Any]] | None = None,
    direction: str = "maximize",
    max_candidates_per_source: int = 1,
    execute_llm: bool | None = None,
    llm_proposals: list[dict[str, Any]] | dict[str, Any] | str | Path | None = None,
    llm_completion_fn: Callable[..., dict[str, Any]] | None = None,
    gate_feedback_memory: dict[str, Any] | str | Path | None = None,
    execute_optimizer_runtimes: bool | None = None,
    allow_style_fallback: bool | None = None,
    optimizer_gate_plugin_manifests: list[dict[str, Any] | str | Path] | None = None,
    optimizer_model: str | None = None,
    optimizer_base_url: str | None = None,
    optimizer_api_key: str | None = None,
    optimizer_timeout_seconds: int = 30,
    optimizer_temperature: float = 0.0,
    optimizer_max_tokens: int = 512,
    output_dir: str | Path | None = None,
    feedback_store_path: str | Path | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
    max_workers: int | None = None,
) -> dict[str, Any]:
    """Generate candidates from multiple optimizer families, then gate-race them."""
    if not race_name:
        raise ValueError("race_name is required")
    if not objective:
        raise ValueError("objective is required")
    run_mode = _multi_optimizer_run_mode(mode)
    execute_optimizer_runtimes = _multi_optimizer_execute_runtime_default(
        mode=run_mode,
        requested=execute_optimizer_runtimes,
    )
    allow_style_fallback = _multi_optimizer_style_fallback_default(
        mode=run_mode,
        requested=allow_style_fallback,
    )
    execute_llm = _multi_optimizer_execute_llm_default(
        mode=run_mode,
        requested=execute_llm,
        endpoint_configured=bool(optimizer_base_url or llm_completion_fn),
    )
    source_names = _multi_optimizer_source_names(optimizer_sources)
    if not source_names:
        raise ValueError("optimizer_sources must not be empty")
    context_payload, context_path = _load_object(context)
    output_root = Path(output_dir) if output_dir is not None else None
    if output_root is not None:
        output_root.mkdir(parents=True, exist_ok=True)
    source_root = output_root / "sources" if output_root else None
    if source_root is not None:
        source_root.mkdir(parents=True, exist_ok=True)
    requested_workers = max_workers or len(source_names)
    worker_count = max(1, min(len(source_names), int(requested_workers)))

    source_results_by_name: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(
                _run_multi_optimizer_candidate_source,
                source_name=source_name,
                source_index=index,
                objective=objective,
                context=context_payload,
                mode=run_mode,
                operators=operators,
                direction=direction,
                max_candidates=max_candidates_per_source,
                execute_llm=execute_llm,
                llm_proposals=llm_proposals,
                llm_completion_fn=llm_completion_fn,
                gate_feedback_memory=gate_feedback_memory,
                execute_optimizer_runtimes=execute_optimizer_runtimes,
                allow_style_fallback=allow_style_fallback,
                optimizer_gate_plugin_manifests=optimizer_gate_plugin_manifests,
                optimizer_model=optimizer_model,
                optimizer_base_url=optimizer_base_url,
                optimizer_api_key=optimizer_api_key,
                optimizer_timeout_seconds=optimizer_timeout_seconds,
                optimizer_temperature=optimizer_temperature,
                optimizer_max_tokens=optimizer_max_tokens,
                output_dir=source_root / source_name if source_root else None,
                overwrite=overwrite,
            ): source_name
            for index, source_name in enumerate(source_names, start=1)
        }
        for future in as_completed(futures):
            source_name = futures[future]
            source_results_by_name[source_name] = future.result()

    source_rows = [source_results_by_name[source_name] for source_name in source_names]
    generated_sources = {
        "schema_version": MULTI_OPTIMIZER_CANDIDATE_RACE_RUN_SCHEMA_VERSION,
        "sources": source_rows,
        "official_scores_claimed": False,
    }
    generated_sources_path = (
        output_root / "generated-candidate-sources.json" if output_root else None
    )
    _method_search_write_payload(
        generated_sources,
        output_path=generated_sources_path,
        overwrite=overwrite,
    )
    _, candidate_pool, _ = _multi_optimizer_candidate_sources(generated_sources)
    generation_trace_path = (
        output_root / "multi-optimizer-generation-trace.json" if output_root else None
    )
    generation_trace = build_method_proposal_generation_trace(
        generation_context={
            "trigger": "multi_optimizer_candidate_race",
            "mode": run_mode,
            "objective": objective,
            "context_ref": str(context_path) if context_path is not None else "inline",
            "optimizer_sources": source_names,
            "parallel_worker_count": worker_count,
            "claim_boundary": {
                "evidence_scope": "local_candidate_generation_only",
                "official_scores_claimed": False,
            },
        },
        generation_run={
            "generator": "MultiOptimizerCandidateRace",
            "mode": run_mode,
            "source_count": len(source_rows),
            "execute_llm": execute_llm,
            "execute_optimizer_runtimes": execute_optimizer_runtimes,
            "allow_style_fallback": allow_style_fallback,
            "max_candidates_per_source": max_candidates_per_source,
            "uses_prior_gate_feedback_memory": gate_feedback_memory is not None,
        },
        reasoning_trace=_multi_optimizer_generation_reasoning_trace(source_rows),
        proposals=candidate_pool,
        ranking_decisions=_multi_optimizer_generation_ranking_decisions(candidate_pool),
        selected_proposal_ids=[
            str(candidate["proposal_id"]) for candidate in candidate_pool
        ],
        output_path=generation_trace_path,
        overwrite=overwrite,
    )

    race_payload: dict[str, Any] | None = None
    if candidate_pool:
        race_dir = output_root / "race" if output_root else None
        race_output_path = (
            race_dir / "multi-optimizer-candidate-race.json" if race_dir else None
        )
        if race_dir is not None:
            race_dir.mkdir(parents=True, exist_ok=True)
        race_payload = build_multi_optimizer_candidate_race(
            race_name=race_name,
            objective=objective,
            candidate_sources=generated_sources_path or generated_sources,
            gate_results=gate_results,
            operators=operators,
            direction=direction,
            model="multi-optimizer-candidate-race-run",
            adapter="multi-optimizer-candidate-race-run",
            slice_id="multi_optimizer_race",
            patch_scope="multi_optimizer_candidate",
            budget={
                "max_candidates_per_source": max_candidates_per_source,
                "source_count": len(source_rows),
                "parallel_worker_count": worker_count,
            },
            output_dir=race_dir,
            feedback_store_path=feedback_store_path,
            output_path=race_output_path,
            overwrite=overwrite,
        )
    blocked_sources = [
        source
        for source in source_rows
        if source.get("status") in {"blocked", "source_failed"}
    ]
    fallback_sources = [
        source for source in source_rows if bool(source.get("fallback_used", False))
    ]
    real_optimizer_candidate_count = _multi_optimizer_real_candidate_count(candidate_pool)
    fallback_candidate_count = _multi_optimizer_fallback_candidate_count(candidate_pool)
    diagnostic_candidate_count = max(
        0,
        len(candidate_pool) - real_optimizer_candidate_count,
    )
    winner = _multi_optimizer_run_winner(
        race_payload=race_payload,
        candidate_pool=candidate_pool,
    )
    if isinstance(race_payload, dict):
        race_payload["winner"] = winner
    payload = {
        "status": _multi_optimizer_run_status(
            race_payload=race_payload,
            candidate_count=len(candidate_pool),
            blocked_source_count=len(blocked_sources),
        ),
        "schema_version": MULTI_OPTIMIZER_CANDIDATE_RACE_RUN_SCHEMA_VERSION,
        "mode": run_mode,
        "race_name": race_name,
        "objective": objective,
        "direction": direction,
        "optimizer_sources_requested": source_names,
        "parallel_worker_count": worker_count,
        "source_generation": {
            "source_count": len(source_rows),
            "generated_candidate_count": len(candidate_pool),
            "real_optimizer_candidate_count": real_optimizer_candidate_count,
            "fallback_candidate_count": fallback_candidate_count,
            "diagnostic_candidate_count": diagnostic_candidate_count,
            "blocked_source_count": len(blocked_sources),
            "fallback_source_count": len(fallback_sources),
            "sources": source_rows,
        },
        "candidate_sources": generated_sources,
        "candidate_pool": candidate_pool,
        "generation_trace": generation_trace,
        "race": race_payload,
        "winner": winner,
        "gate_feedback_memory": (
            race_payload.get("gate_feedback_memory")
            if isinstance(race_payload, dict)
            else {}
        ),
        "acceptance_answers": _multi_optimizer_run_acceptance_answers(
            source_rows=source_rows,
            candidate_pool=candidate_pool,
            race_payload=race_payload,
            mode=run_mode,
            execute_optimizer_runtimes=execute_optimizer_runtimes,
            allow_style_fallback=allow_style_fallback,
        ),
        "artifact_refs": _method_search_artifact_refs(
            context_path=context_path,
            generated_sources_path=generated_sources_path,
            generation_trace_path=generation_trace_path,
            race_path=(
                Path(race_payload["output_path"])
                if isinstance(race_payload, dict)
                and _string_value(race_payload.get("output_path"))
                else None
            ),
            feedback_store_path=Path(feedback_store_path)
            if feedback_store_path is not None
            else None,
        ),
        "claim_boundary": {
            "evidence_scope": "local_gate_only",
            "llm_may_claim_improvement": False,
            "optimizer_may_claim_improvement": False,
            "official_scores_claimed": False,
        },
        "executes_tool": any(bool(source.get("executes_tool")) for source in source_rows),
        "executes_optimizer_runtime": any(
            bool(source.get("executes_optimizer_runtime")) for source in source_rows
        ),
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    _method_search_write_payload(payload, output_path=output_path, overwrite=overwrite)
    return payload


def run_method_search_trajectory(
    *,
    trajectory_name: str,
    objective: str,
    context: dict[str, Any] | str | Path,
    gate_results_by_round: list[dict[str, Any]] | dict[str, Any] | str | Path,
    round_count: int = 4,
    mode: str = "optimization-run",
    optimizer_sources: list[str] | None = None,
    operators: list[str | dict[str, Any]] | None = None,
    direction: str = "maximize",
    max_candidates_per_source: int = 1,
    llm_proposals_by_round: (
        list[dict[str, Any]] | dict[str, Any] | str | Path | None
    ) = None,
    llm_completion_fn: Callable[..., dict[str, Any]] | None = None,
    execute_llm: bool | None = None,
    execute_optimizer_runtimes: bool | None = None,
    allow_style_fallback: bool | None = None,
    optimizer_gate_plugin_manifests: list[dict[str, Any] | str | Path] | None = None,
    optimizer_model: str | None = None,
    optimizer_base_url: str | None = None,
    optimizer_api_key: str | None = None,
    optimizer_timeout_seconds: int = 30,
    optimizer_temperature: float = 0.0,
    optimizer_max_tokens: int = 512,
    output_dir: str | Path | None = None,
    feedback_store_path: str | Path | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
    max_workers: int | None = None,
) -> dict[str, Any]:
    """Run 3-5 gate-feedbacked multi-optimizer races as one search trajectory."""
    if not trajectory_name:
        raise ValueError("trajectory_name is required")
    if not objective:
        raise ValueError("objective is required")
    total_rounds = int(round_count)
    if total_rounds < 3 or total_rounds > 5:
        raise ValueError("round_count must be between 3 and 5")

    context_payload, context_path = _load_object(context)
    gate_rounds = _method_search_trajectory_round_payloads(
        gate_results_by_round,
        list_keys=("gate_results", "results", "validation_links", "outcomes"),
    )
    if len(gate_rounds) < total_rounds:
        raise ValueError("gate_results_by_round must provide at least round_count rounds")
    llm_rounds = _method_search_trajectory_round_payloads(
        llm_proposals_by_round,
        list_keys=("proposals", "candidate_pool", "candidates", "ranked_proposals"),
    )
    output_root = Path(output_dir) if output_dir is not None else None
    if output_root is not None:
        output_root.mkdir(parents=True, exist_ok=True)
    memory_store_path = (
        Path(feedback_store_path)
        if feedback_store_path is not None
        else (output_root / "gate-feedback-memory-store.json" if output_root else None)
    )
    base_operator_ids = _method_search_trajectory_operator_ids(operators)
    current_memory: dict[str, Any] | None = None
    cumulative_gate_results: list[dict[str, Any]] = []
    round_summaries: list[dict[str, Any]] = []
    round_winners: list[dict[str, Any]] = []
    real_optimizer_candidate_count = 0
    fallback_candidate_count = 0
    diagnostic_candidate_count = 0
    blocked_source_count = 0

    for round_number in range(1, total_rounds + 1):
        memory_before = current_memory or build_gate_feedback_memory(
            gate_results=[],
            operators=base_operator_ids,
        )
        round_dir = (
            output_root / f"round-{round_number:03d}" if output_root is not None else None
        )
        if round_dir is not None:
            round_dir.mkdir(parents=True, exist_ok=True)
        round_operators = _method_search_trajectory_operator_order(
            operators=operators,
            memory=memory_before,
        )
        round_payload = run_multi_optimizer_candidate_race(
            race_name=f"{trajectory_name}-round-{round_number:03d}",
            objective=objective,
            context=context_payload,
            gate_results=gate_rounds[round_number - 1],
            mode=mode,
            optimizer_sources=optimizer_sources,
            operators=round_operators,
            direction=direction,
            max_candidates_per_source=max_candidates_per_source,
            execute_llm=execute_llm,
            llm_proposals=(
                llm_rounds[round_number - 1]
                if round_number - 1 < len(llm_rounds)
                else None
            ),
            llm_completion_fn=llm_completion_fn,
            gate_feedback_memory=memory_before,
            execute_optimizer_runtimes=execute_optimizer_runtimes,
            allow_style_fallback=allow_style_fallback,
            optimizer_gate_plugin_manifests=optimizer_gate_plugin_manifests,
            optimizer_model=optimizer_model,
            optimizer_base_url=optimizer_base_url,
            optimizer_api_key=optimizer_api_key,
            optimizer_timeout_seconds=optimizer_timeout_seconds,
            optimizer_temperature=optimizer_temperature,
            optimizer_max_tokens=optimizer_max_tokens,
            output_dir=round_dir,
            feedback_store_path=memory_store_path,
            output_path=(
                round_dir / "multi-optimizer-candidate-race-run.json"
                if round_dir is not None
                else None
            ),
            overwrite=overwrite,
            max_workers=max_workers,
        )
        round_gate_results = _method_search_trajectory_gate_results(round_payload)
        cumulative_gate_results.extend(round_gate_results)
        memory_after_path = (
            round_dir / "cumulative-gate-feedback-memory.json"
            if round_dir is not None
            else None
        )
        memory_after = build_gate_feedback_memory(
            gate_results=cumulative_gate_results,
            operators=base_operator_ids,
            output_path=memory_after_path,
            overwrite=overwrite,
        )
        if memory_store_path is not None:
            persist_gate_feedback_memory_store(
                gate_feedback_memory=memory_after,
                study=_method_search_trajectory_race_study(round_payload),
                gate_result={"gate_results": cumulative_gate_results},
                output_path=memory_store_path,
            )
        current_memory = memory_after

        source_generation = (
            round_payload.get("source_generation")
            if isinstance(round_payload.get("source_generation"), dict)
            else {}
        )
        real_optimizer_candidate_count += int(
            source_generation.get("real_optimizer_candidate_count") or 0
        )
        fallback_candidate_count += int(
            source_generation.get("fallback_candidate_count") or 0
        )
        diagnostic_candidate_count += int(
            source_generation.get("diagnostic_candidate_count") or 0
        )
        blocked_source_count += int(source_generation.get("blocked_source_count") or 0)
        winner = (
            round_payload.get("winner")
            if isinstance(round_payload.get("winner"), dict)
            else None
        )
        if winner is not None:
            round_winners.append({
                **winner,
                "round_number": round_number,
                "round_ref": _string_value(round_payload.get("output_path")),
            })
        round_summaries.append(
            _method_search_trajectory_round_summary(
                round_number=round_number,
                round_payload=round_payload,
                memory_before=memory_before,
                memory_after=memory_after,
            )
        )

    best_path = _method_search_trajectory_best_path(
        round_winners=round_winners,
        direction=direction,
    )
    payload = {
        "status": (
            "completed" if best_path.get("winner") else "completed_without_gate_winner"
        ),
        "schema_version": METHOD_SEARCH_TRAJECTORY_SCHEMA_VERSION,
        "trajectory_name": trajectory_name,
        "objective": objective,
        "mode": _multi_optimizer_run_mode(mode),
        "direction": direction,
        "round_count": len(round_summaries),
        "optimizer_sources_requested": _multi_optimizer_source_names(optimizer_sources),
        "rounds": round_summaries,
        "round_winners": round_winners,
        "best_path": best_path,
        "real_optimizer_candidate_count": real_optimizer_candidate_count,
        "fallback_candidate_count": fallback_candidate_count,
        "diagnostic_candidate_count": diagnostic_candidate_count,
        "blocked_source_count": blocked_source_count,
        "gate_feedback_memory": current_memory or {},
        "acceptance_answers": _method_search_trajectory_acceptance_answers(
            rounds=round_summaries,
            best_path=best_path,
            real_optimizer_candidate_count=real_optimizer_candidate_count,
            fallback_candidate_count=fallback_candidate_count,
        ),
        "artifact_refs": _method_search_artifact_refs(
            context_path=context_path,
            feedback_store_path=memory_store_path,
        ),
        "claim_boundary": {
            "evidence_scope": "local_gate_only",
            "llm_may_claim_improvement": False,
            "optimizer_may_claim_improvement": False,
            "official_scores_claimed": False,
        },
        "executes_tool": any(bool(item.get("executes_tool")) for item in round_summaries),
        "executes_optimizer_runtime": any(
            bool(item.get("executes_optimizer_runtime")) for item in round_summaries
        ),
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    _method_search_write_payload(payload, output_path=output_path, overwrite=overwrite)
    return payload


def run_real_benchmark_readiness_run(
    *,
    run_name: str,
    objective: str,
    rows: list[dict[str, Any]] | dict[str, Any] | str | Path,
    benchmark_id: str = "smol_worldcup",
    context: dict[str, Any] | str | Path | None = None,
    round_count: int = 3,
    mode: str = "optimization-run",
    optimizer_sources: list[str] | None = None,
    operators: list[str | dict[str, Any]] | None = None,
    direction: str = "maximize",
    max_candidates_per_source: int = 1,
    llm_proposals_by_round: (
        list[dict[str, Any]] | dict[str, Any] | str | Path | None
    ) = None,
    llm_completion_fn: Callable[..., dict[str, Any]] | None = None,
    execute_llm: bool | None = None,
    execute_optimizer_runtimes: bool | None = None,
    allow_style_fallback: bool | None = None,
    optimizer_gate_plugin_manifests: list[dict[str, Any] | str | Path] | None = None,
    optimizer_model: str | None = None,
    optimizer_base_url: str | None = None,
    optimizer_api_key: str | None = None,
    optimizer_timeout_seconds: int = 30,
    optimizer_temperature: float = 0.0,
    optimizer_max_tokens: int = 512,
    chat_completion: Callable[..., dict[str, Any]] | None = None,
    model: str = "openai/gpt-oss-20b",
    base_url: str = "http://127.0.0.1:8000/v1",
    model_provider: str = "openai-compatible",
    api_key_env: str | None = None,
    timeout_seconds: int = 120,
    temperature: float = 0.0,
    max_tokens: int = 512,
    judge_mode: str = "heuristic",
    canary_fraction: float = 0.25,
    gate_metric: str = "SHIFT",
    min_dev_delta: float = 0.0,
    min_canary_delta: float = 0.0,
    output_dir: str | Path | None = None,
    feedback_store_path: str | Path | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run optimizer races whose gate results come from local benchmark evals."""
    if not run_name:
        raise ValueError("run_name is required")
    if not objective:
        raise ValueError("objective is required")
    normalized_benchmark = benchmark_id.strip().lower().replace("-", "_")
    if normalized_benchmark != "smol_worldcup":
        raise ValueError("only smol_worldcup is supported for readiness runs")
    total_rounds = int(round_count)
    if total_rounds < 3 or total_rounds > 5:
        raise ValueError("round_count must be between 3 and 5")

    run_mode = _multi_optimizer_run_mode(mode)
    rows_payload, rows_path = _real_benchmark_readiness_rows(rows)
    context_payload, context_path = (
        _load_object(context)
        if context is not None
        else (_real_benchmark_readiness_default_context(rows_payload), None)
    )
    output_root = Path(output_dir) if output_dir is not None else None
    if output_root is not None:
        output_root.mkdir(parents=True, exist_ok=True)
    memory_store_path = (
        Path(feedback_store_path)
        if feedback_store_path is not None
        else (output_root / "gate-feedback-memory-store.json" if output_root else None)
    )
    source_names = _multi_optimizer_source_names(optimizer_sources)
    base_operator_ids = _method_search_trajectory_operator_ids(operators)
    llm_rounds = _method_search_trajectory_round_payloads(
        llm_proposals_by_round,
        list_keys=("proposals", "candidate_pool", "candidates", "ranked_proposals"),
    )
    execute_optimizer_runtimes = _multi_optimizer_execute_runtime_default(
        mode=run_mode,
        requested=execute_optimizer_runtimes,
    )
    allow_style_fallback = _multi_optimizer_style_fallback_default(
        mode=run_mode,
        requested=allow_style_fallback,
    )
    execute_llm = _multi_optimizer_execute_llm_default(
        mode=run_mode,
        requested=execute_llm,
        endpoint_configured=bool(optimizer_base_url or llm_completion_fn),
    )

    baseline_dir = output_root / "baseline" if output_root else None
    if baseline_dir is not None:
        baseline_dir.mkdir(parents=True, exist_ok=True)
    baseline_dev = _real_benchmark_readiness_smol_eval(
        rows=rows_payload,
        chat_completion=chat_completion,
        round_id=f"{run_name}-baseline-dev",
        evaluation_split="dev",
        prompt_profile_registration=None,
        canary_fraction=canary_fraction,
        model=model,
        base_url=base_url,
        model_provider=model_provider,
        api_key_env=api_key_env,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
        max_tokens=max_tokens,
        judge_mode=judge_mode,
        output_path=baseline_dir / "dev-eval.json" if baseline_dir else None,
        overwrite=overwrite,
    )
    baseline_canary = _real_benchmark_readiness_smol_eval(
        rows=rows_payload,
        chat_completion=chat_completion,
        round_id=f"{run_name}-baseline-canary",
        evaluation_split="canary",
        prompt_profile_registration=None,
        canary_fraction=canary_fraction,
        model=model,
        base_url=base_url,
        model_provider=model_provider,
        api_key_env=api_key_env,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
        max_tokens=max_tokens,
        judge_mode=judge_mode,
        output_path=baseline_dir / "canary-eval.json" if baseline_dir else None,
        overwrite=overwrite,
    )

    current_memory: dict[str, Any] | None = None
    cumulative_gate_results: list[dict[str, Any]] = []
    round_summaries: list[dict[str, Any]] = []
    round_winners: list[dict[str, Any]] = []
    real_optimizer_candidate_count = 0
    fallback_candidate_count = 0
    diagnostic_candidate_count = 0
    blocked_source_count = 0
    real_eval_outcome_count = 0

    for round_number in range(1, total_rounds + 1):
        memory_before = current_memory or build_gate_feedback_memory(
            gate_results=[],
            operators=base_operator_ids,
        )
        round_dir = (
            output_root / f"round-{round_number:03d}" if output_root is not None else None
        )
        if round_dir is not None:
            round_dir.mkdir(parents=True, exist_ok=True)
        round_operators = _method_search_trajectory_operator_order(
            operators=operators,
            memory=memory_before,
        )
        source_rows = []
        source_root = round_dir / "sources" if round_dir is not None else None
        if source_root is not None:
            source_root.mkdir(parents=True, exist_ok=True)
        for source_index, source_name in enumerate(source_names, start=1):
            source_rows.append(
                _run_multi_optimizer_candidate_source(
                    source_name=source_name,
                    source_index=source_index,
                    objective=objective,
                    context=context_payload,
                    mode=run_mode,
                    operators=round_operators,
                    direction=direction,
                    max_candidates=max_candidates_per_source,
                    execute_llm=execute_llm,
                    llm_proposals=(
                        llm_rounds[round_number - 1]
                        if round_number - 1 < len(llm_rounds)
                        else None
                    ),
                    llm_completion_fn=llm_completion_fn,
                    gate_feedback_memory=memory_before,
                    execute_optimizer_runtimes=execute_optimizer_runtimes,
                    allow_style_fallback=allow_style_fallback,
                    optimizer_gate_plugin_manifests=optimizer_gate_plugin_manifests,
                    optimizer_model=optimizer_model,
                    optimizer_base_url=optimizer_base_url,
                    optimizer_api_key=optimizer_api_key,
                    optimizer_timeout_seconds=optimizer_timeout_seconds,
                    optimizer_temperature=optimizer_temperature,
                    optimizer_max_tokens=optimizer_max_tokens,
                    output_dir=source_root / source_name if source_root else None,
                    overwrite=overwrite,
                )
            )
        generated_sources = {
            "schema_version": MULTI_OPTIMIZER_CANDIDATE_RACE_RUN_SCHEMA_VERSION,
            "sources": source_rows,
            "official_scores_claimed": False,
        }
        generated_sources_path = (
            round_dir / "generated-candidate-sources.json" if round_dir else None
        )
        _method_search_write_payload(
            generated_sources,
            output_path=generated_sources_path,
            overwrite=overwrite,
        )
        _, candidate_pool, _ = _multi_optimizer_candidate_sources(generated_sources)
        round_gate_results: list[dict[str, Any]] = []
        candidate_eval_records: list[dict[str, Any]] = []
        eval_root = round_dir / "candidate-evals" if round_dir else None
        if eval_root is not None:
            eval_root.mkdir(parents=True, exist_ok=True)
        for candidate in candidate_pool:
            gate_result, eval_record = _real_benchmark_readiness_gate_candidate(
                candidate=candidate,
                rows=rows_payload,
                baseline_dev=baseline_dev,
                baseline_canary=baseline_canary,
                gate_metric=gate_metric,
                min_dev_delta=min_dev_delta,
                min_canary_delta=min_canary_delta,
                chat_completion=chat_completion,
                run_name=run_name,
                round_number=round_number,
                canary_fraction=canary_fraction,
                model=model,
                base_url=base_url,
                model_provider=model_provider,
                api_key_env=api_key_env,
                timeout_seconds=timeout_seconds,
                temperature=temperature,
                max_tokens=max_tokens,
                judge_mode=judge_mode,
                output_dir=(
                    eval_root / str(candidate.get("proposal_id"))
                    if eval_root is not None
                    else None
                ),
                overwrite=overwrite,
            )
            round_gate_results.append(gate_result)
            candidate_eval_records.append(eval_record)
        real_eval_outcome_count += sum(
            1
            for item in candidate_eval_records
            if item.get("status") == "evaluated"
            and bool(item.get("counts_as_real_optimizer_candidate", False))
        )
        gate_results_path = round_dir / "gate-results-from-eval.json" if round_dir else None
        gate_results_payload = {
            "gate_results": round_gate_results,
            "source": "real_benchmark_eval_outcomes",
            "benchmark_id": normalized_benchmark,
            "official_scores_claimed": False,
        }
        _method_search_write_payload(
            gate_results_payload,
            output_path=gate_results_path,
            overwrite=overwrite,
        )
        race_dir = round_dir / "race" if round_dir else None
        if race_dir is not None:
            race_dir.mkdir(parents=True, exist_ok=True)
        race_payload = build_multi_optimizer_candidate_race(
            race_name=f"{run_name}-round-{round_number:03d}",
            objective=objective,
            candidate_sources=generated_sources_path or generated_sources,
            gate_results=gate_results_path or gate_results_payload,
            operators=round_operators,
            direction=direction,
            model="real-benchmark-readiness-run",
            adapter="real-benchmark-eval-gate",
            slice_id="smol_worldcup_readiness",
            patch_scope="prompt_profile_registration_overlay",
            budget={
                "round_number": round_number,
                "max_candidates_per_source": max_candidates_per_source,
                "gate_metric": gate_metric,
            },
            output_dir=race_dir,
            feedback_store_path=memory_store_path,
            output_path=(
                race_dir / "multi-optimizer-candidate-race.json"
                if race_dir is not None
                else None
            ),
            overwrite=overwrite,
        )
        winner = _multi_optimizer_run_winner(
            race_payload=race_payload,
            candidate_pool=candidate_pool,
        )
        if winner is not None:
            race_payload["winner"] = winner
            round_winners.append({
                **winner,
                "round_number": round_number,
                "round_ref": _string_value(race_payload.get("output_path")),
            })
        cumulative_gate_results.extend(
            _method_search_gate_results_from_trials(
                [item for item in race_payload.get("trials", []) if isinstance(item, dict)]
            )
        )
        memory_after = build_gate_feedback_memory(
            gate_results=cumulative_gate_results,
            operators=base_operator_ids,
            output_path=(
                round_dir / "cumulative-gate-feedback-memory.json"
                if round_dir is not None
                else None
            ),
            overwrite=overwrite,
        )
        if memory_store_path is not None:
            persist_gate_feedback_memory_store(
                gate_feedback_memory=memory_after,
                study=(
                    race_payload.get("study")
                    if isinstance(race_payload.get("study"), dict)
                    else {"study_name": run_name, "trials": []}
                ),
                gate_result={"gate_results": cumulative_gate_results},
                output_path=memory_store_path,
            )
        current_memory = memory_after
        source_generation = {
            "source_count": len(source_rows),
            "generated_candidate_count": len(candidate_pool),
            "real_optimizer_candidate_count": _multi_optimizer_real_candidate_count(
                candidate_pool
            ),
            "fallback_candidate_count": _multi_optimizer_fallback_candidate_count(
                candidate_pool
            ),
            "diagnostic_candidate_count": max(
                0,
                len(candidate_pool) - _multi_optimizer_real_candidate_count(candidate_pool),
            ),
            "blocked_source_count": sum(
                1 for source in source_rows if source.get("status") in {"blocked", "source_failed"}
            ),
            "sources": source_rows,
        }
        real_optimizer_candidate_count += int(
            source_generation["real_optimizer_candidate_count"]
        )
        fallback_candidate_count += int(source_generation["fallback_candidate_count"])
        diagnostic_candidate_count += int(source_generation["diagnostic_candidate_count"])
        blocked_source_count += int(source_generation["blocked_source_count"])
        memory_delta = _method_search_direction_change(
            _method_search_trajectory_weights(memory_before, operator_ids=base_operator_ids),
            _method_search_trajectory_weights(memory_after, operator_ids=base_operator_ids),
        )
        round_summaries.append({
            "round_number": round_number,
            "status": "completed" if winner else "completed_without_gate_winner",
            "mode": run_mode,
            "race_ref": _string_value(race_payload.get("output_path")),
            "generated_sources_ref": str(generated_sources_path) if generated_sources_path else None,
            "gate_results_ref": str(gate_results_path) if gate_results_path else None,
            "used_operators": _method_search_trajectory_used_operators({"race": race_payload}),
            "optimizer_sources_tried": source_names,
            "source_summary": source_generation,
            "gate_results": round_gate_results,
            "candidate_evals": candidate_eval_records,
            "proposal_selection": _multi_optimizer_race_acceptance_answers(
                candidate_sources=source_rows,
                candidate_pool=candidate_pool,
                winner=winner,
                study=(
                    race_payload.get("study")
                    if isinstance(race_payload.get("study"), dict)
                    else {}
                ),
                missing_gate_proposal_ids=[],
            )["proposal_selection"],
            "winner": winner,
            "memory_delta": memory_delta,
            "baseline_dev_score": _real_benchmark_readiness_metric_score(
                baseline_dev,
                gate_metric,
            ),
            "baseline_canary_score": _real_benchmark_readiness_metric_score(
                baseline_canary,
                gate_metric,
            ),
            "official_scores_claimed": False,
        })

    best_path = _method_search_trajectory_best_path(
        round_winners=round_winners,
        direction=direction,
    )
    payload = {
        "status": "completed" if best_path.get("winner") else "completed_without_gate_winner",
        "schema_version": REAL_BENCHMARK_READINESS_RUN_SCHEMA_VERSION,
        "run_name": run_name,
        "benchmark_id": normalized_benchmark,
        "objective": objective,
        "mode": run_mode,
        "direction": direction,
        "round_count": len(round_summaries),
        "optimizer_sources_requested": source_names,
        "baseline": {
            "dev": _real_benchmark_readiness_eval_summary(baseline_dev),
            "canary": _real_benchmark_readiness_eval_summary(baseline_canary),
        },
        "rounds": round_summaries,
        "round_winners": round_winners,
        "best_path": best_path,
        "real_optimizer_candidate_count": real_optimizer_candidate_count,
        "fallback_candidate_count": fallback_candidate_count,
        "diagnostic_candidate_count": diagnostic_candidate_count,
        "blocked_source_count": blocked_source_count,
        "real_eval_outcome_count": real_eval_outcome_count,
        "gate_feedback_memory": current_memory or {},
        "acceptance_answers": _real_benchmark_readiness_acceptance_answers(
            baseline_dev=baseline_dev,
            baseline_canary=baseline_canary,
            rounds=round_summaries,
            best_path=best_path,
            real_optimizer_candidate_count=real_optimizer_candidate_count,
            real_eval_outcome_count=real_eval_outcome_count,
            memory=current_memory or {},
        ),
        "artifact_refs": _method_search_artifact_refs(
            context_path=context_path,
            rows_path=rows_path,
            feedback_store_path=memory_store_path,
        ),
        "claim_boundary": {
            "evidence_scope": "local_benchmark_readiness_run",
            "local_benchmark_eval_executed": True,
            "executes_official_submission": False,
            "llm_may_claim_improvement": False,
            "optimizer_may_claim_improvement": False,
            "official_scores_claimed": False,
        },
        "executes_tool": any(
            bool(source.get("executes_tool"))
            for item in round_summaries
            for source in _dict_list(item.get("source_summary", {}).get("sources"))
        ),
        "executes_optimizer_runtime": any(
            bool(source.get("executes_optimizer_runtime"))
            for item in round_summaries
            for source in _dict_list(item.get("source_summary", {}).get("sources"))
        ),
        "executes_experiment": True,
        "executes_official_submission": False,
        "official_scores_claimed": False,
    }
    _method_search_write_payload(payload, output_path=output_path, overwrite=overwrite)
    return payload


def _real_benchmark_readiness_rows(
    value: list[dict[str, Any]] | dict[str, Any] | str | Path,
) -> tuple[list[dict[str, Any]], Path | None]:
    if isinstance(value, list):
        rows = [dict(item) for item in value if isinstance(item, dict)]
        if not rows:
            raise ValueError("rows must not be empty")
        return rows, None
    if isinstance(value, dict):
        for key in ("rows", "dataset_rows", "items"):
            if isinstance(value.get(key), list):
                rows = [dict(item) for item in value[key] if isinstance(item, dict)]
                if not rows:
                    raise ValueError("rows must not be empty")
                return rows, None
        raise ValueError("rows object must contain a rows list")
    path = Path(value)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        rows = [dict(item) for item in payload if isinstance(item, dict)]
    elif isinstance(payload, dict):
        rows = []
        for key in ("rows", "dataset_rows", "items"):
            if isinstance(payload.get(key), list):
                rows = [dict(item) for item in payload[key] if isinstance(item, dict)]
                break
    else:
        rows = []
    if not rows:
        raise ValueError(f"expected non-empty rows in {path}")
    return rows, path


def _real_benchmark_readiness_default_context(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    first_row = rows[0] if rows else {}
    return {
        "schema_version": "2026-06-27.real-benchmark-readiness-context.v1",
        "recommended_patch_contract": {
            "module_id": "smol_worldcup_prompt",
            "section_id": "local_benchmark_readiness",
            "target_slice": _string_value(first_row.get("category")) or "mixed",
            "based_on_slices": [
                _string_value(first_row.get("category")) or "mixed"
            ],
            "before_text": "Improve answer discipline for the target benchmark slice.",
            "protected_slices": ["canary"],
            "protected_sections": ["output_contract"],
        },
        "official_scores_claimed": False,
    }


def _real_benchmark_readiness_smol_eval(
    *,
    rows: list[dict[str, Any]],
    chat_completion: Callable[..., dict[str, Any]] | None,
    round_id: str,
    evaluation_split: str,
    prompt_profile_registration: dict[str, Any] | str | Path | None,
    canary_fraction: float,
    model: str,
    base_url: str,
    model_provider: str,
    api_key_env: str | None,
    timeout_seconds: int,
    temperature: float,
    max_tokens: int,
    judge_mode: str,
    output_path: str | Path | None,
    overwrite: bool,
) -> dict[str, Any]:
    payload = build_smol_worldcup_model_eval(
        fetcher=_smol_worldcup_rows_fetcher(rows),
        chat_completion=chat_completion,
        timeout_seconds=timeout_seconds,
        page_size=min(max(len(rows), 1), 100),
        limit=len(rows),
        model=model,
        base_url=base_url,
        model_provider=model_provider,
        api_key_env=api_key_env,
        temperature=temperature,
        max_tokens=max_tokens,
        round_id=round_id,
        prompt_profile="default",
        prompt_profile_registration=prompt_profile_registration,
        evaluation_split=evaluation_split,
        canary_fraction=canary_fraction,
        judge_mode=judge_mode,
    )
    _method_search_write_payload(payload, output_path=output_path, overwrite=overwrite)
    return payload


def _real_benchmark_readiness_gate_candidate(
    *,
    candidate: dict[str, Any],
    rows: list[dict[str, Any]],
    baseline_dev: dict[str, Any],
    baseline_canary: dict[str, Any],
    gate_metric: str,
    min_dev_delta: float,
    min_canary_delta: float,
    chat_completion: Callable[..., dict[str, Any]] | None,
    run_name: str,
    round_number: int,
    canary_fraction: float,
    model: str,
    base_url: str,
    model_provider: str,
    api_key_env: str | None,
    timeout_seconds: int,
    temperature: float,
    max_tokens: int,
    judge_mode: str,
    output_dir: Path | None,
    overwrite: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    proposal_id = _string_value(candidate.get("proposal_id")) or "candidate"
    operator_id = _string_value(candidate.get("operator_id")) or "unknown"
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
    after_text = _real_benchmark_readiness_candidate_after_text(candidate)
    counts_as_real = bool(candidate.get("counts_as_real_optimizer_candidate", False))
    if not counts_as_real or not after_text:
        hard_blockers = []
        if not counts_as_real:
            hard_blockers.append("candidate_not_from_real_optimizer_runtime")
        if not after_text:
            hard_blockers.append("candidate_missing_materialized_prompt_change")
        gate_result = {
            "proposal_id": proposal_id,
            "operator_id": operator_id,
            "status": "blocked",
            "score": _real_benchmark_readiness_metric_score(baseline_dev, gate_metric),
            "metric_delta": {gate_metric: 0.0},
            "hard_blockers": hard_blockers,
            "eval_outcome": {
                "status": "not_evaluated",
                "reason": "blocked_before_benchmark_eval",
                "official_scores_claimed": False,
            },
            "official_scores_claimed": False,
        }
        return gate_result, {
            "proposal_id": proposal_id,
            "status": "not_evaluated",
            "hard_blockers": hard_blockers,
            "counts_as_real_optimizer_candidate": counts_as_real,
            "official_scores_claimed": False,
        }
    registration = _real_benchmark_readiness_candidate_registration(
        candidate=candidate,
        run_name=run_name,
        round_number=round_number,
        after_text=after_text,
    )
    registration_path = output_dir / "prompt-profile-registration.json" if output_dir else None
    _method_search_write_payload(
        registration,
        output_path=registration_path,
        overwrite=overwrite,
    )
    dev_eval = _real_benchmark_readiness_smol_eval(
        rows=rows,
        chat_completion=chat_completion,
        round_id=f"{run_name}-round-{round_number:03d}-{proposal_id}-dev",
        evaluation_split="dev",
        prompt_profile_registration=registration,
        canary_fraction=canary_fraction,
        model=model,
        base_url=base_url,
        model_provider=model_provider,
        api_key_env=api_key_env,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
        max_tokens=max_tokens,
        judge_mode=judge_mode,
        output_path=output_dir / "dev-eval.json" if output_dir else None,
        overwrite=overwrite,
    )
    canary_eval = _real_benchmark_readiness_smol_eval(
        rows=rows,
        chat_completion=chat_completion,
        round_id=f"{run_name}-round-{round_number:03d}-{proposal_id}-canary",
        evaluation_split="canary",
        prompt_profile_registration=registration,
        canary_fraction=canary_fraction,
        model=model,
        base_url=base_url,
        model_provider=model_provider,
        api_key_env=api_key_env,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
        max_tokens=max_tokens,
        judge_mode=judge_mode,
        output_path=output_dir / "canary-eval.json" if output_dir else None,
        overwrite=overwrite,
    )
    dev_delta = _real_benchmark_readiness_metric_delta(
        dev_eval.get("metrics"),
        baseline_dev.get("metrics"),
    )
    canary_delta = _real_benchmark_readiness_metric_delta(
        canary_eval.get("metrics"),
        baseline_canary.get("metrics"),
    )
    dev_metric_delta = float(dev_delta.get(gate_metric, 0.0))
    canary_metric_delta = float(canary_delta.get(gate_metric, 0.0))
    hard_blockers: list[str] = []
    if dev_metric_delta <= min_dev_delta:
        hard_blockers.append("no_dev_improvement")
    if canary_metric_delta < min_canary_delta:
        hard_blockers.append("canary_regression")
    status = "passed" if not hard_blockers else "blocked"
    score = _real_benchmark_readiness_metric_score(dev_eval, gate_metric)
    eval_outcome = {
        "status": "evaluated",
        "benchmark_id": "smol_worldcup",
        "metric": gate_metric,
        "dev_score": score,
        "canary_score": _real_benchmark_readiness_metric_score(canary_eval, gate_metric),
        "baseline_dev_score": _real_benchmark_readiness_metric_score(
            baseline_dev,
            gate_metric,
        ),
        "baseline_canary_score": _real_benchmark_readiness_metric_score(
            baseline_canary,
            gate_metric,
        ),
        "dev_delta": dev_delta,
        "canary_delta": canary_delta,
        "dev_eval_ref": _string_value(dev_eval.get("output_path")),
        "canary_eval_ref": _string_value(canary_eval.get("output_path")),
        "prompt_profile_registration_ref": (
            str(registration_path) if registration_path is not None else "inline"
        ),
        "official_scores_claimed": False,
    }
    gate_result = {
        "proposal_id": proposal_id,
        "operator_id": operator_id,
        "status": status,
        "score": score,
        "metric_delta": {gate_metric: dev_metric_delta},
        "hard_blockers": hard_blockers,
        "eval_outcome": eval_outcome,
        "official_scores_claimed": False,
    }
    return gate_result, {
        "proposal_id": proposal_id,
        "status": "evaluated",
        "operator_id": operator_id,
        "optimizer": candidate.get("optimizer"),
        "counts_as_real_optimizer_candidate": counts_as_real,
        "eval_outcome": eval_outcome,
        "official_scores_claimed": False,
    }


def _real_benchmark_readiness_candidate_after_text(
    candidate: dict[str, Any],
) -> str:
    direct = _string_value(candidate.get("after_text"))
    if direct:
        return direct
    materialized = (
        candidate.get("materialized_change")
        if isinstance(candidate.get("materialized_change"), dict)
        else {}
    )
    text = _string_value(materialized.get("after_text"))
    if text:
        return text
    slice_candidate = (
        candidate.get("slice_patch_candidate")
        if isinstance(candidate.get("slice_patch_candidate"), dict)
        else {}
    )
    return _string_value(slice_candidate.get("after_text")) or _string_value(
        slice_candidate.get("patch_text")
    )


def _real_benchmark_readiness_candidate_registration(
    *,
    candidate: dict[str, Any],
    run_name: str,
    round_number: int,
    after_text: str,
) -> dict[str, Any]:
    proposal_id = _string_value(candidate.get("proposal_id")) or "candidate"
    slice_candidate = (
        candidate.get("slice_patch_candidate")
        if isinstance(candidate.get("slice_patch_candidate"), dict)
        else {}
    )
    module_id = _string_value(slice_candidate.get("module_id")) or "smol_worldcup_prompt"
    section_id = _string_value(slice_candidate.get("section_id")) or "optimizer_patch"
    profile_id = _real_benchmark_readiness_profile_id(
        f"{run_name}-round-{round_number:03d}-{proposal_id}"
    )
    registry_entry = {
        "active": True,
        "patch_id": proposal_id,
        "module_id": module_id,
        "section_id": section_id,
        "base_profile_id": "default",
        "materialized_change": {
            "after_text": after_text,
        },
        "optimizer": candidate.get("optimizer"),
        "adapter": candidate.get("adapter"),
        "operator_id": candidate.get("operator_id"),
        "official_scores_claimed": False,
    }
    return {
        "status": "registered",
        "schema_version": PROMPT_PROFILE_REGISTRATION_SCHEMA_VERSION,
        "base_profile_id": "default",
        "proposed_profile_id": profile_id,
        "registered_profile": {
            "registered": True,
            "registered_profile_id": profile_id,
            "expected_profile_id": profile_id,
            "registry_ref": "real_benchmark_readiness_run",
        },
        "registry_entry": registry_entry,
        "review": {
            "approved": True,
            "approved_by": "real_benchmark_readiness_runner",
            "requires_explicit_approval": False,
        },
        "hard_blockers": [],
        "official_scores_claimed": False,
    }


def _real_benchmark_readiness_profile_id(value: str) -> str:
    normalized = "".join(
        char if char.isalnum() or char in {"-", "_"} else "-"
        for char in value.strip().lower()
    ).strip("-")
    if not normalized:
        normalized = "real-benchmark-readiness-profile"
    return normalized[:120]


def _real_benchmark_readiness_metric_score(
    payload: dict[str, Any],
    metric: str,
) -> float:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    value = metrics.get(metric)
    if _is_plain_number(value):
        return float(value)
    fallback = _metric_value(metrics)
    return float(fallback) if fallback is not None else 0.0


def _real_benchmark_readiness_metric_delta(
    current: Any,
    baseline: Any,
) -> dict[str, float]:
    current_metrics = current if isinstance(current, dict) else {}
    baseline_metrics = baseline if isinstance(baseline, dict) else {}
    deltas: dict[str, float] = {}
    for key in sorted(set(current_metrics) | set(baseline_metrics)):
        current_value = current_metrics.get(key)
        baseline_value = baseline_metrics.get(key)
        if _is_plain_number(current_value) and _is_plain_number(baseline_value):
            deltas[str(key)] = round(float(current_value) - float(baseline_value), 6)
    return deltas


def _real_benchmark_readiness_eval_summary(
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "round_id": payload.get("round_id"),
        "metrics": payload.get("metrics", {}),
        "dataset": payload.get("dataset", {}),
        "failure_summary": payload.get("failure_summary", {}),
        "output_path": payload.get("output_path"),
        "official_scores_claimed": False,
    }


def _real_benchmark_readiness_acceptance_answers(
    *,
    baseline_dev: dict[str, Any],
    baseline_canary: dict[str, Any],
    rounds: list[dict[str, Any]],
    best_path: dict[str, Any],
    real_optimizer_candidate_count: int,
    real_eval_outcome_count: int,
    memory: dict[str, Any],
) -> dict[str, Any]:
    gate_results = [
        gate_result
        for item in rounds
        for gate_result in _dict_list(item.get("gate_results"))
    ]
    operator_weights = (
        memory.get("operator_weights")
        if isinstance(memory.get("operator_weights"), dict)
        else {}
    )
    return {
        "baseline_reproduced": (
            str(baseline_dev.get("status", "")).startswith("completed")
            and str(baseline_canary.get("status", "")).startswith("completed")
        ),
        "real_optimizer_source_executed": real_optimizer_candidate_count > 0,
        "real_source_candidate_entered_method_search_trial": any(
            bool(item.get("source_summary", {}).get("real_optimizer_candidate_count"))
            for item in rounds
        ),
        "gate_winner_selected": bool(best_path.get("winner")),
        "gate_from_real_eval_outcomes": bool(gate_results)
        and all(isinstance(item.get("eval_outcome"), dict) for item in gate_results),
        "memory_weight_updated": any(
            _is_plain_number(weight) and float(weight) != 1.0
            for weight in operator_weights.values()
        ),
        "sampler_changed_direction_across_rounds": any(
            item.get("memory_delta", {}).get("upweighted_operator_ids")
            or item.get("memory_delta", {}).get("downweighted_operator_ids")
            for item in rounds
        ),
        "official_scores_claimed": False,
        "current_evidence_scope": "local_benchmark_readiness_run",
    }


def persist_gate_feedback_memory_store(
    *,
    gate_feedback_memory: dict[str, Any] | str | Path,
    study: dict[str, Any] | str | Path,
    trial: dict[str, Any] | str | Path | None = None,
    gate_result: dict[str, Any] | str | Path | None = None,
    output_path: str | Path,
) -> dict[str, Any]:
    """Append gate feedback memory to a reusable artifact store."""
    memory_payload, memory_path = _load_object(gate_feedback_memory)
    study_payload, study_path = _load_object(study)
    trial_payload: dict[str, Any] | None = None
    trial_path: Path | None = None
    if trial is not None:
        trial_payload, trial_path = _load_object(trial)
    gate_payload: dict[str, Any] | None = None
    gate_path: Path | None = None
    if gate_result is not None:
        gate_payload, gate_path = _load_object(gate_result)
    output = Path(output_path)
    store = _method_search_load_feedback_memory_store(output)
    records = [
        item for item in store.get("records", []) if isinstance(item, dict)
    ]
    record = _method_search_feedback_store_record(
        memory=memory_payload,
        study=study_payload,
        trial=trial_payload,
        gate_result=gate_payload,
        record_number=len(records) + 1,
        refs=_method_search_artifact_refs(
            memory_path=memory_path,
            study_path=study_path,
            trial_path=trial_path,
            gate_path=gate_path,
        ),
    )
    records.append(record)
    payload = {
        "status": "ready",
        "schema_version": GATE_FEEDBACK_MEMORY_STORE_SCHEMA_VERSION,
        "store_name": "GateFeedbackMemoryStore",
        "study_name": _string_value(study_payload.get("study_name")) or "method_search",
        "storage_adapter": "artifact_json",
        "records": records,
        "latest_memory": memory_payload,
        "operator_weight_history": [
            {
                "record_id": item.get("record_id"),
                "operator_weights": item.get("operator_weights", {}),
            }
            for item in records
        ],
        "dashboard_ready": True,
        "scheduler_ready": True,
        "claim_boundary": {
            "evidence_scope": "local_gate_only",
            "llm_may_claim_improvement": False,
            "official_scores_claimed": False,
        },
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
        "path": str(output),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def build_optuna_sampler_adapter(
    *,
    study: dict[str, Any] | str | Path,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Export an Optuna-compatible sampler contract without importing Optuna."""
    study_payload, study_path = _load_object(study)
    sampler_state = (
        study_payload.get("sampler_state")
        if isinstance(study_payload.get("sampler_state"), dict)
        else {}
    )
    sampler = (
        study_payload.get("sampler")
        if isinstance(study_payload.get("sampler"), dict)
        else {}
    )
    payload = {
        "status": "ready",
        "schema_version": OPTUNA_SAMPLER_ADAPTER_SCHEMA_VERSION,
        "adapter_name": "OptunaSamplerAdapter",
        "study_name": _string_value(study_payload.get("study_name")) or "method_search",
        "objective": _string_value(study_payload.get("objective")) or "",
        "direction": _string_value(study_payload.get("direction")) or "maximize",
        "sampler_name": "HexagonGuidedLLMSampler",
        "ask_tell_mapping": {
            "study": "MethodSearchStudy",
            "trial": "MethodSearchTrial",
            "ask": "MethodSearchStudy.ask",
            "tell": "MethodSearchStudy.tell",
            "trial_params": [
                "operator",
                "adapter",
                "slice",
                "patch_scope",
                "model",
                "budget",
            ],
            "trial_value_source": "gate_after_score",
            "trial_state_source": "gate_outcome",
        },
        "operator_taxonomy": sampler.get("operator_taxonomy", {}),
        "operator_weights": sampler_state.get("operator_weights", {}),
        "gate_feedback_memory_ref": (
            _string_value(sampler_state.get("feedback_store_ref"))
            or "inline_study_sampler_state"
        ),
        "optuna_package_integrated_as_main_path": False,
        "artifact_refs": _method_search_artifact_refs(study_path=study_path),
        "claim_boundary": {
            "evidence_scope": "adapter_contract_only",
            "official_scores_claimed": False,
        },
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    _method_search_write_payload(payload, output_path=output_path, overwrite=overwrite)
    return payload


def build_optuna_storage_adapter(
    *,
    study: dict[str, Any] | str | Path,
    gate_feedback_memory_store: dict[str, Any] | str | Path | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Export a storage contract mapping MethodSearch artifacts to Optuna concepts."""
    study_payload, study_path = _load_object(study)
    store_payload = _method_search_load_feedback_memory_store(
        gate_feedback_memory_store
    )
    store_path = _method_search_feedback_store_path(gate_feedback_memory_store)
    payload = {
        "status": "ready",
        "schema_version": OPTUNA_STORAGE_ADAPTER_SCHEMA_VERSION,
        "adapter_name": "OptunaStorageAdapter",
        "study_snapshot": {
            "study_name": _string_value(study_payload.get("study_name")) or "method_search",
            "objective": _string_value(study_payload.get("objective")) or "",
            "direction": _string_value(study_payload.get("direction")) or "maximize",
            "trial_count": len(
                [
                    item
                    for item in study_payload.get("trials", [])
                    if isinstance(item, dict)
                ]
            ),
            "official_scores_claimed": False,
        },
        "trial_rows": _method_search_trial_rows(study_payload),
        "feedback_store": {
            "schema_version": store_payload.get("schema_version"),
            "path": str(store_path) if store_path is not None else None,
            "record_count": len(
                [
                    item
                    for item in store_payload.get("records", [])
                    if isinstance(item, dict)
                ]
            ),
            "latest_operator_weights": (
                store_payload.get("latest_memory", {}).get("operator_weights", {})
                if isinstance(store_payload.get("latest_memory"), dict)
                else {}
            ),
        },
        "storage_protocol": {
            "backend": "artifact_json",
            "optuna_import_required": False,
            "can_reconstruct_study_trials": True,
            "can_reconstruct_sampler_feedback": bool(store_payload),
        },
        "optuna_package_integrated_as_main_path": False,
        "artifact_refs": _method_search_artifact_refs(
            study_path=study_path,
            feedback_store_path=store_path,
        ),
        "claim_boundary": {
            "evidence_scope": "adapter_contract_only",
            "official_scores_claimed": False,
        },
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    _method_search_write_payload(payload, output_path=output_path, overwrite=overwrite)
    return payload


def build_optuna_dashboard_export(
    *,
    study: dict[str, Any] | str | Path,
    gate_feedback_memory_store: dict[str, Any] | str | Path | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a dashboard-ready Optuna-style JSON export for review."""
    study_payload, study_path = _load_object(study)
    store_payload = _method_search_load_feedback_memory_store(
        gate_feedback_memory_store
    )
    store_path = _method_search_feedback_store_path(gate_feedback_memory_store)
    latest_memory = (
        store_payload.get("latest_memory")
        if isinstance(store_payload.get("latest_memory"), dict)
        else (
            study_payload.get("sampler_state", {}).get("gate_feedback_memory", {})
            if isinstance(study_payload.get("sampler_state"), dict)
            else {}
        )
    )
    payload = {
        "status": "ready",
        "schema_version": OPTUNA_DASHBOARD_EXPORT_SCHEMA_VERSION,
        "export_name": "OptunaDashboardExport",
        "study_name": _string_value(study_payload.get("study_name")) or "method_search",
        "objective": _string_value(study_payload.get("objective")) or "",
        "direction": _string_value(study_payload.get("direction")) or "maximize",
        "trial_rows": _method_search_trial_rows(study_payload),
        "operator_weight_rows": _method_search_operator_weight_rows(latest_memory),
        "feedback_records": [
            item
            for item in store_payload.get("records", [])
            if isinstance(item, dict)
        ],
        "dashboard_contract": {
            "optuna_dashboard_import_required": False,
            "views": [
                "trial_state_table",
                "operator_weight_history",
                "gate_blocker_summary",
                "claim_boundary",
            ],
        },
        "optuna_package_integrated_as_main_path": False,
        "artifact_refs": _method_search_artifact_refs(
            study_path=study_path,
            feedback_store_path=store_path,
        ),
        "claim_boundary": {
            "evidence_scope": "local_gate_only",
            "official_scores_claimed": False,
        },
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    _method_search_write_payload(payload, output_path=output_path, overwrite=overwrite)
    return payload


def materialize_slice_patch_candidate(
    *,
    candidate: dict[str, Any] | str | Path,
    base_profile_id: str,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a review-only materialization bundle for a section-local patch."""
    candidate_payload, candidate_path = _load_slice_candidate(candidate)
    if not base_profile_id:
        raise ValueError("base_profile_id is required")
    module_id = _string_value(candidate_payload.get("module_id")) or "unknown_module"
    section_id = _string_value(candidate_payload.get("section_id")) or "unknown_section"
    materialized_change = {
        "module_id": module_id,
        "section_id": section_id,
        "change_surface": "prompt_section",
        "edit_scope": "single_section",
        "before_text": _string_value(candidate_payload.get("before_text")) or "",
        "after_text": _string_value(candidate_payload.get("after_text")) or "",
        "protected_slices": _string_list(candidate_payload.get("protected_slices")),
        "protected_sections": _string_list(candidate_payload.get("protected_sections")),
    }
    payload = {
        "status": "needs_prompt_profile_registration",
        "schema_version": SLICE_PATCH_MATERIALIZATION_SCHEMA_VERSION,
        "base_profile_id": base_profile_id,
        "candidate_ref": str(candidate_path) if candidate_path is not None else "inline",
        "patch_id": _string_value(candidate_payload.get("patch_id")),
        "optimizer": _string_value(candidate_payload.get("optimizer")),
        "materialized_change": materialized_change,
        "prompt_profile_registration": {
            "required": True,
            "reason": (
                "Smol WorldCup evaluation currently accepts registered prompt_profile "
                "ids; section patches must be reviewed and registered before eval."
            ),
            "target_module": module_id,
            "target_section": section_id,
        },
        "execution_ready": False,
        "recommended_next_steps": [
            "register_prompt_profile_variant",
            "run_prompt_leakage_audit",
            "run_dev_model_eval",
            "evaluate_slice_gate",
        ],
        "gate_constraints": {
            "canary_allowed_before_dev_gate": False,
            "promotion_ready_without_dev_gate": False,
            "protected_slice_regression_allowed": False,
        },
        "claim_boundary": (
            "review-only slice patch materialization; not an executed prompt profile "
            "and not dev/canary evidence"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def build_prompt_profile_registration_plan(
    *,
    materialization: dict[str, Any] | str | Path,
    benchmark_id: str = "smol_worldcup",
    proposed_profile_id: str,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a review-only plan for registering a section patch as a profile."""
    materialization_payload, materialization_path = _load_object(materialization)
    if not proposed_profile_id:
        raise ValueError("proposed_profile_id is required")
    materialized_change = materialization_payload.get("materialized_change")
    if not isinstance(materialized_change, dict):
        raise ValueError("materialization.materialized_change is required")

    adapter = resolve_benchmark_adapter(benchmark_id)
    module_id = _string_value(materialized_change.get("module_id")) or "unknown_module"
    section_id = (
        _string_value(materialized_change.get("section_id")) or "unknown_section"
    )
    base_profile_id = (
        _string_value(materialization_payload.get("base_profile_id"))
        or "unknown_base_profile"
    )
    patch_id = _string_value(materialization_payload.get("patch_id")) or "unknown-patch"
    required_pre_execution_checks = [
        "prompt_leakage_audit",
        "target_smoke",
        "dev_model_eval",
        "build_slice_eval_matrix",
        "evaluate_gate_policy",
        "evaluate_slice_gate",
        "evaluate_slice_variance_gate",
        "build_gate_policy_composition",
    ]
    payload = {
        "status": "ready_for_profile_registration_review",
        "schema_version": PROMPT_PROFILE_REGISTRATION_PLAN_SCHEMA_VERSION,
        "benchmark_adapter": adapter.to_manifest(),
        "materialization_ref": (
            str(materialization_path) if materialization_path is not None else "inline"
        ),
        "base_profile_id": base_profile_id,
        "proposed_profile_id": proposed_profile_id,
        "patch_id": patch_id,
        "optimizer": _string_value(materialization_payload.get("optimizer")),
        "materialized_change": {
            "module_id": module_id,
            "section_id": section_id,
            "change_surface": (
                _string_value(materialized_change.get("change_surface"))
                or "prompt_section"
            ),
            "edit_scope": (
                _string_value(materialized_change.get("edit_scope"))
                or "single_section"
            ),
            "before_text": _string_value(materialized_change.get("before_text")) or "",
            "after_text": _string_value(materialized_change.get("after_text")) or "",
            "protected_slices": _string_list(
                materialized_change.get("protected_slices")
            ),
            "protected_sections": _string_list(
                materialized_change.get("protected_sections")
            ),
        },
        "registry_patch": {
            "operation": "add_prompt_profile",
            "target_profile_id": proposed_profile_id,
            "base_profile_id": base_profile_id,
            "patch_id": patch_id,
            "change_surface": (
                _string_value(materialized_change.get("change_surface"))
                or "prompt_section"
            ),
            "edit_scope": (
                _string_value(materialized_change.get("edit_scope"))
                or "single_section"
            ),
            "module_id": module_id,
            "section_id": section_id,
            "mutation_allowed": False,
            "requires_human_or_runner_review": True,
        },
        "required_pre_execution_checks": required_pre_execution_checks,
        "execution_ready": False,
        "gate_constraints": {
            "canary_allowed_before_dev_gate": False,
            "promotion_ready_without_dev_gate": False,
            "protected_slice_regression_allowed": False,
        },
        "recommended_next_action": "review_and_register_prompt_profile",
        "claim_boundary": (
            "review-only prompt profile registration plan; not a registered "
            "profile, dev/canary run, or promotion decision"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def register_prompt_profile_from_plan(
    *,
    registration_plan: dict[str, Any] | str | Path,
    approved: bool = False,
    approved_by: str | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a registered prompt-profile artifact from a reviewed plan."""
    plan_payload, plan_path = _load_object(registration_plan)
    proposed_profile_id = _string_value(plan_payload.get("proposed_profile_id"))
    if not proposed_profile_id:
        raise ValueError("registration_plan.proposed_profile_id is required")
    base_profile_id = (
        _string_value(plan_payload.get("base_profile_id"))
        or "unknown_base_profile"
    )
    registry_patch = plan_payload.get("registry_patch")
    if not isinstance(registry_patch, dict):
        raise ValueError("registration_plan.registry_patch is required")
    operation = _string_value(registry_patch.get("operation"))
    if operation != "add_prompt_profile":
        raise ValueError("registration_plan.registry_patch.operation must be add_prompt_profile")
    target_profile_id = (
        _string_value(registry_patch.get("target_profile_id"))
        or proposed_profile_id
    )
    if target_profile_id != proposed_profile_id:
        raise ValueError("registry_patch.target_profile_id must match proposed_profile_id")
    materialized_change = plan_payload.get("materialized_change")
    if not isinstance(materialized_change, dict):
        materialized_change = {}
    benchmark_adapter = plan_payload.get("benchmark_adapter")
    if not isinstance(benchmark_adapter, dict):
        benchmark_adapter = {}
    patch_id = (
        _string_value(plan_payload.get("patch_id"))
        or _string_value(registry_patch.get("patch_id"))
        or "unknown-patch"
    )
    source_ref = str(plan_path) if plan_path is not None else "inline"
    registry_ref = str(Path(output_path)) if output_path is not None else "inline"
    is_registered = bool(approved)
    hard_blockers = [] if is_registered else ["registration_review_required"]
    registry_entry = {
        "profile_id": proposed_profile_id,
        "base_profile_id": base_profile_id,
        "benchmark_id": (
            _string_value(benchmark_adapter.get("benchmark_id"))
            or "unknown_benchmark"
        ),
        "patch_id": patch_id,
        "operation": operation,
        "active": is_registered,
        "source_registration_plan_ref": source_ref,
        "module_id": _string_value(materialized_change.get("module_id")),
        "section_id": _string_value(materialized_change.get("section_id")),
        "change_surface": (
            _string_value(materialized_change.get("change_surface"))
            or _string_value(registry_patch.get("change_surface"))
            or "prompt_section"
        ),
        "edit_scope": (
            _string_value(materialized_change.get("edit_scope"))
            or _string_value(registry_patch.get("edit_scope"))
            or "single_section"
        ),
        "materialized_change": {
            "before_text": _string_value(materialized_change.get("before_text")) or "",
            "after_text": _string_value(materialized_change.get("after_text")) or "",
            "protected_slices": _string_list(
                materialized_change.get("protected_slices")
            ),
            "protected_sections": _string_list(
                materialized_change.get("protected_sections")
            ),
        },
    }
    payload = {
        "status": "registered" if is_registered else "blocked_pending_registration_review",
        "schema_version": PROMPT_PROFILE_REGISTRATION_SCHEMA_VERSION,
        "registration_plan_ref": source_ref,
        "base_profile_id": base_profile_id,
        "proposed_profile_id": proposed_profile_id,
        "registered_profile": {
            "registered": is_registered,
            "registered_profile_id": proposed_profile_id if is_registered else None,
            "expected_profile_id": proposed_profile_id,
            "registry_ref": registry_ref if is_registered else None,
        },
        "registry_entry": registry_entry,
        "review": {
            "approved": is_registered,
            "approved_by": _string_value(approved_by),
            "requires_explicit_approval": True,
        },
        "required_pre_execution_checks": _string_list(
            plan_payload.get("required_pre_execution_checks")
        ),
        "hard_blockers": hard_blockers,
        "gate": {
            "canary_allowed": False,
            "promotion_ready": False,
        },
        "recommended_next_action": (
            "run_execution_preflight"
            if is_registered
            else "approve_registration_plan_before_profile_registration"
        ),
        "claim_boundary": (
            "prompt profile registration artifact only; not benchmark execution, "
            "canary evidence, or promotion decision"
        ),
        "mutates_benchmark_code": False,
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def build_optimizer_gate_execution_preflight(
    *,
    registration_plan: dict[str, Any] | str | Path,
    registered_profile_id: str | None = None,
    registered_profile: dict[str, Any] | str | Path | None = None,
    prompt_leakage_audit: dict[str, Any] | str | Path | None = None,
    target_smoke: dict[str, Any] | str | Path | None = None,
    dev_model_eval: dict[str, Any] | str | Path | None = None,
    gate_decisions: list[dict[str, Any]] | str | Path | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a non-executing hard-gate preflight for benchmark execution."""
    plan_payload, plan_path = _load_object(registration_plan)
    proposed_profile_id = _string_value(plan_payload.get("proposed_profile_id"))
    if not proposed_profile_id:
        raise ValueError("registration_plan.proposed_profile_id is required")
    registered_payload, registered_ref = _load_optional_execution_artifact(
        registered_profile
    )
    registered_artifact = _registered_profile_artifact_status(registered_payload)
    explicit_registered_profile_id = _string_value(registered_profile_id)
    artifact_registered_profile_id = registered_artifact["registered_profile_id"]
    normalized_registered_profile_id = (
        explicit_registered_profile_id or artifact_registered_profile_id
    )
    leakage_payload, leakage_ref = _load_optional_execution_artifact(
        prompt_leakage_audit
    )
    smoke_payload, smoke_ref = _load_optional_execution_artifact(target_smoke)
    dev_payload, dev_ref = _load_optional_execution_artifact(dev_model_eval)
    decision_items, decision_refs = _load_gate_decision_items(gate_decisions)

    hard_blockers: list[str] = []
    profile_registered = False
    if (
        explicit_registered_profile_id
        and artifact_registered_profile_id
        and explicit_registered_profile_id != artifact_registered_profile_id
    ):
        hard_blockers.append("registered_prompt_profile_conflict")
    if registered_payload and not registered_artifact["registered"]:
        hard_blockers.append("registered_prompt_profile_artifact_not_registered")
    elif not normalized_registered_profile_id:
        hard_blockers.append("registered_prompt_profile_missing")
    elif normalized_registered_profile_id != proposed_profile_id:
        hard_blockers.append("registered_prompt_profile_mismatch")
    else:
        profile_registered = True

    artifact_preflight = {
        "prompt_leakage_audit": _execution_artifact_status(
            artifact=leakage_payload,
            artifact_ref=leakage_ref,
            expected_profile_id=proposed_profile_id,
            artifact_type="prompt_leakage_audit",
        ),
        "target_smoke": _execution_artifact_status(
            artifact=smoke_payload,
            artifact_ref=smoke_ref,
            expected_profile_id=proposed_profile_id,
            artifact_type="target_smoke",
        ),
        "dev_model_eval": _execution_artifact_status(
            artifact=dev_payload,
            artifact_ref=dev_ref,
            expected_profile_id=proposed_profile_id,
            artifact_type="dev_model_eval",
        ),
    }
    if profile_registered:
        for artifact_name, artifact_status in artifact_preflight.items():
            status = _string_value(artifact_status.get("status")) or "missing"
            if status != "present":
                hard_blockers.append(f"{artifact_name}_{status}")

    gate_preflight = _execution_gate_preflight(decision_items, decision_refs)
    if profile_registered:
        hard_blockers.extend(gate_preflight["hard_blockers"])

    if "registered_prompt_profile_missing" in hard_blockers:
        status = "blocked_prompt_profile_not_registered"
        recommended_next_action = "register_prompt_profile"
    elif "registered_prompt_profile_artifact_not_registered" in hard_blockers:
        status = "blocked_prompt_profile_registration_not_approved"
        recommended_next_action = "approve_registration_plan_before_profile_registration"
    elif "registered_prompt_profile_conflict" in hard_blockers:
        status = "blocked_prompt_profile_registration_conflict"
        recommended_next_action = "review_registered_prompt_profile"
    elif "registered_prompt_profile_mismatch" in hard_blockers:
        status = "blocked_prompt_profile_mismatch"
        recommended_next_action = "review_registered_prompt_profile"
    elif any(item.endswith("_missing") for item in hard_blockers):
        status = "blocked_missing_pre_execution_artifacts"
        recommended_next_action = "collect_pre_execution_artifacts"
    elif gate_preflight["blocking"]:
        status = "blocked_by_hard_gate"
        recommended_next_action = "keep_candidate_blocked"
    elif hard_blockers:
        status = "blocked_pre_execution_check_failed"
        recommended_next_action = "repair_pre_execution_artifacts"
    else:
        status = "ready_for_canary_execution"
        recommended_next_action = "run_canary_execution"

    canary_allowed = status == "ready_for_canary_execution"
    payload = {
        "status": status,
        "schema_version": OPTIMIZER_GATE_EXECUTION_PREFLIGHT_SCHEMA_VERSION,
        "registration_plan_ref": str(plan_path) if plan_path is not None else "inline",
        "base_profile_id": _string_value(plan_payload.get("base_profile_id")),
        "proposed_profile_id": proposed_profile_id,
        "registered_profile": {
            "registered": profile_registered,
            "registered_profile_id": normalized_registered_profile_id,
            "expected_profile_id": proposed_profile_id,
            "registry_ref": registered_ref or registered_artifact["registry_ref"],
        },
        "artifact_preflight": artifact_preflight,
        "gate_preflight": gate_preflight,
        "hard_blockers": _dedupe_strings(hard_blockers),
        "gate": {
            "canary_allowed": canary_allowed,
            "promotion_ready": False,
        },
        "recommended_next_action": recommended_next_action,
        "claim_boundary": (
            "non-executing optimizer/gate execution preflight only; not a "
            "benchmark run and not a promotion decision"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def build_registered_profile_execution_bundle(
    *,
    registration_plan: dict[str, Any] | str | Path,
    registered_profile_id: str | None = None,
    registered_profile: dict[str, Any] | str | Path | None = None,
    prompt_leakage_audit: dict[str, Any] | str | Path | None = None,
    target_smoke: dict[str, Any] | str | Path | None = None,
    dev_model_eval: dict[str, Any] | str | Path | None = None,
    gate_decisions: list[dict[str, Any] | str | Path] | str | Path | None = None,
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a reusable non-executing bundle for registered profile execution."""
    plan_payload, plan_path = _load_object(registration_plan)
    proposed_profile_id = _string_value(plan_payload.get("proposed_profile_id"))
    if not proposed_profile_id:
        raise ValueError("registration_plan.proposed_profile_id is required")
    output_root = Path(output_dir)
    preflight_path = output_root / "optimizer-gate-execution-preflight.json"
    bundle_path = output_root / "registered-profile-execution-bundle.json"
    _ensure_writable(bundle_path, overwrite=overwrite)
    preflight = build_optimizer_gate_execution_preflight(
        registration_plan=registration_plan,
        registered_profile_id=registered_profile_id,
        registered_profile=registered_profile,
        prompt_leakage_audit=prompt_leakage_audit,
        target_smoke=target_smoke,
        dev_model_eval=dev_model_eval,
        gate_decisions=gate_decisions,
        output_path=preflight_path,
        overwrite=overwrite,
    )
    artifact_preflight = (
        preflight.get("artifact_preflight")
        if isinstance(preflight.get("artifact_preflight"), dict)
        else {}
    )
    gate_preflight = (
        preflight.get("gate_preflight")
        if isinstance(preflight.get("gate_preflight"), dict)
        else {}
    )
    registered_profile_payload = (
        preflight.get("registered_profile")
        if isinstance(preflight.get("registered_profile"), dict)
        else {}
    )
    gate = preflight.get("gate") if isinstance(preflight.get("gate"), dict) else {}
    canary_allowed = bool(gate.get("canary_allowed", False))
    profile_registered = bool(registered_profile_payload.get("registered", False))
    overlay_status = "ready" if profile_registered else "blocked"
    stages = [
        {
            "name": "load_prompt_profile_registration",
            "status": "registered" if profile_registered else "blocked",
            "artifact_ref": registered_profile_payload.get("registry_ref"),
            "executes_experiment": False,
        },
        {
            "name": "apply_registration_overlay",
            "status": overlay_status,
            "base_profile_id": _string_value(plan_payload.get("base_profile_id")),
            "target_profile_id": proposed_profile_id,
            "executes_experiment": False,
        },
        _registered_profile_execution_artifact_stage(
            name="prompt_leakage_audit",
            artifact_status=artifact_preflight.get("prompt_leakage_audit"),
        ),
        _registered_profile_execution_artifact_stage(
            name="target_smoke",
            artifact_status=artifact_preflight.get("target_smoke"),
        ),
        _registered_profile_execution_artifact_stage(
            name="dev_model_eval",
            artifact_status=artifact_preflight.get("dev_model_eval"),
        ),
        {
            "name": "gate_decision",
            "status": _registered_profile_execution_gate_stage_status(gate_preflight),
            "decision_count": gate_preflight.get("decision_count", 0),
            "decision_refs": gate_preflight.get("decision_refs", []),
            "executes_experiment": False,
        },
        {
            "name": "execution_preflight",
            "status": _string_value(preflight.get("status")) or "unknown",
            "output_path": str(preflight_path),
            "executes_experiment": False,
        },
        {
            "name": "canary_preflight",
            "status": "ready" if canary_allowed else "blocked",
            "canary_allowed": canary_allowed,
            "executes_experiment": False,
        },
    ]
    payload = {
        "status": _string_value(preflight.get("status")) or "unknown",
        "schema_version": REGISTERED_PROFILE_EXECUTION_BUNDLE_SCHEMA_VERSION,
        "registration_plan_ref": str(plan_path) if plan_path is not None else "inline",
        "base_profile_id": _string_value(plan_payload.get("base_profile_id")),
        "proposed_profile_id": proposed_profile_id,
        "registered_profile": registered_profile_payload,
        "stages": stages,
        "artifacts": {
            "registration_plan": str(plan_path) if plan_path is not None else "inline",
            "registered_profile": registered_profile_payload.get("registry_ref"),
            "prompt_leakage_audit": _artifact_ref_for_stage(
                artifact_preflight.get("prompt_leakage_audit")
            ),
            "target_smoke": _artifact_ref_for_stage(
                artifact_preflight.get("target_smoke")
            ),
            "dev_model_eval": _artifact_ref_for_stage(
                artifact_preflight.get("dev_model_eval")
            ),
            "optimizer_gate_execution_preflight": str(preflight_path),
            "registered_profile_execution_bundle": str(bundle_path),
        },
        "execution_preflight": {
            "status": _string_value(preflight.get("status")) or "unknown",
            "output_path": str(preflight_path),
            "hard_blockers": preflight.get("hard_blockers", []),
            "recommended_next_action": _string_value(
                preflight.get("recommended_next_action")
            ),
        },
        "hard_blockers": preflight.get("hard_blockers", []),
        "gate": {
            "canary_allowed": canary_allowed,
            "promotion_ready": bool(gate.get("promotion_ready", False)),
        },
        "recommended_next_action": _string_value(preflight.get("recommended_next_action")),
        "claim_boundary": (
            "registered profile execution bundle only; consumes pre-execution "
            "artifacts but does not run benchmark dev/canary evaluation or "
            "make promotion decisions"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    bundle_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(bundle_path)
    return payload


def build_registered_profile_gate_decision(
    *,
    registration_plan: dict[str, Any] | str | Path,
    prompt_leakage_audit: dict[str, Any] | str | Path,
    target_smoke: dict[str, Any] | str | Path,
    dev_model_eval: dict[str, Any] | str | Path,
    dev_gate_source: dict[str, Any] | str | Path | None = None,
    policy_id: str = "slice-dev-hard-gate",
    composition_id: str = "registered-profile-dev-hard-gate",
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Generate a reusable hard-gate decision from existing eval artifacts."""
    plan_payload, plan_path = _load_object(registration_plan)
    proposed_profile_id = _string_value(plan_payload.get("proposed_profile_id"))
    if not proposed_profile_id:
        raise ValueError("registration_plan.proposed_profile_id is required")
    leakage_payload, leakage_ref = _load_optional_execution_artifact(
        prompt_leakage_audit
    )
    smoke_payload, smoke_ref = _load_optional_execution_artifact(target_smoke)
    dev_payload, dev_ref = _load_optional_execution_artifact(dev_model_eval)
    gate_source_payload, gate_source_ref = _load_optional_execution_artifact(
        dev_gate_source
    )
    gate_source = gate_source_payload or dev_payload
    gate_source_ref = gate_source_ref or dev_ref
    artifact_preflight = {
        "prompt_leakage_audit": _execution_artifact_status(
            artifact=leakage_payload,
            artifact_ref=leakage_ref,
            expected_profile_id=proposed_profile_id,
            artifact_type="prompt_leakage_audit",
        ),
        "target_smoke": _execution_artifact_status(
            artifact=smoke_payload,
            artifact_ref=smoke_ref,
            expected_profile_id=proposed_profile_id,
            artifact_type="target_smoke",
        ),
        "dev_model_eval": _execution_artifact_status(
            artifact=dev_payload,
            artifact_ref=dev_ref,
            expected_profile_id=proposed_profile_id,
            artifact_type="dev_model_eval",
        ),
    }
    output_root = Path(output_dir)
    gate_input_path = output_root / "gate-policy-input.json"
    gate_decision_path = output_root / "gate-policy-decision.json"
    gate_composition_path = output_root / "gate-policy-composition.json"
    gate_run_path = output_root / "registered-profile-gate-decision.json"
    _ensure_writable(gate_run_path, overwrite=overwrite)

    hard_blockers = _dedupe_strings(
        _string_value(status.get("hard_blocker"))
        for status in artifact_preflight.values()
        if isinstance(status, dict) and _string_value(status.get("hard_blocker"))
    )
    metric_table = _registered_profile_gate_metric_table(gate_source)
    slice_table = _registered_profile_gate_slice_table(gate_source)
    source_tables_available = bool(metric_table or slice_table)
    if not source_tables_available:
        hard_blockers.append("gate_source_tables_missing")

    gate_input: dict[str, Any] | None = None
    gate_decision: dict[str, Any] | None = None
    quality_gate_inputs: dict[str, str] = {}
    quality_gate_decisions: dict[str, str] = {}
    gate_composition: dict[str, Any] | None = None
    if not hard_blockers and source_tables_available:
        task_family = (
            _string_value(plan_payload.get("benchmark_id"))
            or _string_value(
                (
                    plan_payload.get("benchmark_adapter")
                    if isinstance(plan_payload.get("benchmark_adapter"), dict)
                    else {}
                ).get("task_family")
            )
            or "smol_worldcup"
        )
        split = (
            _string_value(gate_source.get("split"))
            or _string_value(dev_payload.get("split"))
            or _artifact_eval_split(dev_payload)
            or "dev"
        )
        quality_constraints = _registered_profile_gate_quality_constraints()
        execution_quality = _registered_profile_gate_execution_quality(
            target_smoke=smoke_payload,
            dev_model_eval=dev_payload,
        )
        gate_input = build_gate_policy_input(
            policy_id=policy_id,
            task_family=task_family,
            split=split,
            metric_table=metric_table,
            slice_table=slice_table,
            quality_constraints=quality_constraints,
            execution_quality=execution_quality,
            output_path=gate_input_path,
            overwrite=overwrite,
        )
        gate_decision = evaluate_gate_policy(
            gate_input=gate_input,
            output_path=gate_decision_path,
            overwrite=overwrite,
        )
        gate_decisions = [gate_decision]
        for quality_policy_id in _registered_profile_quality_gate_policy_ids():
            quality_input_path = output_root / f"{quality_policy_id}-input.json"
            quality_decision_path = output_root / f"{quality_policy_id}-decision.json"
            quality_input = build_gate_policy_input(
                policy_id=quality_policy_id,
                task_family=task_family,
                split=split,
                metric_table=metric_table,
                slice_table=slice_table,
                quality_constraints=quality_constraints,
                execution_quality=execution_quality,
                output_path=quality_input_path,
                overwrite=overwrite,
            )
            quality_decision = evaluate_gate_policy(
                gate_input=quality_input,
                output_path=quality_decision_path,
                overwrite=overwrite,
            )
            quality_gate_inputs[quality_policy_id] = str(quality_input_path)
            quality_gate_decisions[quality_policy_id] = str(quality_decision_path)
            gate_decisions.append(quality_decision)
        gate_composition = build_gate_policy_composition(
            decisions=gate_decisions,
            composition_id=composition_id,
            output_path=gate_composition_path,
            overwrite=overwrite,
        )
        hard_blockers = _string_list(gate_composition.get("hard_blockers"))

    gate = (
        gate_composition.get("gate")
        if isinstance(gate_composition, dict)
        and isinstance(gate_composition.get("gate"), dict)
        else {"canary_allowed": False, "promotion_ready": False}
    )
    status = (
        _string_value(gate_composition.get("status"))
        if isinstance(gate_composition, dict)
        else (
            "blocked_missing_gate_source_tables"
            if "gate_source_tables_missing" in hard_blockers
            else "blocked_pre_execution_artifacts"
        )
    )
    payload = {
        "status": status,
        "schema_version": REGISTERED_PROFILE_GATE_DECISION_SCHEMA_VERSION,
        "registration_plan_ref": str(plan_path) if plan_path is not None else "inline",
        "proposed_profile_id": proposed_profile_id,
        "artifact_preflight": artifact_preflight,
        "source_tables": {
            "metric_row_count": len(metric_table),
            "slice_row_count": len(slice_table),
            "source_ref": gate_source_ref or "inline",
        },
        "generated_artifacts": {
            "gate_policy_input": str(gate_input_path) if gate_input else None,
            "gate_policy_decision": (
                str(gate_decision_path) if gate_decision else None
            ),
            "quality_gate_policy_inputs": quality_gate_inputs,
            "quality_gate_policy_decisions": quality_gate_decisions,
            "gate_policy_composition": (
                str(gate_composition_path) if gate_composition else None
            ),
            "registered_profile_gate_decision": str(gate_run_path),
        },
        "gate": gate,
        "hard_blockers": _dedupe_strings(hard_blockers),
        "claim_boundary": (
            "registered profile hard-gate decision generator only; consumes "
            "existing eval artifacts and does not run model eval or canary"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    gate_run_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(gate_run_path)
    return payload


def run_registered_profile_execution(
    *,
    registration_plan: dict[str, Any] | str | Path,
    registered_profile_id: str | None = None,
    registered_profile: dict[str, Any] | str | Path | None = None,
    prompt_leakage_rows: list[dict[str, Any]] | dict[str, Any] | str | Path | None = None,
    prompt_leakage_audit: dict[str, Any] | str | Path | None = None,
    target_smoke: dict[str, Any] | str | Path | None = None,
    dev_model_eval: dict[str, Any] | str | Path | None = None,
    dev_baseline_eval: dict[str, Any] | str | Path | None = None,
    dev_gate_source: dict[str, Any] | str | Path | None = None,
    model_runtime_preflight: dict[str, Any] | str | Path | None = None,
    execute_model_eval: bool = False,
    target_smoke_rows: list[dict[str, Any]] | dict[str, Any] | str | Path | None = None,
    dev_model_eval_rows: list[dict[str, Any]] | dict[str, Any] | str | Path | None = None,
    model_eval_chat_completion: Any | None = None,
    model_eval_model: str = "qwen/qwen3-8b",
    model_eval_base_url: str = "http://127.0.0.1:1234/v1",
    model_eval_model_provider: str = "openai-compatible",
    model_eval_api_key_env: str | None = None,
    model_eval_timeout_seconds: int = 120,
    model_eval_temperature: float = 0.0,
    model_eval_max_tokens: int = 512,
    model_eval_judge_mode: str = "heuristic",
    gate_decisions: list[dict[str, Any] | str | Path] | str | Path | None = None,
    benchmark_id: str = "smol_worldcup",
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run safe registered-profile execution stages before building the bundle."""
    if benchmark_id != "smol_worldcup":
        raise ValueError(f"unsupported registered profile execution benchmark: {benchmark_id}")
    plan_payload, plan_path = _load_object(registration_plan)
    proposed_profile_id = _string_value(plan_payload.get("proposed_profile_id"))
    if not proposed_profile_id:
        raise ValueError("registration_plan.proposed_profile_id is required")
    output_root = Path(output_dir)
    run_path = output_root / "registered-profile-execution-run.json"
    leakage_path = output_root / "prompt-leakage-audit.json"
    target_smoke_path = output_root / "target-smoke.json"
    dev_model_eval_path = output_root / "dev-model-eval.json"
    dev_gate_source_path = output_root / "dev-slice-eval-matrix.json"
    model_runtime_preflight_path = output_root / "model-runtime-preflight.json"
    _ensure_writable(run_path, overwrite=overwrite)

    rows = _load_prompt_leakage_rows(prompt_leakage_rows)
    generated_leakage_audit: dict[str, Any] | None = None
    if rows is not None:
        if registered_profile is None:
            raise ValueError("registered_profile is required to execute prompt leakage audit")
        generated_leakage_audit = build_smol_worldcup_prompt_leakage_audit(
            rows,
            prompt_profile=proposed_profile_id,
            prompt_profile_registration=registered_profile,
        )
        leakage_path.write_text(
            json.dumps(
                generated_leakage_audit,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        prompt_leakage_input: dict[str, Any] | str | Path | None = generated_leakage_audit
        leakage_execution = {
            "status": "generated",
            "output_path": str(leakage_path),
            "row_count": len(rows),
            "prompt_profile": generated_leakage_audit.get("prompt_profile"),
        }
    else:
        prompt_leakage_input = prompt_leakage_audit
        leakage_execution = _registered_profile_run_input_execution_status(
            prompt_leakage_audit,
            artifact_name="prompt_leakage_audit",
        )

    generated_target_smoke = None
    generated_dev_model_eval = None
    generated_dev_gate_source = None
    target_smoke_input = target_smoke
    dev_model_eval_input = dev_model_eval
    dev_gate_source_input = dev_gate_source
    has_model_eval_rows = target_smoke_rows is not None or dev_model_eval_rows is not None
    if has_model_eval_rows and not execute_model_eval:
        raise ValueError(
            "execute_model_eval=True is required when target_smoke_rows or "
            "dev_model_eval_rows are provided"
        )
    if execute_model_eval:
        if registered_profile is None:
            raise ValueError("registered_profile is required to execute model eval")
        if target_smoke is not None and target_smoke_rows is not None:
            raise ValueError("target_smoke and target_smoke_rows cannot both be provided")
        if dev_model_eval is not None and dev_model_eval_rows is not None:
            raise ValueError("dev_model_eval and dev_model_eval_rows cannot both be provided")
        model_runtime_execution = _model_runtime_preflight_execution_status(
            model_runtime_preflight=model_runtime_preflight,
            output_path=model_runtime_preflight_path,
            model=model_eval_model,
            base_url=model_eval_base_url,
            model_provider=model_eval_model_provider,
            api_key_env=model_eval_api_key_env,
            timeout_seconds=model_eval_timeout_seconds,
            temperature=model_eval_temperature,
            max_tokens=model_eval_max_tokens,
            overwrite=overwrite,
        )
        target_rows = _load_prompt_leakage_rows(target_smoke_rows)
        dev_rows = _load_prompt_leakage_rows(dev_model_eval_rows)
        model_runtime_ready = bool(model_runtime_execution["model_runtime_ready"])
        if target_rows is not None and model_runtime_ready:
            generated_target_smoke = _build_registered_profile_model_eval_from_rows(
                rows=target_rows,
                prompt_profile=proposed_profile_id,
                prompt_profile_registration=registered_profile,
                chat_completion=model_eval_chat_completion,
                model=model_eval_model,
                base_url=model_eval_base_url,
                model_provider=model_eval_model_provider,
                api_key_env=model_eval_api_key_env,
                timeout_seconds=model_eval_timeout_seconds,
                temperature=model_eval_temperature,
                max_tokens=model_eval_max_tokens,
                judge_mode=model_eval_judge_mode,
                round_id=f"{proposed_profile_id}-target-smoke",
            )
            _ensure_writable(target_smoke_path, overwrite=overwrite)
            target_smoke_path.write_text(
                json.dumps(
                    generated_target_smoke,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            target_smoke_input = generated_target_smoke
        if dev_rows is not None and model_runtime_ready:
            generated_dev_model_eval = _build_registered_profile_model_eval_from_rows(
                rows=dev_rows,
                prompt_profile=proposed_profile_id,
                prompt_profile_registration=registered_profile,
                chat_completion=model_eval_chat_completion,
                model=model_eval_model,
                base_url=model_eval_base_url,
                model_provider=model_eval_model_provider,
                api_key_env=model_eval_api_key_env,
                timeout_seconds=model_eval_timeout_seconds,
                temperature=model_eval_temperature,
                max_tokens=model_eval_max_tokens,
                judge_mode=model_eval_judge_mode,
                round_id=f"{proposed_profile_id}-dev-model-eval",
            )
            _ensure_writable(dev_model_eval_path, overwrite=overwrite)
            dev_model_eval_path.write_text(
                json.dumps(
                    generated_dev_model_eval,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            dev_model_eval_input = generated_dev_model_eval
    else:
        model_runtime_execution = _model_runtime_preflight_not_required_status(
            model_runtime_preflight
        )

    if dev_baseline_eval is not None and dev_model_eval_input is not None:
        generated_dev_gate_source = build_slice_eval_matrix(
            baseline_report=dev_baseline_eval,
            candidate_report=dev_model_eval_input,
            candidate_evaluation={
                "evaluation_split": "dev",
                "official_scores_claimed": False,
            },
            output_path=dev_gate_source_path,
            overwrite=overwrite,
        )
        dev_gate_source_input = dev_gate_source_path

    generated_gate_decision = None
    gate_decision_input = gate_decisions
    if (
        gate_decisions is None
        and prompt_leakage_input is not None
        and target_smoke_input is not None
        and dev_model_eval_input is not None
    ):
        generated_gate_decision = build_registered_profile_gate_decision(
            registration_plan=registration_plan,
            prompt_leakage_audit=prompt_leakage_input,
            target_smoke=target_smoke_input,
            dev_model_eval=dev_model_eval_input,
            dev_gate_source=dev_gate_source_input,
            output_dir=output_root,
            overwrite=overwrite,
        )
        generated_artifacts = (
            generated_gate_decision.get("generated_artifacts")
            if isinstance(generated_gate_decision.get("generated_artifacts"), dict)
            else {}
        )
        gate_composition_ref = _string_value(
            generated_artifacts.get("gate_policy_composition")
        )
        if gate_composition_ref:
            gate_decision_input = [gate_composition_ref]

    bundle = build_registered_profile_execution_bundle(
        registration_plan=registration_plan,
        registered_profile_id=registered_profile_id,
        registered_profile=registered_profile,
        prompt_leakage_audit=prompt_leakage_input,
        target_smoke=target_smoke_input,
        dev_model_eval=dev_model_eval_input,
        gate_decisions=gate_decision_input,
        output_dir=output_root,
        overwrite=overwrite,
    )
    gate_execution = _registered_profile_run_gate_execution_status(
        gate_decision_input
    )
    if generated_gate_decision is not None:
        generated_artifacts = (
            generated_gate_decision.get("generated_artifacts")
            if isinstance(generated_gate_decision.get("generated_artifacts"), dict)
            else {}
        )
        gate_composition_ref = _string_value(
            generated_artifacts.get("gate_policy_composition")
        )
        decision_refs: list[str] = []
        base_decision_ref = _string_value(generated_artifacts.get("gate_policy_decision"))
        if base_decision_ref:
            decision_refs.append(base_decision_ref)
        quality_decisions = generated_artifacts.get("quality_gate_policy_decisions")
        if isinstance(quality_decisions, dict):
            for quality_policy_id in _registered_profile_quality_gate_policy_ids():
                quality_ref = _string_value(quality_decisions.get(quality_policy_id))
                if quality_ref:
                    decision_refs.append(quality_ref)
        gate_summary = (
            generated_gate_decision.get("gate")
            if isinstance(generated_gate_decision.get("gate"), dict)
            else {}
        )
        decision_count = gate_summary.get("decision_count")
        if not isinstance(decision_count, int) or isinstance(decision_count, bool):
            decision_count = len(decision_refs)
        gate_execution = {
            "status": "generated" if gate_composition_ref else "generation_blocked",
            "decision_count": decision_count if gate_composition_ref else 0,
            "decision_refs": decision_refs if gate_composition_ref else [],
            "composition_ref": gate_composition_ref if gate_composition_ref else None,
            "output_path": generated_gate_decision.get("output_path"),
            "required_before_canary": True,
        }
    runtime_blocked = (
        has_model_eval_rows
        and execute_model_eval
        and not bool(model_runtime_execution["model_runtime_ready"])
    )
    target_smoke_execution = _registered_profile_run_model_eval_execution_status(
        generated_target_smoke,
        target_smoke,
        output_path=target_smoke_path,
        artifact_name="target_smoke",
    )
    dev_model_eval_execution = _registered_profile_run_model_eval_execution_status(
        generated_dev_model_eval,
        dev_model_eval,
        output_path=dev_model_eval_path,
        artifact_name="dev_model_eval",
    )
    if runtime_blocked and target_smoke_rows is not None and target_smoke is None:
        target_smoke_execution = _model_eval_not_run_status("target_smoke")
    if runtime_blocked and dev_model_eval_rows is not None and dev_model_eval is None:
        dev_model_eval_execution = _model_eval_not_run_status("dev_model_eval")
    hard_blockers = _dedupe_strings(
        list(bundle.get("hard_blockers", []))
        + (
            _string_list(model_runtime_execution.get("hard_blockers"))
            if runtime_blocked
            else []
        )
    )
    gate = (
        {"canary_allowed": False, "promotion_ready": False, "model_runtime_ready": False}
        if runtime_blocked
        else bundle.get("gate", {"canary_allowed": False, "promotion_ready": False})
    )
    payload = {
        "status": (
            "blocked_model_runtime_preflight"
            if runtime_blocked
            else (_string_value(bundle.get("status")) or "unknown")
        ),
        "schema_version": REGISTERED_PROFILE_EXECUTION_RUN_SCHEMA_VERSION,
        "benchmark_id": benchmark_id,
        "registration_plan_ref": str(plan_path) if plan_path is not None else "inline",
        "base_profile_id": _string_value(plan_payload.get("base_profile_id")),
        "proposed_profile_id": proposed_profile_id,
        "execution": {
            "prompt_leakage_audit": leakage_execution,
            "model_runtime_preflight": model_runtime_execution,
            "target_smoke": target_smoke_execution,
            "dev_model_eval": dev_model_eval_execution,
            "dev_gate_source": _registered_profile_run_dev_gate_source_status(
                generated_dev_gate_source,
                dev_gate_source,
                output_path=dev_gate_source_path,
            ),
            "gate_decision": gate_execution,
        },
        "registered_profile_execution_bundle": {
            "status": _string_value(bundle.get("status")) or "unknown",
            "output_path": bundle.get("output_path"),
            "hard_blockers": bundle.get("hard_blockers", []),
        },
        "artifacts": {
            "prompt_leakage_audit": (
                str(leakage_path) if generated_leakage_audit is not None else None
            ),
            "target_smoke": (
                str(target_smoke_path)
                if generated_target_smoke is not None
                else (
                    str(target_smoke)
                    if target_smoke is not None and not isinstance(target_smoke, dict)
                    else None
                )
            ),
            "dev_model_eval": (
                str(dev_model_eval_path)
                if generated_dev_model_eval is not None
                else (
                    str(dev_model_eval)
                    if dev_model_eval is not None and not isinstance(dev_model_eval, dict)
                    else None
                )
            ),
            "dev_gate_source": (
                str(dev_gate_source_path)
                if generated_dev_gate_source is not None
                else (
                    str(dev_gate_source)
                    if dev_gate_source is not None and not isinstance(dev_gate_source, dict)
                    else None
                )
            ),
            "model_runtime_preflight": model_runtime_execution.get("artifact_ref"),
            "optimizer_gate_execution_preflight": (
                bundle.get("artifacts", {}).get("optimizer_gate_execution_preflight")
                if isinstance(bundle.get("artifacts"), dict)
                else None
            ),
            "registered_profile_execution_bundle": bundle.get("output_path"),
            "registered_profile_execution_run": str(run_path),
            "generated_gate_decision": (
                generated_gate_decision.get("generated_artifacts")
                if isinstance(generated_gate_decision, dict)
                else None
            ),
        },
        "hard_blockers": hard_blockers,
        "gate": gate,
        "recommended_next_action": (
            _string_value(model_runtime_execution.get("recommended_next_action"))
            if runtime_blocked
            else _string_value(bundle.get("recommended_next_action"))
        ),
        "claim_boundary": (
            "registered profile execution run only; may execute local prompt leakage "
            "audit from supplied rows, explicitly run local model eval from supplied "
            "rows, and generate hard-gate decisions from supplied dev eval tables, "
            "but does not run canary or promotion decisions"
        ),
        "executes_tool": bool(generated_target_smoke or generated_dev_model_eval),
        "executes_experiment": bool(generated_target_smoke or generated_dev_model_eval),
        "official_scores_claimed": False,
    }
    run_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(run_path)
    return payload


def build_model_runtime_preflight(
    *,
    model: str,
    base_url: str,
    output_path: str | Path,
    model_provider: str = "openai-compatible",
    api_key_env: str | None = None,
    execute_probe: bool = False,
    chat_completion: Any | None = None,
    timeout_seconds: int = 30,
    temperature: float = 0.0,
    max_tokens: int = 512,
    min_max_tokens: int = 32,
    apply_no_think: bool = True,
    probe_prompt: str = "Return compact JSON exactly as {\"ok\": true}.",
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a model runtime preflight before dev/canary execution."""
    output = Path(output_path)
    _ensure_writable(output, overwrite=overwrite)
    parsed_max_tokens = max(1, int(max_tokens))
    parsed_min_max_tokens = max(1, int(min_max_tokens))
    no_think_applied = bool(apply_no_think and _model_runtime_is_qwen(model))
    messages = _model_runtime_preflight_messages(
        probe_prompt=probe_prompt,
        no_think_applied=no_think_applied,
    )
    hard_blockers: list[str] = []
    if parsed_max_tokens < parsed_min_max_tokens:
        hard_blockers.append("model_runtime_max_tokens_too_low")
    probe_result: dict[str, Any] = {
        "execute_probe": execute_probe,
        "no_think_applied": no_think_applied,
        "max_tokens": parsed_max_tokens,
        "min_max_tokens": parsed_min_max_tokens,
        "runtime_error_count": 0,
        "empty_output_count": 0,
        "content_sample": None,
        "input_tokens_estimate": None,
        "output_tokens_estimate": None,
    }
    if execute_probe:
        completion = chat_completion or openai_compatible_chat_completion
        try:
            completion_payload = completion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=parsed_max_tokens,
                timeout_seconds=max(1, int(timeout_seconds)),
                base_url=base_url,
                provider=model_provider,
                api_key_env=api_key_env,
                extra_body=None,
            )
        except Exception as exc:  # pragma: no cover - concrete subclasses vary by client
            hard_blockers.append("model_runtime_error")
            probe_result["runtime_error_count"] = 1
            probe_result["error"] = str(exc)
        else:
            content = _string_value(completion_payload.get("content"))
            if not content:
                hard_blockers.append("model_runtime_empty_output")
                probe_result["empty_output_count"] = 1
            probe_result["content_sample"] = content[:200] if content else None
            probe_result["input_tokens_estimate"] = completion_payload.get(
                "input_tokens_estimate"
            )
            probe_result["output_tokens_estimate"] = completion_payload.get(
                "output_tokens_estimate"
            )
    else:
        hard_blockers.append("model_runtime_probe_not_executed")

    hard_blockers = _dedupe_strings(hard_blockers)
    runtime_ready = execute_probe and not hard_blockers
    status = (
        "model_runtime_ready"
        if runtime_ready
        else (
            "needs_model_runtime_probe"
            if not execute_probe
            else "blocked_model_runtime_not_ready"
        )
    )
    payload = {
        "status": status,
        "schema_version": MODEL_RUNTIME_PREFLIGHT_SCHEMA_VERSION,
        "runtime": {
            "provider": model_provider,
            "model": model,
            "base_url": base_url,
            "api_key_env": api_key_env,
        },
        "probe": probe_result,
        "gate": {
            "model_runtime_ready": runtime_ready,
            "canary_allowed": runtime_ready,
            "promotion_ready": False,
        },
        "hard_blockers": hard_blockers,
        "recommended_next_action": (
            "proceed_to_registered_profile_execution"
            if runtime_ready
            else (
                "execute_model_runtime_probe"
                if not execute_probe
                else "fix_model_runtime_before_dev_or_canary"
            )
        ),
        "claim_boundary": (
            "model runtime preflight only; may execute one chat-completion probe "
            "but does not run benchmark eval, canary, promotion, or official scoring"
        ),
        "executes_tool": execute_probe,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(output)
    return payload


def _model_runtime_is_qwen(model: str) -> bool:
    return "qwen" in model.lower()


def _model_runtime_preflight_messages(
    *,
    probe_prompt: str,
    no_think_applied: bool,
) -> list[dict[str, str]]:
    system_content = "You are a runtime probe. Return only the requested JSON."
    user_content = probe_prompt
    if no_think_applied:
        system_content = "/no_think\n" + system_content
        user_content = "/no_think\n" + user_content
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def _model_runtime_preflight_execution_status(
    *,
    model_runtime_preflight: dict[str, Any] | str | Path | None,
    output_path: str | Path,
    model: str,
    base_url: str,
    model_provider: str,
    api_key_env: str | None,
    timeout_seconds: int,
    temperature: float,
    max_tokens: int,
    overwrite: bool,
) -> dict[str, Any]:
    if model_runtime_preflight is None:
        preflight = build_model_runtime_preflight(
            model=model,
            base_url=base_url,
            model_provider=model_provider,
            api_key_env=api_key_env,
            execute_probe=False,
            timeout_seconds=timeout_seconds,
            temperature=temperature,
            max_tokens=max_tokens,
            output_path=output_path,
            overwrite=overwrite,
        )
        artifact_ref = str(output_path)
        consumed = False
    else:
        preflight, preflight_path = _load_object(model_runtime_preflight)
        artifact_ref = str(preflight_path) if preflight_path is not None else "inline"
        consumed = True

    hard_blockers = _string_list(preflight.get("hard_blockers"))
    runtime = preflight.get("runtime") if isinstance(preflight.get("runtime"), dict) else {}
    if _string_value(runtime.get("model")) and _string_value(runtime.get("model")) != model:
        hard_blockers.append("model_runtime_model_mismatch")
    if _string_value(runtime.get("base_url")) and _string_value(runtime.get("base_url")) != base_url:
        hard_blockers.append("model_runtime_base_url_mismatch")
    if (
        _string_value(runtime.get("provider"))
        and _string_value(runtime.get("provider")) != model_provider
    ):
        hard_blockers.append("model_runtime_provider_mismatch")
    gate = preflight.get("gate") if isinstance(preflight.get("gate"), dict) else {}
    model_runtime_ready = (
        _string_value(preflight.get("status")) == "model_runtime_ready"
        and bool(gate.get("model_runtime_ready", False))
        and not hard_blockers
    )
    if not model_runtime_ready and not hard_blockers:
        hard_blockers.append("model_runtime_preflight_not_ready")
    hard_blockers = _dedupe_strings(hard_blockers)
    return {
        "status": _string_value(preflight.get("status")) or "unknown",
        "artifact_ref": artifact_ref,
        "model_runtime_ready": model_runtime_ready,
        "hard_blockers": hard_blockers,
        "gate": {
            "model_runtime_ready": model_runtime_ready,
            "canary_allowed": bool(gate.get("canary_allowed", False)),
            "promotion_ready": bool(gate.get("promotion_ready", False)),
        },
        "required_before_model_eval": True,
        "source": "consumed" if consumed else "generated_non_executing",
        "recommended_next_action": (
            "proceed_to_model_eval"
            if model_runtime_ready
            else (
                _string_value(preflight.get("recommended_next_action"))
                or "execute_model_runtime_probe"
            )
        ),
    }


def _model_runtime_preflight_not_required_status(
    model_runtime_preflight: dict[str, Any] | str | Path | None,
) -> dict[str, Any]:
    if model_runtime_preflight is None:
        return {
            "status": "not_required",
            "artifact_ref": None,
            "model_runtime_ready": True,
            "hard_blockers": [],
            "required_before_model_eval": False,
        }
    preflight, preflight_path = _load_object(model_runtime_preflight)
    gate = preflight.get("gate") if isinstance(preflight.get("gate"), dict) else {}
    blockers = _string_list(preflight.get("hard_blockers"))
    return {
        "status": _string_value(preflight.get("status")) or "unknown",
        "artifact_ref": str(preflight_path) if preflight_path is not None else "inline",
        "model_runtime_ready": bool(gate.get("model_runtime_ready", False))
        and not blockers,
        "hard_blockers": blockers,
        "required_before_model_eval": False,
        "source": "consumed",
    }


def _model_eval_not_run_status(artifact_name: str) -> dict[str, Any]:
    return {
        "status": "not_run",
        "output_path": None,
        "row_count": 0,
        "required_before_canary": True,
        "artifact": artifact_name,
        "blocked_by": "model_runtime_preflight",
    }


def build_registered_profile_canary_preflight(
    *,
    registered_profile_execution_run: dict[str, Any] | str | Path,
    canary_rows: list[dict[str, Any]] | dict[str, Any] | str | Path | None = None,
    output_path: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a non-executing canary preflight from a registered dev-gated run."""
    run_payload, run_path = _load_object(registered_profile_execution_run)
    output = Path(output_path)
    _ensure_writable(output, overwrite=overwrite)
    gate = run_payload.get("gate") if isinstance(run_payload.get("gate"), dict) else {}
    canary_allowed = bool(gate.get("canary_allowed", False))
    rows = _load_prompt_leakage_rows(canary_rows)
    row_count = len(rows) if rows is not None else 0
    hard_blockers: list[str] = []
    if not canary_allowed:
        hard_blockers.append("canary_not_allowed_by_dev_gate")
    if row_count <= 0:
        hard_blockers.append("canary_rows_missing")
    hard_blockers.extend(_string_list(run_payload.get("hard_blockers")))
    hard_blockers = _dedupe_strings(hard_blockers)
    execution_allowed = canary_allowed and row_count > 0 and not hard_blockers
    status = (
        "ready_for_canary_execution"
        if execution_allowed
        else (
            "blocked_by_dev_hard_gate"
            if not canary_allowed
            else "blocked_missing_canary_rows"
        )
    )
    payload = {
        "status": status,
        "schema_version": REGISTERED_PROFILE_CANARY_PREFLIGHT_SCHEMA_VERSION,
        "registered_profile_execution_run_ref": (
            str(run_path) if run_path is not None else "inline"
        ),
        "proposed_profile_id": _string_value(run_payload.get("proposed_profile_id")),
        "upstream": {
            "status": _string_value(run_payload.get("status")),
            "hard_blockers": _string_list(run_payload.get("hard_blockers")),
            "gate": {
                "canary_allowed": canary_allowed,
                "promotion_ready": bool(gate.get("promotion_ready", False)),
            },
        },
        "canary_execution": {
            "allowed": execution_allowed,
            "row_count": row_count,
            "requires_execute_canary_flag": True,
        },
        "gate": {
            "canary_allowed": canary_allowed,
            "promotion_ready": False,
        },
        "hard_blockers": hard_blockers,
        "recommended_next_action": (
            "run_canary_execution"
            if execution_allowed
            else (
                "keep_candidate_blocked"
                if not canary_allowed
                else "provide_canary_rows"
            )
        ),
        "claim_boundary": (
            "registered profile canary preflight only; consumes dev hard-gate "
            "state and canary rows but does not run canary or promotion"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(output)
    return payload


def run_registered_profile_canary_execution(
    *,
    registered_profile_execution_run: dict[str, Any] | str | Path,
    registered_profile: dict[str, Any] | str | Path | None = None,
    model_runtime_preflight: dict[str, Any] | str | Path | None = None,
    execute_canary: bool = False,
    canary_rows: list[dict[str, Any]] | dict[str, Any] | str | Path | None = None,
    model_eval_chat_completion: Any | None = None,
    model_eval_model: str = "qwen/qwen3-8b",
    model_eval_base_url: str = "http://127.0.0.1:1234/v1",
    model_eval_model_provider: str = "openai-compatible",
    model_eval_api_key_env: str | None = None,
    model_eval_timeout_seconds: int = 120,
    model_eval_temperature: float = 0.0,
    model_eval_max_tokens: int = 512,
    model_eval_judge_mode: str = "heuristic",
    min_canary_row_count: int = 1,
    max_canary_failure_count: int = 0,
    max_canary_runtime_error_count: int = 0,
    max_canary_empty_output_count: int = 0,
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run the explicit canary stage after a registered dev-gated execution run."""
    if canary_rows is not None and not execute_canary:
        raise ValueError("execute_canary=True is required when canary_rows are provided")
    output_root = Path(output_dir)
    preflight_path = output_root / "registered-profile-canary-preflight.json"
    model_runtime_preflight_path = output_root / "model-runtime-preflight.json"
    canary_eval_path = output_root / "canary-model-eval.json"
    execution_path = output_root / "registered-profile-canary-execution.json"
    _ensure_writable(execution_path, overwrite=overwrite)
    preflight = build_registered_profile_canary_preflight(
        registered_profile_execution_run=registered_profile_execution_run,
        canary_rows=canary_rows,
        output_path=preflight_path,
        overwrite=overwrite,
    )
    rows = _load_prompt_leakage_rows(canary_rows)
    canary_eval: dict[str, Any] | None = None
    canary_allowed = bool(
        (
            preflight.get("canary_execution")
            if isinstance(preflight.get("canary_execution"), dict)
            else {}
        ).get("allowed", False)
    )
    requires_model_runtime = execute_canary and canary_allowed and bool(rows)
    if requires_model_runtime:
        model_runtime_execution = _model_runtime_preflight_execution_status(
            model_runtime_preflight=model_runtime_preflight,
            output_path=model_runtime_preflight_path,
            model=model_eval_model,
            base_url=model_eval_base_url,
            model_provider=model_eval_model_provider,
            api_key_env=model_eval_api_key_env,
            timeout_seconds=model_eval_timeout_seconds,
            temperature=model_eval_temperature,
            max_tokens=model_eval_max_tokens,
            overwrite=overwrite,
        )
    else:
        model_runtime_execution = _model_runtime_preflight_not_required_status(
            model_runtime_preflight
        )
    model_runtime_ready = bool(model_runtime_execution["model_runtime_ready"])
    if execute_canary and canary_allowed and model_runtime_ready:
        if registered_profile is None:
            raise ValueError("registered_profile is required to execute canary")
        if not rows:
            raise ValueError("canary_rows are required to execute canary")
        proposed_profile_id = _string_value(preflight.get("proposed_profile_id"))
        if not proposed_profile_id:
            raise ValueError("preflight.proposed_profile_id is required")
        canary_eval = _build_registered_profile_model_eval_from_rows(
            rows=rows,
            prompt_profile=proposed_profile_id,
            prompt_profile_registration=registered_profile,
            chat_completion=model_eval_chat_completion,
            model=model_eval_model,
            base_url=model_eval_base_url,
            model_provider=model_eval_model_provider,
            api_key_env=model_eval_api_key_env,
            timeout_seconds=model_eval_timeout_seconds,
            temperature=model_eval_temperature,
            max_tokens=model_eval_max_tokens,
            judge_mode=model_eval_judge_mode,
            round_id=f"{proposed_profile_id}-canary-model-eval",
            evaluation_split="all",
        )
        if isinstance(canary_eval.get("dataset"), dict):
            canary_eval["dataset"]["evaluation_split"] = "canary"
            canary_eval["dataset"]["row_count"] = len(rows)
        _ensure_writable(canary_eval_path, overwrite=overwrite)
        canary_eval_path.write_text(
            json.dumps(canary_eval, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
    runtime_blocked = requires_model_runtime and not model_runtime_ready
    status = (
        "canary_completed"
        if canary_eval is not None
        else (
            "blocked_model_runtime_preflight"
            if runtime_blocked
            else preflight["status"]
        )
    )
    hard_blockers = _dedupe_strings(
        _string_list(preflight.get("hard_blockers"))
        + (
            _string_list(model_runtime_execution.get("hard_blockers"))
            if runtime_blocked
            else []
        )
    )
    payload = {
        "status": status,
        "schema_version": REGISTERED_PROFILE_CANARY_EXECUTION_SCHEMA_VERSION,
        "proposed_profile_id": _string_value(preflight.get("proposed_profile_id")),
        "execution": {
            "canary_preflight": {
                "status": _string_value(preflight.get("status")),
                "output_path": str(preflight_path),
                "required_before_canary": True,
            },
            "model_runtime_preflight": model_runtime_execution,
            "canary_model_eval": {
                "status": "generated" if canary_eval is not None else "not_run",
                "output_path": str(canary_eval_path) if canary_eval is not None else None,
                "row_count": len(rows) if rows else 0,
                "required_before_promotion": True,
            },
        },
        "artifacts": {
            "registered_profile_canary_preflight": str(preflight_path),
            "model_runtime_preflight": model_runtime_execution.get("artifact_ref"),
            "canary_model_eval": str(canary_eval_path) if canary_eval is not None else None,
            "registered_profile_canary_execution": str(execution_path),
        },
        "gate": {
            "canary_completed": canary_eval is not None,
            "model_runtime_ready": model_runtime_ready,
            "promotion_ready": False,
        },
        "hard_blockers": hard_blockers,
        "recommended_next_action": (
            "evaluate_canary_gate_before_promotion"
            if canary_eval is not None
            else (
                _string_value(model_runtime_execution.get("recommended_next_action"))
                if runtime_blocked
                else _string_value(preflight.get("recommended_next_action"))
            )
        ),
        "claim_boundary": (
            "registered profile canary execution only; may run explicit local "
            "canary model eval but does not make promotion decisions"
        ),
        "executes_tool": canary_eval is not None,
        "executes_experiment": canary_eval is not None,
        "official_scores_claimed": False,
    }
    execution_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(execution_path)
    return payload


def build_registered_profile_canary_result_gate(
    *,
    registered_profile_canary_execution: dict[str, Any] | str | Path,
    output_path: str | Path,
    min_canary_row_count: int = 1,
    max_failure_count: int = 0,
    max_runtime_error_count: int = 0,
    max_empty_output_count: int = 0,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Evaluate canary execution output before any promotion decision."""
    execution_payload, execution_path = _load_object(registered_profile_canary_execution)
    output = Path(output_path)
    _ensure_writable(output, overwrite=overwrite)
    artifacts = (
        execution_payload.get("artifacts")
        if isinstance(execution_payload.get("artifacts"), dict)
        else {}
    )
    canary_eval_ref = _string_value(artifacts.get("canary_model_eval"))
    hard_blockers = _string_list(execution_payload.get("hard_blockers"))
    canary_completed = bool(
        (
            execution_payload.get("gate")
            if isinstance(execution_payload.get("gate"), dict)
            else {}
        ).get("canary_completed", False)
    )
    if _string_value(execution_payload.get("status")) != "canary_completed":
        canary_completed = False
    if not canary_completed:
        hard_blockers.append("canary_execution_not_completed")

    canary_eval: dict[str, Any] = {}
    canary_eval_ref_for_output = canary_eval_ref
    if canary_eval_ref:
        canary_eval_path = Path(canary_eval_ref)
        if canary_eval_path.exists():
            canary_eval, loaded_path = _load_object(canary_eval_path)
            canary_eval_ref_for_output = (
                str(loaded_path) if loaded_path is not None else canary_eval_ref
            )
        else:
            hard_blockers.append("canary_model_eval_missing")
    else:
        hard_blockers.append("canary_model_eval_missing")

    row_count = _artifact_row_count(canary_eval) or 0
    failure_summary = (
        canary_eval.get("failure_summary")
        if isinstance(canary_eval.get("failure_summary"), dict)
        else {}
    )
    failure_count = int(_summary_number(failure_summary, "failure_count"))
    runtime_error_count = int(_summary_number(failure_summary, "runtime_error_count"))
    empty_output_count = int(_summary_number(failure_summary, "empty_output_count"))
    if row_count < min_canary_row_count:
        hard_blockers.append("canary_model_eval_row_count_below_min")
    if failure_count > max_failure_count:
        hard_blockers.append("canary_model_eval_failure_count_gt_max")
    if runtime_error_count > max_runtime_error_count:
        hard_blockers.append("canary_model_eval_runtime_error")
    if empty_output_count > max_empty_output_count:
        hard_blockers.append("canary_model_eval_empty_output")

    hard_blockers = _dedupe_strings(hard_blockers)
    canary_passed = canary_completed and not hard_blockers
    status = "passed_for_promotion" if canary_passed else "blocked_by_canary_result"
    payload = {
        "status": status,
        "schema_version": REGISTERED_PROFILE_CANARY_RESULT_GATE_SCHEMA_VERSION,
        "registered_profile_canary_execution_ref": (
            str(execution_path) if execution_path is not None else "inline"
        ),
        "proposed_profile_id": _string_value(execution_payload.get("proposed_profile_id")),
        "canary_result": {
            "artifact_ref": canary_eval_ref_for_output,
            "row_count": row_count,
            "failure_count": failure_count,
            "runtime_error_count": runtime_error_count,
            "empty_output_count": empty_output_count,
            "status": _string_value(canary_eval.get("status")),
        },
        "constraints": {
            "min_canary_row_count": min_canary_row_count,
            "max_failure_count": max_failure_count,
            "max_runtime_error_count": max_runtime_error_count,
            "max_empty_output_count": max_empty_output_count,
        },
        "gate": {
            "canary_completed": canary_completed,
            "canary_passed": canary_passed,
            "promotion_ready": canary_passed,
        },
        "hard_blockers": hard_blockers,
        "recommended_next_action": (
            "review_promotion_boundary"
            if canary_passed
            else "inspect_canary_failures_before_promotion"
        ),
        "claim_boundary": (
            "registered profile canary result gate only; consumes canary execution "
            "artifacts and may mark local promotion readiness but does not promote "
            "or claim official scores"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "executes_promotion": False,
        "official_scores_claimed": False,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(output)
    return payload


def _registered_profile_outcome_schedule_actions(
    *,
    canary_passed: bool,
    hard_blockers: list[str],
) -> list[str]:
    if canary_passed:
        return [
            "review_promotion_boundary",
            "record_slice_patch_outcome",
            "await_human_promotion_review",
        ]

    actions: list[str] = []
    runtime_blockers = {
        "canary_model_eval_runtime_error",
        "canary_model_eval_empty_output",
        "canary_model_eval_missing",
        "source_claims_official_scores",
    }
    if any(blocker in runtime_blockers for blocker in hard_blockers):
        actions.extend([
            "build_model_runtime_preflight",
            "run_registered_profile_canary_execution",
        ])
    if "canary_execution_not_completed" in hard_blockers:
        actions.append("run_registered_profile_canary_execution")
    actions.extend([
        "build_slice_optimizer_selection",
        "generate_slice_patch_candidates",
    ])
    return _dedupe_strings(actions)


def _registered_profile_outcome_weighting(
    *,
    canary_passed: bool,
    hard_blockers: list[str],
) -> dict[str, Any]:
    blocker_penalties = {
        "canary_model_eval_runtime_error": -4,
        "canary_model_eval_empty_output": -3,
        "canary_model_eval_failure_count_gt_max": -3,
        "canary_model_eval_row_count_below_min": -2,
        "canary_model_eval_missing": -2,
        "canary_execution_not_completed": -2,
        "source_claims_official_scores": -5,
    }
    positive_signals = ["canary_passed"] if canary_passed else []
    negative_signals = list(hard_blockers)
    components: list[dict[str, Any]] = []
    scheduler_weight = 0
    if canary_passed:
        scheduler_weight += 1
        components.append({"signal": "canary_passed", "weight": 1})
    for blocker in hard_blockers:
        weight = blocker_penalties.get(blocker, -1)
        scheduler_weight += weight
        components.append({"signal": blocker, "weight": weight})
    return {
        "scheduler_weight": scheduler_weight,
        "positive_signals": positive_signals,
        "negative_signals": negative_signals,
        "weight_components": components,
        "policy": {
            "canary_passed_bonus": 1,
            "runtime_blocker_penalty": -4,
            "failure_blocker_penalty": -3,
            "row_count_blocker_penalty": -2,
            "generic_blocker_penalty": -1,
        },
    }


def build_registered_profile_outcome_schedule(
    *,
    registered_profile_canary_result_gate: dict[str, Any] | str | Path,
    output_path: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build non-executing outcome weighting from a canary result gate."""
    gate_payload, gate_path = _load_object(registered_profile_canary_result_gate)
    output = Path(output_path)
    _ensure_writable(output, overwrite=overwrite)

    gate = gate_payload.get("gate") if isinstance(gate_payload.get("gate"), dict) else {}
    hard_blockers = _string_list(gate_payload.get("hard_blockers"))
    if bool(gate_payload.get("official_scores_claimed", False)):
        hard_blockers.append("source_claims_official_scores")
    hard_blockers = _dedupe_strings(hard_blockers)

    source_canary_passed = bool(gate.get("canary_passed", False))
    source_promotion_ready = bool(gate.get("promotion_ready", False))
    source_status = _string_value(gate_payload.get("status"))
    canary_passed = (
        source_status == "passed_for_promotion"
        and source_canary_passed
        and source_promotion_ready
        and not hard_blockers
    )
    weighting = _registered_profile_outcome_weighting(
        canary_passed=canary_passed,
        hard_blockers=hard_blockers,
    )
    scheduled_actions = _registered_profile_outcome_schedule_actions(
        canary_passed=canary_passed,
        hard_blockers=hard_blockers,
    )
    status = (
        "ready_for_promotion_review"
        if canary_passed
        else "repair_or_runtime_followup_required"
    )
    payload = {
        "status": status,
        "schema_version": REGISTERED_PROFILE_OUTCOME_SCHEDULE_SCHEMA_VERSION,
        "registered_profile_canary_result_gate_ref": (
            str(gate_path) if gate_path is not None else "inline"
        ),
        "proposed_profile_id": _string_value(gate_payload.get("proposed_profile_id")),
        "source_gate": {
            "status": source_status,
            "canary_passed": source_canary_passed,
            "promotion_ready": source_promotion_ready,
            "hard_blockers": hard_blockers,
            "canary_result": (
                gate_payload.get("canary_result")
                if isinstance(gate_payload.get("canary_result"), dict)
                else {}
            ),
        },
        "outcome_weighting": weighting,
        "scheduled_actions": scheduled_actions,
        "gate": {
            "canary_result_consumed": True,
            "scheduler_allows_promotion_review": canary_passed,
            "promotion_ready": canary_passed,
        },
        "hard_blockers": hard_blockers,
        "recommended_next_action": scheduled_actions[0] if scheduled_actions else None,
        "claim_boundary": (
            "registered profile outcome schedule only; consumes canary result "
            "gate for local weighting and next-step routing but does not execute "
            "optimizers, experiments, promotion, or official scoring"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "executes_promotion": False,
        "official_scores_claimed": False,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(output)
    return payload


def _optimizer_gate_scheduler_runtime_readiness(
    model_runtime_preflight: dict[str, Any] | None,
) -> dict[str, Any]:
    if model_runtime_preflight is None:
        return {
            "status": "missing",
            "model_runtime_ready": False,
            "recommended_next_action": "build_model_runtime_preflight",
            "hard_blockers": ["model_runtime_preflight_missing"],
        }
    gate = (
        model_runtime_preflight.get("gate")
        if isinstance(model_runtime_preflight.get("gate"), dict)
        else {}
    )
    hard_blockers = _string_list(model_runtime_preflight.get("hard_blockers"))
    model_runtime_ready = bool(gate.get("model_runtime_ready", False))
    if bool(model_runtime_preflight.get("official_scores_claimed", False)):
        hard_blockers.append("model_runtime_preflight_claims_official_scores")
        model_runtime_ready = False
    return {
        "status": _string_value(model_runtime_preflight.get("status")) or "unknown",
        "model_runtime_ready": model_runtime_ready,
        "recommended_next_action": _string_value(
            model_runtime_preflight.get("recommended_next_action")
        ),
        "hard_blockers": _dedupe_strings(hard_blockers),
    }


def _optimizer_gate_scheduler_selection_summary(
    slice_optimizer_selection: dict[str, Any] | None,
) -> dict[str, Any]:
    if slice_optimizer_selection is None:
        return {
            "status": "missing",
            "selected_optimizer": None,
            "target_scope": None,
            "failure_labels": [],
            "available": False,
        }
    selected_optimizer = _string_value(
        slice_optimizer_selection.get("selected_optimizer")
    )
    available = (
        _string_value(slice_optimizer_selection.get("status")) == "completed"
        and bool(selected_optimizer)
        and not bool(slice_optimizer_selection.get("official_scores_claimed", False))
    )
    return {
        "status": _string_value(slice_optimizer_selection.get("status")) or "unknown",
        "selected_optimizer": selected_optimizer,
        "target_scope": _string_value(slice_optimizer_selection.get("target_scope")),
        "failure_labels": _string_list(slice_optimizer_selection.get("failure_labels")),
        "available": available,
    }


def _optimizer_gate_scheduler_action_item(
    *,
    action: str,
    promotion_ready: bool,
    model_runtime_ready: bool,
    selection: dict[str, Any],
) -> dict[str, Any]:
    selected_optimizer = _string_value(selection.get("selected_optimizer"))
    selection_available = bool(selection.get("available", False))
    if action == "review_promotion_boundary":
        status = "ready_for_human_review" if promotion_ready else "blocked_by_gate"
        reason = (
            "promotion review requires human boundary check"
            if promotion_ready
            else "promotion review requires passed canary result"
        )
        return {"name": action, "status": status, "reason": reason}
    if action == "record_slice_patch_outcome":
        return {
            "name": action,
            "status": "ready_to_record" if promotion_ready else "ready_to_record_blocker",
            "reason": "record scheduler-visible outcome signal",
        }
    if action == "await_human_promotion_review":
        return {
            "name": action,
            "status": "waiting_for_human_review",
            "reason": "promotion remains manual and outside scheduler execution",
        }
    if action == "build_model_runtime_preflight":
        return {
            "name": action,
            "status": "satisfied" if model_runtime_ready else "ready_to_build",
            "reason": (
                "model runtime preflight is ready"
                if model_runtime_ready
                else "canary rerun requires ready model runtime preflight"
            ),
        }
    if action == "run_registered_profile_canary_execution":
        return {
            "name": action,
            "status": (
                "ready_to_run_canary_execution"
                if model_runtime_ready
                else "blocked_by_model_runtime_preflight"
            ),
            "reason": (
                "ready model runtime preflight is available"
                if model_runtime_ready
                else "canary execution requires ready model runtime preflight"
            ),
        }
    if action == "build_slice_optimizer_selection":
        return {
            "name": action,
            "status": "satisfied" if selection_available else "ready_to_build",
            "reason": (
                "optimizer selection is available"
                if selection_available
                else "repair loop requires optimizer selection"
            ),
        }
    if action == "generate_slice_patch_candidates":
        if selection_available:
            return {
                "name": action,
                "status": "ready_to_generate_candidates",
                "reason": "optimizer selection is available",
                "selected_optimizer": selected_optimizer,
            }
        return {
            "name": action,
            "status": "blocked_by_optimizer_selection",
            "reason": "candidate generation requires optimizer selection",
        }
    return {
        "name": action,
        "status": "planned",
        "reason": "scheduler action carried from outcome schedule",
    }


def _optimizer_gate_scheduler_status(
    *,
    action_queue: list[dict[str, Any]],
    runtime_readiness: dict[str, Any],
) -> tuple[str, str | None, list[str]]:
    if not action_queue:
        return "blocked_scheduler_no_actions", None, ["scheduler_actions_missing"]

    for item in action_queue:
        action = _string_value(item.get("name"))
        action_status = _string_value(item.get("status"))
        if not action:
            continue
        if action_status in {"satisfied", "blocked_by_gate"}:
            continue
        if action == "review_promotion_boundary":
            if action_status == "ready_for_human_review":
                return "ready_for_human_promotion_review", action, []
            continue
        if action == "build_model_runtime_preflight":
            if action_status == "ready_to_build":
                return (
                    "needs_model_runtime_preflight",
                    action,
                    _dedupe_strings(
                        _string_list(runtime_readiness.get("hard_blockers"))
                    ),
                )
            continue
        if action == "run_registered_profile_canary_execution":
            if action_status == "ready_to_run_canary_execution":
                return "ready_for_registered_profile_canary_execution", action, []
            if action_status == "blocked_by_model_runtime_preflight":
                return (
                    "needs_model_runtime_preflight",
                    "build_model_runtime_preflight",
                    _dedupe_strings(
                        _string_list(runtime_readiness.get("hard_blockers"))
                    ),
                )
            continue
        if action == "build_slice_optimizer_selection":
            if action_status == "ready_to_build":
                return (
                    "needs_slice_optimizer_selection",
                    action,
                    ["slice_optimizer_selection_missing"],
                )
            continue
        if action == "generate_slice_patch_candidates":
            if action_status == "ready_to_generate_candidates":
                return (
                    "ready_for_optimizer_candidate_generation",
                    action,
                    [],
                )
            if action_status == "blocked_by_optimizer_selection":
                return (
                    "needs_slice_optimizer_selection",
                    "build_slice_optimizer_selection",
                    ["slice_optimizer_selection_missing"],
                )
            continue
        if action == "record_slice_patch_outcome" and action_status == "ready_to_record":
            return "scheduler_actions_planned", action, []
        if action == "await_human_promotion_review":
            return "ready_for_human_promotion_review", action, []
        if action_status:
            return (
                "scheduler_actions_planned",
                action,
                [],
            )
    return "scheduler_actions_satisfied", None, []


def build_optimizer_gate_scheduler_plan(
    *,
    registered_profile_outcome_schedule: dict[str, Any] | str | Path,
    model_runtime_preflight: dict[str, Any] | str | Path | None = None,
    slice_optimizer_selection: dict[str, Any] | str | Path | None = None,
    output_path: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a non-executing runner-facing scheduler plan."""
    schedule_payload, schedule_path = _load_object(registered_profile_outcome_schedule)
    runtime_payload: dict[str, Any] | None = None
    runtime_path: Path | None = None
    if model_runtime_preflight is not None:
        runtime_payload, runtime_path = _load_object(model_runtime_preflight)
    selection_payload: dict[str, Any] | None = None
    selection_path: Path | None = None
    if slice_optimizer_selection is not None:
        selection_payload, selection_path = _load_object(slice_optimizer_selection)

    output = Path(output_path)
    _ensure_writable(output, overwrite=overwrite)
    scheduled_actions = _string_list(schedule_payload.get("scheduled_actions"))
    outcome_weighting = (
        schedule_payload.get("outcome_weighting")
        if isinstance(schedule_payload.get("outcome_weighting"), dict)
        else {}
    )
    schedule_gate = (
        schedule_payload.get("gate")
        if isinstance(schedule_payload.get("gate"), dict)
        else {}
    )
    source_hard_blockers = _string_list(schedule_payload.get("hard_blockers"))
    runtime_readiness = _optimizer_gate_scheduler_runtime_readiness(runtime_payload)
    selection = _optimizer_gate_scheduler_selection_summary(selection_payload)
    promotion_ready = bool(schedule_gate.get("promotion_ready", False)) and bool(
        schedule_gate.get("scheduler_allows_promotion_review", False)
    )
    action_queue = [
        _optimizer_gate_scheduler_action_item(
            action=action,
            promotion_ready=promotion_ready,
            model_runtime_ready=bool(runtime_readiness.get("model_runtime_ready", False)),
            selection=selection,
        )
        for action in scheduled_actions
    ]
    status, next_runner_action, hard_blockers = _optimizer_gate_scheduler_status(
        action_queue=action_queue,
        runtime_readiness=runtime_readiness,
    )
    if bool(schedule_payload.get("official_scores_claimed", False)):
        hard_blockers.append("outcome_schedule_claims_official_scores")
        status = "blocked_scheduler_claim_boundary"
        next_runner_action = None
    hard_blockers = _dedupe_strings(hard_blockers)
    payload = {
        "status": status,
        "schema_version": OPTIMIZER_GATE_SCHEDULER_PLAN_SCHEMA_VERSION,
        "registered_profile_outcome_schedule_ref": (
            str(schedule_path) if schedule_path is not None else "inline"
        ),
        "model_runtime_preflight_ref": (
            str(runtime_path) if runtime_path is not None else None
        ),
        "slice_optimizer_selection_ref": (
            str(selection_path) if selection_path is not None else None
        ),
        "proposed_profile_id": _string_value(
            schedule_payload.get("proposed_profile_id")
        ),
        "scheduler_inputs": {
            "outcome_schedule_status": (
                _string_value(schedule_payload.get("status")) or "unknown"
            ),
            "scheduler_weight": outcome_weighting.get("scheduler_weight"),
            "positive_signals": _string_list(
                outcome_weighting.get("positive_signals")
            ),
            "negative_signals": _string_list(
                outcome_weighting.get("negative_signals")
            ),
            "scheduled_actions": scheduled_actions,
            "source_hard_blockers": source_hard_blockers,
        },
        "runtime_readiness": runtime_readiness,
        "optimizer_selection": selection,
        "action_queue": action_queue,
        "next_runner_action": next_runner_action,
        "gate": {
            "outcome_schedule_consumed": True,
            "promotion_review_queued": status == "ready_for_human_promotion_review",
            "optimizer_candidate_generation_ready": (
                status == "ready_for_optimizer_candidate_generation"
            ),
            "canary_rerun_ready": any(
                item.get("name") == "run_registered_profile_canary_execution"
                and item.get("status") == "ready_to_run_canary_execution"
                for item in action_queue
            ),
            "executes_promotion": False,
        },
        "hard_blockers": hard_blockers,
        "claim_boundary": (
            "optimizer/gate scheduler plan only; consumes outcome schedule, "
            "runtime readiness, and optimizer selection to route next actions "
            "but does not execute tools, experiments, promotion, or official scoring"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "executes_promotion": False,
        "official_scores_claimed": False,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(output)
    return payload


def _optimizer_gate_scheduler_action_payload(
    *,
    scheduler_plan: dict[str, Any],
    scheduler_plan_ref: str,
    action_name: str | None,
    action_status: str | None,
    status: str,
    action_result: dict[str, Any] | None,
    artifacts: list[dict[str, str]],
    hard_blockers: list[str],
    output_path: Path,
    overwrite: bool,
    executes_tool: bool = False,
    executes_experiment: bool = False,
    executes_promotion: bool = False,
    input_hash: str | None = None,
    budget: dict[str, Any] | None = None,
    stop_reason: str | None = None,
    output_manifest: dict[str, Any] | None = None,
    idempotency: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": OPTIMIZER_GATE_SCHEDULER_ACTION_SCHEMA_VERSION,
        "status": status,
        "optimizer_gate_scheduler_plan_ref": scheduler_plan_ref,
        "proposed_profile_id": _string_value(scheduler_plan.get("proposed_profile_id")),
        "action_name": action_name,
        "action_status": action_status,
        "action_result": action_result or {},
        "artifacts": artifacts,
        "hard_blockers": _dedupe_strings(hard_blockers),
        "claim_boundary": (
            "optimizer/gate scheduler action only; executes an explicit safe "
            "planning action from a scheduler plan and does not execute "
            "experiments, promotion, or official scoring"
        ),
        "executes_tool": bool(executes_tool),
        "executes_experiment": bool(executes_experiment),
        "executes_promotion": bool(executes_promotion),
        "official_scores_claimed": False,
    }
    if input_hash is not None:
        payload["input_hash"] = input_hash
    if budget is not None:
        payload["budget"] = budget
    if stop_reason is not None:
        payload["stop_reason"] = stop_reason
    if output_manifest is not None:
        payload["output_manifest"] = output_manifest
    if idempotency is not None:
        payload["idempotency"] = idempotency
    _ensure_writable(output_path, overwrite=overwrite)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(output_path)
    return payload


def _json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _path_sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _load_canary_runner_bundle_for_scheduler(
    value: dict[str, Any] | str | Path | None,
) -> tuple[dict[str, Any], Path | None, str | None]:
    if value is None:
        return {}, None, None
    payload, path = _load_object(value)
    return payload, path, _input_ref(value, path)


def _scheduler_experiment_budget(
    experiment_budget: dict[str, Any] | None,
    *,
    consumed: int,
) -> dict[str, Any]:
    budget = experiment_budget if isinstance(experiment_budget, dict) else {}
    max_actions = budget.get("max_experiment_actions", 0)
    if not isinstance(max_actions, int) or isinstance(max_actions, bool):
        max_actions = 0
    return {
        "max_experiment_actions": max(0, max_actions),
        "experiment_actions_consumed": max(0, consumed),
        "experiment_actions_remaining": max(0, max(0, max_actions) - max(0, consumed)),
    }


def _scheduler_experiment_action_input_hash(
    *,
    scheduler_plan: dict[str, Any],
    action_name: str,
    action_item: dict[str, Any],
    allowlist: list[str],
    experiment_budget: dict[str, Any] | None,
    canary_runner_bundle: dict[str, Any],
    canary_runner_bundle_path: Path | None,
    canary_runner_bundle_ref: str | None,
) -> str:
    return _json_sha256({
        "scheduler_plan_schema_version": scheduler_plan.get("schema_version"),
        "scheduler_plan_status": scheduler_plan.get("status"),
        "proposed_profile_id": scheduler_plan.get("proposed_profile_id"),
        "action_name": action_name,
        "action_item": action_item,
        "allowlist": sorted(allowlist),
        "experiment_budget": (
            experiment_budget if isinstance(experiment_budget, dict) else {}
        ),
        "canary_runner_bundle_ref": canary_runner_bundle_ref,
        "canary_runner_bundle_sha256": (
            _path_sha256(canary_runner_bundle_path)
            if canary_runner_bundle_path is not None
            else _json_sha256(canary_runner_bundle)
            if canary_runner_bundle
            else None
        ),
    })


def _scheduler_action_output_manifest(
    *,
    action_name: str,
    input_hash: str,
    output_path: Path,
    action_result: dict[str, Any] | None,
    artifacts: list[dict[str, str]],
    manifest_path: Path,
    overwrite: bool,
) -> dict[str, Any]:
    manifest_artifacts = [
        {
            "name": "optimizer_gate_scheduler_action",
            "path": str(output_path),
        },
        *artifacts,
    ]
    action_result_path = _string_value(
        action_result.get("output_path") if isinstance(action_result, dict) else None
    )
    if action_result_path and all(
        item.get("path") != action_result_path for item in manifest_artifacts
    ):
        manifest_artifacts.append({
            "name": f"{action_name}_result",
            "path": action_result_path,
        })
    manifest = {
        "schema_version": f"{OPTIMIZER_GATE_SCHEDULER_ACTION_SCHEMA_VERSION}.output-manifest",
        "action_name": action_name,
        "input_hash": input_hash,
        "artifact_count": len(manifest_artifacts),
        "artifacts": manifest_artifacts,
        "claim_boundary": "scheduler action output manifest only",
        "official_scores_claimed": False,
    }
    _ensure_writable(manifest_path, overwrite=overwrite)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest["path"] = str(manifest_path)
    return manifest


def _find_optimizer_gate_scheduler_action_item(
    scheduler_plan: dict[str, Any],
    action_name: str,
) -> dict[str, Any] | None:
    for item in _dict_list(scheduler_plan.get("action_queue")):
        if _string_value(item.get("name")) == action_name:
            return item
    return None


def _optimizer_gate_scheduler_action_not_ready(
    *,
    action_name: str | None,
    action_status: str | None,
    scheduler_plan: dict[str, Any],
    scheduler_plan_ref: str,
    output_path: Path,
    overwrite: bool,
    hard_blocker: str,
) -> dict[str, Any]:
    return _optimizer_gate_scheduler_action_payload(
        scheduler_plan=scheduler_plan,
        scheduler_plan_ref=scheduler_plan_ref,
        action_name=action_name,
        action_status=action_status,
        status="blocked_scheduler_action_not_ready",
        action_result={},
        artifacts=[],
        hard_blockers=[hard_blocker],
        output_path=output_path,
        overwrite=overwrite,
    )


def run_optimizer_gate_scheduler_action(
    *,
    optimizer_gate_scheduler_plan: dict[str, Any] | str | Path,
    output_dir: str | Path,
    action_name: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    model_provider: str = "openai-compatible",
    api_key_env: str | None = None,
    execute_probe: bool = False,
    apply_no_think: bool = True,
    max_tokens: int = 512,
    timeout_seconds: int = 30,
    context: dict[str, Any] | str | Path | None = None,
    optimizer_gate_plugin_manifests: list[dict[str, Any] | str | Path] | None = None,
    max_candidates: int = 1,
    experiment_action_allowlist: list[str] | None = None,
    experiment_budget: dict[str, Any] | None = None,
    canary_runner_bundle: dict[str, Any] | str | Path | None = None,
    model_eval_chat_completion: Any | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run one explicit safe planning action from an optimizer/gate scheduler plan."""
    scheduler_plan, scheduler_plan_path = _load_object(optimizer_gate_scheduler_plan)
    scheduler_plan_ref = (
        str(scheduler_plan_path) if scheduler_plan_path is not None else "inline"
    )
    output_root = Path(output_dir)
    action_output = output_root / "optimizer-gate-scheduler-action.json"
    selected_action = (
        _string_value(action_name)
        or _string_value(scheduler_plan.get("next_runner_action"))
    )
    if not selected_action:
        return _optimizer_gate_scheduler_action_not_ready(
            action_name=None,
            action_status=None,
            scheduler_plan=scheduler_plan,
            scheduler_plan_ref=scheduler_plan_ref,
            output_path=action_output,
            overwrite=overwrite,
            hard_blocker="scheduler_action_missing",
        )
    action_item = _find_optimizer_gate_scheduler_action_item(
        scheduler_plan,
        selected_action,
    )
    action_status = (
        _string_value(action_item.get("status")) if action_item is not None else None
    )
    if action_item is None:
        return _optimizer_gate_scheduler_action_payload(
            scheduler_plan=scheduler_plan,
            scheduler_plan_ref=scheduler_plan_ref,
            action_name=selected_action,
            action_status=None,
            status="blocked_scheduler_action_unknown",
            action_result={},
            artifacts=[],
            hard_blockers=["scheduler_action_unknown"],
            output_path=action_output,
            overwrite=overwrite,
        )
    if bool(scheduler_plan.get("official_scores_claimed", False)):
        return _optimizer_gate_scheduler_action_payload(
            scheduler_plan=scheduler_plan,
            scheduler_plan_ref=scheduler_plan_ref,
            action_name=selected_action,
            action_status=action_status,
            status="blocked_scheduler_claim_boundary",
            action_result={},
            artifacts=[],
            hard_blockers=["scheduler_plan_claims_official_scores"],
            output_path=action_output,
            overwrite=overwrite,
        )
    if selected_action == "build_model_runtime_preflight":
        if action_status != "ready_to_build":
            return _optimizer_gate_scheduler_action_not_ready(
                action_name=selected_action,
                action_status=action_status,
                scheduler_plan=scheduler_plan,
                scheduler_plan_ref=scheduler_plan_ref,
                output_path=action_output,
                overwrite=overwrite,
                hard_blocker="scheduler_action_not_ready",
            )
        if not model or not base_url:
            return _optimizer_gate_scheduler_action_payload(
                scheduler_plan=scheduler_plan,
                scheduler_plan_ref=scheduler_plan_ref,
                action_name=selected_action,
                action_status=action_status,
                status="blocked_scheduler_action_missing_input",
                action_result={},
                artifacts=[],
                hard_blockers=["model_runtime_preflight_input_missing"],
                output_path=action_output,
                overwrite=overwrite,
            )
        preflight_path = output_root / "model-runtime-preflight.json"
        action_result = build_model_runtime_preflight(
            model=model,
            base_url=base_url,
            model_provider=model_provider,
            api_key_env=api_key_env,
            execute_probe=execute_probe,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
            apply_no_think=apply_no_think,
            output_path=preflight_path,
            overwrite=overwrite,
        )
        return _optimizer_gate_scheduler_action_payload(
            scheduler_plan=scheduler_plan,
            scheduler_plan_ref=scheduler_plan_ref,
            action_name=selected_action,
            action_status=action_status,
            status="action_completed",
            action_result=action_result,
            artifacts=[
                {"name": "model_runtime_preflight", "path": str(preflight_path)}
            ],
            hard_blockers=[],
            output_path=action_output,
            overwrite=overwrite,
            executes_tool=bool(action_result.get("executes_tool", False)),
            executes_experiment=bool(action_result.get("executes_experiment", False)),
            executes_promotion=False,
        )
    if selected_action == "generate_slice_patch_candidates":
        if action_status != "ready_to_generate_candidates":
            return _optimizer_gate_scheduler_action_not_ready(
                action_name=selected_action,
                action_status=action_status,
                scheduler_plan=scheduler_plan,
                scheduler_plan_ref=scheduler_plan_ref,
                output_path=action_output,
                overwrite=overwrite,
                hard_blocker="scheduler_action_not_ready",
            )
        optimizer_selection = (
            scheduler_plan.get("optimizer_selection")
            if isinstance(scheduler_plan.get("optimizer_selection"), dict)
            else {}
        )
        selected_optimizer = (
            _string_value(action_item.get("selected_optimizer"))
            or _string_value(optimizer_selection.get("selected_optimizer"))
        )
        if context is None or not selected_optimizer:
            return _optimizer_gate_scheduler_action_payload(
                scheduler_plan=scheduler_plan,
                scheduler_plan_ref=scheduler_plan_ref,
                action_name=selected_action,
                action_status=action_status,
                status="blocked_scheduler_action_missing_input",
                action_result={},
                artifacts=[],
                hard_blockers=["slice_patch_candidate_input_missing"],
                output_path=action_output,
                overwrite=overwrite,
            )
        candidates_path = output_root / "slice-patch-candidates.json"
        action_result = generate_slice_patch_candidates(
            context=context,
            optimizer=selected_optimizer,
            optimizer_gate_plugin_manifests=optimizer_gate_plugin_manifests,
            max_candidates=max_candidates,
            execute_optimizer=False,
            output_path=candidates_path,
            overwrite=overwrite,
        )
        return _optimizer_gate_scheduler_action_payload(
            scheduler_plan=scheduler_plan,
            scheduler_plan_ref=scheduler_plan_ref,
            action_name=selected_action,
            action_status=action_status,
            status="action_completed",
            action_result=action_result,
            artifacts=[
                {"name": "slice_patch_candidates", "path": str(candidates_path)}
            ],
            hard_blockers=[],
            output_path=action_output,
            overwrite=overwrite,
            executes_tool=bool(action_result.get("executes_tool", False)),
            executes_experiment=bool(action_result.get("executes_experiment", False)),
            executes_promotion=False,
        )
    if selected_action == "review_promotion_boundary":
        if action_status != "ready_for_human_review":
            return _optimizer_gate_scheduler_action_not_ready(
                action_name=selected_action,
                action_status=action_status,
                scheduler_plan=scheduler_plan,
                scheduler_plan_ref=scheduler_plan_ref,
                output_path=action_output,
                overwrite=overwrite,
                hard_blocker="scheduler_action_not_ready",
            )
        review_path = output_root / "promotion-review-boundary.json"
        action_result = {
            "status": "awaiting_human_promotion_review",
            "action_name": selected_action,
            "requires_human_review": True,
            "executes_promotion": False,
            "official_scores_claimed": False,
        }
        _ensure_writable(review_path, overwrite=overwrite)
        review_path.write_text(
            json.dumps(action_result, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        return _optimizer_gate_scheduler_action_payload(
            scheduler_plan=scheduler_plan,
            scheduler_plan_ref=scheduler_plan_ref,
            action_name=selected_action,
            action_status=action_status,
            status="action_completed",
            action_result=action_result,
            artifacts=[
                {"name": "promotion_review_boundary", "path": str(review_path)}
            ],
            hard_blockers=[],
            output_path=action_output,
            overwrite=overwrite,
        )
    if selected_action == "run_registered_profile_canary_execution":
        if action_status != "ready_to_run_canary_execution":
            return _optimizer_gate_scheduler_action_not_ready(
                action_name=selected_action,
                action_status=action_status,
                scheduler_plan=scheduler_plan,
                scheduler_plan_ref=scheduler_plan_ref,
                output_path=action_output,
                overwrite=overwrite,
                hard_blocker="scheduler_action_not_ready",
            )
        allowlist = _string_list(experiment_action_allowlist)
        if selected_action not in allowlist:
            return _optimizer_gate_scheduler_action_payload(
                scheduler_plan=scheduler_plan,
                scheduler_plan_ref=scheduler_plan_ref,
                action_name=selected_action,
                action_status=action_status,
                status="blocked_scheduler_action_unsupported",
                action_result={},
                artifacts=[],
                hard_blockers=["scheduler_action_execution_not_supported"],
                output_path=action_output,
                overwrite=overwrite,
            )
        bundle_payload, bundle_path, bundle_ref = _load_canary_runner_bundle_for_scheduler(
            canary_runner_bundle
        )
        input_hash = _scheduler_experiment_action_input_hash(
            scheduler_plan=scheduler_plan,
            action_name=selected_action,
            action_item=action_item,
            allowlist=allowlist,
            experiment_budget=experiment_budget,
            canary_runner_bundle=bundle_payload,
            canary_runner_bundle_path=bundle_path,
            canary_runner_bundle_ref=bundle_ref,
        )
        if action_output.exists() and not overwrite:
            existing = json.loads(action_output.read_text(encoding="utf-8"))
            if existing.get("input_hash") == input_hash:
                existing = dict(existing)
                existing["status"] = "action_already_completed"
                existing["budget"] = _scheduler_experiment_budget(
                    experiment_budget,
                    consumed=0,
                )
                existing["idempotency"] = {
                    "reused_existing_artifact": True,
                    "reason": "input_hash_match",
                }
                existing["output_path"] = str(action_output)
                return existing
        budget = _scheduler_experiment_budget(experiment_budget, consumed=0)
        if budget["max_experiment_actions"] <= 0:
            manifest = _scheduler_action_output_manifest(
                action_name=selected_action,
                input_hash=input_hash,
                output_path=action_output,
                action_result={},
                artifacts=[],
                manifest_path=output_root / "optimizer-gate-scheduler-action-output-manifest.json",
                overwrite=overwrite,
            )
            return _optimizer_gate_scheduler_action_payload(
                scheduler_plan=scheduler_plan,
                scheduler_plan_ref=scheduler_plan_ref,
                action_name=selected_action,
                action_status=action_status,
                status="blocked_scheduler_experiment_budget",
                action_result={},
                artifacts=[],
                hard_blockers=["experiment_budget_exhausted"],
                output_path=action_output,
                overwrite=overwrite,
                input_hash=input_hash,
                budget=budget,
                stop_reason="budget_exhausted",
                output_manifest=manifest,
            )
        bundle_gate = (
            bundle_payload.get("gate")
            if isinstance(bundle_payload.get("gate"), dict)
            else {}
        )
        bundle_blockers = _string_list(bundle_payload.get("hard_blockers"))
        if (
            not bundle_payload
            or _string_value(bundle_payload.get("status"))
            != "ready_for_explicit_canary_runner"
            or not bool(bundle_gate.get("runner_inputs_ready", False))
            or bundle_blockers
        ):
            hard_blockers = _dedupe_strings(
                bundle_blockers
                or [
                    "canary_runner_bundle_not_ready",
                ]
            )
            manifest = _scheduler_action_output_manifest(
                action_name=selected_action,
                input_hash=input_hash,
                output_path=action_output,
                action_result={},
                artifacts=[],
                manifest_path=output_root / "optimizer-gate-scheduler-action-output-manifest.json",
                overwrite=overwrite,
            )
            return _optimizer_gate_scheduler_action_payload(
                scheduler_plan=scheduler_plan,
                scheduler_plan_ref=scheduler_plan_ref,
                action_name=selected_action,
                action_status=action_status,
                status="blocked_scheduler_experiment_replay",
                action_result={},
                artifacts=[],
                hard_blockers=hard_blockers,
                output_path=action_output,
                overwrite=overwrite,
                input_hash=input_hash,
                budget=budget,
                stop_reason="replay_context_not_ready",
                output_manifest=manifest,
            )
        action_result_dir = output_root / "run-registered-profile-canary-execution"
        action_result = run_optimizer_gate_canary_runner_bundle(
            optimizer_gate_canary_runner_bundle=(
                bundle_path if bundle_path is not None else bundle_payload
            ),
            output_dir=action_result_dir,
            model_eval_chat_completion=model_eval_chat_completion,
            model_eval_model=model or "qwen/qwen3-8b",
            model_eval_base_url=base_url or "http://127.0.0.1:1234/v1",
            model_eval_model_provider=model_provider,
            model_eval_api_key_env=api_key_env,
            model_eval_timeout_seconds=timeout_seconds,
            model_eval_max_tokens=max_tokens,
            overwrite=overwrite,
        )
        artifacts = [
            {
                "name": "optimizer_gate_canary_runner_execution",
                "path": _string_value(action_result.get("output_path"))
                or str(action_result_dir / "optimizer-gate-canary-runner-execution.json"),
            }
        ]
        result_artifacts = (
            action_result.get("artifacts")
            if isinstance(action_result.get("artifacts"), dict)
            else {}
        )
        for name, path in result_artifacts.items():
            path_text = _string_value(path)
            if path_text:
                artifacts.append({"name": name, "path": path_text})
        consumed_budget = _scheduler_experiment_budget(experiment_budget, consumed=1)
        manifest = _scheduler_action_output_manifest(
            action_name=selected_action,
            input_hash=input_hash,
            output_path=action_output,
            action_result=action_result,
            artifacts=artifacts,
            manifest_path=output_root / "optimizer-gate-scheduler-action-output-manifest.json",
            overwrite=overwrite,
        )
        return _optimizer_gate_scheduler_action_payload(
            scheduler_plan=scheduler_plan,
            scheduler_plan_ref=scheduler_plan_ref,
            action_name=selected_action,
            action_status=action_status,
            status="action_completed",
            action_result=action_result,
            artifacts=artifacts,
            hard_blockers=_string_list(action_result.get("hard_blockers")),
            output_path=action_output,
            overwrite=overwrite,
            executes_tool=bool(action_result.get("executes_tool", False)),
            executes_experiment=bool(action_result.get("executes_experiment", False)),
            executes_promotion=False,
            input_hash=input_hash,
            budget=consumed_budget,
            stop_reason="experiment_action_completed",
            output_manifest=manifest,
        )
    return _optimizer_gate_scheduler_action_payload(
        scheduler_plan=scheduler_plan,
        scheduler_plan_ref=scheduler_plan_ref,
        action_name=selected_action,
        action_status=action_status,
        status="blocked_scheduler_action_unsupported",
        action_result={},
        artifacts=[],
        hard_blockers=["scheduler_action_execution_not_supported"],
        output_path=action_output,
        overwrite=overwrite,
    )


_OPTIMIZER_GATE_SCHEDULER_LOOP_READY_STATUSES = {
    "review_promotion_boundary": "ready_for_human_review",
    "build_model_runtime_preflight": "ready_to_build",
    "generate_slice_patch_candidates": "ready_to_generate_candidates",
}


def _optimizer_gate_scheduler_loop_payload(
    *,
    scheduler_plan: dict[str, Any],
    scheduler_plan_ref: str,
    status: str,
    action_results: list[dict[str, Any]],
    artifact_refs: list[dict[str, str]],
    stop_reason: str,
    next_runner_action: str | None,
    recommended_next_action: str | None,
    hard_blockers: list[str],
    output_path: Path,
    overwrite: bool,
    refreshed_scheduler_plans: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    refreshed_plan_results = refreshed_scheduler_plans or []
    payload = {
        "schema_version": OPTIMIZER_GATE_SCHEDULER_LOOP_SCHEMA_VERSION,
        "status": status,
        "optimizer_gate_scheduler_plan_ref": scheduler_plan_ref,
        "proposed_profile_id": _string_value(scheduler_plan.get("proposed_profile_id")),
        "action_count": len(action_results),
        "action_results": action_results,
        "refreshed_scheduler_plan_count": len(refreshed_plan_results),
        "refreshed_scheduler_plans": refreshed_plan_results,
        "artifact_refs": artifact_refs,
        "stop_reason": stop_reason,
        "next_runner_action": next_runner_action,
        "recommended_next_action": recommended_next_action,
        "hard_blockers": _dedupe_strings(hard_blockers),
        "gate": {
            "safe_planning_actions_executed": len(action_results),
            "executes_experiment": any(
                bool(item.get("executes_experiment", False))
                for item in action_results
            ),
            "executes_promotion": False,
        },
        "claim_boundary": (
            "optimizer/gate scheduler loop only; automatically runs safe "
            "planning actions and stops before experiment, canary, promotion, "
            "or official scoring actions"
        ),
        "executes_tool": any(
            bool(item.get("executes_tool", False)) for item in action_results
        ),
        "executes_experiment": any(
            bool(item.get("executes_experiment", False))
            for item in action_results
        ),
        "executes_promotion": False,
        "official_scores_claimed": False,
    }
    _ensure_writable(output_path, overwrite=overwrite)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(output_path)
    return payload


def _optimizer_gate_scheduler_loop_start_index(
    *,
    action_queue: list[dict[str, Any]],
    next_runner_action: str | None,
) -> int:
    if not next_runner_action:
        return 0
    for index, item in enumerate(action_queue):
        if _string_value(item.get("name")) == next_runner_action:
            return index
    return 0


def _optimizer_gate_scheduler_loop_artifact_refs(
    action_payload: dict[str, Any],
) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    output_path = _string_value(action_payload.get("output_path"))
    if output_path:
        refs.append({"name": "scheduler_action", "path": output_path})
    for item in _dict_list(action_payload.get("artifacts")):
        name = _string_value(item.get("name"))
        path = _string_value(item.get("path"))
        if name and path:
            refs.append({"name": name, "path": path})
    return refs


def _optimizer_gate_scheduler_loop_artifact_path(
    action_payload: dict[str, Any],
    artifact_name: str,
) -> str | None:
    for item in _dict_list(action_payload.get("artifacts")):
        if _string_value(item.get("name")) == artifact_name:
            return _string_value(item.get("path"))
    return None


def _optimizer_gate_scheduler_loop_existing_ref(
    scheduler_plan: dict[str, Any],
    key: str,
) -> str | None:
    value = _string_value(scheduler_plan.get(key))
    if not value or value == "inline":
        return None
    return value


def _refresh_optimizer_gate_scheduler_plan_after_action(
    *,
    scheduler_plan: dict[str, Any],
    action_payload: dict[str, Any],
    output_root: Path,
    refresh_index: int,
    overwrite: bool,
) -> tuple[dict[str, Any] | None, list[str]]:
    outcome_schedule_ref = _optimizer_gate_scheduler_loop_existing_ref(
        scheduler_plan,
        "registered_profile_outcome_schedule_ref",
    )
    if outcome_schedule_ref is None:
        return None, ["registered_profile_outcome_schedule_ref_missing_for_refresh"]

    model_runtime_preflight_ref = (
        _optimizer_gate_scheduler_loop_artifact_path(
            action_payload,
            "model_runtime_preflight",
        )
        or _optimizer_gate_scheduler_loop_existing_ref(
            scheduler_plan,
            "model_runtime_preflight_ref",
        )
    )
    slice_optimizer_selection_ref = _optimizer_gate_scheduler_loop_existing_ref(
        scheduler_plan,
        "slice_optimizer_selection_ref",
    )
    output_path = (
        output_root
        / f"refresh-{refresh_index:03d}-optimizer-gate-scheduler-plan.json"
    )
    refreshed_plan = build_optimizer_gate_scheduler_plan(
        registered_profile_outcome_schedule=outcome_schedule_ref,
        model_runtime_preflight=model_runtime_preflight_ref,
        slice_optimizer_selection=slice_optimizer_selection_ref,
        output_path=output_path,
        overwrite=overwrite,
    )
    return refreshed_plan, []


def run_optimizer_gate_scheduler_loop(
    *,
    optimizer_gate_scheduler_plan: dict[str, Any] | str | Path,
    output_dir: str | Path,
    model: str | None = None,
    base_url: str | None = None,
    model_provider: str = "openai-compatible",
    api_key_env: str | None = None,
    execute_probe: bool = False,
    apply_no_think: bool = True,
    max_tokens: int = 512,
    timeout_seconds: int = 30,
    context: dict[str, Any] | str | Path | None = None,
    optimizer_gate_plugin_manifests: list[dict[str, Any] | str | Path] | None = None,
    max_candidates: int = 1,
    max_actions: int = 3,
    auto_refresh_scheduler_plan: bool = False,
    experiment_action_allowlist: list[str] | None = None,
    experiment_budget: dict[str, Any] | None = None,
    canary_runner_bundle: dict[str, Any] | str | Path | None = None,
    model_eval_chat_completion: Any | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run safe scheduler planning actions until the plan needs refresh or stops."""
    scheduler_plan, scheduler_plan_path = _load_object(optimizer_gate_scheduler_plan)
    scheduler_plan_ref = (
        str(scheduler_plan_path) if scheduler_plan_path is not None else "inline"
    )
    output_root = Path(output_dir)
    loop_output = output_root / "optimizer-gate-scheduler-loop.json"
    action_results: list[dict[str, Any]] = []
    refreshed_scheduler_plans: list[dict[str, Any]] = []
    artifact_refs: list[dict[str, str]] = []
    hard_blockers: list[str] = []
    if bool(scheduler_plan.get("official_scores_claimed", False)):
        return _optimizer_gate_scheduler_loop_payload(
            scheduler_plan=scheduler_plan,
            scheduler_plan_ref=scheduler_plan_ref,
            status="loop_blocked_scheduler_claim_boundary",
            action_results=action_results,
            refreshed_scheduler_plans=refreshed_scheduler_plans,
            artifact_refs=artifact_refs,
            stop_reason="scheduler_plan_claims_official_scores",
            next_runner_action=None,
            recommended_next_action="fix_scheduler_plan_claim_boundary",
            hard_blockers=["scheduler_plan_claims_official_scores"],
            output_path=loop_output,
            overwrite=overwrite,
        )
    current_scheduler_plan = scheduler_plan
    current_scheduler_plan_ref = scheduler_plan_ref
    max_action_count = max(1, int(max_actions))
    while True:
        action_queue = _dict_list(current_scheduler_plan.get("action_queue"))
        if not action_queue:
            return _optimizer_gate_scheduler_loop_payload(
                scheduler_plan=current_scheduler_plan,
                scheduler_plan_ref=current_scheduler_plan_ref,
                status="loop_blocked_no_actions",
                action_results=action_results,
                refreshed_scheduler_plans=refreshed_scheduler_plans,
                artifact_refs=artifact_refs,
                stop_reason="scheduler_actions_missing",
                next_runner_action=None,
                recommended_next_action="rebuild_optimizer_gate_scheduler_plan",
                hard_blockers=["scheduler_actions_missing"],
                output_path=loop_output,
                overwrite=overwrite,
            )
        start_index = _optimizer_gate_scheduler_loop_start_index(
            action_queue=action_queue,
            next_runner_action=_string_value(
                current_scheduler_plan.get("next_runner_action")
            ),
        )
        restarted_after_refresh = False
        for queue_index in range(start_index, len(action_queue)):
            item = action_queue[queue_index]
            action_name = _string_value(item.get("name"))
            action_status = _string_value(item.get("status"))
            if not action_name:
                continue
            expected_status = _OPTIMIZER_GATE_SCHEDULER_LOOP_READY_STATUSES.get(
                action_name
            )
            if (
                expected_status is None
                and action_name == "run_registered_profile_canary_execution"
                and action_name in _string_list(experiment_action_allowlist)
            ):
                expected_status = "ready_to_run_canary_execution"
            if expected_status is None:
                if action_results and action_status not in {
                    "ready_to_run_canary_execution",
                    "ready_to_record",
                    "waiting_for_human_review",
                }:
                    return _optimizer_gate_scheduler_loop_payload(
                        scheduler_plan=current_scheduler_plan,
                        scheduler_plan_ref=current_scheduler_plan_ref,
                        status="loop_waiting_for_scheduler_refresh",
                        action_results=action_results,
                        refreshed_scheduler_plans=refreshed_scheduler_plans,
                        artifact_refs=artifact_refs,
                        stop_reason="scheduler_plan_requires_refresh_after_action",
                        next_runner_action=action_name,
                        recommended_next_action="rebuild_optimizer_gate_scheduler_plan",
                        hard_blockers=hard_blockers,
                        output_path=loop_output,
                        overwrite=overwrite,
                    )
                return _optimizer_gate_scheduler_loop_payload(
                    scheduler_plan=current_scheduler_plan,
                    scheduler_plan_ref=current_scheduler_plan_ref,
                    status="loop_stopped_unsupported_action",
                    action_results=action_results,
                    refreshed_scheduler_plans=refreshed_scheduler_plans,
                    artifact_refs=artifact_refs,
                    stop_reason="scheduler_action_execution_not_supported",
                    next_runner_action=action_name,
                    recommended_next_action="manual_review_or_explicit_runner",
                    hard_blockers=hard_blockers
                    + ["scheduler_action_execution_not_supported"],
                    output_path=loop_output,
                    overwrite=overwrite,
                )
            if action_status != expected_status:
                if action_results:
                    return _optimizer_gate_scheduler_loop_payload(
                        scheduler_plan=current_scheduler_plan,
                        scheduler_plan_ref=current_scheduler_plan_ref,
                        status="loop_waiting_for_scheduler_refresh",
                        action_results=action_results,
                        refreshed_scheduler_plans=refreshed_scheduler_plans,
                        artifact_refs=artifact_refs,
                        stop_reason="scheduler_plan_requires_refresh_after_action",
                        next_runner_action=action_name,
                        recommended_next_action="rebuild_optimizer_gate_scheduler_plan",
                        hard_blockers=hard_blockers,
                        output_path=loop_output,
                        overwrite=overwrite,
                    )
                return _optimizer_gate_scheduler_loop_payload(
                    scheduler_plan=current_scheduler_plan,
                    scheduler_plan_ref=current_scheduler_plan_ref,
                    status="loop_stopped_action_not_ready",
                    action_results=action_results,
                    refreshed_scheduler_plans=refreshed_scheduler_plans,
                    artifact_refs=artifact_refs,
                    stop_reason="scheduler_action_not_ready",
                    next_runner_action=action_name,
                    recommended_next_action="rebuild_optimizer_gate_scheduler_plan",
                    hard_blockers=hard_blockers + ["scheduler_action_not_ready"],
                    output_path=loop_output,
                    overwrite=overwrite,
                )
            action_output_dir = (
                output_root
                / f"action-{len(action_results) + 1:03d}-{action_name}"
            )
            action_payload = run_optimizer_gate_scheduler_action(
                optimizer_gate_scheduler_plan=current_scheduler_plan,
                action_name=action_name,
                model=model,
                base_url=base_url,
                model_provider=model_provider,
                api_key_env=api_key_env,
                execute_probe=execute_probe,
                timeout_seconds=timeout_seconds,
                max_tokens=max_tokens,
                apply_no_think=apply_no_think,
                context=context,
                optimizer_gate_plugin_manifests=optimizer_gate_plugin_manifests,
                max_candidates=max_candidates,
                experiment_action_allowlist=experiment_action_allowlist,
                experiment_budget=experiment_budget,
                canary_runner_bundle=canary_runner_bundle,
                model_eval_chat_completion=model_eval_chat_completion,
                output_dir=action_output_dir,
                overwrite=overwrite,
            )
            action_results.append(action_payload)
            artifact_refs.extend(
                _optimizer_gate_scheduler_loop_artifact_refs(action_payload)
            )
            hard_blockers.extend(_string_list(action_payload.get("hard_blockers")))
            if _string_value(action_payload.get("status")) != "action_completed":
                return _optimizer_gate_scheduler_loop_payload(
                    scheduler_plan=current_scheduler_plan,
                    scheduler_plan_ref=current_scheduler_plan_ref,
                    status="loop_stopped_action_failed",
                    action_results=action_results,
                    refreshed_scheduler_plans=refreshed_scheduler_plans,
                    artifact_refs=artifact_refs,
                    stop_reason=_string_value(action_payload.get("status"))
                    or "scheduler_action_failed",
                    next_runner_action=action_name,
                    recommended_next_action="review_scheduler_action_result",
                    hard_blockers=hard_blockers,
                    output_path=loop_output,
                    overwrite=overwrite,
                )
            if len(action_results) >= max_action_count:
                return _optimizer_gate_scheduler_loop_payload(
                    scheduler_plan=current_scheduler_plan,
                    scheduler_plan_ref=current_scheduler_plan_ref,
                    status="loop_max_actions_reached",
                    action_results=action_results,
                    refreshed_scheduler_plans=refreshed_scheduler_plans,
                    artifact_refs=artifact_refs,
                    stop_reason="max_actions_reached",
                    next_runner_action=action_name,
                    recommended_next_action="review_generated_artifacts",
                    hard_blockers=hard_blockers,
                    output_path=loop_output,
                    overwrite=overwrite,
                )
            if auto_refresh_scheduler_plan:
                refreshed_plan, refresh_blockers = (
                    _refresh_optimizer_gate_scheduler_plan_after_action(
                        scheduler_plan=current_scheduler_plan,
                        action_payload=action_payload,
                        output_root=output_root,
                        refresh_index=len(refreshed_scheduler_plans) + 1,
                        overwrite=overwrite,
                    )
                )
                if refresh_blockers:
                    return _optimizer_gate_scheduler_loop_payload(
                        scheduler_plan=current_scheduler_plan,
                        scheduler_plan_ref=current_scheduler_plan_ref,
                        status="loop_waiting_for_scheduler_refresh",
                        action_results=action_results,
                        refreshed_scheduler_plans=refreshed_scheduler_plans,
                        artifact_refs=artifact_refs,
                        stop_reason="scheduler_plan_refresh_input_missing",
                        next_runner_action=action_name,
                        recommended_next_action="rebuild_optimizer_gate_scheduler_plan",
                        hard_blockers=hard_blockers + refresh_blockers,
                        output_path=loop_output,
                        overwrite=overwrite,
                    )
                if refreshed_plan is not None:
                    refreshed_scheduler_plans.append(refreshed_plan)
                    refreshed_path = _string_value(refreshed_plan.get("output_path"))
                    if refreshed_path:
                        artifact_refs.append(
                            {
                                "name": "optimizer_gate_scheduler_plan",
                                "path": refreshed_path,
                            }
                        )
                    current_scheduler_plan = refreshed_plan
                    current_scheduler_plan_ref = refreshed_path or "inline"
                    restarted_after_refresh = True
                    break
        if restarted_after_refresh:
            continue
        return _optimizer_gate_scheduler_loop_payload(
            scheduler_plan=current_scheduler_plan,
            scheduler_plan_ref=current_scheduler_plan_ref,
            status="loop_completed",
            action_results=action_results,
            refreshed_scheduler_plans=refreshed_scheduler_plans,
            artifact_refs=artifact_refs,
            stop_reason="action_queue_exhausted",
            next_runner_action=None,
            recommended_next_action="review_generated_artifacts",
            hard_blockers=hard_blockers,
            output_path=loop_output,
            overwrite=overwrite,
        )


def _optimizer_gate_scheduler_handoff_route(next_runner_action: str | None) -> dict[str, Any]:
    if next_runner_action == "run_registered_profile_canary_execution":
        return {
            "status": "ready_for_explicit_canary_runner",
            "handoff_type": "explicit_canary_runner_handoff",
            "runner": {
                "function": "run_registered_profile_canary_execution",
                "cli_command": "proposal run-registered-profile-canary-execution",
                "mcp_tool": "run_registered_profile_canary_execution",
                "requires_explicit_execute_flag": True,
                "will_execute_experiment_when_invoked": True,
                "executes_promotion_when_invoked": False,
            },
            "required_inputs": [
                "registered_profile_execution_run",
                "registered_profile",
                "canary_rows",
                "model_runtime_preflight",
                "execute_canary_flag",
            ],
            "manual_review_required": True,
            "recommended_next_action": "prepare_explicit_canary_runner_inputs",
        }
    if next_runner_action in {
        "review_promotion_boundary",
        "await_human_promotion_review",
    }:
        return {
            "status": "waiting_for_human_promotion_review",
            "handoff_type": "human_promotion_review_handoff",
            "runner": {
                "function": None,
                "cli_command": None,
                "mcp_tool": None,
                "requires_explicit_execute_flag": False,
                "will_execute_experiment_when_invoked": False,
                "executes_promotion_when_invoked": False,
            },
            "required_inputs": [
                "canary_result_gate",
                "promotion_policy",
                "human_approval",
            ],
            "manual_review_required": True,
            "recommended_next_action": "open_human_promotion_review_queue",
        }
    if next_runner_action == "record_slice_patch_outcome":
        return {
            "status": "ready_for_outcome_recording_review",
            "handoff_type": "outcome_recording_review_handoff",
            "runner": {
                "function": "record_slice_patch_outcome",
                "cli_command": "proposal record-slice-patch-outcome",
                "mcp_tool": "record_slice_patch_outcome",
                "requires_explicit_execute_flag": False,
                "will_execute_experiment_when_invoked": False,
                "executes_promotion_when_invoked": False,
            },
            "required_inputs": ["candidate", "materialization", "gate_decision"],
            "manual_review_required": True,
            "recommended_next_action": "review_and_record_slice_patch_outcome",
        }
    return {
        "status": "waiting_for_scheduler_operator_review",
        "handoff_type": "scheduler_operator_review_handoff",
        "runner": {
            "function": None,
            "cli_command": None,
            "mcp_tool": None,
            "requires_explicit_execute_flag": False,
            "will_execute_experiment_when_invoked": False,
            "executes_promotion_when_invoked": False,
        },
        "required_inputs": ["scheduler_plan_refresh_or_manual_decision"],
        "manual_review_required": True,
        "recommended_next_action": "review_scheduler_loop_result",
    }


def build_optimizer_gate_scheduler_handoff(
    *,
    optimizer_gate_scheduler_loop: dict[str, Any] | str | Path,
    output_path: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a non-executing handoff from scheduler loop boundary output."""
    loop_payload, loop_path = _load_object(optimizer_gate_scheduler_loop)
    output = Path(output_path)
    _ensure_writable(output, overwrite=overwrite)
    next_runner_action = _string_value(loop_payload.get("next_runner_action"))
    route = _optimizer_gate_scheduler_handoff_route(next_runner_action)
    hard_blockers = _string_list(loop_payload.get("hard_blockers"))
    if bool(loop_payload.get("official_scores_claimed", False)):
        hard_blockers.append("scheduler_loop_claims_official_scores")
        route = {
            **_optimizer_gate_scheduler_handoff_route(None),
            "status": "blocked_scheduler_loop_claim_boundary",
            "handoff_type": "claim_boundary_review_handoff",
            "recommended_next_action": "fix_scheduler_loop_claim_boundary",
        }
    payload = {
        "schema_version": OPTIMIZER_GATE_SCHEDULER_HANDOFF_SCHEMA_VERSION,
        "status": route["status"],
        "optimizer_gate_scheduler_loop_ref": (
            str(loop_path) if loop_path is not None else "inline"
        ),
        "optimizer_gate_scheduler_plan_ref": _string_value(
            loop_payload.get("optimizer_gate_scheduler_plan_ref")
        ),
        "proposed_profile_id": _string_value(loop_payload.get("proposed_profile_id")),
        "source_loop_status": _string_value(loop_payload.get("status")) or "unknown",
        "source_stop_reason": _string_value(loop_payload.get("stop_reason")),
        "handoff_type": route["handoff_type"],
        "next_runner_action": next_runner_action,
        "runner": route["runner"],
        "required_inputs": route["required_inputs"],
        "manual_review_required": bool(route["manual_review_required"]),
        "recommended_next_action": route["recommended_next_action"],
        "source_artifact_refs": _dict_list(loop_payload.get("artifact_refs")),
        "hard_blockers": _dedupe_strings(hard_blockers),
        "claim_boundary": (
            "optimizer/gate scheduler handoff only; routes scheduler loop "
            "boundaries to explicit runner or human review inputs but does not "
            "execute experiments, promotion, or official scoring"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "executes_promotion": False,
        "official_scores_claimed": False,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(output)
    return payload


def _input_ref(value: Any, loaded_path: Path | None = None) -> str | None:
    if loaded_path is not None:
        return _path_ref(loaded_path)
    if isinstance(value, (str, Path)):
        return _path_ref(value)
    if value is None:
        return None
    return "inline"


def _path_ref(path_value: str | Path | None) -> str | None:
    if path_value is None:
        return None
    raw_path = Path(path_value)
    try:
        resolved = raw_path.expanduser().resolve()
        return str(resolved.relative_to(Path.cwd().resolve()))
    except (OSError, ValueError):
        return str(path_value)


def build_optimizer_gate_canary_runner_bundle(
    *,
    optimizer_gate_scheduler_handoff: dict[str, Any] | str | Path,
    registered_profile_execution_run: dict[str, Any] | str | Path | None,
    registered_profile: dict[str, Any] | str | Path | None,
    canary_rows: list[dict[str, Any]] | dict[str, Any] | str | Path | None,
    model_runtime_preflight: dict[str, Any] | str | Path | None,
    output_path: str | Path,
    execute_canary: bool = True,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a non-executing bundle for the explicit canary runner."""
    handoff_payload, handoff_path = _load_object(optimizer_gate_scheduler_handoff)
    run_payload: dict[str, Any] = {}
    run_path: Path | None = None
    if registered_profile_execution_run is not None:
        run_payload, run_path = _load_object(registered_profile_execution_run)
    profile_payload: dict[str, Any] = {}
    profile_path: Path | None = None
    if registered_profile is not None:
        profile_payload, profile_path = _load_object(registered_profile)
    preflight_payload: dict[str, Any] = {}
    preflight_path: Path | None = None
    if model_runtime_preflight is not None:
        preflight_payload, preflight_path = _load_object(model_runtime_preflight)
    rows = _load_prompt_leakage_rows(canary_rows)

    output = Path(output_path)
    _ensure_writable(output, overwrite=overwrite)

    handoff_type = _string_value(handoff_payload.get("handoff_type"))
    next_runner_action = _string_value(handoff_payload.get("next_runner_action"))
    runner = (
        handoff_payload.get("runner")
        if isinstance(handoff_payload.get("runner"), dict)
        else {}
    )
    runner_function = _string_value(runner.get("function"))
    canary_handoff = (
        handoff_type == "explicit_canary_runner_handoff"
        and next_runner_action == "run_registered_profile_canary_execution"
        and runner_function == "run_registered_profile_canary_execution"
    )

    run_gate = run_payload.get("gate") if isinstance(run_payload.get("gate"), dict) else {}
    canary_allowed = bool(run_gate.get("canary_allowed", False))
    preflight_gate = (
        preflight_payload.get("gate")
        if isinstance(preflight_payload.get("gate"), dict)
        else {}
    )
    model_runtime_blockers = _string_list(preflight_payload.get("hard_blockers"))
    model_runtime_ready = (
        bool(preflight_gate.get("model_runtime_ready", False))
        and not model_runtime_blockers
    )
    canary_row_count = len(rows) if rows is not None else 0
    proposed_profile_ids = _dedupe_strings([
        _string_value(handoff_payload.get("proposed_profile_id")),
        _string_value(run_payload.get("proposed_profile_id")),
        _string_value(profile_payload.get("proposed_profile_id")),
    ])
    profile_id_consistent = len(proposed_profile_ids) <= 1

    hard_blockers: list[str] = []
    if not canary_handoff:
        hard_blockers.append("handoff_not_for_canary_runner")
    if registered_profile_execution_run is None:
        hard_blockers.append("registered_profile_execution_run_missing")
    if registered_profile is None:
        hard_blockers.append("registered_profile_missing")
    if canary_rows is None or canary_row_count <= 0:
        hard_blockers.append("canary_rows_missing")
    if model_runtime_preflight is None:
        hard_blockers.append("model_runtime_preflight_missing")
    elif not model_runtime_ready:
        hard_blockers.append("model_runtime_preflight_not_ready")
    if not canary_allowed:
        hard_blockers.append("canary_not_allowed_by_dev_gate")
    if not execute_canary:
        hard_blockers.append("execute_canary_flag_missing")
    if not profile_id_consistent:
        hard_blockers.append("proposed_profile_id_mismatch")
    if bool(handoff_payload.get("official_scores_claimed", False)):
        hard_blockers.append("handoff_claims_official_scores")
    if bool(run_payload.get("official_scores_claimed", False)):
        hard_blockers.append("execution_run_claims_official_scores")
    if bool(profile_payload.get("official_scores_claimed", False)):
        hard_blockers.append("registered_profile_claims_official_scores")
    if bool(preflight_payload.get("official_scores_claimed", False)):
        hard_blockers.append("model_runtime_preflight_claims_official_scores")
    handoff_blockers = _string_list(handoff_payload.get("hard_blockers"))
    if canary_handoff:
        handoff_blockers = [
            blocker
            for blocker in handoff_blockers
            if blocker != "scheduler_action_execution_not_supported"
        ]
    hard_blockers.extend(handoff_blockers)
    hard_blockers.extend(_string_list(run_payload.get("hard_blockers")))
    hard_blockers.extend(model_runtime_blockers)
    hard_blockers = _dedupe_strings(hard_blockers)

    runner_inputs_ready = (
        canary_handoff
        and registered_profile_execution_run is not None
        and registered_profile is not None
        and canary_row_count > 0
        and model_runtime_ready
        and canary_allowed
        and execute_canary
        and not hard_blockers
    )
    if runner_inputs_ready:
        status = "ready_for_explicit_canary_runner"
        recommended_next_action = "run_explicit_canary_runner"
    elif not canary_handoff:
        status = "blocked_handoff_not_canary_runner"
        recommended_next_action = "return_to_scheduler_handoff_review"
    elif not canary_allowed:
        status = "blocked_by_dev_hard_gate"
        recommended_next_action = "return_to_registered_profile_gate"
    elif (
        registered_profile_execution_run is None
        or registered_profile is None
        or canary_row_count <= 0
        or model_runtime_preflight is None
    ):
        status = "blocked_missing_runner_inputs"
        recommended_next_action = "provide_canary_runner_inputs"
    elif not model_runtime_ready:
        status = "blocked_model_runtime_preflight"
        recommended_next_action = "refresh_model_runtime_preflight"
    else:
        status = "blocked_runner_input_review"
        recommended_next_action = "review_canary_runner_bundle"

    execution_run_ref = _input_ref(registered_profile_execution_run, run_path)
    registered_profile_ref = _input_ref(registered_profile, profile_path)
    canary_rows_ref = _input_ref(canary_rows)
    model_runtime_preflight_ref = _input_ref(model_runtime_preflight, preflight_path)
    cli_argv = [
        "proposal",
        "run-registered-profile-canary-execution",
        "--registered-profile-execution-run",
        execution_run_ref or "<registered-profile-execution-run>",
        "--registered-profile",
        registered_profile_ref or "<registered-profile>",
        "--canary-rows",
        canary_rows_ref or "<canary-rows>",
        "--model-runtime-preflight",
        model_runtime_preflight_ref or "<model-runtime-preflight>",
        "--execute-canary",
        "--output-dir",
        "<output-dir>",
    ]
    mcp_arguments = {
        "registered_profile_execution_run_file": execution_run_ref,
        "registered_profile_file": registered_profile_ref,
        "canary_rows_file": canary_rows_ref,
        "model_runtime_preflight_file": model_runtime_preflight_ref,
        "execute_canary": True,
        "output_dir": "<output-dir>",
    }
    payload = {
        "schema_version": OPTIMIZER_GATE_CANARY_RUNNER_BUNDLE_SCHEMA_VERSION,
        "status": status,
        "optimizer_gate_scheduler_handoff_ref": _input_ref(
            optimizer_gate_scheduler_handoff,
            handoff_path,
        ),
        "proposed_profile_id": (
            proposed_profile_ids[0] if proposed_profile_ids else None
        ),
        "handoff": {
            "status": _string_value(handoff_payload.get("status")),
            "type": handoff_type,
            "next_runner_action": next_runner_action,
        },
        "runner": {
            "function": "run_registered_profile_canary_execution",
            "cli_command": "proposal run-registered-profile-canary-execution",
            "mcp_tool": "run_registered_profile_canary_execution",
            "requires_explicit_execute_flag": True,
            "will_execute_experiment_when_invoked": True,
            "executes_promotion_when_invoked": False,
        },
        "input_bundle": {
            "registered_profile_execution_run_ref": execution_run_ref,
            "registered_profile_ref": registered_profile_ref,
            "canary_rows_ref": canary_rows_ref,
            "model_runtime_preflight_ref": model_runtime_preflight_ref,
            "execute_canary_flag": bool(execute_canary),
            "canary_row_count": canary_row_count,
        },
        "gate": {
            "runner_inputs_ready": runner_inputs_ready,
            "canary_allowed": canary_allowed,
            "model_runtime_ready": model_runtime_ready,
            "canary_handoff": canary_handoff,
            "profile_id_consistent": profile_id_consistent,
        },
        "hard_blockers": hard_blockers,
        "cli_argv": cli_argv,
        "mcp_tool_call": {
            "name": "run_registered_profile_canary_execution",
            "arguments": mcp_arguments,
        },
        "recommended_next_action": recommended_next_action,
        "claim_boundary": (
            "optimizer/gate canary runner bundle only; binds scheduler handoff "
            "inputs to the explicit canary runner but does not invoke it, run "
            "experiments, promote, or claim official scores"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "executes_promotion": False,
        "official_scores_claimed": False,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(output)
    return payload


def _optimizer_gate_runner_input_path(ref: Any) -> Path | None:
    ref_text = _string_value(ref)
    if not ref_text or ref_text == "inline" or ref_text.startswith("<"):
        return None
    return Path(ref_text)


def run_optimizer_gate_canary_runner_bundle(
    *,
    optimizer_gate_canary_runner_bundle: dict[str, Any] | str | Path,
    output_dir: str | Path,
    model_eval_chat_completion: Any | None = None,
    model_eval_model: str = "qwen/qwen3-8b",
    model_eval_base_url: str = "http://127.0.0.1:1234/v1",
    model_eval_model_provider: str = "openai-compatible",
    model_eval_api_key_env: str | None = None,
    model_eval_timeout_seconds: int = 120,
    model_eval_temperature: float = 0.0,
    model_eval_max_tokens: int = 512,
    model_eval_judge_mode: str = "heuristic",
    min_canary_row_count: int = 1,
    max_failure_count: int = 0,
    max_runtime_error_count: int = 0,
    max_empty_output_count: int = 0,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run the explicit canary runner described by a replayable bundle."""
    bundle_payload, bundle_path = _load_object(optimizer_gate_canary_runner_bundle)
    output_root = Path(output_dir)
    output_path = output_root / "optimizer-gate-canary-runner-execution.json"
    _ensure_writable(output_path, overwrite=overwrite)

    runner = (
        bundle_payload.get("runner")
        if isinstance(bundle_payload.get("runner"), dict)
        else {}
    )
    input_bundle = (
        bundle_payload.get("input_bundle")
        if isinstance(bundle_payload.get("input_bundle"), dict)
        else {}
    )
    source_gate = (
        bundle_payload.get("gate")
        if isinstance(bundle_payload.get("gate"), dict)
        else {}
    )
    runner_function = _string_value(runner.get("function"))
    runner_inputs_ready = bool(source_gate.get("runner_inputs_ready", False))
    proposed_profile_id = _string_value(bundle_payload.get("proposed_profile_id"))

    execution_path = output_root / "registered-profile-canary-execution.json"
    result_gate_path = output_root / "registered-profile-canary-result-gate.json"
    hard_blockers = _string_list(bundle_payload.get("hard_blockers"))
    if _string_value(bundle_payload.get("status")) != "ready_for_explicit_canary_runner":
        hard_blockers.append("canary_runner_bundle_not_ready")
    if not runner_inputs_ready:
        hard_blockers.append("runner_inputs_not_ready")
    if runner_function != "run_registered_profile_canary_execution":
        hard_blockers.append("unsupported_canary_runner_function")
    if not bool(input_bundle.get("execute_canary_flag", False)):
        hard_blockers.append("execute_canary_flag_missing")
    if bool(bundle_payload.get("official_scores_claimed", False)):
        hard_blockers.append("canary_runner_bundle_claims_official_scores")

    registered_profile_execution_run_path = _optimizer_gate_runner_input_path(
        input_bundle.get("registered_profile_execution_run_ref")
    )
    registered_profile_path = _optimizer_gate_runner_input_path(
        input_bundle.get("registered_profile_ref")
    )
    canary_rows_path = _optimizer_gate_runner_input_path(
        input_bundle.get("canary_rows_ref")
    )
    model_runtime_preflight_path = _optimizer_gate_runner_input_path(
        input_bundle.get("model_runtime_preflight_ref")
    )
    replayable_inputs = {
        "registered_profile_execution_run": registered_profile_execution_run_path,
        "registered_profile": registered_profile_path,
        "canary_rows": canary_rows_path,
        "model_runtime_preflight": model_runtime_preflight_path,
    }
    for input_name, input_path in replayable_inputs.items():
        if input_path is None:
            hard_blockers.append(f"{input_name}_ref_not_replayable")
        elif not input_path.exists():
            hard_blockers.append(f"{input_name}_ref_missing")
    hard_blockers = _dedupe_strings(hard_blockers)

    canary_execution: dict[str, Any] | None = None
    canary_result_gate: dict[str, Any] | None = None
    if not hard_blockers:
        canary_execution = run_registered_profile_canary_execution(
            registered_profile_execution_run=registered_profile_execution_run_path,
            registered_profile=registered_profile_path,
            model_runtime_preflight=model_runtime_preflight_path,
            execute_canary=True,
            canary_rows=canary_rows_path,
            model_eval_chat_completion=model_eval_chat_completion,
            model_eval_model=model_eval_model,
            model_eval_base_url=model_eval_base_url,
            model_eval_model_provider=model_eval_model_provider,
            model_eval_api_key_env=model_eval_api_key_env,
            model_eval_timeout_seconds=model_eval_timeout_seconds,
            model_eval_temperature=model_eval_temperature,
            model_eval_max_tokens=model_eval_max_tokens,
            model_eval_judge_mode=model_eval_judge_mode,
            output_dir=output_root,
            overwrite=overwrite,
        )
        canary_result_gate = build_registered_profile_canary_result_gate(
            registered_profile_canary_execution=canary_execution,
            min_canary_row_count=min_canary_row_count,
            max_failure_count=max_failure_count,
            max_runtime_error_count=max_runtime_error_count,
            max_empty_output_count=max_empty_output_count,
            output_path=result_gate_path,
            overwrite=overwrite,
        )
        hard_blockers = _dedupe_strings(
            _string_list(canary_result_gate.get("hard_blockers"))
        )

    canary_completed = bool(
        (
            canary_execution.get("gate")
            if isinstance(canary_execution, dict)
            and isinstance(canary_execution.get("gate"), dict)
            else {}
        ).get("canary_completed", False)
    )
    result_gate = (
        canary_result_gate.get("gate")
        if isinstance(canary_result_gate, dict)
        and isinstance(canary_result_gate.get("gate"), dict)
        else {}
    )
    canary_passed = bool(result_gate.get("canary_passed", False))
    promotion_ready = bool(result_gate.get("promotion_ready", False))
    if canary_result_gate is not None:
        status = (
            "canary_runner_completed"
            if canary_passed
            else "blocked_by_canary_result_gate"
        )
        recommended_next_action = (
            "build_optimizer_gate_scheduler_plan"
            if canary_passed
            else _string_value(canary_result_gate.get("recommended_next_action"))
        )
    elif "runner_inputs_not_ready" in hard_blockers:
        status = "blocked_by_canary_runner_bundle"
        recommended_next_action = "return_to_canary_runner_bundle"
    else:
        status = "blocked_missing_replayable_runner_inputs"
        recommended_next_action = "rebuild_canary_runner_bundle_with_file_refs"

    payload = {
        "schema_version": OPTIMIZER_GATE_CANARY_RUNNER_EXECUTION_SCHEMA_VERSION,
        "status": status,
        "optimizer_gate_canary_runner_bundle_ref": _input_ref(
            optimizer_gate_canary_runner_bundle,
            bundle_path,
        ),
        "proposed_profile_id": proposed_profile_id,
        "runner": {
            "function": "run_registered_profile_canary_execution",
            "source_function": runner_function,
            "result_gate_function": "build_registered_profile_canary_result_gate",
        },
        "input_bundle": {
            "registered_profile_execution_run_ref": (
                str(registered_profile_execution_run_path)
                if registered_profile_execution_run_path is not None
                else None
            ),
            "registered_profile_ref": (
                str(registered_profile_path)
                if registered_profile_path is not None
                else None
            ),
            "canary_rows_ref": (
                str(canary_rows_path) if canary_rows_path is not None else None
            ),
            "model_runtime_preflight_ref": (
                str(model_runtime_preflight_path)
                if model_runtime_preflight_path is not None
                else None
            ),
            "execute_canary_flag": bool(input_bundle.get("execute_canary_flag", False)),
        },
        "artifacts": {
            "registered_profile_canary_execution": (
                str(execution_path) if canary_execution is not None else None
            ),
            "registered_profile_canary_result_gate": (
                str(result_gate_path) if canary_result_gate is not None else None
            ),
        },
        "gate": {
            "runner_inputs_ready": runner_inputs_ready and not hard_blockers,
            "canary_completed": canary_completed,
            "canary_passed": canary_passed,
            "promotion_ready": promotion_ready,
        },
        "hard_blockers": hard_blockers,
        "recommended_next_action": recommended_next_action,
        "claim_boundary": (
            "optimizer/gate canary runner execution wrapper only; executes the "
            "explicit local canary runner from replayable bundle inputs and "
            "builds the local canary result gate, but does not promote, submit, "
            "or claim official scores"
        ),
        "executes_tool": canary_execution is not None,
        "executes_experiment": canary_execution is not None,
        "executes_promotion": False,
        "official_scores_claimed": False,
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(output_path)
    return payload


def build_optimizer_gate_promotion_review_queue(
    *,
    optimizer_gate_scheduler_handoff: dict[str, Any] | str | Path,
    canary_result_gate: dict[str, Any] | str | Path | None,
    output_path: str | Path,
    promotion_policy: dict[str, Any] | str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a non-executing human promotion review queue from a handoff."""
    handoff_payload, handoff_path = _load_object(optimizer_gate_scheduler_handoff)
    gate_payload: dict[str, Any] = {}
    gate_path: Path | None = None
    if canary_result_gate is not None:
        gate_payload, gate_path = _load_object(canary_result_gate)
    policy_payload: dict[str, Any] = {}
    policy_path: Path | None = None
    if promotion_policy is not None:
        policy_payload, policy_path = _load_object(promotion_policy)

    output = Path(output_path)
    _ensure_writable(output, overwrite=overwrite)

    handoff_type = _string_value(handoff_payload.get("handoff_type"))
    next_runner_action = _string_value(handoff_payload.get("next_runner_action"))
    promotion_handoff = (
        handoff_type == "human_promotion_review_handoff"
        and next_runner_action
        in {"review_promotion_boundary", "await_human_promotion_review"}
    )
    gate = gate_payload.get("gate") if isinstance(gate_payload.get("gate"), dict) else {}
    promotion_ready = bool(gate.get("promotion_ready", False))
    canary_passed = bool(gate.get("canary_passed", False))
    canary_completed = bool(gate.get("canary_completed", canary_passed))
    human_approval_required = bool(
        policy_payload.get("requires_human_approval", True)
        if isinstance(policy_payload, dict)
        else True
    )
    proposed_profile_ids = _dedupe_strings([
        _string_value(handoff_payload.get("proposed_profile_id")),
        _string_value(gate_payload.get("proposed_profile_id")),
    ])
    profile_id_consistent = len(proposed_profile_ids) <= 1

    hard_blockers: list[str] = []
    if not promotion_handoff:
        hard_blockers.append("handoff_not_for_promotion_review")
    if canary_result_gate is None:
        hard_blockers.append("canary_result_gate_missing")
    if not canary_completed:
        hard_blockers.append("canary_not_completed")
    if not canary_passed:
        hard_blockers.append("canary_not_passed")
    if not promotion_ready:
        hard_blockers.append("promotion_not_ready_by_canary_gate")
    if not profile_id_consistent:
        hard_blockers.append("proposed_profile_id_mismatch")
    if bool(handoff_payload.get("official_scores_claimed", False)):
        hard_blockers.append("handoff_claims_official_scores")
    if bool(gate_payload.get("official_scores_claimed", False)):
        hard_blockers.append("canary_result_gate_claims_official_scores")
    if bool(policy_payload.get("official_scores_claimed", False)):
        hard_blockers.append("promotion_policy_claims_official_scores")
    handoff_blockers = _string_list(handoff_payload.get("hard_blockers"))
    if promotion_handoff:
        handoff_blockers = [
            blocker
            for blocker in handoff_blockers
            if blocker != "scheduler_action_execution_not_supported"
        ]
    hard_blockers.extend(handoff_blockers)
    hard_blockers.extend(_string_list(gate_payload.get("hard_blockers")))
    hard_blockers = _dedupe_strings(hard_blockers)

    review_queue_ready = promotion_handoff and not hard_blockers
    if review_queue_ready:
        status = "waiting_for_human_promotion_review"
        recommended_next_action = "collect_human_promotion_review"
    elif not promotion_handoff:
        status = "blocked_handoff_not_promotion_review"
        recommended_next_action = "return_to_scheduler_handoff_review"
    elif canary_result_gate is None:
        status = "blocked_missing_review_inputs"
        recommended_next_action = "provide_canary_result_gate"
    else:
        status = "blocked_promotion_review_gate"
        recommended_next_action = "return_to_canary_result_gate"

    proposed_profile_id = proposed_profile_ids[0] if proposed_profile_ids else None
    review_item = {
        "item_id": (
            f"{proposed_profile_id}-promotion-review"
            if proposed_profile_id
            else "promotion-review"
        ),
        "review_type": "promotion_boundary",
        "proposed_profile_id": proposed_profile_id,
        "canary_result_gate_ref": _input_ref(canary_result_gate, gate_path),
        "promotion_policy_ref": _input_ref(promotion_policy, policy_path),
        "required_decisions": [
            "confirm_canary_result_gate",
            "confirm_claim_boundary",
            "approve_or_reject_local_promotion_candidate",
        ],
        "status": "waiting_for_human_review" if review_queue_ready else "blocked",
    }
    payload = {
        "schema_version": OPTIMIZER_GATE_PROMOTION_REVIEW_QUEUE_SCHEMA_VERSION,
        "status": status,
        "optimizer_gate_scheduler_handoff_ref": _input_ref(
            optimizer_gate_scheduler_handoff,
            handoff_path,
        ),
        "canary_result_gate_ref": _input_ref(canary_result_gate, gate_path),
        "promotion_policy_ref": _input_ref(promotion_policy, policy_path),
        "proposed_profile_id": proposed_profile_id,
        "handoff": {
            "status": _string_value(handoff_payload.get("status")),
            "type": handoff_type,
            "next_runner_action": next_runner_action,
        },
        "source_gate": {
            "status": _string_value(gate_payload.get("status")),
            "canary_completed": canary_completed,
            "canary_passed": canary_passed,
            "promotion_ready": promotion_ready,
        },
        "promotion_policy": (
            policy_payload
            if policy_payload
            else {
                "policy_id": "default-human-promotion-review",
                "requires_human_approval": True,
            }
        ),
        "review_queue": [review_item] if review_queue_ready else [review_item],
        "gate": {
            "review_queue_ready": review_queue_ready,
            "promotion_ready": promotion_ready,
            "human_approval_required": human_approval_required,
            "profile_id_consistent": profile_id_consistent,
        },
        "hard_blockers": hard_blockers,
        "recommended_next_action": recommended_next_action,
        "claim_boundary": (
            "optimizer/gate promotion review queue only; queues a human "
            "promotion boundary review from local canary gate evidence but does "
            "not approve, promote, submit, or claim official scores"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "executes_promotion": False,
        "official_scores_claimed": False,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(output)
    return payload


def build_optimizer_gate_human_promotion_approval(
    *,
    promotion_review_queue: dict[str, Any] | str | Path,
    output_path: str | Path,
    approved: bool,
    approved_by: str,
    decision_notes: str | None = None,
    reviewed_at: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Record a human promotion review decision without executing promotion."""
    queue_payload, queue_path = _load_object(promotion_review_queue)
    output = Path(output_path)
    _ensure_writable(output, overwrite=overwrite)

    gate = (
        queue_payload.get("gate")
        if isinstance(queue_payload.get("gate"), dict)
        else {}
    )
    queue_items = (
        queue_payload.get("review_queue")
        if isinstance(queue_payload.get("review_queue"), list)
        else []
    )
    proposed_profile_id = _string_value(queue_payload.get("proposed_profile_id"))
    queue_ready = (
        _string_value(queue_payload.get("status")) == "waiting_for_human_promotion_review"
        and bool(gate.get("review_queue_ready", False))
        and bool(gate.get("promotion_ready", False))
        and bool(queue_items)
    )
    reviewer = _string_value(approved_by)

    hard_blockers = _string_list(queue_payload.get("hard_blockers"))
    if not queue_ready:
        hard_blockers.append("promotion_review_queue_not_ready")
    if not reviewer:
        hard_blockers.append("approved_by_missing")
    if bool(queue_payload.get("official_scores_claimed", False)):
        hard_blockers.append("promotion_review_queue_claims_official_scores")
    hard_blockers = _dedupe_strings(hard_blockers)

    human_approved = bool(approved) and not hard_blockers
    human_rejected = not bool(approved) and queue_ready and not hard_blockers
    if human_approved:
        status = "approved_for_local_promotion_action"
        recommended_next_action = "run_local_promotion_action"
    elif human_rejected:
        status = "rejected_by_human_review"
        recommended_next_action = "return_to_optimizer_selection"
    else:
        status = "blocked_review_queue_not_ready"
        recommended_next_action = "return_to_promotion_review_queue"

    review_item = queue_items[0] if queue_items and isinstance(queue_items[0], dict) else {}
    payload = {
        "schema_version": OPTIMIZER_GATE_HUMAN_PROMOTION_APPROVAL_SCHEMA_VERSION,
        "status": status,
        "promotion_review_queue_ref": _input_ref(promotion_review_queue, queue_path),
        "proposed_profile_id": proposed_profile_id,
        "review_item_ref": _string_value(review_item.get("item_id")),
        "review": {
            "approved": bool(approved),
            "approved_by": reviewer or None,
            "reviewed_at": _string_value(reviewed_at),
            "decision_notes": _string_value(decision_notes),
            "required_decisions": (
                review_item.get("required_decisions")
                if isinstance(review_item.get("required_decisions"), list)
                else []
            ),
        },
        "gate": {
            "review_queue_ready": queue_ready,
            "human_approved": human_approved,
            "human_rejected": human_rejected,
            "promotion_ready": human_approved,
        },
        "hard_blockers": hard_blockers,
        "recommended_next_action": recommended_next_action,
        "claim_boundary": (
            "optimizer/gate human promotion approval artifact only; records a "
            "human decision from local canary gate evidence but does not execute "
            "promotion, submit results, or claim official scores"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "executes_promotion": False,
        "official_scores_claimed": False,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(output)
    return payload


def run_optimizer_gate_local_promotion_action(
    *,
    human_promotion_approval: dict[str, Any] | str | Path,
    output_path: str | Path,
    execute_promotion: bool = False,
    promoted_by: str | None = None,
    promoted_at: str | None = None,
    profile_registry: dict[str, Any] | str | Path | None = None,
    registry_output_path: str | Path | None = None,
    rollback_output_path: str | Path | None = None,
    audit_log_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Apply an explicit local registry promotion after human approval."""
    approval_payload, approval_path = _load_object(human_promotion_approval)
    output = Path(output_path)
    _ensure_writable(output, overwrite=overwrite)
    registry_payload: dict[str, Any] | None = None
    registry_path: Path | None = None
    if profile_registry is not None:
        registry_payload, registry_path = _load_object(profile_registry)
    elif registry_output_path is not None and Path(registry_output_path).exists():
        registry_payload, registry_path = _load_object(Path(registry_output_path))

    approval_gate = (
        approval_payload.get("gate")
        if isinstance(approval_payload.get("gate"), dict)
        else {}
    )
    approval_ready = (
        _string_value(approval_payload.get("status"))
        == "approved_for_local_promotion_action"
        and bool(approval_gate.get("human_approved", False))
        and bool(approval_gate.get("promotion_ready", False))
    )
    proposed_profile_id = _string_value(approval_payload.get("proposed_profile_id"))
    promoter = _string_value(promoted_by)

    hard_blockers = _string_list(approval_payload.get("hard_blockers"))
    if not approval_ready:
        hard_blockers.append("human_promotion_approval_not_ready")
    if not execute_promotion:
        hard_blockers.append("execute_promotion_flag_missing")
    if not promoter:
        hard_blockers.append("promoted_by_missing")
    if execute_promotion and registry_output_path is None:
        hard_blockers.append("registry_output_path_missing")
    if execute_promotion and registry_payload is None:
        hard_blockers.append("profile_registry_missing")
    if execute_promotion and rollback_output_path is None:
        hard_blockers.append("rollback_output_path_missing")
    if execute_promotion and audit_log_path is None:
        hard_blockers.append("audit_log_path_missing")
    if bool(approval_payload.get("official_scores_claimed", False)):
        hard_blockers.append("human_promotion_approval_claims_official_scores")
    if registry_payload is not None and bool(
        registry_payload.get("official_scores_claimed", False)
    ):
        hard_blockers.append("profile_registry_claims_official_scores")
    profiles = (
        registry_payload.get("profiles")
        if isinstance(registry_payload, dict) and isinstance(registry_payload.get("profiles"), dict)
        else {}
    )
    if execute_promotion and registry_payload is not None and not proposed_profile_id:
        hard_blockers.append("proposed_profile_id_missing")
    if (
        execute_promotion
        and registry_payload is not None
        and proposed_profile_id
        and proposed_profile_id not in profiles
    ):
        hard_blockers.append("proposed_profile_missing_from_registry")
    hard_blockers = _dedupe_strings(hard_blockers)

    promotion_executed = approval_ready and execute_promotion and not hard_blockers
    if promotion_executed:
        status = "local_promotion_recorded"
        recommended_next_action = "record_slice_patch_outcome"
    else:
        status = "blocked_local_promotion_action"
        recommended_next_action = "return_to_human_promotion_approval"

    local_promotion_record = (
        {
            "proposed_profile_id": proposed_profile_id,
            "promoted_by": promoter,
            "promoted_at": _string_value(promoted_at),
            "source_approval_ref": _input_ref(human_promotion_approval, approval_path),
            "promotion_scope": "local_optimizer_gate_registry",
            "official_submission": False,
        }
        if promotion_executed
        else None
    )
    write_target: dict[str, Any] | None = None
    registry_diff: dict[str, Any] | None = None
    rollback_record: dict[str, Any] | None = None
    audit_log: dict[str, Any] | None = None
    if promotion_executed and registry_payload is not None:
        target = Path(registry_output_path)  # type: ignore[arg-type]
        rollback_target = Path(rollback_output_path)  # type: ignore[arg-type]
        audit_target = Path(audit_log_path)  # type: ignore[arg-type]
        _ensure_writable(rollback_target, overwrite=overwrite)
        audit_target.parent.mkdir(parents=True, exist_ok=True)
        before_registry = _json_clone(registry_payload)
        after_registry = _json_clone(registry_payload)
        before_active = _string_value(before_registry.get("active_profile_id"))
        after_profiles = (
            after_registry.get("profiles")
            if isinstance(after_registry.get("profiles"), dict)
            else {}
        )
        proposed_profile = after_profiles[proposed_profile_id]
        if isinstance(proposed_profile, dict):
            proposed_profile["status"] = "active"
            proposed_profile["promoted_by"] = promoter
            proposed_profile["promoted_at"] = _string_value(promoted_at)
            proposed_profile["source_approval_ref"] = _input_ref(
                human_promotion_approval,
                approval_path,
            )
        after_registry["schema_version"] = _string_value(
            after_registry.get("schema_version")
        ) or LOCAL_PROFILE_REGISTRY_SCHEMA_VERSION
        after_registry["active_profile_id"] = proposed_profile_id
        after_registry["last_promotion"] = {
            "proposed_profile_id": proposed_profile_id,
            "promoted_by": promoter,
            "promoted_at": _string_value(promoted_at),
            "source_approval_ref": _input_ref(human_promotion_approval, approval_path),
            "official_scores_claimed": False,
        }
        after_registry["official_scores_claimed"] = False
        changed_fields = []
        if before_active != proposed_profile_id:
            changed_fields.append("active_profile_id")
        changed_fields.append(f"profiles.{proposed_profile_id}.status")
        changed_fields.append("last_promotion")
        registry_diff = {
            "before": {
                "active_profile_id": before_active,
                "profile_count": len(
                    before_registry.get("profiles")
                    if isinstance(before_registry.get("profiles"), dict)
                    else {}
                ),
            },
            "after": {
                "active_profile_id": proposed_profile_id,
                "profile_count": len(after_profiles),
            },
            "changed_fields": _dedupe_strings(changed_fields),
        }
        rollback_payload = {
            "schema_version": OPTIMIZER_GATE_LOCAL_PROMOTION_ROLLBACK_SCHEMA_VERSION,
            "status": "rollback_ready",
            "target": {
                "kind": "local_profile_registry",
                "path": str(target),
            },
            "restore_registry": before_registry,
            "promotion_action_ref": str(output),
            "rollback_action": "restore_local_profile_registry",
            "claim_boundary": (
                "optimizer/gate local registry rollback artifact only; restores "
                "local registry state and does not submit or claim official scores"
            ),
            "official_scores_claimed": False,
        }
        target.write_text(
            json.dumps(after_registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        rollback_target.write_text(
            json.dumps(rollback_payload, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        audit_event = {
            "schema_version": "2026-06-16.local-profile-registry-audit-event.v1",
            "event_type": "local_profile_registry_promoted",
            "proposed_profile_id": proposed_profile_id,
            "previous_active_profile_id": before_active,
            "active_profile_id": proposed_profile_id,
            "promoted_by": promoter,
            "promoted_at": _string_value(promoted_at),
            "source_approval_ref": _input_ref(human_promotion_approval, approval_path),
            "registry_path": str(target),
            "rollback_record_path": str(rollback_target),
            "official_scores_claimed": False,
        }
        with audit_target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(audit_event, ensure_ascii=False, sort_keys=True) + "\n")
        write_target = {
            "kind": "local_profile_registry",
            "path": str(target),
            "written": True,
        }
        rollback_record = {
            "path": str(rollback_target),
            "status": "rollback_ready",
            "target": str(target),
        }
        audit_log = {
            "path": str(audit_target),
            "event_type": "local_profile_registry_promoted",
            "written": True,
        }
    payload = {
        "schema_version": OPTIMIZER_GATE_LOCAL_PROMOTION_ACTION_SCHEMA_VERSION,
        "status": status,
        "human_promotion_approval_ref": _input_ref(
            human_promotion_approval,
            approval_path,
        ),
        "proposed_profile_id": proposed_profile_id,
        "local_promotion_record": local_promotion_record,
        "write_target": write_target,
        "registry_diff": registry_diff,
        "rollback_record": rollback_record,
        "audit_log": audit_log,
        "gate": {
            "approval_ready": approval_ready,
            "execute_promotion_flag": bool(execute_promotion),
            "promotion_executed": promotion_executed,
            "registry_write_ready": bool(
                registry_output_path is not None and registry_payload is not None
            ),
        },
        "hard_blockers": hard_blockers,
        "recommended_next_action": recommended_next_action,
        "claim_boundary": (
            "optimizer/gate local promotion action only; records a local "
            "registry promotion after human approval but does not submit "
            "benchmark results, update external systems, or claim official scores"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "executes_promotion": promotion_executed,
        "official_scores_claimed": False,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(output)
    return payload


def run_optimizer_gate_local_promotion_rollback(
    *,
    rollback_record: dict[str, Any] | str | Path,
    output_path: str | Path,
    rolled_back_by: str | None = None,
    rolled_back_at: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Restore a local profile registry from a promotion rollback artifact."""
    rollback_payload, rollback_path = _load_object(rollback_record)
    output = Path(output_path)
    _ensure_writable(output, overwrite=overwrite)
    target = (
        rollback_payload.get("target")
        if isinstance(rollback_payload.get("target"), dict)
        else {}
    )
    target_path_value = _string_value(target.get("path"))
    target_path = Path(target_path_value) if target_path_value else None
    restore_registry = (
        rollback_payload.get("restore_registry")
        if isinstance(rollback_payload.get("restore_registry"), dict)
        else None
    )
    operator = _string_value(rolled_back_by)
    hard_blockers = _string_list(rollback_payload.get("hard_blockers"))
    if _string_value(rollback_payload.get("status")) != "rollback_ready":
        hard_blockers.append("rollback_record_not_ready")
    if target_path is None:
        hard_blockers.append("rollback_target_path_missing")
    if restore_registry is None:
        hard_blockers.append("restore_registry_missing")
    if not operator:
        hard_blockers.append("rolled_back_by_missing")
    if bool(rollback_payload.get("official_scores_claimed", False)):
        hard_blockers.append("rollback_record_claims_official_scores")
    hard_blockers = _dedupe_strings(hard_blockers)

    rollback_applied = not hard_blockers and restore_registry is not None
    if rollback_applied:
        assert target_path is not None
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(
            json.dumps(restore_registry, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        status = "local_registry_rollback_applied"
        recommended_next_action = "review_registry_after_rollback"
    else:
        status = "blocked_local_registry_rollback"
        recommended_next_action = "return_to_promotion_rollback_review"

    payload = {
        "schema_version": OPTIMIZER_GATE_LOCAL_PROMOTION_ROLLBACK_SCHEMA_VERSION,
        "status": status,
        "rollback_record_ref": _input_ref(rollback_record, rollback_path),
        "target": {
            "kind": _string_value(target.get("kind")) or "local_profile_registry",
            "path": str(target_path) if target_path is not None else None,
            "restored": rollback_applied,
        },
        "rolled_back_by": operator,
        "rolled_back_at": _string_value(rolled_back_at),
        "hard_blockers": hard_blockers,
        "recommended_next_action": recommended_next_action,
        "claim_boundary": (
            "optimizer/gate local registry rollback execution only; restores "
            "local registry state and does not submit or claim official scores"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "executes_rollback": rollback_applied,
        "executes_promotion": False,
        "official_scores_claimed": False,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(output)
    return payload


def build_optimizer_gate_official_submission(
    *,
    local_promotion_action: dict[str, Any] | str | Path,
    benchmark_id: str,
    submission_id: str,
    public_url: str,
    submitted_by: str,
    submitted_at: str | None,
    output_path: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Record an explicit official-submission boundary artifact."""
    promotion_payload, promotion_path = _load_object(local_promotion_action)
    output = Path(output_path)
    _ensure_writable(output, overwrite=overwrite)

    hard_blockers = _string_list(promotion_payload.get("hard_blockers"))
    if _string_value(promotion_payload.get("status")) != "local_promotion_recorded":
        hard_blockers.append("local_promotion_action_not_recorded")
    if not bool(promotion_payload.get("executes_promotion", False)):
        hard_blockers.append("local_promotion_not_executed")
    if bool(promotion_payload.get("official_scores_claimed", False)):
        hard_blockers.append("local_promotion_claims_official_scores")
    if not _string_value(benchmark_id):
        hard_blockers.append("benchmark_id_missing")
    if not _string_value(submission_id):
        hard_blockers.append("submission_id_missing")
    if not _string_value(public_url):
        hard_blockers.append("public_url_missing")
    if not _string_value(submitted_by):
        hard_blockers.append("submitted_by_missing")
    hard_blockers = _dedupe_strings(hard_blockers)

    submission_ready = not hard_blockers
    status = (
        "official_submission_recorded"
        if submission_ready
        else "blocked_official_submission"
    )
    payload = {
        "schema_version": OPTIMIZER_GATE_OFFICIAL_SUBMISSION_SCHEMA_VERSION,
        "status": status,
        "local_promotion_action_ref": _input_ref(local_promotion_action, promotion_path),
        "proposed_profile_id": _string_value(promotion_payload.get("proposed_profile_id")),
        "submission": {
            "benchmark_id": _string_value(benchmark_id),
            "submission_id": _string_value(submission_id),
            "public_url": _string_value(public_url),
            "submitted_by": _string_value(submitted_by),
            "submitted_at": _string_value(submitted_at),
        },
        "gate": {
            "local_promotion_ready": submission_ready,
            "official_submission_recorded": submission_ready,
            "requires_public_result_verifier": True,
        },
        "hard_blockers": hard_blockers,
        "recommended_next_action": (
            "verify_public_result"
            if submission_ready
            else "return_to_local_promotion_or_submission_review"
        ),
        "claim_boundary": (
            "optimizer/gate official submission boundary artifact only; records "
            "an explicit official submission id and public result location but "
            "does not verify public results or claim official scores"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "executes_official_submission": submission_ready,
        "executes_promotion": False,
        "official_scores_claimed": False,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(output)
    return payload


def _submit_optimizer_gate_external_submission(
    submission_url: str,
    payload: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    request = urllib.request.Request(
        submission_url,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        decoded = response.read().decode("utf-8")
    parsed = json.loads(decoded)
    if not isinstance(parsed, dict):
        raise ValueError("external submission endpoint returned non-object JSON")
    return parsed


def run_optimizer_gate_external_submission_action(
    *,
    local_promotion_action: dict[str, Any] | str | Path,
    benchmark_id: str,
    submission_url: str,
    submission_payload: dict[str, Any] | None,
    submitted_by: str,
    output_path: str | Path,
    execute_submission: bool = False,
    timeout_seconds: int = 30,
    submitter: Callable[[str, dict[str, Any], int], dict[str, Any]] | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Execute an explicit external benchmark submission action."""
    promotion_payload, promotion_path = _load_object(local_promotion_action)
    output = Path(output_path)
    _ensure_writable(output, overwrite=overwrite)

    target_url = _string_value(submission_url)
    parsed_url = urllib.parse.urlparse(target_url)
    timeout = max(1, int(timeout_seconds))
    request_payload = dict(submission_payload or {})
    hard_blockers = _string_list(promotion_payload.get("hard_blockers"))
    submit_error: dict[str, str] | None = None
    response_payload: dict[str, Any] | None = None
    submission: dict[str, Any] | None = None

    if _string_value(promotion_payload.get("status")) != "local_promotion_recorded":
        hard_blockers.append("local_promotion_action_not_recorded")
    if not bool(promotion_payload.get("executes_promotion", False)):
        hard_blockers.append("local_promotion_not_executed")
    if bool(promotion_payload.get("official_scores_claimed", False)):
        hard_blockers.append("local_promotion_claims_official_scores")
    if not _string_value(benchmark_id):
        hard_blockers.append("benchmark_id_missing")
    if not target_url:
        hard_blockers.append("submission_url_missing")
    elif parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        hard_blockers.append("submission_url_not_http")
    if not _string_value(submitted_by):
        hard_blockers.append("submitted_by_missing")
    if not execute_submission:
        hard_blockers.append("execute_submission_flag_missing")

    if not hard_blockers:
        try:
            response_payload = (submitter or _submit_optimizer_gate_external_submission)(
                target_url,
                request_payload,
                timeout,
            )
            if not isinstance(response_payload, dict):
                raise ValueError("external submission submitter returned non-object")
        except Exception as exc:  # pragma: no cover - concrete transport varies
            submit_error = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
            hard_blockers.append("external_submission_failed")

    if response_payload is not None:
        submission = {
            "benchmark_id": _string_value(benchmark_id),
            "submission_id": _string_value(response_payload.get("submission_id")),
            "public_url": _string_value(response_payload.get("public_url")),
            "submitted_by": _string_value(submitted_by),
            "submitted_at": _string_value(response_payload.get("submitted_at")),
            "submission_url": target_url,
            "raw_response_id": _string_value(response_payload.get("raw_response_id")),
        }
        if not submission["submission_id"]:
            hard_blockers.append("submission_id_missing")
        if not submission["public_url"]:
            hard_blockers.append("public_url_missing")

    hard_blockers = _dedupe_strings(hard_blockers)
    submitted = response_payload is not None and not hard_blockers
    payload = {
        "schema_version": OPTIMIZER_GATE_EXTERNAL_SUBMISSION_ACTION_SCHEMA_VERSION,
        "status": (
            "external_submission_submitted"
            if submitted
            else "blocked_external_submission_action"
        ),
        "local_promotion_action_ref": _input_ref(local_promotion_action, promotion_path),
        "proposed_profile_id": _string_value(promotion_payload.get("proposed_profile_id")),
        "submission": submission,
        "request": {
            "benchmark_id": _string_value(benchmark_id),
            "submission_url": target_url,
            "submitted_by": _string_value(submitted_by),
            "timeout_seconds": timeout,
            "payload": request_payload,
        },
        "response": response_payload,
        "gate": {
            "execute_submission_flag": bool(execute_submission),
            "local_promotion_ready": (
                _string_value(promotion_payload.get("status"))
                == "local_promotion_recorded"
                and bool(promotion_payload.get("executes_promotion", False))
            ),
            "external_submission_executed": submitted,
            "requires_public_result_fetch": submitted,
        },
        "hard_blockers": hard_blockers,
        "submit_error": submit_error,
        "recommended_next_action": (
            "fetch_public_result" if submitted else "return_to_external_submission_review"
        ),
        "claim_boundary": (
            "optimizer/gate external submission action only; may submit a "
            "promoted local artifact to an external benchmark endpoint but "
            "does not fetch public results or claim official scores"
        ),
        "executes_tool": response_payload is not None,
        "executes_experiment": False,
        "executes_official_submission": submitted,
        "executes_promotion": False,
        "official_scores_claimed": False,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(output)
    return payload


class _OptimizerGatePublicResultPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._capture_script = False
        self._script_chunks: list[str] = []
        self.embedded_json_payloads: list[str] = []
        self.meta: dict[str, str] = {}
        self.time_datetimes: list[str] = []
        self.tables: list[dict[str, Any]] = []
        self._current_table: dict[str, Any] | None = None
        self._current_row: dict[str, Any] | None = None
        self._current_cell: dict[str, Any] | None = None
        self._cell_chunks: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag_name = tag.lower()
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        if tag_name == "script":
            script_type = attrs_dict.get("type", "").lower()
            script_id = attrs_dict.get("id", "")
            if (
                script_type == "application/json"
                and script_id == "optimizer-gate-public-result"
            ):
                self._capture_script = True
                self._script_chunks = []
        if tag_name == "meta":
            key = (
                attrs_dict.get("name")
                or attrs_dict.get("property")
                or attrs_dict.get("itemprop")
                or ""
            )
            content = attrs_dict.get("content", "")
            if key and content:
                self.meta[key] = content
        if tag_name == "time" and attrs_dict.get("datetime"):
            self.time_datetimes.append(attrs_dict["datetime"])
        if tag_name == "table":
            self._current_table = {"attrs": attrs_dict, "rows": []}
            return
        if tag_name == "tr" and self._current_table is not None:
            self._current_row = {"attrs": attrs_dict, "cells": []}
            return
        if tag_name in {"th", "td"} and self._current_row is not None:
            self._current_cell = {
                "tag": tag_name,
                "attrs": attrs_dict,
                "text": "",
                "links": [],
            }
            self._cell_chunks = []
            return
        if tag_name == "a" and self._current_cell is not None:
            href = attrs_dict.get("href")
            if href:
                self._current_cell["links"].append(href)

    def handle_data(self, data: str) -> None:
        if self._capture_script:
            self._script_chunks.append(data)
        if self._current_cell is not None:
            self._cell_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag_name = tag.lower()
        if tag_name == "script" and self._capture_script:
            self.embedded_json_payloads.append("".join(self._script_chunks))
            self._script_chunks = []
            self._capture_script = False
        if tag_name in {"th", "td"} and self._current_cell is not None:
            self._current_cell["text"] = _compact_html_text(" ".join(self._cell_chunks))
            if self._current_row is not None:
                self._current_row["cells"].append(self._current_cell)
            self._current_cell = None
            self._cell_chunks = []
        if tag_name == "tr" and self._current_row is not None:
            if self._current_table is not None:
                self._current_table["rows"].append(self._current_row)
            self._current_row = None
        if tag_name == "table" and self._current_table is not None:
            self.tables.append(self._current_table)
            self._current_table = None


def _compact_html_text(value: str) -> str:
    return " ".join(value.split())


def _parse_optimizer_gate_leaderboard_dom(
    parser: _OptimizerGatePublicResultPageParser,
    *,
    public_result_url: str,
) -> dict[str, Any] | None:
    target_submission_ids = _public_result_url_submission_ids(public_result_url)
    for table in parser.tables:
        rows = table.get("rows")
        if not isinstance(rows, list) or not rows:
            continue
        header_rows = [
            row
            for row in rows
            if all(
                isinstance(cell, dict) and cell.get("tag") == "th"
                for cell in row.get("cells", [])
            )
        ]
        header_cells = (
            header_rows[-1].get("cells", []) if header_rows else rows[0].get("cells", [])
        )
        header_labels = [
            _string_value(cell.get("text")) or ""
            for cell in header_cells
            if isinstance(cell, dict)
        ]
        headers = [_leaderboard_header_key(label) for label in header_labels]
        data_rows = [
            row
            for row in rows
            if any(
                isinstance(cell, dict) and cell.get("tag") == "td"
                for cell in row.get("cells", [])
            )
        ]
        for row in data_rows:
            payload = _leaderboard_row_public_result(
                row=row,
                headers=headers,
                header_labels=header_labels,
                target_submission_ids=target_submission_ids,
                public_result_url=public_result_url,
                default_published_at=parser.time_datetimes[0]
                if parser.time_datetimes
                else "",
            )
            if payload is not None:
                return payload
    return None


def _public_result_url_submission_ids(public_result_url: str) -> list[str]:
    parsed = urllib.parse.urlparse(public_result_url)
    query = urllib.parse.parse_qs(parsed.query)
    candidates: list[str] = []
    for key in ("submission_id", "submission", "run_id", "id"):
        for value in query.get(key, []):
            if value:
                candidates.append(value)
    for segment in parsed.path.split("/"):
        if segment and any(char.isdigit() for char in segment):
            candidates.append(segment)
    return _dedupe_strings(candidates)


def _leaderboard_header_key(value: str) -> str:
    normalized = "".join(
        char.lower() if char.isalnum() else "_"
        for char in value.strip()
    ).strip("_")
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    aliases = {
        "submission": "submission_id",
        "submissionid": "submission_id",
        "submission_id": "submission_id",
        "run": "submission_id",
        "run_id": "submission_id",
        "id": "submission_id",
        "result": "public_url",
        "result_url": "public_url",
        "public_url": "public_url",
        "url": "public_url",
        "link": "public_url",
        "published": "published_at",
        "published_at": "published_at",
        "submitted": "published_at",
        "submitted_at": "published_at",
        "row": "row_count",
        "rows": "row_count",
        "row_count": "row_count",
        "n": "row_count",
        "samples": "row_count",
        "denominator": "row_count",
    }
    return aliases.get(normalized, normalized)


def _leaderboard_row_public_result(
    *,
    row: dict[str, Any],
    headers: list[str],
    header_labels: list[str],
    target_submission_ids: list[str],
    public_result_url: str,
    default_published_at: str,
) -> dict[str, Any] | None:
    cells = [cell for cell in row.get("cells", []) if isinstance(cell, dict)]
    if not cells:
        return None
    attrs = row.get("attrs") if isinstance(row.get("attrs"), dict) else {}
    submission_id = (
        _string_value(attrs.get("data-submission-id"))
        or _string_value(attrs.get("data-run-id"))
        or _leaderboard_cell_text(cells, headers, "submission_id")
    )
    if not submission_id:
        for target_id in target_submission_ids:
            if any(target_id in (_string_value(cell.get("text")) or "") for cell in cells):
                submission_id = target_id
                break
    if target_submission_ids and submission_id not in target_submission_ids:
        row_text = " ".join(_string_value(cell.get("text")) or "" for cell in cells)
        row_links = " ".join(
            link
            for cell in cells
            for link in cell.get("links", [])
            if isinstance(link, str)
        )
        if not any(
            target_id in row_text or target_id in row_links
            for target_id in target_submission_ids
        ):
            return None
    public_url = _leaderboard_cell_link_or_text(
        cells,
        headers,
        "public_url",
        public_result_url=public_result_url,
    )
    if not public_url:
        for cell in cells:
            links = cell.get("links")
            if isinstance(links, list) and links:
                public_url = urllib.parse.urljoin(public_result_url, str(links[0]))
                break
    published_at = (
        _string_value(attrs.get("data-published-at"))
        or _leaderboard_cell_text(cells, headers, "published_at")
        or default_published_at
    )
    metrics: dict[str, float] = {}
    denominator: dict[str, float] = {}
    rank: int | None = None
    for index, cell in enumerate(cells):
        header = headers[index] if index < len(headers) else f"column_{index + 1}"
        text = _string_value(cell.get("text")) or ""
        numeric = _leaderboard_number(text)
        if numeric is None:
            continue
        if header == "rank":
            rank = int(numeric)
            continue
        if header == "row_count":
            denominator["row_count"] = numeric
            continue
        if header in {"submission_id", "public_url", "published_at"}:
            continue
        metrics[_leaderboard_metric_name(header_labels, index, header)] = numeric
    if not submission_id or not public_url or not metrics or not denominator:
        return None
    payload: dict[str, Any] = {
        "submission_id": submission_id,
        "public_url": public_url,
        "published_at": published_at,
        "metrics": metrics,
        "denominator": denominator,
        "leaderboard_row": {
            "rank": rank,
            "headers": headers,
        },
    }
    return payload


def _leaderboard_cell_text(
    cells: list[dict[str, Any]],
    headers: list[str],
    key: str,
) -> str:
    for index, header in enumerate(headers):
        if header == key and index < len(cells):
            return _string_value(cells[index].get("text")) or ""
    return ""


def _leaderboard_metric_name(
    header_labels: list[str],
    index: int,
    fallback: str,
) -> str:
    if index < len(header_labels):
        label = _compact_html_text(header_labels[index])
        if label:
            return label
    return fallback


def _leaderboard_cell_link_or_text(
    cells: list[dict[str, Any]],
    headers: list[str],
    key: str,
    *,
    public_result_url: str,
) -> str:
    for index, header in enumerate(headers):
        if header != key or index >= len(cells):
            continue
        links = cells[index].get("links")
        if isinstance(links, list) and links:
            return urllib.parse.urljoin(public_result_url, str(links[0]))
        return _string_value(cells[index].get("text")) or ""
    return ""


def _leaderboard_number(value: str) -> float | None:
    cleaned = value.strip().replace(",", "")
    if cleaned.endswith("%"):
        cleaned = cleaned[:-1].strip()
    cleaned = "".join(
        char
        for char in cleaned
        if char.isdigit() or char in {".", "-", "+"}
    )
    if cleaned in {"", "-", "+", ".", "-.", "+."}:
        return None
    try:
        numeric = float(cleaned)
    except ValueError:
        return None
    if numeric.is_integer():
        return int(numeric)
    return numeric


def _parse_optimizer_gate_public_result_page_with_parser(
    html: str,
    *,
    public_result_url: str,
) -> tuple[dict[str, Any], str]:
    """Parse a public benchmark result HTML page into the verifier payload shape."""
    parser = _OptimizerGatePublicResultPageParser()
    parser.feed(html)
    for embedded in parser.embedded_json_payloads:
        try:
            payload = json.loads(embedded)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload, "html_embedded_json"

    leaderboard_payload = _parse_optimizer_gate_leaderboard_dom(
        parser,
        public_result_url=public_result_url,
    )
    if leaderboard_payload is not None:
        return leaderboard_payload, "html_leaderboard_dom"

    def meta_value(*keys: str) -> str:
        for key in keys:
            value = _string_value(parser.meta.get(key))
            if value:
                return value
        return ""

    metrics: dict[str, float] = {}
    for key, value in parser.meta.items():
        if key.startswith("optimizer-gate:metric:"):
            metric_name = key.rsplit(":", 1)[-1]
            try:
                metrics[metric_name] = float(value)
            except (TypeError, ValueError):
                pass
    denominator: dict[str, float] = {}
    for key, value in parser.meta.items():
        if key.startswith("optimizer-gate:denominator:"):
            denominator_name = key.rsplit(":", 1)[-1]
            try:
                denominator[denominator_name] = float(value)
            except (TypeError, ValueError):
                pass
    return {
        "submission_id": meta_value(
            "optimizer-gate:submission_id",
            "submission_id",
        ),
        "public_url": meta_value("optimizer-gate:public_url", "public_url")
        or public_result_url,
        "published_at": meta_value(
            "optimizer-gate:published_at",
            "published_at",
        ),
        "metrics": metrics,
        "denominator": denominator,
    }, "html_meta_tags"


def parse_optimizer_gate_public_result_page(
    html: str,
    *,
    public_result_url: str,
) -> dict[str, Any]:
    """Parse a public benchmark result HTML page into the verifier payload shape."""
    payload, _parser_kind = _parse_optimizer_gate_public_result_page_with_parser(
        html,
        public_result_url=public_result_url,
    )
    return payload


def _fetch_public_result_json(
    public_result_url: str,
    timeout_seconds: int,
) -> tuple[dict[str, Any], str]:
    request = urllib.request.Request(
        public_result_url,
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        body = response.read()
        content_type = _string_value(response.headers.get("Content-Type")).lower()
    decoded = body.decode("utf-8")
    try:
        payload = json.loads(decoded)
    except json.JSONDecodeError:
        payload, parser_kind = _parse_optimizer_gate_public_result_page_with_parser(
            decoded,
            public_result_url=public_result_url,
        )
        return payload, parser_kind
    if not isinstance(payload, dict):
        raise ValueError("public result URL did not return a JSON object")
    parser_kind = "json"
    if "html" in content_type:
        parser_kind = "html_embedded_json"
    return payload, parser_kind


def fetch_optimizer_gate_public_result(
    *,
    public_result_url: str,
    output_path: str | Path,
    timeout_seconds: int = 30,
    fetcher: (
        Callable[[str, int], dict[str, Any] | tuple[dict[str, Any], str]] | None
    ) = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Fetch and normalize an optimizer/gate public result from a URL."""
    output = Path(output_path)
    _ensure_writable(output, overwrite=overwrite)

    source_url = _string_value(public_result_url)
    timeout = max(1, int(timeout_seconds))
    parsed_url = urllib.parse.urlparse(source_url)
    hard_blockers: list[str] = []
    raw_payload: dict[str, Any] | None = None
    fetched_public_result: dict[str, Any] | None = None
    fetch_error: dict[str, str] | None = None
    parser_kind = "custom_fetcher" if fetcher is not None else "json"

    if not source_url:
        hard_blockers.append("public_result_url_missing")
    elif parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        hard_blockers.append("public_result_url_not_http")

    if not hard_blockers:
        try:
            fetched_payload = (fetcher or _fetch_public_result_json)(source_url, timeout)
            if isinstance(fetched_payload, tuple):
                raw_payload, parser_kind = fetched_payload
            else:
                raw_payload = fetched_payload
            if not isinstance(raw_payload, dict):
                raise ValueError("public result fetcher returned non-object payload")
        except Exception as exc:  # pragma: no cover - exception class depends on transport
            fetch_error = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
            hard_blockers.append("public_result_fetch_failed")

    if raw_payload is not None:
        metrics = _numeric_metric_map(raw_payload.get("metrics"))
        denominator = (
            raw_payload.get("denominator")
            if isinstance(raw_payload.get("denominator"), dict)
            else {}
        )
        denominator_numbers = _numeric_metric_map(denominator)
        fetched_public_result = {
            "submission_id": _string_value(raw_payload.get("submission_id")),
            "public_url": _string_value(raw_payload.get("public_url")),
            "published_at": _string_value(raw_payload.get("published_at")),
            "metrics": metrics,
            "denominator": denominator,
        }
        if not fetched_public_result["submission_id"]:
            hard_blockers.append("submission_id_missing")
        if not fetched_public_result["public_url"]:
            hard_blockers.append("public_url_missing")
        if not fetched_public_result["published_at"]:
            hard_blockers.append("published_at_missing")
        if not metrics:
            hard_blockers.append("public_metrics_missing")
        if not denominator_numbers:
            hard_blockers.append("public_denominator_missing")
        if any(value <= 0 for value in denominator_numbers.values()):
            hard_blockers.append("public_denominator_not_positive")

    hard_blockers = _dedupe_strings(hard_blockers)
    fetched = raw_payload is not None and not hard_blockers
    payload = {
        "schema_version": OPTIMIZER_GATE_PUBLIC_RESULT_FETCH_SCHEMA_VERSION,
        "status": "public_result_fetched" if fetched else "blocked_public_result_fetch",
        "source": {
            "public_result_url": source_url,
            "timeout_seconds": timeout,
            "transport": parsed_url.scheme or None,
            "parser": parser_kind,
        },
        "fetched_public_result": fetched_public_result if fetched else None,
        "raw_public_result": raw_payload,
        "gate": {
            "fetch_succeeded": raw_payload is not None,
            "json_parsed": raw_payload is not None,
            "metrics_present": bool(
                fetched_public_result and fetched_public_result.get("metrics")
            ),
            "denominator_present": bool(
                fetched_public_result and _numeric_metric_map(
                    fetched_public_result.get("denominator")
                )
            ),
            "public_result_fetch_ready": fetched,
        },
        "hard_blockers": hard_blockers,
        "fetch_error": fetch_error,
        "recommended_next_action": (
            "verify_public_result" if fetched else "return_to_public_result_url_collection"
        ),
        "claim_boundary": (
            "optimizer/gate public result fetch artifact only; fetches and "
            "parses a public result URL but does not verify the submission or "
            "claim official scores"
        ),
        "executes_tool": raw_payload is not None,
        "executes_experiment": False,
        "executes_promotion": False,
        "official_scores_claimed": False,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(output)
    return payload


def verify_optimizer_gate_public_result(
    *,
    official_submission: dict[str, Any] | str | Path,
    public_result: dict[str, Any] | str | Path,
    output_path: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Verify a public result before any official claim artifact can be built."""
    submission_payload, submission_path = _load_object(official_submission)
    result_payload, result_path = _load_object(public_result)
    output = Path(output_path)
    _ensure_writable(output, overwrite=overwrite)

    submission_schema = _string_value(submission_payload.get("schema_version"))
    official_submission_source = {
        "kind": (
            "external_submission_action_artifact"
            if submission_schema
            == OPTIMIZER_GATE_EXTERNAL_SUBMISSION_ACTION_SCHEMA_VERSION
            else "official_submission_artifact"
        ),
        "submission_status": _string_value(submission_payload.get("status")),
    }
    public_result_source = {
        "kind": "public_result_payload",
        "public_result_url": None,
        "fetch_status": None,
    }
    fetch_blockers: list[str] = []
    if (
        _string_value(result_payload.get("schema_version"))
        == OPTIMIZER_GATE_PUBLIC_RESULT_FETCH_SCHEMA_VERSION
    ):
        source = (
            result_payload.get("source")
            if isinstance(result_payload.get("source"), dict)
            else {}
        )
        public_result_source = {
            "kind": "public_result_fetch_artifact",
            "public_result_url": _string_value(source.get("public_result_url")),
            "fetch_status": _string_value(result_payload.get("status")),
        }
        fetch_blockers.extend(_string_list(result_payload.get("hard_blockers")))
        if _string_value(result_payload.get("status")) != "public_result_fetched":
            fetch_blockers.append("public_result_fetch_not_ready")
        fetched_payload = (
            result_payload.get("fetched_public_result")
            if isinstance(result_payload.get("fetched_public_result"), dict)
            else {}
        )
        result_payload = fetched_payload

    submission = (
        submission_payload.get("submission")
        if isinstance(submission_payload.get("submission"), dict)
        else {}
    )
    expected_submission_id = _string_value(submission.get("submission_id"))
    expected_public_url = _string_value(submission.get("public_url"))
    result_submission_id = _string_value(result_payload.get("submission_id"))
    result_public_url = _string_value(result_payload.get("public_url"))
    metrics = _numeric_metric_map(result_payload.get("metrics"))
    denominator = (
        result_payload.get("denominator")
        if isinstance(result_payload.get("denominator"), dict)
        else {}
    )
    denominator_numbers = _numeric_metric_map(denominator)

    hard_blockers = _string_list(submission_payload.get("hard_blockers"))
    hard_blockers.extend(fetch_blockers)
    if submission_schema == OPTIMIZER_GATE_EXTERNAL_SUBMISSION_ACTION_SCHEMA_VERSION:
        if _string_value(submission_payload.get("status")) != "external_submission_submitted":
            hard_blockers.append("external_submission_not_submitted")
        if not bool(submission_payload.get("executes_official_submission", False)):
            hard_blockers.append("external_submission_not_executed")
    elif _string_value(submission_payload.get("status")) != "official_submission_recorded":
        hard_blockers.append("official_submission_not_recorded")
    if bool(submission_payload.get("official_scores_claimed", False)):
        hard_blockers.append("official_submission_claims_official_scores")
    if not expected_submission_id:
        hard_blockers.append("submission_id_missing")
    if result_submission_id != expected_submission_id:
        hard_blockers.append("submission_id_mismatch")
    if not expected_public_url:
        hard_blockers.append("expected_public_url_missing")
    if result_public_url != expected_public_url:
        hard_blockers.append("public_url_mismatch")
    if not _string_value(result_payload.get("published_at")):
        hard_blockers.append("published_at_missing")
    if not metrics:
        hard_blockers.append("public_metrics_missing")
    if not denominator_numbers:
        hard_blockers.append("public_denominator_missing")
    if any(value <= 0 for value in denominator_numbers.values()):
        hard_blockers.append("public_denominator_not_positive")
    hard_blockers = _dedupe_strings(hard_blockers)

    verified = not hard_blockers
    status = "public_result_verified" if verified else "blocked_public_result_verifier"
    verified_public_result = {
        "benchmark_id": _string_value(submission.get("benchmark_id")),
        "submission_id": result_submission_id,
        "public_url": result_public_url,
        "published_at": _string_value(result_payload.get("published_at")),
        "metrics": metrics,
        "denominator": denominator,
    }
    payload = {
        "schema_version": OPTIMIZER_GATE_PUBLIC_RESULT_VERIFIER_SCHEMA_VERSION,
        "status": status,
        "official_submission_ref": _input_ref(official_submission, submission_path),
        "official_submission_source": official_submission_source,
        "public_result_ref": _input_ref(public_result, result_path),
        "public_result_source": public_result_source,
        "verified_public_result": verified_public_result if verified else None,
        "gate": {
            "submission_id_matches": result_submission_id == expected_submission_id,
            "public_url_matches": result_public_url == expected_public_url,
            "public_result_fetch_ready": not fetch_blockers,
            "metrics_present": bool(metrics),
            "denominator_present": bool(denominator_numbers),
            "public_result_verified": verified,
        },
        "hard_blockers": hard_blockers,
        "recommended_next_action": (
            "build_official_claim_artifact"
            if verified
            else "return_to_public_result_collection"
        ),
        "claim_boundary": (
            "optimizer/gate public result verifier only; binds a public result "
            "to an explicit submission but does not itself claim official scores"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "executes_promotion": False,
        "official_scores_claimed": False,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(output)
    return payload


def build_optimizer_gate_official_claim(
    *,
    public_result_verifier: dict[str, Any] | str | Path,
    claim_id: str,
    output_path: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build the only optimizer/gate artifact allowed to claim official scores."""
    verifier_payload, verifier_path = _load_object(public_result_verifier)
    output = Path(output_path)
    _ensure_writable(output, overwrite=overwrite)

    gate = (
        verifier_payload.get("gate")
        if isinstance(verifier_payload.get("gate"), dict)
        else {}
    )
    verified_public_result = (
        verifier_payload.get("verified_public_result")
        if isinstance(verifier_payload.get("verified_public_result"), dict)
        else None
    )
    hard_blockers = _string_list(verifier_payload.get("hard_blockers"))
    if (
        _string_value(verifier_payload.get("schema_version"))
        != OPTIMIZER_GATE_PUBLIC_RESULT_VERIFIER_SCHEMA_VERSION
        or _string_value(verifier_payload.get("status")) != "public_result_verified"
        or not bool(gate.get("public_result_verified", False))
        or verified_public_result is None
    ):
        hard_blockers.append("public_result_verifier_not_passed")
    if bool(verifier_payload.get("official_scores_claimed", False)):
        hard_blockers.append("public_result_verifier_claims_official_scores")
    if not _string_value(claim_id):
        hard_blockers.append("claim_id_missing")
    hard_blockers = _dedupe_strings(hard_blockers)

    claim_verified = not hard_blockers and verified_public_result is not None
    status = "official_claim_verified" if claim_verified else "blocked_official_claim"
    claim = None
    if claim_verified:
        claim = {
            "claim_id": _string_value(claim_id),
            "benchmark_id": _string_value(verified_public_result.get("benchmark_id")),
            "submission_id": _string_value(verified_public_result.get("submission_id")),
            "public_url": _string_value(verified_public_result.get("public_url")),
            "published_at": _string_value(verified_public_result.get("published_at")),
            "metrics": verified_public_result.get("metrics"),
            "denominator": verified_public_result.get("denominator"),
        }
    payload = {
        "schema_version": OPTIMIZER_GATE_OFFICIAL_CLAIM_SCHEMA_VERSION,
        "status": status,
        "public_result_verifier_ref": _input_ref(
            public_result_verifier,
            verifier_path,
        ),
        "claim": claim,
        "gate": {
            "public_result_verified": claim_verified,
            "official_claim_allowed": claim_verified,
        },
        "hard_blockers": hard_blockers,
        "recommended_next_action": (
            "publish_official_claim"
            if claim_verified
            else "return_to_public_result_verifier"
        ),
        "claim_boundary": (
            "optimizer/gate official claim artifact; this is the only artifact "
            "in the local optimizer/gate chain allowed to set official_scores_claimed=true"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "executes_promotion": False,
        "official_scores_claimed": claim_verified,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(output)
    return payload


def record_slice_patch_outcome(
    *,
    candidate: dict[str, Any] | str | Path,
    materialization: dict[str, Any] | str | Path,
    gate_decision: dict[str, Any] | str | Path,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Record a slice patch outcome for optimizer/gate learning."""
    candidate_payload, candidate_path = _load_slice_candidate(candidate)
    materialization_payload, materialization_path = _load_object(materialization)
    gate_payload, gate_path = _load_object(gate_decision)

    materialized_change = (
        materialization_payload.get("materialized_change")
        if isinstance(materialization_payload.get("materialized_change"), dict)
        else {}
    )
    patch_id = (
        _string_value(candidate_payload.get("patch_id"))
        or _string_value(materialization_payload.get("patch_id"))
        or "unknown-patch"
    )
    module_id = (
        _string_value(candidate_payload.get("module_id"))
        or _string_value(materialized_change.get("module_id"))
        or "unknown_module"
    )
    section_id = (
        _string_value(candidate_payload.get("section_id"))
        or _string_value(materialized_change.get("section_id"))
        or "unknown_section"
    )
    optimizer = (
        _string_value(candidate_payload.get("optimizer"))
        or _string_value(materialization_payload.get("optimizer"))
        or "unknown_optimizer"
    )
    gate = gate_payload.get("gate") if isinstance(gate_payload.get("gate"), dict) else {}
    gate_status = _string_value(gate_payload.get("status")) or "unknown"
    canary_allowed = bool(gate.get("canary_allowed", False))
    promotion_ready = bool(gate.get("promotion_ready", False))
    accepted_for_next_stage = canary_allowed and gate_status in {
        "passed",
        "passed_for_canary",
        "completed",
    }
    metric_delta = _metric_delta_map(gate_payload)
    failure_labels = _slice_patch_outcome_failure_labels(
        gate_payload=gate_payload,
        accepted_for_next_stage=accepted_for_next_stage,
    )
    target_scope = f"{module_id}/{section_id}"
    artifact_refs = []
    if candidate_path is not None:
        artifact_refs.append({"name": "candidate", "path": str(candidate_path)})
    if materialization_path is not None:
        artifact_refs.append({
            "name": "materialization",
            "path": str(materialization_path),
        })
    if gate_path is not None:
        artifact_refs.append({"name": "gate_decision", "path": str(gate_path)})

    payload = {
        "status": "completed",
        "schema_version": SLICE_PATCH_OUTCOME_SCHEMA_VERSION,
        "outcome_id": f"{patch_id}-outcome",
        "patch_id": patch_id,
        "optimizer": optimizer,
        "candidate_strategy": _string_value(candidate_payload.get("candidate_strategy")),
        "module_id": module_id,
        "section_id": section_id,
        "base_profile_id": _string_value(materialization_payload.get("base_profile_id")),
        "gate_status": gate_status,
        "gate_policy_id": _string_value(gate_payload.get("policy_id")),
        "split": _string_value(gate_payload.get("split")),
        "accepted_for_next_stage": accepted_for_next_stage,
        "gate": {
            "canary_allowed": canary_allowed,
            "promotion_ready": promotion_ready,
        },
        "metric_delta": metric_delta,
        "failure_labels": failure_labels,
        "slice_regressions": _dict_list(gate_payload.get("slice_regressions")),
        "stable_repair_targets": _dict_list(gate_payload.get("stable_repair_targets")),
        "learning_signal": {
            "outcome": "passed_for_canary" if accepted_for_next_stage else gate_status,
            "optimizer": optimizer,
            "candidate_strategy": _string_value(candidate_payload.get("candidate_strategy")),
            "target_scope": target_scope,
            "based_on_slices": _string_list(candidate_payload.get("based_on_slices")),
            "protected_slices": _string_list(candidate_payload.get("protected_slices")),
            "failure_labels": failure_labels,
        },
        "recommended_next_actions": _slice_patch_outcome_next_actions(
            accepted_for_next_stage=accepted_for_next_stage,
        ),
        "artifact_refs": artifact_refs,
        "claim_boundary": "local slice patch outcome only; not dev/canary proof",
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def build_slice_optimizer_selection(
    *,
    outcomes: list[dict[str, Any]] | str | Path,
    target_scope: str | None = None,
    failure_labels: list[str] | None = None,
    candidate_optimizers: list[str] | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Select an optimizer adapter from prior slice patch outcomes."""
    outcome_items = _load_outcome_items(outcomes)
    normalized_target_scope = _string_value(target_scope) or "unknown"
    normalized_failure_labels = _dedupe_strings(failure_labels or [])
    optimizer_names = (
        _dedupe_strings(candidate_optimizers or [])
        or [adapter.name for adapter in _optimizer_adapter_registry_objects()]
    )
    adapters = [resolve_optimizer_adapter(name) for name in optimizer_names]
    optimizer_scores = [
        _slice_optimizer_selection_score(
            optimizer=adapter.name,
            outcomes=outcome_items,
            target_scope=normalized_target_scope,
            failure_labels=normalized_failure_labels,
        )
        for adapter in adapters
    ]
    optimizer_scores.sort(key=lambda item: (-item["score"], item["optimizer"]))
    selected_optimizer = (
        _string_value(optimizer_scores[0].get("optimizer"))
        if optimizer_scores
        else "manual-template"
    )
    payload = {
        "status": "completed",
        "schema_version": SLICE_OPTIMIZER_SELECTION_SCHEMA_VERSION,
        "selected_optimizer": selected_optimizer,
        "target_scope": normalized_target_scope,
        "failure_labels": normalized_failure_labels,
        "candidate_optimizers": [adapter.name for adapter in adapters],
        "outcome_count": len(outcome_items),
        "optimizer_scores": optimizer_scores,
        "selection_policy": {
            "passed_same_scope_bonus": 3,
            "blocked_same_scope_penalty": -1,
            "blocked_matching_failure_penalty": -3,
            "tie_breaker": "optimizer_name_ascending",
        },
        "recommended_next_action": "generate_slice_patch_candidates",
        "claim_boundary": "local slice optimizer selection only; not an executed optimizer",
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def _optimizer_gate_loop_canary_outcome_inputs(
    *,
    canary_result_gate: dict[str, Any],
    slice_repair_context: dict[str, Any],
    base_profile_id: str,
) -> dict[str, Any]:
    contract = (
        slice_repair_context.get("recommended_patch_contract")
        if isinstance(slice_repair_context.get("recommended_patch_contract"), dict)
        else {}
    )
    module_id = _string_value(contract.get("module_id")) or "unknown_module"
    section_id = _string_value(contract.get("section_id")) or "unknown_section"
    proposed_profile_id = (
        _string_value(canary_result_gate.get("proposed_profile_id"))
        or "unknown-profile"
    )
    hard_blockers = _string_list(canary_result_gate.get("hard_blockers"))
    gate = (
        canary_result_gate.get("gate")
        if isinstance(canary_result_gate.get("gate"), dict)
        else {}
    )
    canary_result = (
        canary_result_gate.get("canary_result")
        if isinstance(canary_result_gate.get("canary_result"), dict)
        else {}
    )
    patch_id = f"{proposed_profile_id}-canary-outcome"
    before_text = _string_value(contract.get("before_text")) or ""
    candidate = {
        "schema_version": SLICE_PATCH_CANDIDATE_SCHEMA_VERSION,
        "patch_id": patch_id,
        "optimizer": "canary-result-gate",
        "candidate_strategy": "canary_result_feedback",
        "module_id": module_id,
        "section_id": section_id,
        "change_surface": "prompt_section",
        "edit_scope": _string_value(contract.get("edit_scope")) or "single_section",
        "before_text": before_text,
        "after_text": before_text,
        "based_on_slices": _string_list(contract.get("based_on_slices")),
        "protected_slices": _string_list(contract.get("protected_slices")),
        "protected_sections": _string_list(contract.get("protected_sections")),
    }
    materialization = {
        "schema_version": SLICE_PATCH_MATERIALIZATION_SCHEMA_VERSION,
        "status": "needs_prompt_profile_registration",
        "base_profile_id": base_profile_id,
        "patch_id": patch_id,
        "optimizer": "canary-result-gate",
        "materialized_change": {
            "module_id": module_id,
            "section_id": section_id,
            "change_surface": "prompt_section",
            "edit_scope": _string_value(contract.get("edit_scope")) or "single_section",
            "before_text": before_text,
            "after_text": before_text,
            "protected_slices": _string_list(contract.get("protected_slices")),
            "protected_sections": _string_list(contract.get("protected_sections")),
        },
        "official_scores_claimed": False,
    }
    failure_labels = hard_blockers or ["canary_result_blocked"]
    gate_decision = {
        "schema_version": GATE_POLICY_DECISION_SCHEMA_VERSION,
        "status": _string_value(canary_result_gate.get("status")) or "unknown",
        "policy_id": "canary-result-gate",
        "split": "canary",
        "gate": {
            "canary_allowed": False,
            "promotion_ready": bool(gate.get("promotion_ready", False)),
        },
        "hard_blockers": failure_labels,
        "metric_delta": {},
        "slice_regressions": [
            {
                "slice_key": item,
                "slice_name": item,
                "delta": -float(canary_result.get("failure_count", 1) or 1),
                "gate": "blocked",
            }
            for item in failure_labels
        ],
        "claim_boundary": "local canary result feedback only",
        "official_scores_claimed": False,
    }
    return {
        "candidate": candidate,
        "materialization": materialization,
        "gate_decision": gate_decision,
        "target_scope": f"{module_id}/{section_id}",
        "failure_labels": failure_labels,
    }


def _optimizer_gate_loop_trace_entry(
    *,
    name: str,
    payload: dict[str, Any],
    path: str | Path | None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": _string_value(payload.get("status")) or "unknown",
        "schema_version": _string_value(payload.get("schema_version")),
        "artifact_ref": str(path) if path is not None else payload.get("output_path"),
        "executes_tool": bool(payload.get("executes_tool", False)),
        "executes_experiment": bool(payload.get("executes_experiment", False)),
        "executes_promotion": bool(payload.get("executes_promotion", False)),
        "official_scores_claimed": bool(payload.get("official_scores_claimed", False)),
    }


def _write_optimizer_gate_loop_manifest(
    *,
    artifacts: list[dict[str, Any]],
    output_path: Path,
    overwrite: bool,
) -> dict[str, Any]:
    _ensure_writable(output_path, overwrite=overwrite)
    manifest = {
        "schema_version": f"{OPTIMIZER_GATE_EXECUTABLE_LOOP_SCHEMA_VERSION}.artifact-manifest",
        "status": "completed",
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "claim_boundary": (
            "optimizer/gate executable loop artifact manifest only; local trace, "
            "not official scoring or external system update"
        ),
        "official_scores_claimed": False,
    }
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest["output_path"] = str(output_path)
    return manifest


def run_optimizer_gate_executable_loop(
    *,
    canary_result_gate: dict[str, Any] | str | Path,
    slice_repair_context: dict[str, Any] | str | Path,
    candidate_optimizers: list[str] | None = None,
    optimizer_gate_plugin_manifests: list[dict[str, Any] | str | Path] | None = None,
    base_profile_id: str = "p3-dev-v2",
    proposed_profile_prefix: str = "optimizer-gate-loop-profile",
    max_iterations: int = 1,
    max_candidates: int = 1,
    execute_optimizer: bool = False,
    optimizer_model: str | None = None,
    optimizer_base_url: str | None = None,
    optimizer_api_key: str | None = None,
    optimizer_timeout_seconds: int = 30,
    optimizer_temperature: float = 0.0,
    optimizer_max_tokens: int = 512,
    auto_approve_registration: bool = False,
    approved_by: str | None = None,
    prompt_leakage_rows: list[dict[str, Any]] | dict[str, Any] | str | Path | None = None,
    prompt_leakage_audit: dict[str, Any] | str | Path | None = None,
    target_smoke: dict[str, Any] | str | Path | None = None,
    dev_model_eval: dict[str, Any] | str | Path | None = None,
    dev_baseline_eval: dict[str, Any] | str | Path | None = None,
    dev_gate_source: dict[str, Any] | str | Path | None = None,
    model_runtime_preflight: dict[str, Any] | str | Path | None = None,
    execute_model_eval: bool = False,
    target_smoke_rows: list[dict[str, Any]] | dict[str, Any] | str | Path | None = None,
    dev_model_eval_rows: list[dict[str, Any]] | dict[str, Any] | str | Path | None = None,
    execute_canary_runner: bool = False,
    canary_rows: list[dict[str, Any]] | dict[str, Any] | str | Path | None = None,
    model_eval_chat_completion: Any | None = None,
    model_eval_model: str = "qwen/qwen3-8b",
    model_eval_base_url: str = "http://127.0.0.1:1234/v1",
    model_eval_model_provider: str = "openai-compatible",
    model_eval_api_key_env: str | None = None,
    model_eval_timeout_seconds: int = 120,
    model_eval_temperature: float = 0.0,
    model_eval_max_tokens: int = 512,
    model_eval_judge_mode: str = "heuristic",
    min_canary_row_count: int = 1,
    max_canary_failure_count: int = 0,
    max_canary_runtime_error_count: int = 0,
    max_canary_empty_output_count: int = 0,
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Run a bounded optimizer/gate executable loop until a hard boundary."""
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    loop_path = output_root / "optimizer-gate-executable-loop.json"
    _ensure_writable(loop_path, overwrite=overwrite)

    canary_payload, canary_path = _load_object(canary_result_gate)
    context_payload, context_path = _load_object(slice_repair_context)
    trace: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []

    def add_artifact(name: str, payload: dict[str, Any], path: str | Path | None) -> None:
        entry = _optimizer_gate_loop_trace_entry(name=name, payload=payload, path=path)
        trace.append(entry)
        if entry.get("artifact_ref"):
            artifacts.append({
                "name": name,
                "path": entry["artifact_ref"],
                "schema_version": entry.get("schema_version"),
                "status": entry.get("status"),
            })

    def materialize_rows_input(
        value: list[dict[str, Any]] | dict[str, Any] | str | Path | None,
        path: Path,
    ) -> Path | None:
        if value is None:
            return None
        if isinstance(value, (str, Path)):
            return Path(value)
        rows = _load_prompt_leakage_rows(value)
        if rows is None:
            return None
        _ensure_writable(path, overwrite=overwrite)
        path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    def materialize_object_input(
        value: dict[str, Any] | str | Path | None,
        path: Path,
    ) -> Path | None:
        if value is None:
            return None
        if isinstance(value, (str, Path)):
            return Path(value)
        _ensure_writable(path, overwrite=overwrite)
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    add_artifact(
        "consume_canary_result_gate",
        canary_payload,
        str(canary_path) if canary_path is not None else None,
    )
    budget = {
        "max_iterations": max(0, int(max_iterations)),
        "iterations_used": 0,
        "max_candidates": max(1, int(max_candidates)),
    }
    loop_state = {
        "last_canary_result_gate_consumed": True,
        "outcome_recorded": False,
        "optimizer_selection_built": False,
        "runtime_probe_executed": False,
        "candidate_generated": False,
        "method_proposal_trace_built": False,
        "registration_plan_built": False,
        "registration_approved": False,
        "dev_bundle_executed": False,
        "dev_gate_passed": False,
        "canary_runner_executed": False,
        "outcome_schedule_built": False,
        "scheduler_plan_built": False,
        "scheduler_loop_state_built": False,
        "promotion_boundary_reached": False,
    }
    hard_blockers: list[str] = []
    status = "running"
    stop_reason = None
    recommended_next_action = None
    loop_executes_experiment = False

    gate = canary_payload.get("gate") if isinstance(canary_payload.get("gate"), dict) else {}
    if bool(canary_payload.get("official_scores_claimed", False)):
        status = "stopped_at_official_boundary"
        stop_reason = "official_boundary"
        hard_blockers.append("source_claims_official_scores")
        recommended_next_action = "review_official_claim_boundary"
    elif bool(gate.get("promotion_ready", False)):
        status = "stopped_at_promotion_boundary"
        stop_reason = "promotion_boundary"
        loop_state["promotion_boundary_reached"] = True
        recommended_next_action = "build_human_promotion_review_queue"
    elif budget["max_iterations"] <= 0:
        status = "stopped_budget_exhausted"
        stop_reason = "budget_exhausted"
        recommended_next_action = "increase_loop_budget_or_stop"
    else:
        budget["iterations_used"] = 1
        outcome_inputs = _optimizer_gate_loop_canary_outcome_inputs(
            canary_result_gate=canary_payload,
            slice_repair_context=context_payload,
            base_profile_id=base_profile_id,
        )
        outcome_path = output_root / "slice-patch-outcome.json"
        outcome = record_slice_patch_outcome(
            candidate=outcome_inputs["candidate"],
            materialization=outcome_inputs["materialization"],
            gate_decision=outcome_inputs["gate_decision"],
            output_path=outcome_path,
            overwrite=overwrite,
        )
        loop_state["outcome_recorded"] = True
        add_artifact("record_slice_patch_outcome", outcome, outcome_path)

        selection_path = output_root / "slice-optimizer-selection.json"
        selection = build_slice_optimizer_selection(
            outcomes=[outcome],
            target_scope=outcome_inputs["target_scope"],
            failure_labels=outcome_inputs["failure_labels"],
            candidate_optimizers=candidate_optimizers,
            output_path=selection_path,
            overwrite=overwrite,
        )
        loop_state["optimizer_selection_built"] = True
        add_artifact("build_slice_optimizer_selection", selection, selection_path)

        selected_optimizer = _string_value(selection.get("selected_optimizer")) or "manual-template"
        runtime_probe_path = output_root / "optimizer-runtime-probe.json"
        runtime_probe = probe_optimizer_runtime(
            optimizer=selected_optimizer,
            optimizer_gate_plugin_manifests=optimizer_gate_plugin_manifests,
            execute_probe=True,
            optimizer_model=optimizer_model,
            optimizer_base_url=optimizer_base_url,
            optimizer_timeout_seconds=optimizer_timeout_seconds,
            output_path=runtime_probe_path,
            overwrite=overwrite,
        )
        loop_state["runtime_probe_executed"] = True
        add_artifact("probe_optimizer_runtime", runtime_probe, runtime_probe_path)

        if not bool(runtime_probe.get("runtime_ready", False)):
            status = "stopped_runtime_not_ready"
            stop_reason = "runtime_not_ready"
            hard_blockers.extend(_string_list(runtime_probe.get("hard_blockers")))
            recommended_next_action = _string_value(runtime_probe.get("recommended_next_action"))
        else:
            candidates_path = output_root / "slice-patch-candidates.json"
            candidates = generate_slice_patch_candidates(
                context=context_payload,
                optimizer=selected_optimizer,
                optimizer_gate_plugin_manifests=optimizer_gate_plugin_manifests,
                max_candidates=budget["max_candidates"],
                execute_optimizer=execute_optimizer,
                optimizer_model=optimizer_model,
                optimizer_base_url=optimizer_base_url,
                optimizer_api_key=optimizer_api_key,
                optimizer_timeout_seconds=optimizer_timeout_seconds,
                optimizer_temperature=optimizer_temperature,
                optimizer_max_tokens=optimizer_max_tokens,
                output_path=candidates_path,
                overwrite=overwrite,
            )
            candidate_items = _dict_list(candidates.get("candidates"))
            loop_state["candidate_generated"] = bool(candidate_items)
            add_artifact("generate_slice_patch_candidates", candidates, candidates_path)

            if not candidate_items:
                status = "stopped_candidate_generation_blocked"
                stop_reason = "gate_blocked"
                hard_blockers.append("candidate_generation_empty")
                recommended_next_action = "inspect_optimizer_candidate_generation"
            else:
                materialization_path = output_root / "slice-patch-materialization.json"
                registration_plan_path = output_root / "prompt-profile-registration-plan.json"
                selected_candidate = candidate_items[0]
                selected_proposal_id = (
                    _string_value(selected_candidate.get("proposal_id"))
                    or _string_value(selected_candidate.get("patch_id"))
                    or "proposal-001"
                )
                target_contract = (
                    context_payload.get("recommended_patch_contract")
                    if isinstance(
                        context_payload.get("recommended_patch_contract"),
                        dict,
                    )
                    else {}
                )
                method_trace_path = output_root / "method-proposal-generation-trace.json"
                method_trace = build_method_proposal_generation_trace(
                    generation_context={
                        "trigger": "optimizer_gate_executable_loop",
                        "task_family": (
                            _string_value(context_payload.get("task_family"))
                            or "smol_worldcup_prompt_routing"
                        ),
                        "failure_slice": (
                            _string_value(target_contract.get("target_slice"))
                            or _string_value(canary_payload.get("proposed_profile_id"))
                        ),
                        "objective": (
                            "Search bounded repair proposals after a blocked canary "
                            "result, then hand the selected candidate to optimizer/gate "
                            "registration and validation."
                        ),
                        "constraints": [
                            "optimizer only generates structured candidates",
                            "gate decides canary/promotion readiness",
                            "module_or_section_local_patch_only",
                            "official_scores_claimed_false",
                        ],
                        "outcome_memory_refs": [
                            str(outcome_path),
                            str(selection_path),
                            str(runtime_probe_path),
                            str(candidates_path),
                        ],
                    },
                    generation_run={
                        "generator": selected_optimizer,
                        "model": optimizer_model,
                        "prompt_template_id": (
                            f"optimizer-gate-executable-loop:{selected_optimizer}"
                        ),
                        "temperature": optimizer_temperature,
                        "max_tokens": optimizer_max_tokens,
                        "tool_versions": {
                            "runtime_probe_schema_version": runtime_probe.get(
                                "schema_version"
                            ),
                            "candidate_schema_version": candidates.get(
                                "schema_version"
                            ),
                        },
                    },
                    reasoning_trace={
                        "trace_kind": "structured_loop_rationale",
                        "steps": [
                            {
                                "step_id": "reason-001",
                                "summary": (
                                    "Previous canary gate was blocked, so record the "
                                    "failure outcome and select a bounded optimizer."
                                ),
                                "proposal_ids": [],
                                "assumptions": [
                                    "blocked canary result is valid local feedback",
                                ],
                                "risks": [
                                    "single local repair may not improve dev/canary",
                                ],
                            },
                            {
                                "step_id": "reason-002",
                                "summary": (
                                    "Generate section-local candidates and select the "
                                    "top ranked candidate for registration review."
                                ),
                                "proposal_ids": [selected_proposal_id],
                                "assumptions": [
                                    "candidate remains within the repair contract",
                                ],
                                "risks": [
                                    "gate evidence may still block validation",
                                ],
                            },
                        ],
                        "assumptions": [
                            "candidate improvement is unproven until gate evidence exists",
                        ],
                        "self_critique": [
                            "trace records structured rationale, not private chain-of-thought",
                        ],
                    },
                    proposals=candidate_items,
                    ranking_decisions=[
                        {
                            "proposal_id": (
                                _string_value(candidate.get("proposal_id"))
                                or _string_value(candidate.get("patch_id"))
                                or f"proposal-{index:03d}"
                            ),
                            "rank": index,
                            "decision": (
                                "selected_for_validation"
                                if index == 1
                                else "pruned_for_later_review"
                            ),
                            "score": float(len(candidate_items) - index + 1),
                            "rationale": (
                                "first bounded candidate advances to registration review"
                                if index == 1
                                else "outside current loop candidate budget"
                            ),
                            "risk_notes": [
                                "requires downstream gate validation before promotion"
                            ],
                        }
                        for index, candidate in enumerate(candidate_items, start=1)
                    ],
                    selected_proposal_ids=[selected_proposal_id],
                    execution_links=[
                        {
                            "proposal_id": selected_proposal_id,
                            "artifact": "slice_patch_materialization",
                            "path": str(materialization_path),
                        },
                        {
                            "proposal_id": selected_proposal_id,
                            "artifact": "prompt_profile_registration_plan",
                            "path": str(registration_plan_path),
                        },
                    ],
                    output_path=method_trace_path,
                    overwrite=overwrite,
                )
                loop_state["method_proposal_trace_built"] = True
                add_artifact(
                    "build_method_proposal_generation_trace",
                    method_trace,
                    method_trace_path,
                )
                materialization = materialize_slice_patch_candidate(
                    candidate=candidate_items[0],
                    base_profile_id=base_profile_id,
                    output_path=materialization_path,
                    overwrite=overwrite,
                )
                add_artifact(
                    "materialize_slice_patch_candidate",
                    materialization,
                    materialization_path,
                )
                registration_plan = build_prompt_profile_registration_plan(
                    materialization=materialization,
                    proposed_profile_id=(
                        f"{proposed_profile_prefix}-i{budget['iterations_used']}-c1"
                    ),
                    output_path=registration_plan_path,
                    overwrite=overwrite,
                )
                loop_state["registration_plan_built"] = True
                add_artifact(
                    "build_prompt_profile_registration_plan",
                    registration_plan,
                    registration_plan_path,
                )
                if not auto_approve_registration:
                    status = "stopped_at_human_review_boundary"
                    stop_reason = "human_review_boundary"
                    recommended_next_action = "review_and_register_prompt_profile"
                else:
                    registration_path = output_root / "prompt-profile-registration.json"
                    registration = register_prompt_profile_from_plan(
                        registration_plan=registration_plan,
                        approved=True,
                        approved_by=approved_by,
                        output_path=registration_path,
                        overwrite=overwrite,
                    )
                    loop_state["registration_approved"] = True
                    add_artifact(
                        "register_prompt_profile_from_plan",
                        registration,
                        registration_path,
                    )
                    dev_output_dir = output_root / "registered-profile-execution-run"
                    dev_run = run_registered_profile_execution(
                        registration_plan=registration_plan,
                        registered_profile=registration,
                        prompt_leakage_rows=prompt_leakage_rows,
                        prompt_leakage_audit=prompt_leakage_audit,
                        target_smoke=target_smoke,
                        dev_model_eval=dev_model_eval,
                        dev_baseline_eval=dev_baseline_eval,
                        dev_gate_source=dev_gate_source,
                        model_runtime_preflight=model_runtime_preflight,
                        execute_model_eval=execute_model_eval,
                        target_smoke_rows=target_smoke_rows,
                        dev_model_eval_rows=dev_model_eval_rows,
                        model_eval_chat_completion=model_eval_chat_completion,
                        model_eval_model=model_eval_model,
                        model_eval_base_url=model_eval_base_url,
                        model_eval_model_provider=model_eval_model_provider,
                        model_eval_api_key_env=model_eval_api_key_env,
                        model_eval_timeout_seconds=model_eval_timeout_seconds,
                        model_eval_temperature=model_eval_temperature,
                        model_eval_max_tokens=model_eval_max_tokens,
                        model_eval_judge_mode=model_eval_judge_mode,
                        output_dir=dev_output_dir,
                        overwrite=overwrite,
                    )
                    loop_state["dev_bundle_executed"] = True
                    dev_gate = (
                        dev_run.get("gate")
                        if isinstance(dev_run.get("gate"), dict)
                        else {}
                    )
                    loop_state["dev_gate_passed"] = bool(
                        dev_gate.get("canary_allowed", False)
                    )
                    loop_executes_experiment = bool(
                        dev_run.get("executes_experiment", False)
                    )
                    add_artifact(
                        "run_registered_profile_execution",
                        dev_run,
                        dev_run.get("output_path"),
                    )
                    if loop_state["dev_gate_passed"]:
                        if not execute_canary_runner:
                            status = "stopped_before_canary_runner"
                            stop_reason = "canary_runner_boundary"
                            recommended_next_action = "build_canary_runner_bundle"
                        else:
                            canary_rows_path = materialize_rows_input(
                                canary_rows,
                                output_root / "canary-rows.json",
                            )
                            model_runtime_preflight_path = materialize_object_input(
                                model_runtime_preflight,
                                output_root / "canary-model-runtime-preflight.json",
                            )
                            if model_runtime_preflight_path is None:
                                dev_artifacts = (
                                    dev_run.get("artifacts")
                                    if isinstance(dev_run.get("artifacts"), dict)
                                    else {}
                                )
                                dev_runtime_ref = _string_value(
                                    dev_artifacts.get("model_runtime_preflight")
                                )
                                if dev_runtime_ref and dev_runtime_ref != "inline":
                                    model_runtime_preflight_path = Path(dev_runtime_ref)
                            canary_handoff_path = (
                                output_root / "optimizer-gate-scheduler-handoff.json"
                            )
                            canary_handoff = {
                                "schema_version": (
                                    OPTIMIZER_GATE_SCHEDULER_HANDOFF_SCHEMA_VERSION
                                ),
                                "status": "ready_for_explicit_canary_runner",
                                "proposed_profile_id": _string_value(
                                    registration_plan.get("proposed_profile_id")
                                ),
                                "source_loop_status": _string_value(dev_run.get("status")),
                                "source_stop_reason": None,
                                "handoff_type": "explicit_canary_runner_handoff",
                                "next_runner_action": (
                                    "run_registered_profile_canary_execution"
                                ),
                                "runner": {
                                    "function": "run_registered_profile_canary_execution",
                                    "cli_command": (
                                        "proposal "
                                        "run-registered-profile-canary-execution"
                                    ),
                                    "mcp_tool": "run_registered_profile_canary_execution",
                                    "requires_explicit_execute_flag": True,
                                    "will_execute_experiment_when_invoked": True,
                                    "executes_promotion_when_invoked": False,
                                },
                                "required_inputs": [
                                    "registered_profile_execution_run",
                                    "registered_profile",
                                    "canary_rows",
                                    "model_runtime_preflight",
                                    "execute_canary_flag",
                                ],
                                "manual_review_required": False,
                                "recommended_next_action": (
                                    "prepare_explicit_canary_runner_inputs"
                                ),
                                "source_artifact_refs": [
                                    dev_run.get("output_path"),
                                    str(registration_path),
                                ],
                                "hard_blockers": [],
                                "claim_boundary": (
                                    "optimizer/gate executable loop generated "
                                    "canary handoff only"
                                ),
                                "executes_tool": False,
                                "executes_experiment": False,
                                "executes_promotion": False,
                                "official_scores_claimed": False,
                            }
                            _ensure_writable(canary_handoff_path, overwrite=overwrite)
                            canary_handoff_path.write_text(
                                json.dumps(
                                    canary_handoff,
                                    ensure_ascii=False,
                                    indent=2,
                                    sort_keys=True,
                                )
                                + "\n",
                                encoding="utf-8",
                            )
                            add_artifact(
                                "prepare_explicit_canary_runner_handoff",
                                canary_handoff,
                                canary_handoff_path,
                            )
                            canary_bundle_path = (
                                output_root / "optimizer-gate-canary-runner-bundle.json"
                            )
                            canary_bundle = build_optimizer_gate_canary_runner_bundle(
                                optimizer_gate_scheduler_handoff=canary_handoff_path,
                                registered_profile_execution_run=dev_run.get("output_path"),
                                registered_profile=registration_path,
                                canary_rows=canary_rows_path,
                                model_runtime_preflight=model_runtime_preflight_path,
                                output_path=canary_bundle_path,
                                execute_canary=True,
                                overwrite=overwrite,
                            )
                            add_artifact(
                                "build_optimizer_gate_canary_runner_bundle",
                                canary_bundle,
                                canary_bundle_path,
                            )
                            canary_runner_dir = (
                                output_root / "optimizer-gate-canary-runner-execution"
                            )
                            canary_runner = run_optimizer_gate_canary_runner_bundle(
                                optimizer_gate_canary_runner_bundle=canary_bundle_path,
                                output_dir=canary_runner_dir,
                                model_eval_chat_completion=model_eval_chat_completion,
                                model_eval_model=model_eval_model,
                                model_eval_base_url=model_eval_base_url,
                                model_eval_model_provider=model_eval_model_provider,
                                model_eval_api_key_env=model_eval_api_key_env,
                                model_eval_timeout_seconds=model_eval_timeout_seconds,
                                model_eval_temperature=model_eval_temperature,
                                model_eval_max_tokens=model_eval_max_tokens,
                                model_eval_judge_mode=model_eval_judge_mode,
                                min_canary_row_count=min_canary_row_count,
                                max_failure_count=max_canary_failure_count,
                                max_runtime_error_count=max_canary_runtime_error_count,
                                max_empty_output_count=max_canary_empty_output_count,
                                overwrite=overwrite,
                            )
                            loop_state["canary_runner_executed"] = bool(
                                canary_runner.get("executes_experiment", False)
                            )
                            loop_executes_experiment = (
                                loop_executes_experiment
                                or bool(canary_runner.get("executes_experiment", False))
                            )
                            add_artifact(
                                "run_optimizer_gate_canary_runner_bundle",
                                canary_runner,
                                canary_runner.get("output_path"),
                            )
                            canary_runner_artifacts = (
                                canary_runner.get("artifacts")
                                if isinstance(canary_runner.get("artifacts"), dict)
                                else {}
                            )
                            canary_result_gate_ref = _string_value(
                                canary_runner_artifacts.get(
                                    "registered_profile_canary_result_gate"
                                )
                            )
                            if canary_result_gate_ref:
                                outcome_schedule_path = (
                                    output_root
                                    / "registered-profile-outcome-schedule.json"
                                )
                                outcome_schedule = (
                                    build_registered_profile_outcome_schedule(
                                        registered_profile_canary_result_gate=(
                                            canary_result_gate_ref
                                        ),
                                        output_path=outcome_schedule_path,
                                        overwrite=overwrite,
                                    )
                                )
                                loop_state["outcome_schedule_built"] = True
                                add_artifact(
                                    "build_registered_profile_outcome_schedule",
                                    outcome_schedule,
                                    outcome_schedule_path,
                                )
                                scheduler_plan_path = (
                                    output_root / "optimizer-gate-scheduler-plan.json"
                                )
                                scheduler_plan = build_optimizer_gate_scheduler_plan(
                                    registered_profile_outcome_schedule=(
                                        outcome_schedule_path
                                    ),
                                    model_runtime_preflight=(
                                        model_runtime_preflight_path
                                    ),
                                    slice_optimizer_selection=selection_path,
                                    output_path=scheduler_plan_path,
                                    overwrite=overwrite,
                                )
                                loop_state["scheduler_plan_built"] = True
                                add_artifact(
                                    "build_optimizer_gate_scheduler_plan",
                                    scheduler_plan,
                                    scheduler_plan_path,
                                )
                                scheduler_loop_dir = (
                                    output_root / "optimizer-gate-scheduler-loop"
                                )
                                scheduler_loop = run_optimizer_gate_scheduler_loop(
                                    optimizer_gate_scheduler_plan=scheduler_plan_path,
                                    output_dir=scheduler_loop_dir,
                                    model=model_eval_model,
                                    base_url=model_eval_base_url,
                                    model_provider=model_eval_model_provider,
                                    api_key_env=model_eval_api_key_env,
                                    context=context_payload,
                                    optimizer_gate_plugin_manifests=(
                                        optimizer_gate_plugin_manifests
                                    ),
                                    max_candidates=budget["max_candidates"],
                                    max_actions=1,
                                    auto_refresh_scheduler_plan=False,
                                    overwrite=overwrite,
                                )
                                loop_state["scheduler_loop_state_built"] = True
                                add_artifact(
                                    "run_optimizer_gate_scheduler_loop",
                                    scheduler_loop,
                                    scheduler_loop.get("output_path"),
                                )
                            canary_gate = (
                                canary_runner.get("gate")
                                if isinstance(canary_runner.get("gate"), dict)
                                else {}
                            )
                            runner_blockers = _string_list(
                                canary_runner.get("hard_blockers")
                            )
                            if bool(canary_gate.get("promotion_ready", False)):
                                status = "stopped_at_promotion_boundary"
                                stop_reason = "promotion_boundary"
                                loop_state["promotion_boundary_reached"] = True
                                recommended_next_action = (
                                    "build_human_promotion_review_queue"
                                )
                            else:
                                hard_blockers.extend(runner_blockers)
                                if any(
                                    blocker.startswith("model_runtime_preflight")
                                    for blocker in runner_blockers
                                ):
                                    status = "stopped_runtime_not_ready"
                                    stop_reason = "runtime_not_ready"
                                else:
                                    status = "stopped_gate_blocked"
                                    stop_reason = "gate_blocked"
                                recommended_next_action = (
                                    _string_value(
                                        canary_runner.get("recommended_next_action")
                                    )
                                    or "record_blocked_canary_outcome"
                                )
                    else:
                        status = "stopped_gate_blocked"
                        stop_reason = "gate_blocked"
                        hard_blockers.extend(_string_list(dev_run.get("hard_blockers")))
                        recommended_next_action = (
                            _string_value(dev_run.get("recommended_next_action"))
                            or "record_blocked_dev_outcome"
                        )

    manifest_path = output_root / "artifact-manifest.json"
    manifest = _write_optimizer_gate_loop_manifest(
        artifacts=artifacts,
        output_path=manifest_path,
        overwrite=overwrite,
    )
    payload = {
        "status": status,
        "schema_version": OPTIMIZER_GATE_EXECUTABLE_LOOP_SCHEMA_VERSION,
        "stop_reason": stop_reason,
        "registered_profile_canary_result_gate_ref": (
            str(canary_path) if canary_path is not None else "inline"
        ),
        "slice_repair_context_ref": (
            str(context_path) if context_path is not None else "inline"
        ),
        "budget": budget,
        "loop_state": loop_state,
        "artifact_trace": trace,
        "artifact_manifest": manifest,
        "hard_blockers": _dedupe_strings(hard_blockers),
        "recommended_next_action": recommended_next_action,
        "claim_boundary": (
            "optimizer/gate executable loop only; may run local optimizer runtime "
            "probe, local candidate generation, explicitly approved local dev "
            "model eval, and explicitly requested local canary runner, but stops "
            "at human review, promotion, official, runtime, gate, or budget "
            "boundaries and does not submit benchmarks, execute promotion, or "
            "update external systems"
        ),
        "executes_tool": bool(trace),
        "executes_experiment": loop_executes_experiment,
        "executes_promotion": False,
        "official_scores_claimed": False,
    }
    loop_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(loop_path)
    return payload


def build_optimizer_gate_system_spec(
    *,
    plugin_manifests: list[dict[str, Any] | str | Path] | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a non-executing registry for optimizer adapters and gate policies."""
    loaded_plugin_manifests = _load_optimizer_gate_plugin_manifests(plugin_manifests)
    payload = {
        "status": "completed",
        "schema_version": OPTIMIZER_GATE_SYSTEM_SPEC_SCHEMA_VERSION,
        "optimizer_adapters": _optimizer_adapter_registry(
            plugin_manifests=loaded_plugin_manifests
        ),
        "gate_policies": _gate_policy_registry(
            plugin_manifests=loaded_plugin_manifests
        ),
        "benchmark_adapters": _benchmark_adapter_registry(),
        "runner_contract": {
            "function": "build_optimizer_gate_run_plan",
            "cli_command": "proposal build-optimizer-gate-run",
            "mcp_tool": "build_optimizer_gate_run",
            "stages": [
                "probe_optimizer_runtime",
                "generate_slice_patch_candidates",
                "materialize_slice_patch_candidate",
                "gate_plan",
            ],
            "executes_experiment": False,
            "registers_prompt_profile": False,
            "canary_allowed_by_default": False,
            "execution_plan_function": "build_optimizer_gate_execution_plan",
            "supports_external_optimizer_runtime_plugins": True,
            "external_runtime_requires_explicit_execution": True,
            "external_runtime_executes_experiment": False,
            "runtime_probe_function": "probe_optimizer_runtime",
        },
        "prompt_profile_registration_contract": {
            "function": "build_prompt_profile_registration_plan",
            "cli_command": "proposal build-prompt-profile-registration-plan",
            "mcp_tool": "build_prompt_profile_registration_plan",
            "schema_version": PROMPT_PROFILE_REGISTRATION_PLAN_SCHEMA_VERSION,
            "input_artifact": SLICE_PATCH_MATERIALIZATION_SCHEMA_VERSION,
            "output_artifact": "prompt_profile_registration_plan",
            "registration_artifact_function": "register_prompt_profile_from_plan",
            "registration_artifact_cli_command": "proposal register-prompt-profile",
            "registration_artifact_mcp_tool": "register_prompt_profile_from_plan",
            "registration_artifact_schema_version": (
                PROMPT_PROFILE_REGISTRATION_SCHEMA_VERSION
            ),
            "registration_artifact_requires_explicit_approval": True,
            "registration_artifact_mutates_benchmark_code": False,
            "registers_prompt_profile": False,
            "executes_tool": False,
            "executes_experiment": False,
            "canary_allowed_by_default": False,
            "recommended_next_action": "review_and_register_prompt_profile",
        },
        "execution_preflight_contract": {
            "function": "build_optimizer_gate_execution_preflight",
            "cli_command": "proposal build-optimizer-gate-execution-preflight",
            "mcp_tool": "build_optimizer_gate_execution_preflight",
            "schema_version": OPTIMIZER_GATE_EXECUTION_PREFLIGHT_SCHEMA_VERSION,
            "input_artifact": PROMPT_PROFILE_REGISTRATION_PLAN_SCHEMA_VERSION,
            "requires_registered_prompt_profile": True,
            "registered_profile_artifact_schema": (
                PROMPT_PROFILE_REGISTRATION_SCHEMA_VERSION
            ),
            "required_pre_execution_artifacts": [
                "registered_profile",
                "prompt_leakage_audit",
                "target_smoke",
                "dev_model_eval",
                "gate_decision",
            ],
            "canary_requires_hard_gate": True,
            "promotion_ready_by_default": False,
            "executes_tool": False,
            "executes_experiment": False,
        },
        "registered_profile_execution_bundle_contract": {
            "function": "build_registered_profile_execution_bundle",
            "cli_command": "proposal build-registered-profile-execution-bundle",
            "mcp_tool": "build_registered_profile_execution_bundle",
            "schema_version": REGISTERED_PROFILE_EXECUTION_BUNDLE_SCHEMA_VERSION,
            "input_artifact": PROMPT_PROFILE_REGISTRATION_SCHEMA_VERSION,
            "preflight_function": "build_optimizer_gate_execution_preflight",
            "preflight_schema_version": OPTIMIZER_GATE_EXECUTION_PREFLIGHT_SCHEMA_VERSION,
            "stages": [
                "load_prompt_profile_registration",
                "apply_registration_overlay",
                "prompt_leakage_audit",
                "target_smoke",
                "dev_model_eval",
                "gate_decision",
                "execution_preflight",
                "canary_preflight",
            ],
            "requires_registered_prompt_profile": True,
            "canary_requires_hard_gate": True,
            "executes_tool": False,
            "executes_experiment": False,
            "promotion_ready_by_default": False,
        },
        "registered_profile_execution_run_contract": {
            "function": "run_registered_profile_execution",
            "cli_command": "proposal run-registered-profile-execution",
            "mcp_tool": "run_registered_profile_execution",
            "schema_version": REGISTERED_PROFILE_EXECUTION_RUN_SCHEMA_VERSION,
            "input_artifact": PROMPT_PROFILE_REGISTRATION_SCHEMA_VERSION,
            "bundle_function": "build_registered_profile_execution_bundle",
            "bundle_schema_version": REGISTERED_PROFILE_EXECUTION_BUNDLE_SCHEMA_VERSION,
            "gate_decision_generator_function": (
                "build_registered_profile_gate_decision"
            ),
            "gate_decision_generator_schema_version": (
                REGISTERED_PROFILE_GATE_DECISION_SCHEMA_VERSION
            ),
            "auto_executable_stages": [
                "prompt_leakage_audit",
                "gate_policy_input",
                "gate_policy_decision",
                "quality_gate_policy_inputs",
                "quality_gate_policy_decisions",
                "gate_policy_composition",
            ],
            "artifact_consumed_stages": [
                "target_smoke",
                "dev_model_eval",
                "gate_decision",
            ],
            "auto_generates_gate_decision_when": (
                "registered profile, leakage audit, target smoke, dev model eval, "
                "and dev gate source tables are present"
            ),
            "supports_explicit_model_eval_execution": True,
            "requires_execute_model_eval_flag": True,
            "requires_model_runtime_preflight_before_model_eval": True,
            "model_runtime_preflight_function": "build_model_runtime_preflight",
            "model_runtime_preflight_schema_version": (
                MODEL_RUNTIME_PREFLIGHT_SCHEMA_VERSION
            ),
            "explicit_executable_stages": [
                "target_smoke",
                "dev_model_eval",
            ],
            "executes_experiment_when_model_eval_executed": True,
            "dev_gate_source_generator_function": "build_slice_eval_matrix",
            "dev_gate_source_artifact": "dev-slice-eval-matrix.json",
            "quality_gate_function": "build_gate_policy_input",
            "quality_gate_policy_ids": _registered_profile_quality_gate_policy_ids(),
            "default_required_gate_policies": (
                _registered_profile_required_gate_policy_ids()
            ),
            "default_quality_constraints": (
                _registered_profile_gate_quality_constraints()
            ),
            "canary_preflight_requires_absolute_quality": True,
            "executes_model_eval": False,
            "executes_canary": False,
            "executes_promotion": False,
            "executes_tool": False,
            "executes_experiment": False,
        },
        "registered_profile_canary_preflight_contract": {
            "function": "build_registered_profile_canary_preflight",
            "cli_command": "proposal build-registered-profile-canary-preflight",
            "mcp_tool": "build_registered_profile_canary_preflight",
            "schema_version": REGISTERED_PROFILE_CANARY_PREFLIGHT_SCHEMA_VERSION,
            "input_artifact": REGISTERED_PROFILE_EXECUTION_RUN_SCHEMA_VERSION,
            "requires_dev_gate_canary_allowed": True,
            "requires_canary_rows": True,
            "executes_canary": False,
            "executes_promotion": False,
            "executes_tool": False,
            "executes_experiment": False,
        },
        "registered_profile_canary_execution_contract": {
            "function": "run_registered_profile_canary_execution",
            "cli_command": "proposal run-registered-profile-canary-execution",
            "mcp_tool": "run_registered_profile_canary_execution",
            "schema_version": REGISTERED_PROFILE_CANARY_EXECUTION_SCHEMA_VERSION,
            "input_artifact": REGISTERED_PROFILE_CANARY_PREFLIGHT_SCHEMA_VERSION,
            "preflight_function": "build_registered_profile_canary_preflight",
            "requires_execute_canary_flag": True,
            "requires_model_runtime_preflight_before_canary_model_eval": True,
            "model_runtime_preflight_function": "build_model_runtime_preflight",
            "model_runtime_preflight_schema_version": (
                MODEL_RUNTIME_PREFLIGHT_SCHEMA_VERSION
            ),
            "explicit_executable_stages": ["canary_model_eval"],
            "executes_canary": True,
            "executes_promotion": False,
            "executes_experiment_when_canary_executed": True,
            "promotion_ready_by_default": False,
        },
        "registered_profile_canary_result_gate_contract": {
            "function": "build_registered_profile_canary_result_gate",
            "cli_command": "proposal build-registered-profile-canary-result-gate",
            "mcp_tool": "build_registered_profile_canary_result_gate",
            "schema_version": REGISTERED_PROFILE_CANARY_RESULT_GATE_SCHEMA_VERSION,
            "input_artifact": REGISTERED_PROFILE_CANARY_EXECUTION_SCHEMA_VERSION,
            "promotion_ready_requires_canary_passed": True,
            "default_constraints": {
                "min_canary_row_count": 1,
                "max_failure_count": 0,
                "max_runtime_error_count": 0,
                "max_empty_output_count": 0,
            },
            "executes_tool": False,
            "executes_experiment": False,
            "executes_promotion": False,
            "official_scores_claimed": False,
        },
        "registered_profile_outcome_schedule_contract": {
            "function": "build_registered_profile_outcome_schedule",
            "cli_command": "proposal build-registered-profile-outcome-schedule",
            "mcp_tool": "build_registered_profile_outcome_schedule",
            "schema_version": REGISTERED_PROFILE_OUTCOME_SCHEDULE_SCHEMA_VERSION,
            "input_artifact": REGISTERED_PROFILE_CANARY_RESULT_GATE_SCHEMA_VERSION,
            "consumes_canary_result_gate": True,
            "outputs": [
                "outcome_weighting",
                "scheduled_actions",
                "promotion_review_gate",
            ],
            "promotion_review_requires_canary_passed": True,
            "executes_tool": False,
            "executes_experiment": False,
            "executes_promotion": False,
            "official_scores_claimed": False,
        },
        "optimizer_gate_scheduler_plan_contract": {
            "function": "build_optimizer_gate_scheduler_plan",
            "cli_command": "proposal build-optimizer-gate-scheduler-plan",
            "mcp_tool": "build_optimizer_gate_scheduler_plan",
            "schema_version": OPTIMIZER_GATE_SCHEDULER_PLAN_SCHEMA_VERSION,
            "input_artifact": REGISTERED_PROFILE_OUTCOME_SCHEDULE_SCHEMA_VERSION,
            "optional_inputs": [
                MODEL_RUNTIME_PREFLIGHT_SCHEMA_VERSION,
                SLICE_OPTIMIZER_SELECTION_SCHEMA_VERSION,
            ],
            "routes_actions": [
                "review_promotion_boundary",
                "build_model_runtime_preflight",
                "run_registered_profile_canary_execution",
                "build_slice_optimizer_selection",
                "generate_slice_patch_candidates",
            ],
            "executes_tool": False,
            "executes_experiment": False,
            "executes_promotion": False,
            "official_scores_claimed": False,
        },
        "optimizer_gate_scheduler_action_contract": {
            "function": "run_optimizer_gate_scheduler_action",
            "cli_command": "proposal run-optimizer-gate-scheduler-action",
            "mcp_tool": "run_optimizer_gate_scheduler_action",
            "schema_version": OPTIMIZER_GATE_SCHEDULER_ACTION_SCHEMA_VERSION,
            "input_artifact": OPTIMIZER_GATE_SCHEDULER_PLAN_SCHEMA_VERSION,
            "allowed_explicit_actions": [
                "review_promotion_boundary",
                "build_model_runtime_preflight",
                "generate_slice_patch_candidates",
            ],
            "unsupported_executable_actions": [
                "run_registered_profile_canary_execution",
            ],
            "auto_executes_next_action": False,
            "executes_experiment": False,
            "executes_promotion": False,
            "official_scores_claimed": False,
        },
        "optimizer_gate_scheduler_loop_contract": {
            "function": "run_optimizer_gate_scheduler_loop",
            "cli_command": "proposal run-optimizer-gate-scheduler-loop",
            "mcp_tool": "run_optimizer_gate_scheduler_loop",
            "schema_version": OPTIMIZER_GATE_SCHEDULER_LOOP_SCHEMA_VERSION,
            "input_artifact": OPTIMIZER_GATE_SCHEDULER_PLAN_SCHEMA_VERSION,
            "safe_auto_actions": [
                "review_promotion_boundary",
                "build_model_runtime_preflight",
                "generate_slice_patch_candidates",
            ],
            "stops_before_actions": [
                "run_registered_profile_canary_execution",
                "record_slice_patch_outcome",
                "await_human_promotion_review",
            ],
            "supports_auto_scheduler_plan_refresh": True,
            "auto_executes_experiment_actions": False,
            "executes_promotion": False,
            "official_scores_claimed": False,
        },
        "optimizer_gate_scheduler_handoff_contract": {
            "function": "build_optimizer_gate_scheduler_handoff",
            "cli_command": "proposal build-optimizer-gate-scheduler-handoff",
            "mcp_tool": "build_optimizer_gate_scheduler_handoff",
            "schema_version": OPTIMIZER_GATE_SCHEDULER_HANDOFF_SCHEMA_VERSION,
            "input_artifact": OPTIMIZER_GATE_SCHEDULER_LOOP_SCHEMA_VERSION,
            "routes_to_explicit_canary_runner": True,
            "routes_to_human_promotion_review": True,
            "executes_tool": False,
            "executes_experiment": False,
            "executes_promotion": False,
            "official_scores_claimed": False,
        },
        "optimizer_gate_canary_runner_bundle_contract": {
            "function": "build_optimizer_gate_canary_runner_bundle",
            "cli_command": "proposal build-optimizer-gate-canary-runner-bundle",
            "mcp_tool": "build_optimizer_gate_canary_runner_bundle",
            "schema_version": OPTIMIZER_GATE_CANARY_RUNNER_BUNDLE_SCHEMA_VERSION,
            "input_artifact": OPTIMIZER_GATE_SCHEDULER_HANDOFF_SCHEMA_VERSION,
            "binds_explicit_canary_runner_inputs": True,
            "output_runner_function": "run_registered_profile_canary_execution",
            "requires_registered_profile_execution_run": True,
            "requires_registered_profile": True,
            "requires_canary_rows": True,
            "requires_model_runtime_preflight": True,
            "requires_execute_canary_flag": True,
            "runner_will_execute_experiment_when_invoked": True,
            "executes_tool": False,
            "executes_experiment": False,
            "executes_promotion": False,
            "official_scores_claimed": False,
        },
        "optimizer_gate_canary_runner_execution_contract": {
            "function": "run_optimizer_gate_canary_runner_bundle",
            "cli_command": "proposal run-optimizer-gate-canary-runner-bundle",
            "mcp_tool": "run_optimizer_gate_canary_runner_bundle",
            "schema_version": OPTIMIZER_GATE_CANARY_RUNNER_EXECUTION_SCHEMA_VERSION,
            "input_artifact": OPTIMIZER_GATE_CANARY_RUNNER_BUNDLE_SCHEMA_VERSION,
            "runner_function": "run_registered_profile_canary_execution",
            "result_gate_function": "build_registered_profile_canary_result_gate",
            "requires_replayable_file_refs": True,
            "requires_execute_canary_flag": True,
            "outputs": [
                REGISTERED_PROFILE_CANARY_EXECUTION_SCHEMA_VERSION,
                REGISTERED_PROFILE_CANARY_RESULT_GATE_SCHEMA_VERSION,
            ],
            "executes_tool": True,
            "executes_experiment": True,
            "executes_promotion": False,
            "official_scores_claimed": False,
        },
        "optimizer_gate_promotion_review_queue_contract": {
            "function": "build_optimizer_gate_promotion_review_queue",
            "cli_command": "proposal build-optimizer-gate-promotion-review-queue",
            "mcp_tool": "build_optimizer_gate_promotion_review_queue",
            "schema_version": OPTIMIZER_GATE_PROMOTION_REVIEW_QUEUE_SCHEMA_VERSION,
            "input_artifact": OPTIMIZER_GATE_SCHEDULER_HANDOFF_SCHEMA_VERSION,
            "required_inputs": [
                REGISTERED_PROFILE_CANARY_RESULT_GATE_SCHEMA_VERSION,
                "promotion_policy",
                "human_approval",
            ],
            "queues_human_promotion_review": True,
            "requires_canary_result_gate_promotion_ready": True,
            "requires_human_approval": True,
            "executes_tool": False,
            "executes_experiment": False,
            "executes_promotion": False,
            "official_scores_claimed": False,
        },
        "optimizer_gate_human_promotion_approval_contract": {
            "function": "build_optimizer_gate_human_promotion_approval",
            "cli_command": "proposal build-optimizer-gate-human-promotion-approval",
            "mcp_tool": "build_optimizer_gate_human_promotion_approval",
            "schema_version": OPTIMIZER_GATE_HUMAN_PROMOTION_APPROVAL_SCHEMA_VERSION,
            "input_artifact": OPTIMIZER_GATE_PROMOTION_REVIEW_QUEUE_SCHEMA_VERSION,
            "records_human_review_decision": True,
            "requires_review_queue_ready": True,
            "approval_enables_local_promotion_action": True,
            "executes_tool": False,
            "executes_experiment": False,
            "executes_promotion": False,
            "official_scores_claimed": False,
        },
        "optimizer_gate_local_promotion_action_contract": {
            "function": "run_optimizer_gate_local_promotion_action",
            "cli_command": "proposal run-optimizer-gate-local-promotion-action",
            "mcp_tool": "run_optimizer_gate_local_promotion_action",
            "schema_version": OPTIMIZER_GATE_LOCAL_PROMOTION_ACTION_SCHEMA_VERSION,
            "input_artifact": OPTIMIZER_GATE_HUMAN_PROMOTION_APPROVAL_SCHEMA_VERSION,
            "requires_human_approval": True,
            "requires_execute_promotion_flag": True,
            "requires_local_profile_registry": True,
            "writes_local_profile_registry": True,
            "records_registry_diff": True,
            "writes_rollback_record": True,
            "writes_audit_log": True,
            "promotion_scope": "local_optimizer_gate_registry",
            "executes_tool": False,
            "executes_experiment": False,
            "executes_promotion": True,
            "official_scores_claimed": False,
        },
        "optimizer_gate_local_promotion_rollback_contract": {
            "function": "run_optimizer_gate_local_promotion_rollback",
            "cli_command": "proposal run-optimizer-gate-local-promotion-rollback",
            "mcp_tool": "run_optimizer_gate_local_promotion_rollback",
            "schema_version": OPTIMIZER_GATE_LOCAL_PROMOTION_ROLLBACK_SCHEMA_VERSION,
            "input_artifact": OPTIMIZER_GATE_LOCAL_PROMOTION_ROLLBACK_SCHEMA_VERSION,
            "restores_local_profile_registry": True,
            "executes_tool": False,
            "executes_experiment": False,
            "executes_rollback": True,
            "executes_promotion": False,
            "official_scores_claimed": False,
        },
        "optimizer_gate_external_submission_action_contract": {
            "function": "run_optimizer_gate_external_submission_action",
            "cli_command": "proposal run-optimizer-gate-external-submission-action",
            "mcp_tool": "run_optimizer_gate_external_submission_action",
            "schema_version": OPTIMIZER_GATE_EXTERNAL_SUBMISSION_ACTION_SCHEMA_VERSION,
            "input_artifact": OPTIMIZER_GATE_LOCAL_PROMOTION_ACTION_SCHEMA_VERSION,
            "requires_local_promotion_action": True,
            "requires_execute_submission_flag": True,
            "requires_http_submission_url": True,
            "requires_submission_payload": False,
            "requires_public_result_fetch": True,
            "executes_tool": True,
            "executes_experiment": False,
            "executes_official_submission": True,
            "executes_promotion": False,
            "official_scores_claimed": False,
        },
        "optimizer_gate_official_submission_contract": {
            "function": "build_optimizer_gate_official_submission",
            "cli_command": "proposal build-optimizer-gate-official-submission",
            "mcp_tool": "build_optimizer_gate_official_submission",
            "schema_version": OPTIMIZER_GATE_OFFICIAL_SUBMISSION_SCHEMA_VERSION,
            "input_artifact": OPTIMIZER_GATE_LOCAL_PROMOTION_ACTION_SCHEMA_VERSION,
            "requires_explicit_submission_id": True,
            "requires_public_result_verifier": True,
            "executes_official_submission": True,
            "executes_promotion": False,
            "official_scores_claimed": False,
        },
        "optimizer_gate_public_result_fetch_contract": {
            "function": "fetch_optimizer_gate_public_result",
            "cli_command": "proposal fetch-optimizer-gate-public-result",
            "mcp_tool": "fetch_optimizer_gate_public_result",
            "schema_version": OPTIMIZER_GATE_PUBLIC_RESULT_FETCH_SCHEMA_VERSION,
            "requires_public_result_url": True,
            "supported_parsers": [
                "json",
                "html_embedded_json",
                "html_meta_tags",
                "html_leaderboard_dom",
            ],
            "produces_fetch_artifact": True,
            "executes_tool": True,
            "executes_experiment": False,
            "executes_promotion": False,
            "official_scores_claimed": False,
        },
        "optimizer_package_runtime_benefit_audit_contract": {
            "function": "build_optimizer_package_runtime_benefit_audit",
            "cli_command": "proposal build-optimizer-package-runtime-benefit-audit",
            "mcp_tool": "build_optimizer_package_runtime_benefit_audit",
            "schema_version": OPTIMIZER_PACKAGE_RUNTIME_BENEFIT_AUDIT_SCHEMA_VERSION,
            "input_artifacts": [
                OPTIMIZER_RUNTIME_PROBE_SCHEMA_VERSION,
                SLICE_PATCH_CANDIDATES_SCHEMA_VERSION,
                GATE_POLICY_DECISION_SCHEMA_VERSION,
            ],
            "requires_runtime_ready": True,
            "requires_candidate_generated": True,
            "requires_gate_evidence_for_benefit_claim": True,
            "executes_tool": False,
            "executes_experiment": False,
            "executes_promotion": False,
            "official_scores_claimed": False,
        },
        "method_proposal_generation_trace_contract": {
            "function": "build_method_proposal_generation_trace",
            "cli_command": "proposal build-method-proposal-generation-trace",
            "mcp_tool": "build_method_proposal_generation_trace",
            "schema_version": METHOD_PROPOSAL_GENERATION_TRACE_SCHEMA_VERSION,
            "input_artifacts": [
                "generation_context",
                "generation_run",
                "structured_reasoning_trace",
                "method_proposals",
                "ranking_decisions",
            ],
            "records_all_generated_proposals": True,
            "records_structured_rationale": True,
            "records_private_chain_of_thought": False,
            "links_gate_results": True,
            "executes_tool": False,
            "executes_experiment": False,
            "executes_promotion": False,
            "official_scores_claimed": False,
        },
        "method_search_study_contract": {
            "functions": [
                "build_method_search_study",
                "ask_method_search_trial",
                "tell_method_search_trial",
                "sample_hexagon_guided_llm_proposals",
                "build_gate_feedback_memory",
            ],
            "cli_commands": [
                "proposal build-method-search-study",
                "proposal ask-method-search-trial",
                "proposal tell-method-search-trial",
            ],
            "mcp_tools": [
                "build_method_search_study",
                "ask_method_search_trial",
                "tell_method_search_trial",
            ],
            "schema_versions": {
                "study": METHOD_SEARCH_STUDY_SCHEMA_VERSION,
                "trial": METHOD_SEARCH_TRIAL_SCHEMA_VERSION,
                "sampler": HEXAGON_GUIDED_LLM_SAMPLER_SCHEMA_VERSION,
                "gate_feedback_memory": GATE_FEEDBACK_MEMORY_SCHEMA_VERSION,
            },
            "optuna_compatible": True,
            "supports_ask_tell": True,
            "trial_states": ["COMPLETE", "PRUNED", "FAIL", "WAITING"],
            "reserved_optuna_adapters": [
                "OptunaSamplerAdapter",
                "OptunaStorageAdapter",
                "OptunaDashboardExport",
            ],
            "optuna_package_integrated_as_main_path": False,
            "idea_hexagon_role": "operator_taxonomy_only",
            "llm_generates_proposals_under_operator": True,
            "supports_live_openai_compatible_llm_generation": True,
            "supports_injected_llm_completion_for_tests": True,
            "rule_only_round_robin": False,
            "gate_feedback_updates_sampler": True,
            "llm_may_claim_improvement": False,
            "executes_tool": False,
            "executes_experiment": False,
            "executes_promotion": False,
            "official_scores_claimed": False,
        },
        "multi_optimizer_candidate_race_contract": {
            "function": "build_multi_optimizer_candidate_race",
            "cli_command": "proposal build-multi-optimizer-candidate-race",
            "mcp_tool": "build_multi_optimizer_candidate_race",
            "schema_version": MULTI_OPTIMIZER_CANDIDATE_RACE_SCHEMA_VERSION,
            "run_function": "run_multi_optimizer_candidate_race",
            "run_cli_command": "proposal run-multi-optimizer-candidate-race",
            "run_mcp_tool": "run_multi_optimizer_candidate_race",
            "run_schema_version": MULTI_OPTIMIZER_CANDIDATE_RACE_RUN_SCHEMA_VERSION,
            "candidate_sources": [
                "llm",
                "optuna",
                "textgrad",
                "dspy",
                "promptwizard",
                "heuristic",
                "registered_optimizer_plugin",
            ],
            "parallel_candidate_generation_supported": True,
            "default_run_mode": "optimization-run",
            "run_modes": ["optimization-run", "review/dry-run"],
            "optimization_run_defaults": {
                "execute_optimizer_runtimes": True,
                "execute_llm_when_endpoint_configured": True,
                "allow_style_fallback": False,
                "fallback_counts_as_real_optimizer_candidate": False,
            },
            "python_package_runtime_cache_supported": True,
            "python_package_runtime_cache_root": ".research_cache/optimizer-runtime-packages",
            "review_dry_run_defaults": {
                "execute_optimizer_runtimes": False,
                "execute_llm": False,
                "allow_style_fallback": True,
                "fallback_counts_as_real_optimizer_candidate": False,
            },
            "style_fallback_must_be_marked": True,
            "fallback_winner_kind": "local_diagnostic_winner",
            "real_optimizer_winner_kind": "optimizer_winner",
            "normalizes_to_method_search_trials": True,
            "requires_gate_results": True,
            "winner_selected_by_gate_only": True,
            "updates_gate_feedback_memory": True,
            "executes_tool": False,
            "executes_experiment": False,
            "executes_promotion": False,
            "official_scores_claimed": False,
        },
        "optimizer_gate_public_result_verifier_contract": {
            "function": "verify_optimizer_gate_public_result",
            "cli_command": "proposal verify-optimizer-gate-public-result",
            "mcp_tool": "verify_optimizer_gate_public_result",
            "schema_version": OPTIMIZER_GATE_PUBLIC_RESULT_VERIFIER_SCHEMA_VERSION,
            "input_artifact": OPTIMIZER_GATE_OFFICIAL_SUBMISSION_SCHEMA_VERSION,
            "alternate_input_artifacts": [
                OPTIMIZER_GATE_EXTERNAL_SUBMISSION_ACTION_SCHEMA_VERSION,
            ],
            "accepts_public_result_fetch_artifact": True,
            "accepts_external_submission_action_artifact": True,
            "binds_submission_id": True,
            "binds_public_url": True,
            "requires_metrics_and_denominator": True,
            "official_scores_claimed": False,
        },
        "optimizer_gate_official_claim_contract": {
            "function": "build_optimizer_gate_official_claim",
            "cli_command": "proposal build-optimizer-gate-official-claim",
            "mcp_tool": "build_optimizer_gate_official_claim",
            "schema_version": OPTIMIZER_GATE_OFFICIAL_CLAIM_SCHEMA_VERSION,
            "input_artifact": OPTIMIZER_GATE_PUBLIC_RESULT_VERIFIER_SCHEMA_VERSION,
            "requires_verified_public_result": True,
            "blocks_local_scores_as_official_claims": True,
            "official_scores_claimed_when_verified": True,
        },
        "optimizer_gate_executable_loop_contract": {
            "function": "run_optimizer_gate_executable_loop",
            "cli_command": "proposal run-optimizer-gate-executable-loop",
            "mcp_tool": "run_optimizer_gate_executable_loop",
            "schema_version": OPTIMIZER_GATE_EXECUTABLE_LOOP_SCHEMA_VERSION,
            "input_artifact": REGISTERED_PROFILE_CANARY_RESULT_GATE_SCHEMA_VERSION,
            "auto_records_outcome": True,
            "auto_builds_optimizer_selection": True,
            "auto_executes_optimizer_runtime_probe": True,
            "auto_generates_next_candidate": True,
            "supports_auto_approve_registration": True,
            "auto_executes_dev_bundle_when_approved": True,
            "auto_runs_canary_runner_when_requested": True,
            "requires_execute_canary_runner_flag": True,
            "writes_outcome_schedule_after_canary": True,
            "writes_scheduler_loop_state_after_canary": True,
            "writes_method_proposal_generation_trace": True,
            "method_proposal_generation_trace_schema_version": (
                METHOD_PROPOSAL_GENERATION_TRACE_SCHEMA_VERSION
            ),
            "writes_artifact_manifest": True,
            "supports_budget": True,
            "supports_max_iterations": True,
            "stops_at_human_review_boundary": True,
            "stops_at_canary_runner_boundary": True,
            "stops_at_gate_blocked": True,
            "stops_at_runtime_not_ready": True,
            "stops_at_promotion_boundary": True,
            "stops_at_official_boundary": True,
            "executes_tool": True,
            "executes_experiment_when_dev_or_canary_eval_executed": True,
            "executes_promotion": False,
            "official_scores_claimed": False,
        },
        "model_runtime_preflight_contract": {
            "function": "build_model_runtime_preflight",
            "cli_command": "proposal build-model-runtime-preflight",
            "mcp_tool": "build_model_runtime_preflight",
            "schema_version": MODEL_RUNTIME_PREFLIGHT_SCHEMA_VERSION,
            "recommended_for_stages": [
                "target_smoke",
                "dev_model_eval",
                "canary_model_eval",
            ],
            "default_provider": "openai-compatible",
            "default_apply_no_think_for_qwen": True,
            "default_execute_probe": False,
            "supports_execute_probe": True,
            "blocks_on": [
                "model_runtime_probe_not_executed",
                "model_runtime_max_tokens_too_low",
                "model_runtime_error",
                "model_runtime_empty_output",
            ],
            "executes_tool_by_default": False,
            "executes_experiment": False,
            "executes_promotion": False,
            "official_scores_claimed": False,
        },
        "gate_composition_contract": {
            "function": "build_gate_policy_composition",
            "cli_command": "proposal build-gate-policy-composition",
            "mcp_tool": "build_gate_policy_composition",
            "schema_version": GATE_POLICY_COMPOSITION_SCHEMA_VERSION,
            "input_decision_schemas": [
                GATE_POLICY_DECISION_SCHEMA_VERSION,
                SLICE_GATE_DECISION_SCHEMA_VERSION,
                SLICE_VARIANCE_GATE_DECISION_SCHEMA_VERSION,
            ],
            "blocks_when_any_policy_blocks": True,
            "canary_allowed_when": "all required gate decisions allow canary",
            "executes_experiment": False,
        },
        "gate_policy_graph_contract": {
            "build_function": "build_gate_policy_graph",
            "evaluate_function": "evaluate_gate_policy_graph",
            "build_cli_command": "proposal build-gate-policy-graph",
            "evaluate_cli_command": "proposal evaluate-gate-policy-graph",
            "build_mcp_tool": "build_gate_policy_graph",
            "evaluate_mcp_tool": "evaluate_gate_policy_graph",
            "graph_schema": GATE_POLICY_GRAPH_SCHEMA_VERSION,
            "decision_schema": GATE_POLICY_GRAPH_DECISION_SCHEMA_VERSION,
            "composition_mode": "all_required_must_pass",
            "executes_experiment": False,
        },
        "benchmark_boundary": {
            "current_fixture": "smol_worldcup",
            "portable_inputs_supported": [
                "metric_table",
                "slice_table",
                "gate_policy",
                "gate_policy_composition",
                "gate_policy_graph",
                "paired_repeat_manifest",
                "slice_patch_outcome",
                "slice_optimizer_selection",
            ],
            "gate_policy_input_schema": GATE_POLICY_INPUT_SCHEMA_VERSION,
            "gate_policy_decision_schema": GATE_POLICY_DECISION_SCHEMA_VERSION,
            "gate_policy_composition_schema": GATE_POLICY_COMPOSITION_SCHEMA_VERSION,
            "gate_policy_graph_schema": GATE_POLICY_GRAPH_SCHEMA_VERSION,
            "gate_policy_graph_decision_schema": GATE_POLICY_GRAPH_DECISION_SCHEMA_VERSION,
            "profile_artifacts_are_fixtures": True,
            "plugin_manifest_schema": OPTIMIZER_GATE_PLUGIN_MANIFEST_SCHEMA_VERSION,
        },
        "plugin_manifests": [
            {
                "plugin_id": manifest["plugin_id"],
                "plugin_ref": manifest["plugin_ref"],
                "optimizer_adapter_count": manifest["plugin_summary"][
                    "optimizer_adapter_count"
                ],
                "gate_policy_count": manifest["plugin_summary"]["gate_policy_count"],
                "runtime_capable_optimizer_count": manifest["plugin_summary"].get(
                    "runtime_capable_optimizer_count",
                    0,
                ),
                "manifest_only": bool(
                    manifest["plugin_summary"].get("manifest_only", True)
                ),
            }
            for manifest in loaded_plugin_manifests
        ],
        "planned_integrations": [
            {
                "name": "dspy-mipro",
                "status": "not_integrated",
                "expected_surface": "module_section_instruction_search",
            },
            {
                "name": "textgrad-python",
                "status": "not_integrated",
                "expected_surface": "section_local_gradient_text_feedback",
            },
            {
                "name": "promptwizard-runtime",
                "status": "not_integrated",
                "expected_surface": "constrained_instruction_variant_search",
            },
        ],
        "claim_boundary": "non-executing optimizer/gate system registry only",
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def build_optimizer_gate_run_plan(
    *,
    context: dict[str, Any] | str | Path,
    base_profile_id: str,
    optimizer: str = "manual-template",
    optimizer_gate_plugin_manifests: list[dict[str, Any] | str | Path] | None = None,
    max_candidates: int = 1,
    execute_runtime_probe: bool = False,
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a non-executing optimizer/gate pipeline bundle."""
    if not base_profile_id:
        raise ValueError("base_profile_id is required")
    adapter = resolve_optimizer_adapter(
        optimizer,
        plugin_manifests=optimizer_gate_plugin_manifests,
    )
    output_root = Path(output_dir)
    runtime_probe_path = output_root / "optimizer-runtime-probe.json"
    candidates_path = output_root / "slice-patch-candidates.json"
    materialization_path = output_root / "slice-patch-materialization.json"
    run_path = output_root / "optimizer-gate-run.json"
    _ensure_writable(run_path, overwrite=overwrite)

    runtime_probe = probe_optimizer_runtime(
        optimizer=adapter.name,
        optimizer_gate_plugin_manifests=optimizer_gate_plugin_manifests,
        execute_probe=execute_runtime_probe,
        output_path=runtime_probe_path,
        overwrite=overwrite,
    )
    runtime_ready = bool(runtime_probe.get("runtime_ready", False))
    if runtime_ready:
        candidates = generate_slice_patch_candidates(
            context=context,
            optimizer=adapter.name,
            optimizer_gate_plugin_manifests=optimizer_gate_plugin_manifests,
            max_candidates=max_candidates,
            execute_optimizer=False,
            output_path=candidates_path,
            overwrite=overwrite,
        )
    else:
        candidates = {
            "status": "skipped",
            "candidate_count": 0,
            "candidates": [],
            "optimizer_runtime": runtime_probe.get("runtime") or {},
            "executes_tool": False,
            "executes_experiment": False,
            "official_scores_claimed": False,
        }
    candidate_items = candidates.get("candidates")
    first_candidate = (
        candidate_items[0]
        if isinstance(candidate_items, list)
        and candidate_items
        and isinstance(candidate_items[0], dict)
        else None
    )
    materialization: dict[str, Any] = {}
    if (
        _string_value(candidates.get("status")) == "completed"
        and isinstance(first_candidate, dict)
    ):
        materialization = materialize_slice_patch_candidate(
            candidate=first_candidate,
            base_profile_id=base_profile_id,
            output_path=materialization_path,
            overwrite=overwrite,
        )

    status = _optimizer_gate_run_status(
        runtime_probe=runtime_probe,
        candidates=candidates,
        materialization=materialization,
    )
    candidate_status = _string_value(candidates.get("status")) or "unknown"
    materialization_status = _string_value(materialization.get("status")) or "skipped"
    payload = {
        "status": status,
        "schema_version": OPTIMIZER_GATE_RUN_SCHEMA_VERSION,
        "base_profile_id": base_profile_id,
        "optimizer": {
            "name": adapter.name,
            "registry_ref": f"optimizer_adapter:{adapter.name}",
            "adapter_type": adapter.adapter_type,
            "runtime_status": adapter.runtime_status,
            "candidate_schema": adapter.candidate_schema,
            "module_scope": adapter.module_scope,
            "candidate_count": int(candidates.get("candidate_count", 0) or 0),
            "runtime": candidates.get("optimizer_runtime")
            or runtime_probe.get("runtime")
            or {},
            "executes_tool": bool(
                runtime_probe.get("executes_tool", False)
                or candidates.get("executes_tool", False)
            ),
        },
        "runtime_probe": {
            "status": _string_value(runtime_probe.get("status")) or "unknown",
            "runtime_ready": runtime_ready,
            "recommended_next_action": _string_value(
                runtime_probe.get("recommended_next_action")
            ),
            "output_path": str(runtime_probe_path),
        },
        "stages": [
            {
                "name": "probe_optimizer_runtime",
                "status": _string_value(runtime_probe.get("status")) or "unknown",
                "output_path": str(runtime_probe_path),
            },
            {
                "name": "generate_slice_patch_candidates",
                "status": candidate_status if runtime_ready else "skipped",
                "output_path": str(candidates_path) if runtime_ready else None,
            },
            {
                "name": "materialize_slice_patch_candidate",
                "status": materialization_status,
                "output_path": str(materialization_path) if materialization else None,
            },
            {
                "name": "gate_plan",
                "status": "planned",
                "output_path": str(run_path),
            },
        ],
        "artifacts": {
            "optimizer_runtime_probe": str(runtime_probe_path),
            "slice_patch_candidates": str(candidates_path) if runtime_ready else None,
            "slice_patch_materialization": (
                str(materialization_path) if materialization else None
            ),
            "optimizer_gate_run": str(run_path),
        },
        "materialization": {
            "status": _string_value(materialization.get("status")) or "skipped",
            "execution_ready": bool(materialization.get("execution_ready", False)),
            "patch_id": _string_value(materialization.get("patch_id")),
        },
        "gate_plan": {
            "required_gates": [
                "prompt_leakage_audit",
                "target_smoke",
                "dev_model_eval",
                "evaluate_gate_policy",
                "evaluate_slice_gate",
                "evaluate_slice_variance_gate",
                "build_gate_policy_composition",
            ],
            "policy_refs": [
                f"gate_policy:{policy.policy_id}"
                for policy in _gate_policy_registry_objects(
                    plugin_manifests=optimizer_gate_plugin_manifests
                )
            ],
            "canary_allowed": False,
            "promotion_ready": False,
            "requires_prompt_profile_registration": bool(materialization),
            "protected_slice_regression_allowed": False,
        },
        "claim_boundary": (
            "non-executing optimizer/gate run plan only; not a dev/canary run "
            "and not a promotion decision"
        ),
        "executes_tool": bool(
            runtime_probe.get("executes_tool", False)
            or candidates.get("executes_tool", False)
        ),
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    run_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(run_path)
    return payload


def build_optimizer_gate_execution_plan(
    *,
    optimizer_gate_run: dict[str, Any] | str | Path,
    benchmark_id: str = "smol_worldcup",
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a non-executing benchmark adapter plan for an optimizer/gate run."""
    run_payload, run_path = _load_object(optimizer_gate_run)
    adapter = resolve_benchmark_adapter(benchmark_id)
    materialization = (
        run_payload.get("materialization")
        if isinstance(run_payload.get("materialization"), dict)
        else {}
    )
    runtime_probe = (
        run_payload.get("runtime_probe")
        if isinstance(run_payload.get("runtime_probe"), dict)
        else {}
    )
    optimizer_payload = (
        run_payload.get("optimizer")
        if isinstance(run_payload.get("optimizer"), dict)
        else {}
    )
    runtime_probe_status = _string_value(runtime_probe.get("status")) or "unknown"
    runtime_ready = bool(runtime_probe.get("runtime_ready", True))
    candidate_count = int(optimizer_payload.get("candidate_count") or 0)
    execution_ready = bool(materialization.get("execution_ready", False))
    hard_blockers: list[str] = []
    if not runtime_ready:
        status = "blocked_optimizer_runtime_not_ready"
        stage_status = "blocked_by_optimizer_runtime"
        register_profile_status = "blocked_by_optimizer_runtime"
        hard_blockers.append("optimizer_runtime_not_ready")
    elif candidate_count <= 0:
        status = "blocked_optimizer_candidate_missing"
        stage_status = "blocked_until_optimizer_candidate"
        register_profile_status = "blocked_until_optimizer_candidate"
        hard_blockers.append("optimizer_candidate_missing")
    else:
        status = (
            "ready_for_dev_execution_plan"
            if execution_ready
            else "needs_prompt_profile_registration"
        )
        stage_status = (
            "planned" if execution_ready else "blocked_until_prompt_profile_registered"
        )
        register_profile_status = (
            "skipped_already_ready"
            if execution_ready
            else "required_before_execution"
        )
    preflight = {
        "run_status": _string_value(run_payload.get("status")) or "unknown",
        "runtime_probe_status": runtime_probe_status,
        "runtime_ready": runtime_ready,
        "candidate_count": candidate_count,
        "materialization_status": _string_value(materialization.get("status"))
        or "unknown",
        "execution_ready": execution_ready,
        "hard_blockers": hard_blockers,
    }
    stages = [
        {
            "name": "register_prompt_profile",
            "status": register_profile_status,
            "executes_experiment": False,
            "artifact": "registered_prompt_profile",
        }
    ]
    for stage_name in adapter.planned_execution_stages:
        stages.append({
            "name": stage_name,
            "status": stage_status,
            "executes_experiment": False,
        })
    gate_plan = (
        run_payload.get("gate_plan")
        if isinstance(run_payload.get("gate_plan"), dict)
        else {}
    )
    required_gates = _string_list(gate_plan.get("required_gates"))
    payload = {
        "status": status,
        "schema_version": OPTIMIZER_GATE_EXECUTION_PLAN_SCHEMA_VERSION,
        "benchmark_adapter": adapter.to_manifest(),
        "optimizer_gate_run_ref": str(run_path) if run_path is not None else "inline",
        "base_profile_id": _string_value(run_payload.get("base_profile_id")),
        "preflight": preflight,
        "stages": stages,
        "artifact_contract": {
            "required_inputs": list(adapter.required_artifacts),
            "expected_outputs": list(adapter.gate_outputs),
            "profile_registration_required": not execution_ready,
        },
        "gate_plan": {
            "required_gates": required_gates,
            "canary_allowed": False,
            "promotion_ready": False,
            "composition_required": "build_gate_policy_composition" in required_gates,
        },
        "claim_boundary": (
            "non-executing optimizer/gate benchmark execution plan only; "
            "not a dev/canary run and not a promotion decision"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def build_cp_bench_proposal_effectiveness_bundle(
    *,
    round_reports: list[dict[str, Any] | str | Path],
    output_dir: str | Path,
    control_label: str = "without_failure_driven_context",
    treatment_label: str = "with_failure_driven_context",
    overwrite: bool = False,
) -> dict[str, Any]:
    reports = _load_cp_bench_round_reports(round_reports)
    output = Path(output_dir)
    if output.exists() and not overwrite:
        report_file = output / "proposal-effectiveness.json"
        if report_file.exists():
            raise FileExistsError(
                f"{output} already contains effectiveness artifacts; pass overwrite=True to replace them"
            )
    output.mkdir(parents=True, exist_ok=True)
    control_outcomes = [_cp_bench_control_outcome(report) for report in reports]
    treatment_outcomes = [_cp_bench_treatment_outcome(report) for report in reports]
    control_path = output / "control-outcomes.jsonl"
    treatment_path = output / "treatment-outcomes.jsonl"
    report_path = output / "proposal-effectiveness.json"
    markdown_path = output / "proposal-effectiveness.md"
    _write_jsonl(control_outcomes, control_path)
    _write_jsonl(treatment_outcomes, treatment_path)
    effectiveness = evaluate_failure_driven_proposal_effectiveness(
        control_outcomes=control_outcomes,
        treatment_outcomes=treatment_outcomes,
        output_path=report_path,
        control_label=control_label,
        treatment_label=treatment_label,
        overwrite=True,
    )
    _write_cp_bench_effectiveness_markdown(
        effectiveness=effectiveness,
        reports=reports,
        path=markdown_path,
    )
    return {
        "status": "completed",
        "schema_version": CP_BENCH_EFFECTIVENESS_BUNDLE_SCHEMA_VERSION,
        "round_report_count": len(reports),
        "control_outcome_count": len(control_outcomes),
        "treatment_outcome_count": len(treatment_outcomes),
        "control_outcomes_path": str(control_path),
        "treatment_outcomes_path": str(treatment_path),
        "effectiveness_report_path": str(report_path),
        "markdown_path": str(markdown_path),
        "comparison": effectiveness.get("comparison", {}),
        "claim_boundary": (
            "local CP-Bench proposal effectiveness bundle only; not official leaderboard proof"
        ),
        "executes_tool": False,
        "official_scores_claimed": False,
    }


def build_fasttext_proposal_effectiveness_bundle(
    *,
    multi_round_reports: list[dict[str, Any] | str | Path],
    output_dir: str | Path,
    control_label: str = "without_failure_driven_context",
    treatment_label: str = "with_failure_driven_context",
    include_failed_rounds: bool = True,
    overwrite: bool = False,
) -> dict[str, Any]:
    reports = _load_fasttext_multi_round_reports(multi_round_reports)
    output = Path(output_dir)
    if output.exists() and not overwrite:
        report_file = output / "proposal-effectiveness.json"
        if report_file.exists():
            raise FileExistsError(
                f"{output} already contains effectiveness artifacts; pass overwrite=True to replace them"
            )
    output.mkdir(parents=True, exist_ok=True)
    control_outcomes = _flatten_fasttext_control_outcomes(
        reports,
        include_failed_rounds=include_failed_rounds,
    )
    treatment_outcomes = _flatten_fasttext_treatment_outcomes(
        reports,
        include_failed_rounds=include_failed_rounds,
    )
    control_path = output / "control-outcomes.jsonl"
    treatment_path = output / "treatment-outcomes.jsonl"
    report_path = output / "proposal-effectiveness.json"
    markdown_path = output / "proposal-effectiveness.md"
    _write_jsonl(control_outcomes, control_path)
    _write_jsonl(treatment_outcomes, treatment_path)
    effectiveness = evaluate_failure_driven_proposal_effectiveness(
        control_outcomes=control_outcomes,
        treatment_outcomes=treatment_outcomes,
        output_path=report_path,
        control_label=control_label,
        treatment_label=treatment_label,
        overwrite=True,
    )
    _write_fasttext_effectiveness_markdown(
        effectiveness=effectiveness,
        reports=reports,
        include_failed_rounds=include_failed_rounds,
        path=markdown_path,
    )
    return {
        "status": "completed",
        "schema_version": FASTTEXT_EFFECTIVENESS_BUNDLE_SCHEMA_VERSION,
        "multi_round_report_count": len(reports),
        "include_failed_rounds": include_failed_rounds,
        "control_outcome_count": len(control_outcomes),
        "treatment_outcome_count": len(treatment_outcomes),
        "control_outcomes_path": str(control_path),
        "treatment_outcomes_path": str(treatment_path),
        "effectiveness_report_path": str(report_path),
        "markdown_path": str(markdown_path),
        "comparison": effectiveness.get("comparison", {}),
        "claim_boundary": (
            "local fastText proposal effectiveness bundle only; not an official benchmark score "
            "or arbitrary autonomous optimization claim"
        ),
        "executes_tool": False,
        "official_scores_claimed": False,
    }


def build_smol_worldcup_proposal_effectiveness_bundle(
    *,
    control_reports: list[dict[str, Any] | str | Path],
    treatment_reports: list[dict[str, Any] | str | Path],
    output_dir: str | Path,
    control_label: str = "without_failure_driven_context",
    treatment_label: str = "with_failure_driven_context",
    split_filter: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    controls = _load_smol_worldcup_reports(control_reports)
    treatments = _load_smol_worldcup_reports(treatment_reports)
    if len(controls) != len(treatments):
        raise ValueError("control_reports and treatment_reports must have the same length")
    output = Path(output_dir)
    if output.exists() and not overwrite:
        report_file = output / "proposal-effectiveness.json"
        if report_file.exists():
            raise FileExistsError(
                f"{output} already contains effectiveness artifacts; pass overwrite=True to replace them"
            )
    output.mkdir(parents=True, exist_ok=True)
    paired_reports = list(zip(controls, treatments, strict=True))
    if split_filter is not None:
        normalized_split = split_filter.strip().lower()
        paired_reports = [
            (control, treatment)
            for control, treatment in paired_reports
            if _smol_worldcup_eval_split(treatment) == normalized_split
        ]
        if not paired_reports:
            raise ValueError(f"no Smol WorldCup report pairs matched split_filter={split_filter!r}")
    control_outcomes = [
        _smol_worldcup_control_outcome(control=control, treatment=treatment)
        for control, treatment in paired_reports
    ]
    treatment_outcomes = [
        _smol_worldcup_treatment_outcome(control=control, treatment=treatment)
        for control, treatment in paired_reports
    ]
    control_path = output / "control-outcomes.jsonl"
    treatment_path = output / "treatment-outcomes.jsonl"
    report_path = output / "proposal-effectiveness.json"
    markdown_path = output / "proposal-effectiveness.md"
    _write_jsonl(control_outcomes, control_path)
    _write_jsonl(treatment_outcomes, treatment_path)
    effectiveness = evaluate_failure_driven_proposal_effectiveness(
        control_outcomes=control_outcomes,
        treatment_outcomes=treatment_outcomes,
        output_path=report_path,
        control_label=control_label,
        treatment_label=treatment_label,
        overwrite=True,
    )
    _write_smol_worldcup_effectiveness_markdown(
        effectiveness=effectiveness,
        pairs=paired_reports,
        split_filter=split_filter,
        path=markdown_path,
    )
    return {
        "status": "completed",
        "schema_version": SMOL_WORLDCUP_EFFECTIVENESS_BUNDLE_SCHEMA_VERSION,
        "comparison_pair_count": len(paired_reports),
        "split_filter": split_filter,
        "control_outcome_count": len(control_outcomes),
        "treatment_outcome_count": len(treatment_outcomes),
        "control_outcomes_path": str(control_path),
        "treatment_outcomes_path": str(treatment_path),
        "effectiveness_report_path": str(report_path),
        "markdown_path": str(markdown_path),
        "comparison": effectiveness.get("comparison", {}),
        "claim_boundary": (
            "local Smol WorldCup proposal effectiveness bundle only; not official leaderboard "
            "proof, hidden-test evidence, or broad prompt-optimization proof"
        ),
        "executes_tool": False,
        "official_scores_claimed": False,
    }


def build_smol_worldcup_result_analysis(
    *,
    control_reports: list[dict[str, Any] | str | Path],
    treatment_reports: list[dict[str, Any] | str | Path],
    output_dir: str | Path,
    split_filter: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    controls = _load_smol_worldcup_reports(control_reports)
    treatments = _load_smol_worldcup_reports(treatment_reports)
    if len(controls) != len(treatments):
        raise ValueError("control_reports and treatment_reports must have the same length")
    paired_reports = list(zip(controls, treatments, strict=True))
    if split_filter is not None:
        normalized_split = split_filter.strip().lower()
        paired_reports = [
            (control, treatment)
            for control, treatment in paired_reports
            if _smol_worldcup_eval_split(treatment) == normalized_split
        ]
        if not paired_reports:
            raise ValueError(f"no Smol WorldCup report pairs matched split_filter={split_filter!r}")

    output = Path(output_dir)
    if output.exists() and not overwrite:
        analysis_file = output / "smol-worldcup-result-analysis.json"
        if analysis_file.exists():
            raise FileExistsError(
                f"{output} already contains result analysis artifacts; pass overwrite=True to replace them"
            )
    output.mkdir(parents=True, exist_ok=True)

    metric_regressions = _smol_worldcup_result_metric_regressions(paired_reports)
    row_deltas = _smol_worldcup_result_row_deltas(paired_reports)
    regression_rows = [item for item in row_deltas if float(item["score_delta"]) < 0]
    improvement_rows = [item for item in row_deltas if float(item["score_delta"]) > 0]
    direct_regressions = [
        item
        for item in regression_rows
        if item.get("root_cause_hypothesis") == "direct_prompt_change_candidate"
    ]
    repeat_first_regressions = [
        item
        for item in regression_rows
        if item.get("root_cause_hypothesis")
        in {"stochastic_or_format_variation", "runtime_error_or_truncated_output"}
    ]
    if repeat_first_regressions:
        next_action = "run_paired_repeat_before_changing_prompt"
    elif direct_regressions:
        next_action = "inspect_prompt_delta_before_changing_prompt"
    elif regression_rows:
        next_action = "collect_missing_artifacts_before_changing_prompt"
    else:
        next_action = "proceed_to_gate_review_without_regression_repair"
    status = (
        "analysis_required_before_next_change"
        if metric_regressions or regression_rows
        else "analysis_completed_no_regression"
    )
    payload = {
        "status": status,
        "schema_version": SMOL_WORLDCUP_RESULT_ANALYSIS_SCHEMA_VERSION,
        "split_filter": split_filter,
        "comparison_pair_count": len(paired_reports),
        "metric_regressions": metric_regressions,
        "row_deltas": row_deltas,
        "summary": {
            "regression_row_count": len(regression_rows),
            "improvement_row_count": len(improvement_rows),
            "direct_prompt_change_regression_count": len(direct_regressions),
            "repeat_first_regression_count": len(repeat_first_regressions),
        },
        "next_action": next_action,
        "analysis_boundary": (
            "Analyze benchmark result deltas before changing prompts or launching the next "
            "optimizer round. This artifact explains local evidence only."
        ),
        "executes_tool": False,
        "official_scores_claimed": False,
    }
    analysis_path = output / "smol-worldcup-result-analysis.json"
    markdown_path = output / "README.md"
    analysis_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_smol_worldcup_result_analysis_markdown(payload=payload, path=markdown_path)
    return {
        **payload,
        "analysis_path": str(analysis_path),
        "markdown_path": str(markdown_path),
    }


def build_smol_worldcup_confidence_variance_gate(
    *,
    aa_result_analysis: dict[str, Any] | str | Path,
    candidate_result_analyses: list[dict[str, Any] | str | Path],
    output_path: str | Path | None = None,
    confidence_category: str = "confidence_calibration",
    min_abs_score_delta: float = 1.0,
    aa_coverage_ratio: float = 1.0,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Gate confidence-row regression attribution against A/A variance evidence."""
    if not candidate_result_analyses:
        raise ValueError("candidate_result_analyses is required")
    aa_payload, aa_path = _load_object(aa_result_analysis)
    candidate_payloads: list[tuple[dict[str, Any], Path | None]] = [
        _load_object(item) for item in candidate_result_analyses
    ]
    threshold = abs(float(min_abs_score_delta))
    aa_rows = _smol_worldcup_confidence_variance_rows(
        aa_payload,
        confidence_category=confidence_category,
        min_abs_score_delta=threshold,
    )
    aa_by_row = {str(row["row_id"]): row for row in aa_rows}
    max_abs_score_delta = max(
        [abs(float(row["score_delta"])) for row in aa_rows],
        default=0.0,
    )
    candidate_assessments = [
        _smol_worldcup_confidence_candidate_assessment(
            payload=candidate_payload,
            ref=str(candidate_path) if candidate_path is not None else "inline",
            aa_by_row=aa_by_row,
            confidence_category=confidence_category,
            min_abs_score_delta=threshold,
            aa_coverage_ratio=aa_coverage_ratio,
        )
        for candidate_payload, candidate_path in candidate_payloads
    ]
    candidate_confidence_regression_count = sum(
        len(item["confidence_rows"]) for item in candidate_assessments
    )
    hard_blockers: set[str] = set()
    if _smol_worldcup_confidence_input_claimed_official(
        aa_payload,
        [payload for payload, _ in candidate_payloads],
    ):
        hard_blockers.add("official_scores_claimed_input")
    if aa_rows:
        hard_blockers.add("aa_confidence_variance_detected")
    if not aa_rows and candidate_confidence_regression_count:
        hard_blockers.add("missing_aa_confidence_variance_baseline")

    if "official_scores_claimed_input" in hard_blockers:
        status = "blocked_official_claim_input"
    elif aa_rows:
        status = "blocked_by_aa_confidence_variance"
    elif candidate_confidence_regression_count:
        status = "needs_aa_confidence_repeat"
    else:
        status = "passed_for_optimizer_regression_attribution"
    attribution_allowed = status == "passed_for_optimizer_regression_attribution"
    if aa_rows:
        next_action = "build_cached_confidence_scoring_gate_before_prompt_repair"
    elif candidate_confidence_regression_count:
        next_action = "run_aa_confidence_repeat_before_regression_attribution"
    else:
        next_action = "proceed_to_prompt_delta_review"
    payload = {
        "status": status,
        "schema_version": SMOL_WORLDCUP_CONFIDENCE_VARIANCE_GATE_SCHEMA_VERSION,
        "confidence_category": confidence_category,
        "min_abs_score_delta": round(threshold, 6),
        "aa_coverage_ratio": round(float(aa_coverage_ratio), 6),
        "aa_result_analysis_ref": str(aa_path) if aa_path is not None else "inline",
        "candidate_result_analysis_refs": [
            str(path) if path is not None else "inline"
            for _, path in candidate_payloads
        ],
        "aa_confidence_variance": {
            "row_count": len(aa_rows),
            "affected_row_ids": [str(row["row_id"]) for row in aa_rows],
            "max_abs_score_delta": round(max_abs_score_delta, 6),
            "rows": aa_rows,
        },
        "candidate_assessments": candidate_assessments,
        "summary": {
            "candidate_count": len(candidate_assessments),
            "candidate_confidence_regression_count": candidate_confidence_regression_count,
            "aa_confidence_variance_row_count": len(aa_rows),
        },
        "gate": {
            "aa_confidence_variance_detected": bool(aa_rows),
            "optimizer_regression_attribution_allowed": attribution_allowed,
            "prompt_repair_allowed": attribution_allowed,
            "canary_allowed": False,
            "promotion_ready": False,
        },
        "hard_blockers": sorted(hard_blockers),
        "recommended_next_action": next_action,
        "claim_boundary": (
            "local Smol WorldCup confidence variance gate only; it does not execute "
            "benchmark runs, repair prompts, promote profiles, or claim official scores"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def build_smol_worldcup_cached_confidence_scoring_gate(
    *,
    model_eval_reports: list[dict[str, Any] | str | Path],
    output_path: str | Path | None = None,
    confidence_category: str = "confidence_calibration",
    min_repeats: int = 2,
    max_score_range: float = 0.0,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Gate confidence prompt repair on cached output and deterministic scoring evidence."""
    if not model_eval_reports:
        raise ValueError("model_eval_reports is required")
    loaded_reports = [_load_object(item) for item in model_eval_reports]
    threshold = max(0.0, float(max_score_range))
    rows = _smol_worldcup_cached_confidence_row_diagnostics(
        loaded_reports,
        confidence_category=confidence_category,
        min_repeats=int(min_repeats),
        max_score_range=threshold,
    )
    hard_blockers: set[str] = set()
    if any(bool(payload.get("official_scores_claimed")) for payload, _ in loaded_reports):
        hard_blockers.add("official_scores_claimed_input")
    if not rows:
        hard_blockers.add("missing_confidence_rows")
    for row in rows:
        hard_blockers.update(str(item) for item in row.get("hard_blockers", []))

    if "official_scores_claimed_input" in hard_blockers:
        status = "blocked_official_claim_input"
    elif hard_blockers:
        status = "blocked_cached_confidence_scoring_not_ready"
    else:
        status = "passed_cached_confidence_scoring_gate"
    allowed = status == "passed_cached_confidence_scoring_gate"
    if allowed:
        next_action = "resume_prompt_delta_review"
    else:
        next_action = "add_response_cache_and_scorer_version_then_repeat_confidence_rows"
    report_refs = [str(path) if path is not None else "inline" for _, path in loaded_reports]
    payload = {
        "status": status,
        "schema_version": SMOL_WORLDCUP_CACHED_CONFIDENCE_SCORING_GATE_SCHEMA_VERSION,
        "confidence_category": confidence_category,
        "min_repeats": int(min_repeats),
        "max_score_range": round(threshold, 6),
        "model_eval_report_refs": report_refs,
        "summary": {
            "report_count": len(loaded_reports),
            "confidence_row_count": len(rows),
            "blocked_row_count": sum(1 for row in rows if row.get("hard_blockers")),
            "all_rows_cached_output_ready": bool(rows)
            and all(bool(row.get("cached_output_ready")) for row in rows),
            "all_rows_scoring_deterministic": bool(rows)
            and all(bool(row.get("scoring_deterministic")) for row in rows),
        },
        "row_diagnostics": rows,
        "gate": {
            "cached_confidence_scoring_ready": allowed,
            "optimizer_regression_attribution_allowed": allowed,
            "prompt_repair_allowed": allowed,
            "canary_allowed": False,
            "promotion_ready": False,
        },
        "hard_blockers": sorted(hard_blockers),
        "recommended_next_action": next_action,
        "claim_boundary": (
            "local Smol WorldCup cached confidence scoring gate only; it consumes "
            "existing model-eval artifacts and does not execute benchmark runs, repair "
            "prompts, promote profiles, or claim official scores"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def build_real_paper_proposal_effectiveness_bundle(
    *,
    proof_archives: list[dict[str, Any] | str | Path],
    output_dir: str | Path,
    control_label: str = "without_failure_driven_context",
    treatment_label: str = "with_failure_driven_context",
    overwrite: bool = False,
) -> dict[str, Any]:
    archives = _load_real_paper_proof_archives(proof_archives)
    output = Path(output_dir)
    if output.exists() and not overwrite:
        report_file = output / "proposal-effectiveness.json"
        if report_file.exists():
            raise FileExistsError(
                f"{output} already contains effectiveness artifacts; pass overwrite=True to replace them"
            )
    output.mkdir(parents=True, exist_ok=True)
    metric_names = sorted(
        {
            metric_name
            for archive in archives
            for metric_name in _real_paper_metric_delta(archive)
        }
    )
    control_outcomes = [
        _real_paper_control_outcome(archive, metric_names=metric_names) for archive in archives
    ]
    treatment_outcomes = [
        _real_paper_treatment_outcome(archive, metric_names=metric_names) for archive in archives
    ]
    control_path = output / "control-outcomes.jsonl"
    treatment_path = output / "treatment-outcomes.jsonl"
    report_path = output / "proposal-effectiveness.json"
    markdown_path = output / "proposal-effectiveness.md"
    _write_jsonl(control_outcomes, control_path)
    _write_jsonl(treatment_outcomes, treatment_path)
    effectiveness = evaluate_failure_driven_proposal_effectiveness(
        control_outcomes=control_outcomes,
        treatment_outcomes=treatment_outcomes,
        output_path=report_path,
        control_label=control_label,
        treatment_label=treatment_label,
        overwrite=True,
    )
    _write_real_paper_effectiveness_markdown(
        effectiveness=effectiveness,
        archives=archives,
        path=markdown_path,
    )
    return {
        "status": "completed",
        "schema_version": REAL_PAPER_EFFECTIVENESS_BUNDLE_SCHEMA_VERSION,
        "proof_archive_count": len(archives),
        "control_outcome_count": len(control_outcomes),
        "treatment_outcome_count": len(treatment_outcomes),
        "control_outcomes_path": str(control_path),
        "treatment_outcomes_path": str(treatment_path),
        "effectiveness_report_path": str(report_path),
        "markdown_path": str(markdown_path),
        "comparison": effectiveness.get("comparison", {}),
        "claim_boundary": (
            "local real-paper public-slice proposal effectiveness bundle only; not an official "
            "benchmark score, full paper reproduction, or proof of general cross-task improvement"
        ),
        "executes_tool": False,
        "official_scores_claimed": False,
    }


def build_cross_task_proposal_effectiveness_summary(
    *,
    effectiveness_reports: list[dict[str, Any] | str | Path],
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    reports = _load_effectiveness_reports(effectiveness_reports)
    output = Path(output_dir)
    if output.exists() and not overwrite:
        summary_file = output / "cross-task-summary.json"
        if summary_file.exists():
            raise FileExistsError(
                f"{output} already contains cross-task summary artifacts; pass overwrite=True to replace them"
            )
    output.mkdir(parents=True, exist_ok=True)
    task_summaries = [_cross_task_entry(report=report) for report in reports]
    metric_aggregate = _cross_task_metric_aggregate(task_summaries)
    verdict_counts = _cross_task_verdict_counts(task_summaries)
    summary = {
        "status": "completed",
        "schema_version": CROSS_TASK_EFFECTIVENESS_SUMMARY_SCHEMA_VERSION,
        "task_count": len(task_summaries),
        "task_summaries": task_summaries,
        "aggregate": {
            "verdict_counts": verdict_counts,
            "metric_aggregate": metric_aggregate,
            "consistent_improvements": _consistent_positive_metrics(metric_aggregate),
            "tradeoff_metrics": _tradeoff_metrics(metric_aggregate),
        },
        "claim_boundary": (
            "cross-task local proposal effectiveness summary only; not proof of broad "
            "generalization or official benchmark improvement"
        ),
        "executes_tool": False,
        "official_scores_claimed": False,
    }
    summary_path = output / "cross-task-summary.json"
    markdown_path = output / "cross-task-summary.md"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_cross_task_effectiveness_markdown(summary=summary, path=markdown_path)
    summary["summary_path"] = str(summary_path)
    summary["markdown_path"] = str(markdown_path)
    return summary


def build_proposal_effectiveness_claim_audit(
    *,
    cross_task_summary: dict[str, Any] | str | Path,
    output_dir: str | Path,
    minimum_task_count: int = 3,
    minimum_positive_task_families: int = 2,
    overwrite: bool = False,
) -> dict[str, Any]:
    summary, _ = _load_object(cross_task_summary)
    output = Path(output_dir)
    if output.exists() and not overwrite:
        audit_file = output / "proposal-effectiveness-claim-audit.json"
        if audit_file.exists():
            raise FileExistsError(
                f"{output} already contains claim audit artifacts; pass overwrite=True to replace them"
            )
    output.mkdir(parents=True, exist_ok=True)
    task_count = int(summary.get("task_count", 0) or 0)
    aggregate = summary.get("aggregate") if isinstance(summary.get("aggregate"), dict) else {}
    verdict_counts_raw = (
        aggregate.get("verdict_counts") if isinstance(aggregate.get("verdict_counts"), dict) else {}
    )
    verdict_counts = {str(key): int(value) for key, value in verdict_counts_raw.items() if _is_plain_number(value)}
    positive_count = int(verdict_counts.get("treatment_improved_on_measured_metrics", 0))
    mixed_count = int(verdict_counts.get("mixed_signal", 0))
    regressed_count = int(verdict_counts.get("treatment_regressed_on_measured_metrics", 0))
    task_families = [
        _string_value(item.get("task_family")) or "unknown_task_family"
        for item in summary.get("task_summaries", [])
        if isinstance(item, dict)
    ]
    consistent_improvements = _string_list(aggregate.get("consistent_improvements"))
    tradeoff_metrics = _string_list(aggregate.get("tradeoff_metrics"))
    gates = {
        "minimum_task_count": {
            "required": minimum_task_count,
            "observed": task_count,
            "passed": task_count >= minimum_task_count,
        },
        "multiple_positive_task_families": {
            "required": minimum_positive_task_families,
            "observed": positive_count,
            "passed": positive_count >= minimum_positive_task_families,
        },
        "no_mixed_signal_tasks": {
            "required": 0,
            "observed": mixed_count,
            "passed": mixed_count == 0,
        },
        "no_regressed_task_families": {
            "required": 0,
            "observed": regressed_count,
            "passed": regressed_count == 0,
        },
    }
    if all(gate["passed"] for gate in gates.values()):
        claim_readiness = "bounded_cross_task_effectiveness_claim_review_ready"
    else:
        claim_readiness = "insufficient_evidence_for_cross_task_effectiveness_claim"
    allowed_claims = [
        "local_multi_task_signal_present",
        "failure_driven_proposal_effectiveness_bundles_reproducible",
    ]
    if positive_count > 0:
        allowed_claims.append("at_least_one_task_family_has_positive_local_signal")
    if mixed_count > 0:
        allowed_claims.append("mixed_signal_and_tradeoff_detection_present")
    blocked_claims = [
        "proposal_effectiveness_proven_cross_task",
        "proposal_is_validated_causal_driver_of_continuous_improvement",
        "proposal_effectiveness_generally_promotable_without_manual_review",
    ]
    gaps = []
    if not gates["multiple_positive_task_families"]["passed"]:
        gaps.append(
            "positive task families are fewer than the minimum needed for bounded cross-task claim review"
        )
    if not gates["no_mixed_signal_tasks"]["passed"]:
        gaps.append(
            "mixed-signal task families remain, so current evidence still contains unresolved tradeoffs"
        )
    if not gates["no_regressed_task_families"]["passed"]:
        gaps.append(
            "at least one task family is purely regressed, which blocks any stronger effectiveness claim"
        )
    payload = {
        "status": "completed",
        "schema_version": PROPOSAL_EFFECTIVENESS_CLAIM_AUDIT_SCHEMA_VERSION,
        "claim_readiness": claim_readiness,
        "evidence_snapshot": {
            "task_count": task_count,
            "task_families": task_families,
            "verdict_counts": verdict_counts,
            "consistent_improvements": consistent_improvements,
            "tradeoff_metrics": tradeoff_metrics,
        },
        "gates": gates,
        "allowed_claims": sorted(set(allowed_claims)),
        "blocked_claims": blocked_claims,
        "gaps": gaps,
        "recommended_next_actions": _proposal_effectiveness_claim_next_actions(
            gates=gates,
            mixed_count=mixed_count,
            regressed_count=regressed_count,
        ),
        "claim_boundary": (
            "proposal effectiveness claim audit only; this reviews local evidence sufficiency "
            "and does not prove generalization or official benchmark improvement"
        ),
        "executes_tool": False,
        "official_scores_claimed": False,
    }
    audit_path = output / "proposal-effectiveness-claim-audit.json"
    markdown_path = output / "proposal-effectiveness-claim-audit.md"
    audit_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_proposal_effectiveness_claim_audit_markdown(payload=payload, path=markdown_path)
    payload["audit_path"] = str(audit_path)
    payload["markdown_path"] = str(markdown_path)
    return payload


def build_mixed_signal_proposal_effectiveness_audit(
    *,
    effectiveness_reports: list[dict[str, Any] | str | Path],
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    reports = _load_effectiveness_reports(effectiveness_reports)
    output = Path(output_dir)
    if output.exists() and not overwrite:
        audit_file = output / "mixed-signal-audit.json"
        if audit_file.exists():
            raise FileExistsError(
                f"{output} already contains mixed-signal audit artifacts; pass overwrite=True to replace them"
            )
    output.mkdir(parents=True, exist_ok=True)
    audits = []
    for report in reports:
        audit = _mixed_signal_task_audit(report)
        if audit is not None:
            audits.append(audit)
    recommended_actions = sorted(
        {
            action
            for audit in audits
            for action in _string_list(audit.get("recommended_actions"))
        }
    )
    blocker_counts: dict[str, int] = {}
    for audit in audits:
        for blocker in _string_list(audit.get("blocking_signals")):
            blocker_counts[blocker] = blocker_counts.get(blocker, 0) + 1
    payload = {
        "status": "completed",
        "schema_version": MIXED_SIGNAL_EFFECTIVENESS_AUDIT_SCHEMA_VERSION,
        "mixed_signal_task_count": len(audits),
        "task_audits": audits,
        "aggregate": {
            "blocking_signal_counts": dict(sorted(blocker_counts.items())),
            "recommended_actions": recommended_actions,
        },
        "claim_boundary": (
            "mixed-signal local proposal effectiveness audit only; this diagnoses "
            "task-family tradeoffs and does not prove generalization"
        ),
        "executes_tool": False,
        "official_scores_claimed": False,
    }
    audit_path = output / "mixed-signal-audit.json"
    markdown_path = output / "mixed-signal-audit.md"
    audit_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_mixed_signal_effectiveness_markdown(payload=payload, path=markdown_path)
    payload["audit_path"] = str(audit_path)
    payload["markdown_path"] = str(markdown_path)
    return payload


def build_smol_worldcup_promotion_gate(
    *,
    dev_effectiveness_report: dict[str, Any] | str | Path,
    canary_effectiveness_report: dict[str, Any] | str | Path,
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    dev_report, _ = _load_object(dev_effectiveness_report)
    canary_report, _ = _load_object(canary_effectiveness_report)
    output = Path(output_dir)
    if output.exists() and not overwrite:
        gate_file = output / "smol-worldcup-promotion-gate.json"
        if gate_file.exists():
            raise FileExistsError(
                f"{output} already contains promotion gate artifacts; pass overwrite=True to replace them"
            )
    output.mkdir(parents=True, exist_ok=True)
    dev_gate = _smol_worldcup_gate_arm(report=dev_report, arm="dev")
    canary_gate = _smol_worldcup_gate_arm(report=canary_report, arm="canary")
    if dev_gate["passed"] and canary_gate["passed"]:
        status = "ready_for_prompt_profile_promotion"
        recommended_next_action = "review_and_promote_prompt_profile"
    elif not dev_gate["passed"]:
        status = "blocked_on_dev_signal"
        recommended_next_action = "build_smol_worldcup_result_analysis_before_prompt_changes"
    else:
        status = "blocked_on_canary_confirmation"
        recommended_next_action = "tighten_canary_gate_before_prompt_profile_promotion"
    payload = {
        "status": status,
        "schema_version": SMOL_WORLDCUP_PROMOTION_GATE_SCHEMA_VERSION,
        "dev_gate": dev_gate,
        "canary_gate": canary_gate,
        "promotion_ready": dev_gate["passed"] and canary_gate["passed"],
        "recommended_next_action": recommended_next_action,
        "claim_boundary": (
            "local Smol WorldCup promotion gate only; this decides whether a prompt-profile "
            "proposal is ready to move from dev evidence to canary-confirmed promotion"
        ),
        "executes_tool": False,
        "official_scores_claimed": False,
    }
    gate_path = output / "smol-worldcup-promotion-gate.json"
    markdown_path = output / "README.md"
    gate_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_smol_worldcup_promotion_gate_markdown(payload=payload, path=markdown_path)
    payload["gate_path"] = str(gate_path)
    payload["markdown_path"] = str(markdown_path)
    return payload


def build_smol_worldcup_canary_failure_slice_audit(
    *,
    canary_effectiveness_report: dict[str, Any] | str | Path,
    promotion_gate: dict[str, Any] | str | Path,
    control_outcomes: list[dict[str, Any]] | str | Path,
    treatment_outcomes: list[dict[str, Any]] | str | Path,
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    report, _ = _load_object(canary_effectiveness_report)
    gate, _ = _load_object(promotion_gate)
    control_items = _load_outcome_items(control_outcomes)
    treatment_items = _load_outcome_items(treatment_outcomes)
    output = Path(output_dir)
    if output.exists() and not overwrite:
        audit_file = output / "smol-worldcup-canary-failure-slice-audit.json"
        if audit_file.exists():
            raise FileExistsError(
                f"{output} already contains canary failure-slice audit artifacts; "
                "pass overwrite=True to replace them"
            )
    output.mkdir(parents=True, exist_ok=True)
    comparison = report.get("comparison") if isinstance(report.get("comparison"), dict) else {}
    canary_gate = gate.get("canary_gate") if isinstance(gate.get("canary_gate"), dict) else {}
    metric_lift = (
        comparison.get("avg_metric_delta_lift")
        if isinstance(comparison.get("avg_metric_delta_lift"), dict)
        else {}
    )
    observed_failure_labels = sorted(
        {
            label
            for item in treatment_items
            for label in _string_list(item.get("failure_labels"))
        }
    )
    rollback_reasons = sorted(
        {
            label
            for item in treatment_items
            for label in _string_list(item.get("rollback_reasons"))
        }
    )
    negative_metrics = sorted(
        str(metric_name)
        for metric_name, delta in metric_lift.items()
        if _is_plain_number(delta) and float(delta) < 0
    )
    failure_slice_label = _select_primary_failure_slice_label(observed_failure_labels)
    gate_status = _string_value(gate.get("status")) or "unknown"
    if gate_status == "blocked_on_canary_confirmation" and failure_slice_label:
        status = "failure_slice_control_arm_required"
        recommended_next_action = "add_failure_slice_specific_control_arm"
    elif gate_status == "ready_for_prompt_profile_promotion":
        status = "promotion_ready_without_extra_slice_audit"
        recommended_next_action = "review_and_promote_prompt_profile"
    else:
        status = "review_gate_before_slice_audit"
        recommended_next_action = "review_canary_gate"
    payload = {
        "status": status,
        "schema_version": SMOL_WORLDCUP_CANARY_FAILURE_SLICE_AUDIT_SCHEMA_VERSION,
        "gate_status": gate_status,
        "failure_slice_label": failure_slice_label,
        "observed_failure_labels": observed_failure_labels,
        "negative_metric_names": negative_metrics,
        "rollback_reasons": rollback_reasons,
        "control_outcome_ids": [
            _string_value(item.get("outcome_id")) or "unknown-control"
            for item in control_items
        ],
        "treatment_outcome_ids": [
            _string_value(item.get("outcome_id")) or "unknown-treatment"
            for item in treatment_items
        ],
        "canary_gate_blockers": _string_list(canary_gate.get("blockers")),
        "control_arm_spec": {
            "task_family": "smol_worldcup_prompt_routing",
            "evaluation_split": "canary",
            "failure_slice_label": failure_slice_label,
            "baseline_requirement": "matched_canary_negative_control",
            "comparison_requirement": "same_metric_family_and_split",
            "success_criteria": [
                "proposal_accept_rate_lift_gt_0",
                "rollback_rate_reduction_gte_0",
                "no_negative_metric_delta",
                "canary_gate_blockers_cleared",
            ],
            "promotion_rule": "do_not_promote_until_failure_slice_control_arm_passes",
        },
        "recommended_next_action": recommended_next_action,
        "claim_boundary": (
            "local Smol WorldCup canary failure-slice audit only; this specifies "
            "the next control-arm requirement and does not prove broader effectiveness"
        ),
        "executes_tool": False,
        "official_scores_claimed": False,
    }
    audit_path = output / "smol-worldcup-canary-failure-slice-audit.json"
    markdown_path = output / "README.md"
    audit_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_smol_worldcup_canary_failure_slice_audit_markdown(
        payload=payload,
        path=markdown_path,
    )
    payload["audit_path"] = str(audit_path)
    payload["markdown_path"] = str(markdown_path)
    return payload


def build_smol_worldcup_canary_control_arm_handoff(
    *,
    failure_slice_audit: dict[str, Any] | str | Path,
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    audit, _ = _load_object(failure_slice_audit)
    output = Path(output_dir)
    if output.exists() and not overwrite:
        handoff_file = output / "smol-worldcup-canary-control-arm-handoff.json"
        if handoff_file.exists():
            raise FileExistsError(
                f"{output} already contains canary control-arm handoff artifacts; "
                "pass overwrite=True to replace them"
            )
    output.mkdir(parents=True, exist_ok=True)
    failure_slice_label = _string_value(audit.get("failure_slice_label")) or "canary_not_confirmed"
    control_arm_spec = (
        audit.get("control_arm_spec") if isinstance(audit.get("control_arm_spec"), dict) else {}
    )
    evaluation_split = _string_value(control_arm_spec.get("evaluation_split")) or "canary"
    comparison_requirement = (
        _string_value(control_arm_spec.get("comparison_requirement"))
        or "same_metric_family_and_split"
    )
    promotion_rule = (
        _string_value(control_arm_spec.get("promotion_rule"))
        or "do_not_promote_until_failure_slice_control_arm_passes"
    )
    audit_artifact = (
        _string_value(audit.get("audit_path"))
        or "smol-worldcup-canary-failure-slice-audit"
    )
    proposal_id = (
        f"smol-worldcup-{evaluation_split}-control-arm-"
        f"{failure_slice_label.replace('_', '-')}"
    )
    proposal_template = {
        "proposal_id": proposal_id,
        "hypothesis": (
            f"If we run a matched {evaluation_split} control arm for {failure_slice_label}, "
            "we can isolate whether the current canary regression is caused by the "
            "prompt-profile treatment and only promote after the canary blockers clear."
        ),
        "evidence_used": [
            {
                "artifact": audit_artifact,
                "observation": (
                    f"The current {evaluation_split} gate is blocked on {failure_slice_label} "
                    "and the audit requires a matched control arm before promotion."
                ),
            }
        ],
        "based_on_failures": [failure_slice_label],
        "change_surface": "prompt_profile",
        "change_spec": {
            "single_primary_variable": True,
            "control_arm_kind": "matched_canary_negative_control",
            "failure_slice_label": failure_slice_label,
            "comparison_requirement": comparison_requirement,
            "promotion_rule": promotion_rule,
            "task_family": _string_value(control_arm_spec.get("task_family"))
            or "smol_worldcup_prompt_routing",
        },
        "expected_effect": {
            "primary_metric": "SHIFT",
            "expected_direction": "maximize",
            "secondary_metrics": ["I", "WCS_local_diagnostic"],
        },
        "validation_plan": {
            "first_split": evaluation_split,
            "promotion_split": evaluation_split,
            "rollback_if": ["canary_delta_lt_0", "canary_gate_blockers_present"],
            "max_rounds": 1,
        },
        "risk_assessment": {
            "primary": (
                "If the control arm is not matched to the same canary slice and metric family, "
                "the result will remain confounded."
            ),
            "rollback": (
                "Keep the prompt-profile proposal blocked if any canary blocker remains after "
                "the matched control-arm run."
            ),
        },
        "next_if_success": (
            "rebuild_smol_worldcup_promotion_gate_and_recheck_prompt_profile_promotion"
        ),
        "next_if_failure": (
            "keep_prompt_profile_blocked_and_narrow_the_canary_failure_slice_before_promotion"
        ),
        "claim_boundary": (
            "local Smol WorldCup canary control-arm handoff only; client must review "
            "before any execution"
        ),
        "official_scores_claimed": False,
    }
    validation_result = validate_client_proposal(proposal_template)
    accepted = validation_result.get("status") == "accepted"
    payload = {
        "status": "ready_for_client_review" if accepted else "template_needs_revision",
        "schema_version": SMOL_WORLDCUP_CANARY_CONTROL_ARM_HANDOFF_SCHEMA_VERSION,
        "failure_slice_label": failure_slice_label,
        "gate_status": _string_value(audit.get("gate_status")) or "unknown",
        "canary_gate_blockers": _string_list(audit.get("canary_gate_blockers")),
        "control_outcome_ids": _string_list(audit.get("control_outcome_ids")),
        "treatment_outcome_ids": _string_list(audit.get("treatment_outcome_ids")),
        "control_arm_spec": control_arm_spec,
        "proposal_template": proposal_template,
        "validation_result": validation_result,
        "recommended_next_step": {
            "mcp_tool": "validate_client_proposal_contract" if accepted else None,
            "human_action": (
                "review_and_run_matched_canary_control_arm"
                if accepted
                else "fix_control_arm_template_before_execution"
            ),
            "executes_tool": False,
        },
        "client_review_required": True,
        "claim_boundary": (
            "local Smol WorldCup canary control-arm handoff only; this prepares "
            "the next bounded proposal and does not prove effectiveness"
        ),
        "executes_tool": False,
        "official_scores_claimed": False,
    }
    handoff_path = output / "smol-worldcup-canary-control-arm-handoff.json"
    markdown_path = output / "README.md"
    handoff_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_smol_worldcup_canary_control_arm_handoff_markdown(
        payload=payload,
        path=markdown_path,
    )
    payload["handoff_path"] = str(handoff_path)
    payload["markdown_path"] = str(markdown_path)
    return payload


def build_smol_worldcup_canary_control_arm_execution_bundle(
    *,
    handoff: dict[str, Any] | str | Path,
    output_dir: str | Path,
    current_report: str | Path | None = None,
    baseline_report: str | Path | None = None,
    target_prompt_profile: str | None = None,
    evidence_root: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    handoff_payload, _ = _load_object(handoff)
    output = Path(output_dir)
    if output.exists() and not overwrite:
        proposal_file = output / "proposal.json"
        request_file = output / "execution-request.json"
        if proposal_file.exists() or request_file.exists():
            raise FileExistsError(
                f"{output} already contains execution bundle artifacts; "
                "pass overwrite=True to replace them"
            )
    output.mkdir(parents=True, exist_ok=True)
    proposal_template = (
        handoff_payload.get("proposal_template")
        if isinstance(handoff_payload.get("proposal_template"), dict)
        else {}
    )
    validation_result = (
        handoff_payload.get("validation_result")
        if isinstance(handoff_payload.get("validation_result"), dict)
        else {}
    )
    validation_status = _string_value(validation_result.get("status")) or "unknown"
    profile = target_prompt_profile or _infer_smol_prompt_profile_from_outcome_ids(
        _string_list(handoff_payload.get("control_outcome_ids"))
    )
    if profile is None:
        profile = "p3-dev-v2"
    source_model_hint = _infer_smol_model_hint_from_outcome_ids(
        _string_list(handoff_payload.get("control_outcome_ids"))
        + _string_list(handoff_payload.get("treatment_outcome_ids"))
    )
    proposal = dict(proposal_template)
    change_spec = (
        dict(proposal.get("change_spec"))
        if isinstance(proposal.get("change_spec"), dict)
        else {}
    )
    change_spec["target_file_or_profile"] = profile
    proposal["change_spec"] = change_spec
    validation_plan = (
        dict(proposal.get("validation_plan"))
        if isinstance(proposal.get("validation_plan"), dict)
        else {}
    )
    evaluation_split = _string_value(validation_plan.get("first_split")) or "canary"
    resolved_current_report = (
        Path(current_report).expanduser().resolve()
        if current_report is not None
        else _resolve_smol_worldcup_current_report(
            evidence_root=Path(evidence_root).expanduser().resolve()
            if evidence_root is not None
            else None,
            prompt_profile=profile,
            evaluation_split=evaluation_split,
            model_id=_string_value(source_model_hint.get("model")),
        )
    )
    runtime_config = _smol_runtime_config_from_report_or_hint(
        report_path=resolved_current_report,
        model_hint=source_model_hint,
    )
    execution_run_dir = output / "execution-run"
    execution_request = {
        "tool": "run_smol_worldcup_proposal_round",
        "proposal_file": str(output / "proposal.json"),
        "output_dir": str(execution_run_dir),
        "current_report": str(resolved_current_report) if resolved_current_report else None,
        "baseline_report": str(Path(baseline_report).expanduser().resolve())
        if baseline_report is not None
        else None,
        "prompt_profile": profile,
        "evaluation_split": evaluation_split,
        "model": runtime_config.get("model"),
        "base_url": runtime_config.get("base_url"),
        "model_provider": runtime_config.get("model_provider"),
        "judge_mode": runtime_config.get("judge_mode"),
        "judge_model": runtime_config.get("judge_model"),
        "judge_base_url": runtime_config.get("judge_base_url"),
        "model_size_billion": runtime_config.get("model_size_billion"),
        "estimated_ram_gb": runtime_config.get("estimated_ram_gb"),
        "official_scores_claimed": False,
    }
    recommended_command = [
        "ml-loop",
        "hf-eval",
        "smol-worldcup-proposal-round",
        "--proposal",
        str(output / "proposal.json"),
        "--output-dir",
        str(execution_run_dir),
        "--model",
        str(runtime_config.get("model") or "openai/gpt-oss-20b"),
        "--base-url",
        str(runtime_config.get("base_url") or "http://127.0.0.1:1234/v1"),
        "--model-provider",
        str(runtime_config.get("model_provider") or "openai-compatible"),
        "--prompt-profile",
        profile,
        "--evaluation-split",
        evaluation_split,
        "--judge-mode",
        str(runtime_config.get("judge_mode") or "heuristic"),
        "--model-size-billion",
        str(runtime_config.get("model_size_billion") or 20.0),
        "--estimated-ram-gb",
        str(runtime_config.get("estimated_ram_gb") or 32.0),
        "--json",
    ]
    judge_model = _string_value(runtime_config.get("judge_model"))
    if judge_model:
        recommended_command.extend(["--judge-model", judge_model])
    judge_base_url = _string_value(runtime_config.get("judge_base_url"))
    if judge_base_url:
        recommended_command.extend(["--judge-base-url", judge_base_url])
    if current_report is not None:
        recommended_command.extend(
            ["--current-report", str(Path(current_report).expanduser().resolve())]
        )
    elif resolved_current_report is not None:
        recommended_command.extend(["--current-report", str(resolved_current_report)])
    if baseline_report is not None:
        recommended_command.extend(
            ["--baseline-report", str(Path(baseline_report).expanduser().resolve())]
        )
    payload = {
        "status": (
            "ready_for_guarded_execution"
            if validation_status == "accepted"
            else "blocked_by_invalid_handoff_template"
        ),
        "schema_version": (
            SMOL_WORLDCUP_CANARY_CONTROL_ARM_EXECUTION_BUNDLE_SCHEMA_VERSION
        ),
        "failure_slice_label": _string_value(handoff_payload.get("failure_slice_label"))
        or "canary_not_confirmed",
        "target_prompt_profile": profile,
        "evaluation_split": evaluation_split,
        "proposal_validation_status": validation_status,
        "current_report_resolution": {
            "status": (
                "provided_explicitly"
                if current_report is not None
                else "resolved_from_evidence"
                if resolved_current_report is not None
                else "not_resolved"
            ),
            "path": str(resolved_current_report) if resolved_current_report else None,
        },
        "runtime_config": runtime_config,
        "recommended_command": recommended_command,
        "recommended_next_step": {
            "mcp_tool": (
                "run_smol_worldcup_proposal_round"
                if validation_status == "accepted"
                else None
            ),
            "human_action": (
                "review_and_run_guarded_smol_control_arm"
                if validation_status == "accepted"
                else "fix_handoff_before_execution"
            ),
            "executes_tool": False,
        },
        "claim_boundary": (
            "local Smol WorldCup canary control-arm execution bundle only; this "
            "prepares guarded execution inputs and does not itself run experiments"
        ),
        "executes_tool": False,
        "official_scores_claimed": False,
    }
    proposal_path = output / "proposal.json"
    request_path = output / "execution-request.json"
    readme_path = output / "README.md"
    manifest_path = output / "artifact-manifest.json"
    proposal_path.write_text(
        json.dumps(proposal, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    request_path.write_text(
        json.dumps(execution_request, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": (
            f"{SMOL_WORLDCUP_CANARY_CONTROL_ARM_EXECUTION_BUNDLE_SCHEMA_VERSION}.artifact-manifest"
        ),
        "status": payload["status"],
        "official_scores_claimed": False,
        "artifacts": {
            "proposal": str(proposal_path),
            "execution_request": str(request_path),
            "readme": str(readme_path),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_smol_worldcup_canary_control_arm_execution_bundle_markdown(
        payload=payload,
        path=readme_path,
    )
    payload["proposal_path"] = str(proposal_path)
    payload["execution_request_path"] = str(request_path)
    payload["artifact_manifest_path"] = str(manifest_path)
    payload["markdown_path"] = str(readme_path)
    return payload


def build_smol_worldcup_promotion_gate_refresh(
    *,
    previous_gate: dict[str, Any] | str | Path,
    proposal_round_summary: dict[str, Any] | str | Path,
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    previous_gate_payload, _ = _load_object(previous_gate)
    proposal_round_payload, _ = _load_object(proposal_round_summary)
    output = Path(output_dir)
    if output.exists() and not overwrite:
        refresh_file = output / "smol-worldcup-promotion-gate-refresh.json"
        if refresh_file.exists():
            raise FileExistsError(
                f"{output} already contains promotion gate refresh artifacts; "
                "pass overwrite=True to replace them"
            )
    output.mkdir(parents=True, exist_ok=True)
    previous_status = _string_value(previous_gate_payload.get("status")) or "unknown"
    dev_gate = (
        previous_gate_payload.get("dev_gate")
        if isinstance(previous_gate_payload.get("dev_gate"), dict)
        else {}
    )
    dev_passed = bool(dev_gate.get("passed"))
    proposal_round_status = _string_value(proposal_round_payload.get("status")) or "unknown"
    proposal_validation_status = (
        _string_value(proposal_round_payload.get("validation_status")) or "unknown"
    )
    evaluation = (
        proposal_round_payload.get("evaluation")
        if isinstance(proposal_round_payload.get("evaluation"), dict)
        else {}
    )
    canary_delta = (
        evaluation.get("canary_delta")
        if isinstance(evaluation.get("canary_delta"), dict)
        else {}
    )
    rollback_reasons = _string_list(evaluation.get("rollback_reasons"))
    negative_metrics = sorted(
        str(metric_name)
        for metric_name, delta in canary_delta.items()
        if _is_plain_number(delta) and float(delta) < 0
    )
    promotion_gate_passed = bool(evaluation.get("promotion_gate_passed"))
    canary_passed = (
        proposal_round_status == "completed"
        and proposal_validation_status == "accepted"
        and promotion_gate_passed
        and not rollback_reasons
        and not negative_metrics
    )
    if proposal_round_status != "completed" or proposal_validation_status != "accepted":
        status = "pending_valid_canary_round"
        promotion_ready = False
        recommended_next_action = "run_or_repeat_guarded_canary_round"
    elif canary_passed and dev_passed:
        status = "ready_for_prompt_profile_promotion"
        promotion_ready = True
        recommended_next_action = "review_and_promote_prompt_profile"
    elif not dev_passed:
        status = "blocked_on_dev_signal"
        promotion_ready = False
        recommended_next_action = "improve_dev_arm_before_any_promotion"
    else:
        status = "blocked_on_canary_confirmation"
        promotion_ready = False
        recommended_next_action = "keep_prompt_profile_blocked_and_revise_control_arm"
    canary_gate_refresh = {
        "passed": canary_passed,
        "selected_prompt_profile": _string_value(
            proposal_round_payload.get("selected_prompt_profile")
        ),
        "evaluation_split": _string_value(proposal_round_payload.get("evaluation_split"))
        or "canary",
        "canary_delta": canary_delta,
        "rollback_reasons": rollback_reasons,
        "negative_metrics": negative_metrics,
        "promotion_gate_passed": promotion_gate_passed,
        "reflection_status": _string_value(proposal_round_payload.get("reflection_status")),
        "claim_boundary": "local Smol WorldCup canary gate refresh only; not public proof",
        "official_scores_claimed": False,
    }
    payload = {
        "status": status,
        "schema_version": SMOL_WORLDCUP_PROMOTION_GATE_REFRESH_SCHEMA_VERSION,
        "promotion_ready": promotion_ready,
        "previous_gate_status": previous_status,
        "proposal_round_status": proposal_round_status,
        "proposal_validation_status": proposal_validation_status,
        "dev_gate_preserved": dev_passed,
        "canary_gate_refresh": canary_gate_refresh,
        "recommended_next_action": recommended_next_action,
        "claim_boundary": (
            "local Smol WorldCup promotion gate refresh only; this re-evaluates "
            "promotion readiness from one guarded proposal round and does not prove "
            "broader effectiveness"
        ),
        "executes_tool": False,
        "official_scores_claimed": False,
    }
    refresh_path = output / "smol-worldcup-promotion-gate-refresh.json"
    markdown_path = output / "README.md"
    refresh_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_smol_worldcup_promotion_gate_refresh_markdown(
        payload=payload,
        path=markdown_path,
    )
    payload["refresh_path"] = str(refresh_path)
    payload["markdown_path"] = str(markdown_path)
    return payload


def build_failure_driven_proposal_context(
    *,
    objective: str,
    failure_records: list[dict[str, Any]] | str | Path,
    pattern_memory: list[dict[str, Any]] | str | Path | None = None,
    output_path: str | Path | None = None,
    max_proposals: int = 3,
    overwrite: bool = False,
) -> dict[str, Any]:
    records = _load_failure_records(failure_records)
    patterns = _load_pattern_memory(pattern_memory)
    failure_type_counts = _failure_type_counts(records)
    matched_patterns = _matched_patterns(records, patterns)
    payload = {
        "status": "ready_for_failure_driven_proposals",
        "schema_version": FAILURE_DRIVEN_CONTEXT_SCHEMA_VERSION,
        "objective": objective,
        "max_proposals": max_proposals,
        "failure_summary": {
            "record_count": len(records),
            "top_failure_types": failure_type_counts,
            "records": records,
        },
        "pattern_summary": {
            "pattern_count": len(patterns),
            "matched_patterns": matched_patterns,
        },
        "ranking_rubric": {
            "formula": "expected_gain + pattern_prior - risk_penalty - redundancy_penalty",
            "score_components": [
                "expected_gain",
                "pattern_prior",
                "risk_penalty",
                "redundancy_penalty",
            ],
        },
        "planner_constraints": [
            "one primary change per proposal",
            "proposal must bind to observed failures",
            "proposal must include verification_plan and rollback_rule",
            "proposal does not claim official scores",
        ],
        "proposal_template": {
            "required_fields": [
                "proposal_id",
                "proposal_type",
                "based_on_failures",
                "intent",
                "change_surface",
                "target_scope",
                "verification_plan",
                "rollback_rule",
                "claim_boundary",
                "official_scores_claimed",
            ]
        },
        "prompt_markdown": _render_failure_driven_prompt(
            objective=objective,
            failure_type_counts=failure_type_counts,
            matched_patterns=matched_patterns,
            max_proposals=max_proposals,
        ),
        "executes_tool": False,
        "official_scores_claimed": False,
        "claim_boundary": "local proposal planning only; not public proof",
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        payload["output_path"] = str(output)
    return payload


def generate_failure_driven_proposals(
    *,
    context: dict[str, Any] | str | Path,
    output_path: str | Path | None = None,
    preferred_change_surfaces: list[str] | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    context_payload, _ = _load_object(context)
    failure_records = _context_failure_records(context_payload)
    patterns = _context_matched_patterns(context_payload)
    max_proposals = _context_max_proposals(context_payload)
    proposals: list[dict[str, Any]] = []
    pattern_index = _patterns_by_failure_type(patterns)
    for index, group in enumerate(
        _group_failure_records_by_type(failure_records)[:max_proposals],
        start=1,
    ):
        failure_type = group["failure_type"]
        source_records = group["records"]
        matched_pattern = _best_pattern_for_failure(pattern_index, failure_type)
        proposal_type = _proposal_type_for_failure_group(
            failure_type=failure_type,
            repeated_count=len(source_records),
            matched_pattern=matched_pattern,
        )
        change_surface = _proposal_change_surface(
            failure_type=failure_type,
            records=source_records,
            preferred_change_surfaces=preferred_change_surfaces,
        )
        proposal_id = f"fdp-{index:02d}-{failure_type}"
        intent = _proposal_intent(
            failure_type=failure_type,
            change_surface=change_surface,
            repeated_count=len(source_records),
            records=source_records,
        )
        target_scope = _proposal_target_scope(
            source_records,
            change_surface=change_surface,
            failure_type=failure_type,
        )
        proposal = {
            "schema_version": "2026-06-02.proposal-card.v1",
            "proposal_id": proposal_id,
            "proposal_type": proposal_type,
            "based_on_failures": [item["failure_id"] for item in source_records],
            "intent": intent,
            "change_surface": change_surface,
            "target_scope": target_scope,
            "expected_gain": {
                "score": _proposal_expected_gain(matched_pattern, failure_type=failure_type)
            },
            "risk_level": _proposal_risk_level(source_records),
            "verification_plan": _proposal_verification_plan(
                failure_type=failure_type,
                records=source_records,
            ),
            "rollback_rule": _proposal_rollback_rule(failure_type=failure_type),
            "planner_rationale": _proposal_rationale(
                failure_type=failure_type,
                source_records=source_records,
                matched_pattern=matched_pattern,
            ),
            "claim_boundary": (
                "failure-driven proposal draft only; client must review before ranking "
                "or execution"
            ),
            "official_scores_claimed": False,
        }
        proposals.append(proposal)
    payload = {
        "status": "completed" if proposals else "needs_failure_records",
        "schema_version": FAILURE_DRIVEN_GENERATION_SCHEMA_VERSION,
        "objective": context_payload.get("objective"),
        "proposal_count": len(proposals),
        "proposals": proposals,
        "generation_strategy": {
            "source": "failure_driven_context_wrapper",
            "max_proposals": max_proposals,
            "preferred_change_surfaces": preferred_change_surfaces or [],
            "matched_pattern_count": len(patterns),
            "client_review_required": True,
        },
        "prompt_markdown": context_payload.get("prompt_markdown"),
        "recommended_next_step": {
            "mcp_tool": "rank_failure_driven_proposals" if proposals else None,
            "human_action": (
                "review_generated_failure_driven_proposals"
                if proposals
                else "add_failure_records_or_context"
            ),
            "executes_tool": False,
        },
        "claim_boundary": (
            "generated proposal drafts only; not autonomous planning or public proof"
        ),
        "executes_tool": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def rank_failure_driven_proposals(
    *,
    proposals: list[dict[str, Any]] | str | Path,
    failure_records: list[dict[str, Any]] | str | Path,
    pattern_memory: list[dict[str, Any]] | str | Path | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    proposal_items = _load_proposals(proposals)
    records = _load_failure_records(failure_records)
    patterns = _load_pattern_memory(pattern_memory)
    failure_index = _failure_index(records)
    redundancy_counts: dict[str, int] = {}
    ranked: list[dict[str, Any]] = []
    for proposal in proposal_items:
        based_on = _string_list(proposal.get("based_on_failures"))
        signature = _proposal_signature(proposal)
        redundancy_counts[signature] = redundancy_counts.get(signature, 0) + 1
        breakdown = _score_breakdown(
            proposal=proposal,
            based_on_failures=based_on,
            failure_index=failure_index,
            patterns=patterns,
            redundancy_count=redundancy_counts[signature],
        )
        ranked.append(
            {
                "proposal_id": _string_value(proposal.get("proposal_id")) or "unknown-proposal",
                "proposal_type": _string_value(proposal.get("proposal_type")) or "failure_fix",
                "based_on_failures": based_on,
                "intent": _string_value(proposal.get("intent")),
                "change_surface": _string_value(proposal.get("change_surface")),
                "target_scope": _string_value(proposal.get("target_scope")),
                "risk_level": _string_value(proposal.get("risk_level")),
                "verification_plan": (
                    dict(proposal.get("verification_plan"))
                    if isinstance(proposal.get("verification_plan"), dict)
                    else {}
                ),
                "rollback_rule": (
                    dict(proposal.get("rollback_rule"))
                    if isinstance(proposal.get("rollback_rule"), dict)
                    else {}
                ),
                "score": round(
                    breakdown["expected_gain"]
                    + breakdown["pattern_prior"]
                    - breakdown["risk_penalty"]
                    - breakdown["redundancy_penalty"],
                    4,
                ),
                "score_breakdown": breakdown,
                "gate_labels": _gate_labels(proposal, based_on, failure_index),
                "claim_boundary": "local ranking only; not public proof",
                "official_scores_claimed": False,
            }
        )
    ranked.sort(
        key=lambda item: (
            len(item["gate_labels"]) > 0,
            -float(item["score"]),
            str(item["proposal_id"]),
        )
    )
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
    payload = {
        "status": "completed",
        "schema_version": FAILURE_DRIVEN_RANKING_SCHEMA_VERSION,
        "ranked_proposals": ranked,
        "executes_tool": False,
        "official_scores_claimed": False,
        "claim_boundary": "local ranking only; not public proof",
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        payload["output_path"] = str(output)
    return payload


def build_failure_driven_proposal_handoff(
    *,
    context: dict[str, Any] | str | Path,
    ranking: dict[str, Any] | str | Path,
    output_dir: str | Path,
    max_selected: int = 1,
    overwrite: bool = False,
) -> dict[str, Any]:
    context_payload, _ = _load_object(context)
    ranking_payload, _ = _load_object(ranking)
    output = Path(output_dir)
    if output.exists() and not overwrite:
        proposal_file = output / "failure-driven-proposal-handoff.json"
        markdown_file = output / "failure-driven-proposal-handoff.md"
        if proposal_file.exists() or markdown_file.exists():
            raise FileExistsError(
                f"{output} already contains handoff artifacts; pass overwrite=True to replace them"
            )
    output.mkdir(parents=True, exist_ok=True)
    ranked_proposals = [
        item
        for item in ranking_payload.get("ranked_proposals", [])
        if isinstance(item, dict)
    ]
    selectable = [
        item
        for item in ranked_proposals
        if not item.get("gate_labels")
    ]
    selected = [
        {
            "proposal_id": item.get("proposal_id"),
            "proposal_type": item.get("proposal_type"),
            "rank": item.get("rank"),
            "score": item.get("score"),
            "based_on_failures": list(item.get("based_on_failures", [])),
            "intent": _string_value(item.get("intent")),
            "change_surface": _string_value(item.get("change_surface")),
            "target_scope": _string_value(item.get("target_scope")),
            "risk_level": _string_value(item.get("risk_level")),
            "verification_plan": (
                dict(item.get("verification_plan"))
                if isinstance(item.get("verification_plan"), dict)
                else {}
            ),
            "rollback_rule": (
                dict(item.get("rollback_rule"))
                if isinstance(item.get("rollback_rule"), dict)
                else {}
            ),
            "score_breakdown": dict(item.get("score_breakdown", {})),
            "requires_client_review": True,
            "executes_tool": False,
        }
        for item in selectable[:max_selected]
    ]
    memory_bridge = [
        {
            "proposal_id": item["proposal_id"],
            "future_memory_type": "patch_or_failure",
            "source_failure_ids": list(item.get("based_on_failures", [])),
            "source_pattern_ids": _source_pattern_ids(
                item.get("score_breakdown", {}),
                context_payload=context_payload,
            ),
            "record_after": "proposal_outcome_available",
            "claim_boundary": "bridge plan only; not a memory record",
        }
        for item in selected
    ]
    recommended_next_step = {
        "mcp_tool": "validate_client_proposal_contract" if selected else None,
        "human_action": (
            "review_selected_failure_driven_proposals"
            if selected
            else "generate_or_rank_additional_failure_driven_proposals"
        ),
        "executes_tool": False,
    }
    proposal_file = output / "failure-driven-proposal-handoff.json"
    markdown_file = output / "failure-driven-proposal-handoff.md"
    payload = {
        "status": "completed" if selected else "needs_more_proposals",
        "schema_version": FAILURE_DRIVEN_HANDOFF_SCHEMA_VERSION,
        "objective": context_payload.get("objective"),
        "selected_next_proposals": selected,
        "recommended_next_step": recommended_next_step,
        "memory_bridge": memory_bridge,
        "failure_summary": context_payload.get("failure_summary", {}),
        "pattern_summary": context_payload.get("pattern_summary", {}),
        "claim_boundary": (
            "failure-driven proposal handoff only; client must review before "
            "any MCP execution or memory recording"
        ),
        "executes_tool": False,
        "official_scores_claimed": False,
        "proposal_file": str(proposal_file),
        "markdown_file": str(markdown_file),
    }
    proposal_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_failure_handoff_markdown(payload, markdown_file)
    return payload


def build_failure_driven_client_proposal_templates(
    *,
    handoff: dict[str, Any] | str | Path,
    output_dir: str | Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    handoff_payload, _ = _load_object(handoff)
    output = Path(output_dir)
    if output.exists() and not overwrite:
        proposal_file = output / "failure-driven-client-proposal-templates.json"
        markdown_file = output / "failure-driven-client-proposal-templates.md"
        if proposal_file.exists() or markdown_file.exists():
            raise FileExistsError(
                f"{output} already contains template artifacts; pass overwrite=True to replace them"
            )
    output.mkdir(parents=True, exist_ok=True)
    selected = handoff_payload.get("selected_next_proposals", [])
    templates = [
        _client_template_from_selected(
            selected_item=selected_item,
            failure_records=_handoff_failure_records(handoff_payload),
        )
        for selected_item in selected
        if isinstance(selected_item, dict)
    ]
    payload = {
        "status": "completed" if templates else "needs_selected_proposals",
        "schema_version": FAILURE_DRIVEN_TEMPLATE_SCHEMA_VERSION,
        "objective": handoff_payload.get("objective"),
        "proposal_templates": templates,
        "validation_results": [
            validate_client_proposal(template) for template in templates
        ],
        "recommended_next_step": {
            "mcp_tool": "validate_client_proposal_contract" if templates else None,
            "human_action": (
                "review_and_finalize_client_proposal_templates"
                if templates
                else "build_or_rank_failure_driven_proposals"
            ),
            "executes_tool": False,
        },
        "claim_boundary": (
            "client proposal templates only; client must review before "
            "any MCP execution"
        ),
        "executes_tool": False,
        "official_scores_claimed": False,
    }
    proposal_file = output / "failure-driven-client-proposal-templates.json"
    markdown_file = output / "failure-driven-client-proposal-templates.md"
    proposal_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_client_templates_markdown(payload, markdown_file)
    payload["proposal_file"] = str(proposal_file)
    payload["markdown_file"] = str(markdown_file)
    return payload


def bridge_failure_driven_outcome_to_memory_card(
    *,
    outcome: dict[str, Any] | str | Path,
    handoff: dict[str, Any] | str | Path | None = None,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    outcome_payload, outcome_source = _load_object(outcome)
    handoff_payload = _load_optional_object(handoff)
    proposal_id = _string_value(outcome_payload.get("proposal_id")) or "unknown-proposal"
    artifact_path = _memory_bridge_artifact_path(outcome_payload, source_path=outcome_source)
    if artifact_path is None:
        raise ValueError("proposal outcome bridge requires an existing outcome artifact path")
    selected_lookup = _handoff_selected_lookup(handoff_payload)
    selected = selected_lookup.get(proposal_id, {})
    failure_lookup = _handoff_failure_lookup(handoff_payload)
    based_on_failures = _string_list(outcome_payload.get("based_on_failures")) or _string_list(
        selected.get("based_on_failures")
    )
    failure_category = _bridge_failure_category(
        outcome_payload=outcome_payload,
        based_on_failures=based_on_failures,
        failure_lookup=failure_lookup,
    )
    change_surface = (
        _string_value(outcome_payload.get("change_surface"))
        or _string_value(selected.get("change_surface"))
        or "unknown"
    )
    target_scope = _string_value(outcome_payload.get("target_scope")) or _string_value(
        selected.get("target_scope")
    )
    metric_delta = outcome_payload.get("metric_delta")
    summary = _bridge_summary(
        proposal_id=proposal_id,
        accepted=bool(outcome_payload.get("accepted")),
        change_surface=change_surface,
        failure_category=failure_category,
        metric_delta=metric_delta if isinstance(metric_delta, dict) else {},
    )
    card = ResearchMemoryCard(
        card_id=f"failure-driven-{proposal_id}",
        memory_type="patch" if outcome_payload.get("accepted") is True else "failure",
        task_family="failure-driven-proposal",
        summary=summary,
        patch_type=change_surface,
        failure_category=failure_category,
        config={
            "proposal_id": proposal_id,
            "proposal_type": _string_value(outcome_payload.get("proposal_type")) or "failure_fix",
            "based_on_failures": based_on_failures,
            "target_scope": target_scope,
            "metric_delta": metric_delta if isinstance(metric_delta, dict) else {},
            "objective": handoff_payload.get("objective") if handoff_payload else None,
            "selected_rank": selected.get("rank"),
        },
        evidence_refs=[
            MemoryEvidenceRef(
                source_id=f"failure_driven_outcome:{proposal_id}",
                artifact_path=str(artifact_path),
                quote=_string_value(outcome_payload.get("outcome_summary")) or summary,
                strength="proposal_outcome",
            )
        ],
        artifact_refs=[
            MemoryArtifactRef.from_path(
                "failure_driven_outcome",
                artifact_path,
                artifact_type="proposal_outcome",
            )
        ],
        claim_boundary=(
            "local failure-driven proposal memory candidate only; "
            "not public proof; review before recording"
        ),
        official_scores_claimed=False,
        tags=[
            "failure-driven-proposal",
            change_surface,
            _string_value(outcome_payload.get("proposal_type")) or "failure_fix",
            failure_category or "no-failure-category",
        ],
    )
    payload = {
        "status": "completed",
        "schema_version": FAILURE_DRIVEN_MEMORY_BRIDGE_SCHEMA_VERSION,
        "memory_card_candidate": card.to_dict(),
        "review_required": True,
        "recommended_next_step": {
            "mcp_tool": "record_research_memory",
            "human_action": "review_memory_card_candidate_before_recording",
            "executes_tool": False,
        },
        "claim_boundary": (
            "memory bridge candidate only; does not record into the memory store automatically"
        ),
        "executes_tool": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def evaluate_failure_driven_proposal_effectiveness(
    *,
    control_outcomes: list[dict[str, Any]] | str | Path,
    treatment_outcomes: list[dict[str, Any]] | str | Path,
    output_path: str | Path | None = None,
    control_label: str = "without_failure_driven_context",
    treatment_label: str = "with_failure_driven_context",
    overwrite: bool = False,
) -> dict[str, Any]:
    control_items = _load_outcome_items(control_outcomes)
    treatment_items = _load_outcome_items(treatment_outcomes)
    control_summary = _effectiveness_arm_summary(control_items, label=control_label)
    treatment_summary = _effectiveness_arm_summary(treatment_items, label=treatment_label)
    payload = {
        "status": "completed",
        "schema_version": PROPOSAL_EFFECTIVENESS_SCHEMA_VERSION,
        "control_summary": control_summary,
        "treatment_summary": treatment_summary,
        "comparison": _effectiveness_comparison(
            control_summary=control_summary,
            treatment_summary=treatment_summary,
        ),
        "recommended_next_step": {
            "human_action": "review_effectiveness_report_before_claiming_proposal_value",
            "executes_tool": False,
        },
        "claim_boundary": (
            "local proposal effectiveness comparison only; not proof of generalization "
            "or public benchmark improvement"
        ),
        "executes_tool": False,
        "official_scores_claimed": False,
    }
    if output_path is not None:
        output = Path(output_path)
        _ensure_writable(output, overwrite=overwrite)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        payload["output_path"] = str(output)
    return payload


def _extract_failure_records_from_payload(
    payload: dict[str, Any],
    *,
    source_path: Path | None,
) -> list[dict[str, Any]]:
    proposal = payload.get("proposal") if isinstance(payload.get("proposal"), dict) else {}
    proposal_id = (
        _string_value(payload.get("proposal_id"))
        or _string_value(proposal.get("proposal_id"))
        or "unknown-proposal"
    )
    failure_labels = _failure_labels_from_payload(payload)
    if not failure_labels:
        return []
    evaluation = payload.get("evaluation") if isinstance(payload.get("evaluation"), dict) else {}
    metric_before = _metric_map(evaluation.get("metric_before"))
    metric_after = _metric_map(evaluation.get("metric_after"))
    if not metric_after and _metric_delta_map(evaluation):
        metric_after = _metric_delta_map(evaluation)
    bad_cases = _failure_bad_cases(evaluation=evaluation)
    rollback_action = (
        _string_value(payload.get("recommended_next_action"))
        or _string_value(payload.get("rollback_reason"))
        or (_string_list(evaluation.get("rollback_reasons")) or [None])[0]
    )
    root_cause = _string_value(payload.get("root_cause_hypothesis")) or _string_value(
        proposal.get("hypothesis")
    )
    scope = _string_value(proposal.get("change_surface")) or _string_value(payload.get("scope"))

    records: list[dict[str, Any]] = []
    for index, label in enumerate(failure_labels, start=1):
        records.append(
            {
                "schema_version": FAILURE_RECORD_SCHEMA_VERSION,
                "failure_id": f"{proposal_id}:{label}:{index}",
                "task_id": proposal_id,
                "artifact_ref": str(source_path) if source_path is not None else None,
                "failure_type": _normalize_failure_type(label),
                "symptom": _failure_symptom(label, payload=payload, evaluation=evaluation),
                "scope": scope,
                "severity": _severity_for_failure(label),
                "metric_before": metric_before,
                "metric_after": metric_after,
                "bad_cases": bad_cases,
                "rollback_action": rollback_action,
                "root_cause_hypothesis": root_cause,
                "claim_boundary": "local failure record only; not public proof",
                "official_scores_claimed": False,
            }
        )
    return records


def _failure_bad_cases(*, evaluation: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(evaluation.get("bad_cases"), list):
        return [item for item in evaluation.get("bad_cases", []) if isinstance(item, dict)]
    failure_cases_path = _string_value(evaluation.get("failure_cases_path"))
    if not failure_cases_path:
        return []
    path = Path(failure_cases_path).expanduser()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, dict):
        payload = payload.get("failure_cases")
    if not isinstance(payload, list):
        return []
    category_counts: dict[str, int] = {}
    category_examples: dict[str, list[str]] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        category = _string_value(item.get("category"))
        if not category:
            continue
        category_counts[category] = category_counts.get(category, 0) + 1
        subcategory = _string_value(item.get("subcategory"))
        if subcategory:
            examples = category_examples.setdefault(category, [])
            if subcategory not in examples and len(examples) < 3:
                examples.append(subcategory)
    ranked = sorted(category_counts.items(), key=lambda entry: (-entry[1], entry[0]))
    return [
        {
            "category": category,
            "count": count,
            "subcategory_examples": category_examples.get(category, []),
        }
        for category, count in ranked
    ]


def _pattern_from_group(
    *,
    proposal_type: str,
    failure_types: list[str],
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    total = len(items)
    accepted_count = sum(1 for item in items if item.get("accepted") is True)
    avg_delta = _average_metric_delta(items)
    task_family = _most_common_string(item.get("task_family") for item in items)
    risks = sorted(
        {
            *(label for item in items for label in _string_list(item.get("failure_labels"))),
            *(reason for item in items for reason in _string_list(item.get("rollback_reasons"))),
        }
    )
    example_proposals = [
        proposal_id
        for proposal_id in (_string_value(item.get("proposal_id")) for item in items[:3])
        if proposal_id
    ]
    evidence_refs = [
        {
            "outcome_id": item.get("outcome_id"),
            "artifact_refs": item.get("artifact_refs", []),
        }
        for item in items[:3]
    ]
    return {
        "schema_version": PROPOSAL_PATTERN_MEMORY_SCHEMA_VERSION,
        "pattern_id": f"{proposal_type}::{'+'.join(failure_types)}",
        "pattern_summary": (
            f"{proposal_type} against {', '.join(failure_types)} "
            f"across {total} recorded proposal outcomes."
        ),
        "proposal_type": proposal_type,
        "applicable_when": failure_types,
        "task_family": task_family,
        "metric_names": sorted(avg_delta),
        "historical_success_rate": round(accepted_count / total, 4) if total else 0.0,
        "historical_failure_rate": round((total - accepted_count) / total, 4) if total else 0.0,
        "avg_delta": avg_delta,
        "typical_risks": risks,
        "example_proposals": example_proposals,
        "evidence_refs": evidence_refs,
        "claim_boundary": "local proposal pattern memory only; not public proof",
        "official_scores_claimed": False,
    }


def _average_metric_delta(items: list[dict[str, Any]]) -> dict[str, float]:
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for item in items:
        deltas = item.get("metric_delta")
        if not isinstance(deltas, dict):
            continue
        for key, value in deltas.items():
            if _is_plain_number(value):
                sums[str(key)] = sums.get(str(key), 0.0) + float(value)
                counts[str(key)] = counts.get(str(key), 0) + 1
    return {
        key: round(sums[key] / counts[key], 4)
        for key in sorted(sums)
        if counts.get(key)
    }


def _pattern_match(
    *,
    pattern: dict[str, Any],
    query: dict[str, str | None],
) -> dict[str, Any] | None:
    reasons: list[str] = []
    score = 0.0
    failure_type = query.get("failure_type")
    if failure_type:
        applicable = set(_string_list(pattern.get("applicable_when")))
        if failure_type not in applicable:
            return None
        reasons.append(f"failure_type={failure_type}")
        score += 2.0
    proposal_type = query.get("proposal_type")
    if proposal_type:
        current = _string_value(pattern.get("proposal_type"))
        if current != proposal_type:
            return None
        reasons.append(f"proposal_type={proposal_type}")
        score += 1.5
    task_family = query.get("task_family")
    if task_family:
        current = _string_value(pattern.get("task_family"))
        if current != task_family:
            return None
        reasons.append(f"task_family={task_family}")
        score += 1.0
    metric_name = query.get("metric_name")
    if metric_name:
        metric_names = set(_string_list(pattern.get("metric_names")))
        if metric_name not in metric_names:
            return None
        reasons.append(f"metric_name={metric_name}")
        score += 1.0
    if not reasons:
        reasons.append("no_query_filters")
    score += float(pattern.get("historical_success_rate", 0.0))
    score -= float(pattern.get("historical_failure_rate", 0.0)) * 0.25
    return {
        "pattern": pattern,
        "score": round(score, 4),
        "match_reasons": reasons,
    }


def _most_common_string(values: Any) -> str | None:
    counts: dict[str, int] = {}
    for value in values:
        if isinstance(value, str) and value:
            counts[value] = counts.get(value, 0) + 1
    if not counts:
        return None
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _load_cp_bench_round_reports(
    reports: list[dict[str, Any] | str | Path],
) -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = []
    for item in reports:
        if isinstance(item, dict):
            loaded.append(item)
            continue
        payload, _ = _load_object(item)
        loaded.append(payload)
    return loaded


def _load_fasttext_multi_round_reports(
    reports: list[dict[str, Any] | str | Path],
) -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = []
    for item in reports:
        if isinstance(item, dict):
            loaded.append(item)
            continue
        payload, _ = _load_object(item)
        loaded.append(payload)
    return loaded


def _load_smol_worldcup_reports(
    reports: list[dict[str, Any] | str | Path],
) -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = []
    for item in reports:
        if isinstance(item, dict):
            loaded.append(item)
            continue
        payload, _ = _load_object(item)
        loaded.append(payload)
    return loaded


def _load_real_paper_proof_archives(
    reports: list[dict[str, Any] | str | Path],
) -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = []
    for item in reports:
        if isinstance(item, dict):
            loaded.append(item)
            continue
        payload, _ = _load_object(item)
        loaded.append(payload)
    return loaded


def _load_effectiveness_reports(
    reports: list[dict[str, Any] | str | Path],
) -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = []
    for item in reports:
        if isinstance(item, dict):
            loaded.append(item)
            continue
        payload, _ = _load_object(item)
        loaded.append(payload)
    return loaded


def _flatten_fasttext_control_outcomes(
    reports: list[dict[str, Any]],
    *,
    include_failed_rounds: bool,
) -> list[dict[str, Any]]:
    outcomes: list[dict[str, Any]] = []
    for report in reports:
        for round_payload in _fasttext_rounds(report, include_failed_rounds=include_failed_rounds):
            outcomes.append(_fasttext_control_outcome(report=report, round_payload=round_payload))
    return outcomes


def _flatten_fasttext_treatment_outcomes(
    reports: list[dict[str, Any]],
    *,
    include_failed_rounds: bool,
) -> list[dict[str, Any]]:
    outcomes: list[dict[str, Any]] = []
    for report in reports:
        for round_payload in _fasttext_rounds(report, include_failed_rounds=include_failed_rounds):
            outcomes.append(_fasttext_treatment_outcome(report=report, round_payload=round_payload))
    return outcomes


def _fasttext_rounds(
    report: dict[str, Any],
    *,
    include_failed_rounds: bool,
) -> list[dict[str, Any]]:
    rounds = report.get("rounds")
    if not isinstance(rounds, list):
        return []
    items = [item for item in rounds if isinstance(item, dict)]
    if include_failed_rounds:
        return items
    return [
        item
        for item in items
        if (_string_value(item.get("status")) or "").lower() == "completed"
    ]


def _fasttext_control_outcome(
    *,
    report: dict[str, Any],
    round_payload: dict[str, Any],
) -> dict[str, Any]:
    proposal_id = _string_value(round_payload.get("proposal_id")) or "fasttext-control"
    return {
        "schema_version": PROPOSAL_OUTCOME_SCHEMA_VERSION,
        "outcome_id": f"{proposal_id}-control",
        "proposal_id": f"{proposal_id}-control",
        "proposal_type": "baseline_negative_control",
        "task_family": "text_classification",
        "based_on_failures": [],
        "change_surface": "baseline_negative_control",
        "target_scope": "fastText AG News bounded baseline",
        "executed": True,
        "accepted": False,
        "metric_delta": {"p_at_1": 0.0},
        "regression": False,
        "rollback_triggered": False,
        "rollback_reasons": [],
        "failure_labels": ["no_improvement"],
        "outcome_summary": (
            f"Baseline negative control for {proposal_id}; no failure-driven proposal applied."
        ),
        "artifact_refs": [],
        "claim_boundary": "local fastText baseline negative control only; not public proof",
        "official_scores_claimed": False,
    }


def _fasttext_treatment_outcome(
    *,
    report: dict[str, Any],
    round_payload: dict[str, Any],
) -> dict[str, Any]:
    proposal_id = _string_value(round_payload.get("proposal_id")) or "fasttext-proposal"
    delta = _fasttext_metric_delta(round_payload)
    status = _string_value(round_payload.get("status")) or "unknown"
    rollback_action = _string_value(round_payload.get("rollback_action"))
    failure_labels = _fasttext_failure_labels(round_payload)
    accepted = bool(round_payload.get("improved_best")) or any(value > 0 for value in delta.values())
    rollback_triggered = status == "failed" or rollback_action == "keep_best_so_far"
    return {
        "schema_version": PROPOSAL_OUTCOME_SCHEMA_VERSION,
        "outcome_id": f"{proposal_id}-treatment",
        "proposal_id": proposal_id,
        "proposal_type": "hyperparameter_patch",
        "task_family": "text_classification",
        "based_on_failures": failure_labels,
        "change_surface": "training_recipe",
        "target_scope": "fastText AG News bounded proposal round",
        "executed": True,
        "accepted": accepted,
        "metric_delta": delta,
        "regression": any(value < 0 for value in delta.values()),
        "rollback_triggered": rollback_triggered,
        "rollback_reasons": [rollback_action or status] if rollback_triggered else [],
        "failure_labels": failure_labels,
        "outcome_summary": (
            f"fastText proposal round {proposal_id} status={status}; metric_delta={delta}."
        ),
        "artifact_refs": [],
        "claim_boundary": "local fastText proposal round only; not public proof",
        "official_scores_claimed": False,
    }


def _fasttext_metric_delta(round_payload: dict[str, Any]) -> dict[str, float]:
    delta = round_payload.get("delta_vs_baseline")
    if _is_plain_number(delta):
        return {"p_at_1": round(float(delta), 4)}
    return {"p_at_1": 0.0}


def _fasttext_failure_labels(round_payload: dict[str, Any]) -> list[str]:
    status = _string_value(round_payload.get("status"))
    if status == "failed":
        error = (_string_value(round_payload.get("error")) or "").lower()
        if "unsupported" in error or "allow" in error:
            return ["invalid_patch"]
        return ["runtime_error"]
    delta = round_payload.get("delta_vs_baseline")
    if _is_plain_number(delta) and float(delta) <= 0:
        return ["no_improvement"]
    return []


def _cp_bench_control_outcome(report: dict[str, Any]) -> dict[str, Any]:
    proposal_id = _cp_bench_proposal_id(report)
    return {
        "schema_version": PROPOSAL_OUTCOME_SCHEMA_VERSION,
        "outcome_id": f"{proposal_id}-control",
        "proposal_id": f"{proposal_id}-control",
        "proposal_type": "baseline_negative_control",
        "task_family": "constraint_model_generation",
        "based_on_failures": [],
        "change_surface": "baseline_negative_control",
        "target_scope": _cp_bench_target_scope(report),
        "executed": True,
        "accepted": False,
        "metric_delta": _cp_bench_zero_delta(report),
        "regression": False,
        "rollback_triggered": False,
        "rollback_reasons": [],
        "failure_labels": ["no_improvement"],
        "outcome_summary": (
            f"Baseline negative control for {proposal_id}; no failure-driven proposal applied."
        ),
        "artifact_refs": [],
        "claim_boundary": "local baseline negative control only; not public proof",
        "official_scores_claimed": False,
    }


def _cp_bench_treatment_outcome(report: dict[str, Any]) -> dict[str, Any]:
    proposal_id = _cp_bench_proposal_id(report)
    delta = _cp_bench_metric_delta(report)
    status = _string_value(report.get("status")) or "unknown"
    failure_labels = _cp_bench_failure_labels(report)
    accepted = status == "improved" or any(value > 0 for value in delta.values())
    rollback_triggered = status in {"regressed", "failed", "rolled_back"}
    return {
        "schema_version": PROPOSAL_OUTCOME_SCHEMA_VERSION,
        "outcome_id": f"{proposal_id}-treatment",
        "proposal_id": proposal_id,
        "proposal_type": _cp_bench_proposal_type(report),
        "task_family": "constraint_model_generation",
        "based_on_failures": failure_labels,
        "change_surface": _cp_bench_change_surface(report),
        "target_scope": _cp_bench_target_scope(report),
        "executed": True,
        "accepted": accepted,
        "metric_delta": delta,
        "regression": any(value < 0 for value in delta.values()),
        "rollback_triggered": rollback_triggered,
        "rollback_reasons": [status] if rollback_triggered else [],
        "failure_labels": failure_labels,
        "outcome_summary": (
            f"CP-Bench candidate round {proposal_id} status={status}; metric_delta={delta}."
        ),
        "artifact_refs": [],
        "claim_boundary": "local CP-Bench candidate round only; not public proof",
        "official_scores_claimed": False,
    }


def _cp_bench_proposal_id(report: dict[str, Any]) -> str:
    proposal = report.get("proposal")
    if isinstance(proposal, dict):
        value = _string_value(proposal.get("proposal_id"))
        if value:
            return value
    return _string_value(report.get("target_id")) or "cp-bench-round"


def _cp_bench_proposal_type(report: dict[str, Any]) -> str:
    proposal = report.get("proposal")
    if isinstance(proposal, dict):
        value = _string_value(proposal.get("change_type"))
        if value:
            return value
    return "code_patch"


def _cp_bench_change_surface(report: dict[str, Any]) -> str:
    proposal_type = _cp_bench_proposal_type(report)
    mapping = {
        "code_patch": "code_patch",
        "prompt_profile": "prompt_profile",
    }
    return mapping.get(proposal_type, "code_patch")


def _cp_bench_target_scope(report: dict[str, Any]) -> str:
    before = report.get("before_summary")
    if isinstance(before, dict):
        submitted = before.get("submitted_models")
        if _is_plain_number(submitted):
            return f"{int(submitted)} verified CP-Bench rows"
    return "verified CP-Bench slice"


def _cp_bench_zero_delta(report: dict[str, Any]) -> dict[str, float]:
    return {key: 0.0 for key in _cp_bench_metric_delta(report)}


def _cp_bench_metric_delta(report: dict[str, Any]) -> dict[str, float]:
    before = report.get("before_summary") if isinstance(report.get("before_summary"), dict) else {}
    after = report.get("after_summary") if isinstance(report.get("after_summary"), dict) else {}
    keys = [
        "coverage_percent",
        "consistency_percent",
        "final_solution_accuracy_percent",
    ]
    delta: dict[str, float] = {}
    for key in keys:
        before_value = before.get(key)
        after_value = after.get(key)
        if _is_plain_number(before_value) and _is_plain_number(after_value):
            delta[key] = round(float(after_value) - float(before_value), 4)
    return delta


def _cp_bench_failure_labels(report: dict[str, Any]) -> list[str]:
    failure_summary = report.get("failure_summary")
    if not isinstance(failure_summary, dict):
        return []
    by_type = failure_summary.get("by_failure_type")
    if not isinstance(by_type, dict):
        return []
    labels = []
    for key, value in by_type.items():
        if not _is_plain_number(value) or float(value) <= 0:
            continue
        normalized = _normalize_failure_type(str(key))
        if normalized != "no_improvement" or str(key) == "no_improvement":
            labels.append(normalized)
    return sorted(set(labels))


def _write_cp_bench_effectiveness_markdown(
    *,
    effectiveness: dict[str, Any],
    reports: list[dict[str, Any]],
    path: Path,
) -> None:
    comparison = effectiveness.get("comparison", {})
    lines = [
        "# CP-Bench failure-driven proposal effectiveness bundle",
        "",
        "## Scope",
        "",
        f"- round reports: {len(reports)}",
        f"- proposal_accept_rate_lift: {comparison.get('proposal_accept_rate_lift')}",
        f"- rollback_rate_reduction: {comparison.get('rollback_rate_reduction')}",
        f"- failure_repeat_rate_reduction: {comparison.get('failure_repeat_rate_reduction')}",
        f"- verdict: {comparison.get('verdict')}",
        "",
        "## Claim boundary",
        "",
        "本产物只证明本地 CP-Bench candidate round artifacts 可以被转换成 control/treatment outcome，",
        "并用于 proposal effectiveness 的本地 A/B 评估。它不是官方 leaderboard 结果，也不证明跨任务泛化。",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_fasttext_effectiveness_markdown(
    *,
    effectiveness: dict[str, Any],
    reports: list[dict[str, Any]],
    include_failed_rounds: bool,
    path: Path,
) -> None:
    comparison = effectiveness.get("comparison", {})
    proposal_count = sum(
        len(_fasttext_rounds(report, include_failed_rounds=include_failed_rounds))
        for report in reports
    )
    lines = [
        "# fastText failure-driven proposal effectiveness bundle",
        "",
        "## Scope",
        "",
        f"- multi-round reports: {len(reports)}",
        f"- proposal rounds: {proposal_count}",
        f"- include_failed_rounds: {include_failed_rounds}",
        f"- proposal_accept_rate_lift: {comparison.get('proposal_accept_rate_lift')}",
        f"- rollback_rate_reduction: {comparison.get('rollback_rate_reduction')}",
        f"- failure_repeat_rate_reduction: {comparison.get('failure_repeat_rate_reduction')}",
        f"- verdict: {comparison.get('verdict')}",
        "",
        "## Claim boundary",
        "",
        "本产物只证明本地 fastText multi-round proposal artifacts 可以被转换成 control/treatment outcome，",
        "并用于 proposal effectiveness 的本地 A/B 评估。它不是官方 leaderboard 结果，也不证明任意模型都可自动持续优化。",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _smol_worldcup_control_outcome(
    *,
    control: dict[str, Any],
    treatment: dict[str, Any],
) -> dict[str, Any]:
    proposal_id = _smol_worldcup_proposal_id(control)
    return {
        "schema_version": PROPOSAL_OUTCOME_SCHEMA_VERSION,
        "outcome_id": f"{proposal_id}-control",
        "proposal_id": f"{proposal_id}-control",
        "proposal_type": "baseline_negative_control",
        "task_family": "smol_worldcup_prompt_routing",
        "based_on_failures": _smol_worldcup_based_on_failures(control),
        "change_surface": "baseline_negative_control",
        "target_scope": _smol_worldcup_target_scope(control=control, treatment=treatment),
        "executed": True,
        "accepted": False,
        "metric_delta": _smol_worldcup_zero_delta(control=control, treatment=treatment),
        "regression": False,
        "rollback_triggered": False,
        "rollback_reasons": [],
        "failure_labels": _smol_worldcup_failure_labels(control),
        "outcome_summary": (
            f"Baseline negative control for {_smol_worldcup_round_id(control)}; "
            "no follow-up failure-driven proposal applied."
        ),
        "artifact_refs": [],
        "claim_boundary": "local Smol WorldCup negative control only; not public proof",
        "official_scores_claimed": False,
    }


def _smol_worldcup_treatment_outcome(
    *,
    control: dict[str, Any],
    treatment: dict[str, Any],
) -> dict[str, Any]:
    proposal_id = _smol_worldcup_proposal_id(treatment)
    delta = _smol_worldcup_metric_delta(control=control, treatment=treatment)
    shift_delta = float(delta.get("SHIFT", 0.0))
    wcs_delta = float(delta.get("WCS_local_diagnostic", 0.0))
    accepted = shift_delta > 0 or wcs_delta > 0
    regression = any(value < 0 for value in delta.values())
    rollback_triggered = regression
    split = _smol_worldcup_eval_split(treatment)
    failure_labels = _smol_worldcup_failure_labels(treatment)
    if rollback_triggered:
        rollback_label = "canary_not_confirmed" if split == "canary" else "metric_regression"
        failure_labels = sorted(set([rollback_label, *failure_labels]))
    return {
        "schema_version": PROPOSAL_OUTCOME_SCHEMA_VERSION,
        "outcome_id": f"{proposal_id}-treatment",
        "proposal_id": proposal_id,
        "proposal_type": "prompt_profile_patch",
        "task_family": "smol_worldcup_prompt_routing",
        "based_on_failures": _smol_worldcup_based_on_failures(control),
        "change_surface": "prompt_profile",
        "target_scope": _smol_worldcup_target_scope(control=control, treatment=treatment),
        "executed": True,
        "accepted": accepted,
        "metric_delta": delta,
        "regression": regression,
        "rollback_triggered": rollback_triggered,
        "rollback_reasons": [rollback_label] if rollback_triggered else [],
        "failure_labels": failure_labels,
        "outcome_summary": (
            f"Smol WorldCup proposal round {_smol_worldcup_round_id(treatment)} "
            f"split={split}; metric_delta={delta}."
        ),
        "artifact_refs": [],
        "claim_boundary": "local Smol WorldCup proposal comparison only; not public proof",
        "official_scores_claimed": False,
    }


def _smol_worldcup_proposal_id(report: dict[str, Any]) -> str:
    proposal = report.get("proposal")
    if isinstance(proposal, dict):
        value = _string_value(proposal.get("proposal_id"))
        if value:
            return value
    return _smol_worldcup_round_id(report)


def _smol_worldcup_round_id(report: dict[str, Any]) -> str:
    return _string_value(report.get("round_id")) or "smol-worldcup-round"


def _smol_worldcup_eval_split(report: dict[str, Any]) -> str:
    dataset = report.get("dataset")
    if isinstance(dataset, dict):
        value = _string_value(dataset.get("evaluation_split"))
        if value:
            return value
    return "unknown"


def _smol_worldcup_prompt_profile(report: dict[str, Any]) -> str:
    model = report.get("model")
    if isinstance(model, dict):
        value = _string_value(model.get("prompt_profile"))
        if value:
            return value
    return "unknown-profile"


def _smol_worldcup_target_scope(
    *,
    control: dict[str, Any],
    treatment: dict[str, Any],
) -> str:
    split = _smol_worldcup_eval_split(treatment)
    row_count = None
    dataset = treatment.get("dataset")
    if isinstance(dataset, dict) and _is_plain_number(dataset.get("row_count")):
        row_count = int(float(dataset["row_count"]))
    source = _smol_worldcup_prompt_profile(control)
    target = _smol_worldcup_prompt_profile(treatment)
    if row_count is not None:
        return f"Smol WorldCup {split} split ({row_count} rows) {source} -> {target}"
    return f"Smol WorldCup {split} split {source} -> {target}"


def _smol_worldcup_metric_delta(
    *,
    control: dict[str, Any],
    treatment: dict[str, Any],
) -> dict[str, float]:
    control_metrics = control.get("metrics") if isinstance(control.get("metrics"), dict) else {}
    treatment_metrics = (
        treatment.get("metrics") if isinstance(treatment.get("metrics"), dict) else {}
    )
    keys = ["H", "I", "SHIFT", "WCS_local_diagnostic"]
    delta: dict[str, float] = {}
    for key in keys:
        before_value = control_metrics.get(key)
        after_value = treatment_metrics.get(key)
        if _is_plain_number(before_value) and _is_plain_number(after_value):
            delta[key] = round(float(after_value) - float(before_value), 4)
    return delta


def _smol_worldcup_result_metric_regressions(
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
) -> list[dict[str, Any]]:
    regressions = []
    for index, (control, treatment) in enumerate(pairs, start=1):
        split = _smol_worldcup_eval_split(treatment)
        delta = _smol_worldcup_metric_delta(control=control, treatment=treatment)
        for metric, value in sorted(delta.items()):
            if float(value) < 0:
                regressions.append({
                    "pair_index": index,
                    "split": split,
                    "metric": metric,
                    "delta": value,
                    "control_profile": _smol_worldcup_prompt_profile(control),
                    "treatment_profile": _smol_worldcup_prompt_profile(treatment),
                    "analysis_required": True,
                })
    return regressions


def _smol_worldcup_result_row_deltas(
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows = []
    for index, (control, treatment) in enumerate(pairs, start=1):
        control_predictions = _smol_worldcup_predictions_by_row_id(control)
        treatment_predictions = _smol_worldcup_predictions_by_row_id(treatment)
        for row_id in sorted(set(control_predictions) & set(treatment_predictions)):
            before = control_predictions[row_id]
            after = treatment_predictions[row_id]
            if not _is_plain_number(before.get("score")) or not _is_plain_number(after.get("score")):
                continue
            score_delta = round(float(after["score"]) - float(before["score"]), 4)
            if score_delta == 0:
                continue
            messages_changed = _smol_worldcup_prediction_messages_changed(
                control=control,
                treatment=treatment,
                control_prediction=before,
                treatment_prediction=after,
            )
            root_cause = _smol_worldcup_row_delta_root_cause(
                before=before,
                after=after,
                score_delta=score_delta,
                messages_changed=messages_changed,
            )
            rows.append({
                "pair_index": index,
                "split": _smol_worldcup_eval_split(treatment),
                "row_id": row_id,
                "shift_axis": _string_value(after.get("shift_axis"))
                or _string_value(before.get("shift_axis"))
                or "unknown",
                "category": _string_value(after.get("category"))
                or _string_value(before.get("category"))
                or "unknown",
                "subcategory": _string_value(after.get("subcategory"))
                or _string_value(before.get("subcategory"))
                or "unknown",
                "auto_grade": _string_value(after.get("auto_grade"))
                or _string_value(before.get("auto_grade"))
                or "unknown",
                "control_score": float(before["score"]),
                "treatment_score": float(after["score"]),
                "max_score": float(after.get("max_score") or before.get("max_score") or 0.0),
                "score_delta": score_delta,
                "control_grading_method": _string_value(before.get("grading_method")) or "unknown",
                "treatment_grading_method": _string_value(after.get("grading_method")) or "unknown",
                "control_grading_reason": _string_value(before.get("grading_reason")),
                "treatment_grading_reason": _string_value(after.get("grading_reason")),
                "prompt_profile_messages_changed": messages_changed,
                "root_cause_hypothesis": root_cause,
                "recommended_next_action": _smol_worldcup_row_delta_next_action(root_cause),
                "response_preview": {
                    "control": _smol_worldcup_response_preview(before),
                    "treatment": _smol_worldcup_response_preview(after),
                },
            })
    return sorted(rows, key=lambda item: (float(item["score_delta"]), str(item["row_id"])))


def _smol_worldcup_confidence_variance_rows(
    payload: dict[str, Any],
    *,
    confidence_category: str,
    min_abs_score_delta: float,
) -> list[dict[str, Any]]:
    rows = []
    for row in payload.get("row_deltas") or []:
        if not isinstance(row, dict):
            continue
        if _string_value(row.get("category")) != confidence_category:
            continue
        if not _is_plain_number(row.get("score_delta")):
            continue
        score_delta = round(float(row["score_delta"]), 6)
        if abs(score_delta) < min_abs_score_delta:
            continue
        rows.append({
            "row_id": _string_value(row.get("row_id")) or "unknown",
            "category": _string_value(row.get("category")) or "unknown",
            "score_delta": score_delta,
            "abs_score_delta": round(abs(score_delta), 6),
            "prompt_profile_messages_changed": row.get("prompt_profile_messages_changed"),
            "root_cause_hypothesis": _string_value(row.get("root_cause_hypothesis"))
            or "unknown",
        })
    return sorted(rows, key=lambda item: (-float(item["abs_score_delta"]), str(item["row_id"])))


def _smol_worldcup_confidence_candidate_assessment(
    *,
    payload: dict[str, Any],
    ref: str,
    aa_by_row: dict[str, dict[str, Any]],
    confidence_category: str,
    min_abs_score_delta: float,
    aa_coverage_ratio: float,
) -> dict[str, Any]:
    rows = []
    for row in payload.get("row_deltas") or []:
        if not isinstance(row, dict):
            continue
        if _string_value(row.get("category")) != confidence_category:
            continue
        if not _is_plain_number(row.get("score_delta")):
            continue
        score_delta = round(float(row["score_delta"]), 6)
        if score_delta >= -abs(min_abs_score_delta):
            continue
        row_id = _string_value(row.get("row_id")) or "unknown"
        aa_row = aa_by_row.get(row_id)
        aa_abs_delta = (
            float(aa_row.get("abs_score_delta"))
            if isinstance(aa_row, dict) and _is_plain_number(aa_row.get("abs_score_delta"))
            else 0.0
        )
        candidate_abs_delta = abs(score_delta)
        messages_changed = row.get("prompt_profile_messages_changed")
        if messages_changed is True:
            classification = "direct_prompt_change_candidate"
        elif aa_abs_delta and candidate_abs_delta <= aa_abs_delta * float(aa_coverage_ratio):
            classification = "covered_by_aa_confidence_variance"
        elif aa_abs_delta:
            classification = "exceeds_aa_variance_but_prompt_unchanged"
        else:
            classification = "needs_aa_confidence_repeat_for_row"
        rows.append({
            "row_id": row_id,
            "score_delta": score_delta,
            "abs_score_delta": round(candidate_abs_delta, 6),
            "aa_abs_score_delta": round(aa_abs_delta, 6),
            "prompt_profile_messages_changed": messages_changed,
            "root_cause_hypothesis": _string_value(row.get("root_cause_hypothesis"))
            or "unknown",
            "classification": classification,
        })
    return {
        "candidate_ref": ref,
        "metric_regressions": [
            item
            for item in payload.get("metric_regressions") or []
            if isinstance(item, dict)
        ],
        "confidence_rows": sorted(
            rows,
            key=lambda item: (-float(item["abs_score_delta"]), str(item["row_id"])),
        ),
    }


def _smol_worldcup_confidence_input_claimed_official(
    aa_payload: dict[str, Any],
    candidate_payloads: list[dict[str, Any]],
) -> bool:
    payloads = [aa_payload, *candidate_payloads]
    return any(bool(payload.get("official_scores_claimed")) for payload in payloads)


def _smol_worldcup_cached_confidence_row_diagnostics(
    loaded_reports: list[tuple[dict[str, Any], Path | None]],
    *,
    confidence_category: str,
    min_repeats: int,
    max_score_range: float,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for report_index, (report, path) in enumerate(loaded_reports, start=1):
        report_ref = str(path) if path is not None else "inline"
        round_id = _string_value(report.get("round_id")) or f"report-{report_index}"
        model = report.get("model") if isinstance(report.get("model"), dict) else {}
        dataset = report.get("dataset") if isinstance(report.get("dataset"), dict) else {}
        report_scorer_version = _smol_worldcup_report_scorer_version(report)
        predictions = report.get("predictions")
        if not isinstance(predictions, list):
            continue
        for prediction in predictions:
            if not isinstance(prediction, dict):
                continue
            if _string_value(prediction.get("category")) != confidence_category:
                continue
            if not _is_plain_number(prediction.get("score")):
                continue
            row_id = _string_value(prediction.get("row_id")) or "unknown"
            response = str(prediction.get("response") or "")
            prompt = str(prediction.get("prompt") or "")
            scorer_version = (
                _smol_worldcup_prediction_scorer_version(prediction)
                or report_scorer_version
            )
            grouped.setdefault(row_id, []).append({
                "report_ref": report_ref,
                "round_id": round_id,
                "model_config": _smol_worldcup_repeat_model_config(model),
                "evaluation_split": _string_value(dataset.get("evaluation_split"))
                or _string_value(dataset.get("split"))
                or "unknown",
                "score": round(float(prediction["score"]), 6),
                "max_score": (
                    round(float(prediction["max_score"]), 6)
                    if _is_plain_number(prediction.get("max_score"))
                    else None
                ),
                "response_hash": _stable_text_hash(response),
                "prompt_hash": _stable_text_hash(prompt),
                "response_cache_key": _smol_worldcup_prediction_cache_key(prediction),
                "scorer_version": scorer_version,
                "grading_method": _string_value(prediction.get("grading_method")) or "unknown",
                "grading_reason": _string_value(prediction.get("grading_reason")) or "",
            })
    diagnostics = []
    for row_id, repeats in grouped.items():
        scores = [float(item["score"]) for item in repeats]
        score_range = max(scores) - min(scores) if scores else 0.0
        response_hashes = sorted({str(item["response_hash"]) for item in repeats})
        prompt_hashes = sorted({str(item["prompt_hash"]) for item in repeats})
        cache_keys = [
            str(item["response_cache_key"])
            for item in repeats
            if _string_value(item.get("response_cache_key"))
        ]
        scorer_versions = [
            str(item["scorer_version"])
            for item in repeats
            if _string_value(item.get("scorer_version"))
        ]
        model_configs = {
            json.dumps(item.get("model_config", {}), sort_keys=True)
            for item in repeats
        }
        splits = {str(item.get("evaluation_split") or "unknown") for item in repeats}
        hard_blockers = []
        if len(repeats) < min_repeats:
            hard_blockers.append("insufficient_confidence_repeats")
        if len(cache_keys) != len(repeats):
            hard_blockers.append("missing_response_cache_key")
        elif len(set(cache_keys)) > 1:
            hard_blockers.append("response_cache_key_mismatch")
        if len(response_hashes) > 1:
            hard_blockers.append("confidence_response_variance_detected")
        if len(scorer_versions) != len(repeats):
            hard_blockers.append("missing_confidence_scorer_version")
        elif len(set(scorer_versions)) > 1:
            hard_blockers.append("confidence_scorer_version_mismatch")
        if score_range > max_score_range:
            hard_blockers.append("confidence_score_variance_detected")
        if len(model_configs) > 1:
            hard_blockers.append("inconsistent_repeat_model_config")
        if len(splits) > 1:
            hard_blockers.append("inconsistent_repeat_split")
        cached_output_ready = (
            len(repeats) >= min_repeats
            and len(cache_keys) == len(repeats)
            and len(set(cache_keys)) == 1
            and len(response_hashes) == 1
        )
        scoring_deterministic = (
            len(repeats) >= min_repeats
            and len(scorer_versions) == len(repeats)
            and len(set(scorer_versions)) == 1
            and score_range <= max_score_range
        )
        diagnostics.append({
            "row_id": row_id,
            "repeat_count": len(repeats),
            "score_min": round(min(scores), 6) if scores else None,
            "score_max": round(max(scores), 6) if scores else None,
            "score_range": round(score_range, 6),
            "unique_response_hash_count": len(response_hashes),
            "unique_prompt_hash_count": len(prompt_hashes),
            "response_cache_key_count": len(cache_keys),
            "scorer_version_count": len(scorer_versions),
            "cached_output_ready": cached_output_ready,
            "scoring_deterministic": scoring_deterministic,
            "hard_blockers": sorted(set(hard_blockers)),
            "repeats": sorted(repeats, key=lambda item: str(item["round_id"])),
        })
    return sorted(diagnostics, key=lambda item: str(item["row_id"]))


def _smol_worldcup_prediction_cache_key(prediction: dict[str, Any]) -> str | None:
    for key in (
        "response_cache_key",
        "output_cache_key",
        "cached_response_key",
        "cache_key",
    ):
        value = _string_value(prediction.get(key))
        if value:
            return value
    cache = prediction.get("response_cache")
    if isinstance(cache, dict):
        for key in ("key", "cache_key", "response_cache_key"):
            value = _string_value(cache.get(key))
            if value:
                return value
    return None


def _smol_worldcup_prediction_scorer_version(prediction: dict[str, Any]) -> str | None:
    for key in ("scorer_version", "scoring_version", "grading_version"):
        value = _string_value(prediction.get(key))
        if value:
            return value
    return None


def _smol_worldcup_report_scorer_version(report: dict[str, Any]) -> str | None:
    for key in ("scorer_version", "scoring_version", "grading_version"):
        value = _string_value(report.get(key))
        if value:
            return value
    scorer = report.get("scorer")
    if isinstance(scorer, dict):
        for key in ("version", "scorer_version"):
            value = _string_value(scorer.get(key))
            if value:
                return value
    return None


def _smol_worldcup_repeat_model_config(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _string_value(model.get("id")) or "unknown",
        "provider": _string_value(model.get("provider")) or "unknown",
        "prompt_profile": _string_value(model.get("prompt_profile")) or "unknown",
        "temperature": model.get("temperature"),
        "max_tokens": model.get("max_tokens"),
        "judge_mode": model.get("judge_mode"),
    }


def _stable_text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _smol_worldcup_predictions_by_row_id(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    predictions = report.get("predictions")
    if not isinstance(predictions, list):
        return {}
    rows = {}
    for prediction in predictions:
        if not isinstance(prediction, dict):
            continue
        row_id = _string_value(prediction.get("row_id"))
        if row_id:
            rows[row_id] = prediction
    return rows


def _smol_worldcup_prediction_messages_changed(
    *,
    control: dict[str, Any],
    treatment: dict[str, Any],
    control_prediction: dict[str, Any],
    treatment_prediction: dict[str, Any],
) -> bool | None:
    control_profile = _smol_worldcup_prompt_profile(control)
    treatment_profile = _smol_worldcup_prompt_profile(treatment)
    if control_profile == "unknown-profile" or treatment_profile == "unknown-profile":
        return None
    try:
        control_messages = _build_model_messages(
            _smol_worldcup_prediction_row(control_prediction),
            prompt_profile=control_profile,
        )
        treatment_messages = _build_model_messages(
            _smol_worldcup_prediction_row(treatment_prediction),
            prompt_profile=treatment_profile,
        )
    except Exception:
        return None
    return control_messages != treatment_messages


def _smol_worldcup_prediction_row(prediction: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": prediction.get("row_id"),
        "shift_axis": prediction.get("shift_axis"),
        "category": prediction.get("category"),
        "subcategory": prediction.get("subcategory"),
        "auto_grade": prediction.get("auto_grade"),
        "max_score": prediction.get("max_score"),
        "prompt": prediction.get("prompt"),
    }


def _smol_worldcup_row_delta_root_cause(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    score_delta: float,
    messages_changed: bool | None,
) -> str:
    if score_delta >= 0:
        return "candidate_improved_row"
    if (
        _string_value(after.get("grading_method")) == "runtime_error"
        or _string_value(after.get("error_type"))
    ):
        return "runtime_error_or_truncated_output"
    if messages_changed is False:
        return "stochastic_or_format_variation"
    if messages_changed is True:
        return "direct_prompt_change_candidate"
    return "insufficient_artifact_detail"


def _smol_worldcup_row_delta_next_action(root_cause: str) -> str:
    if root_cause == "candidate_improved_row":
        return "retain_as_positive_evidence"
    if root_cause == "stochastic_or_format_variation":
        return "repeat_row_before_prompt_change"
    if root_cause == "runtime_error_or_truncated_output":
        return "rerun_runtime_clean_before_prompt_change"
    if root_cause == "direct_prompt_change_candidate":
        return "inspect_prompt_delta_before_prompt_change"
    return "collect_full_prompt_artifacts_before_prompt_change"


def _smol_worldcup_response_preview(prediction: dict[str, Any]) -> str:
    response = _string_value(prediction.get("response")) or ""
    return response.replace("\n", " ")[:320]


def _smol_worldcup_zero_delta(
    *,
    control: dict[str, Any],
    treatment: dict[str, Any],
) -> dict[str, float]:
    return {key: 0.0 for key in _smol_worldcup_metric_delta(control=control, treatment=treatment)}


def _smol_worldcup_failure_labels(report: dict[str, Any]) -> list[str]:
    summary = report.get("failure_summary")
    if not isinstance(summary, dict):
        return []
    top = summary.get("top_failure_categories")
    if not isinstance(top, list):
        return []
    labels = []
    for item in top:
        if not isinstance(item, dict):
            continue
        category = _string_value(item.get("category"))
        if category:
            labels.append(_normalize_failure_type(category))
    return sorted(set(labels))


def _smol_worldcup_based_on_failures(control: dict[str, Any]) -> list[str]:
    return _smol_worldcup_failure_labels(control)


def _write_smol_worldcup_result_analysis_markdown(
    *,
    payload: dict[str, Any],
    path: Path,
) -> None:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    lines = [
        "# Smol WorldCup result analysis",
        "",
        "## Scope",
        "",
        f"- status: `{payload.get('status')}`",
        f"- comparison_pair_count: `{payload.get('comparison_pair_count')}`",
        f"- split_filter: `{payload.get('split_filter')}`",
        f"- regression_row_count: `{summary.get('regression_row_count')}`",
        f"- improvement_row_count: `{summary.get('improvement_row_count')}`",
        f"- next_action: `{payload.get('next_action')}`",
        "",
        "## Metric regressions",
        "",
    ]
    regressions = payload.get("metric_regressions")
    if isinstance(regressions, list) and regressions:
        for item in regressions:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- `{item.get('split')}` `{item.get('metric')}` delta `{item.get('delta')}`"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Row deltas", ""])
    row_deltas = payload.get("row_deltas")
    if isinstance(row_deltas, list) and row_deltas:
        for item in row_deltas[:20]:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- "
                f"`{item.get('row_id')}` `{item.get('category')}` "
                f"delta `{item.get('score_delta')}` "
                f"prompt_changed `{item.get('prompt_profile_messages_changed')}` "
                f"cause `{item.get('root_cause_hypothesis')}` "
                f"next `{item.get('recommended_next_action')}`"
            )
    else:
        lines.append("- none")
    lines.extend([
        "",
        "## Boundary",
        "",
        "本产物只做结果归因和下一步动作分流。它不修改 prompt，不执行新评测，",
        "也不把 local diagnostic evidence 升级为 official score。",
        "",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_smol_worldcup_effectiveness_markdown(
    *,
    effectiveness: dict[str, Any],
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
    split_filter: str | None,
    path: Path,
) -> None:
    comparison = effectiveness.get("comparison", {})
    lines = [
        "# Smol WorldCup failure-driven proposal effectiveness bundle",
        "",
        "## Scope",
        "",
        f"- comparison_pairs: {len(pairs)}",
        f"- split_filter: {split_filter}",
        f"- proposal_accept_rate_lift: {comparison.get('proposal_accept_rate_lift')}",
        f"- rollback_rate_reduction: {comparison.get('rollback_rate_reduction')}",
        f"- failure_repeat_rate_reduction: {comparison.get('failure_repeat_rate_reduction')}",
        f"- verdict: {comparison.get('verdict')}",
        "",
        "## Pairs",
        "",
    ]
    for control, treatment in pairs:
        lines.extend(
            [
                (
                    f"- `{_smol_worldcup_eval_split(treatment)}`: "
                    f"`{_smol_worldcup_prompt_profile(control)}` -> "
                    f"`{_smol_worldcup_prompt_profile(treatment)}`"
                ),
            ]
        )
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            "本产物只证明本地 Smol WorldCup prompt-profile proposal artifacts 可以被转换成",
            "control/treatment outcome，并用于 proposal effectiveness 的本地 A/B 评估。",
            "它不是 Hugging Face 官方提交、hidden-test 结果，也不证明 prompt proposal 已跨任务稳定有效。",
            "",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _real_paper_control_outcome(
    archive: dict[str, Any],
    *,
    metric_names: list[str],
) -> dict[str, Any]:
    proposal_id = _real_paper_proposal_id(archive)
    return {
        "schema_version": PROPOSAL_OUTCOME_SCHEMA_VERSION,
        "outcome_id": f"{proposal_id}-control",
        "proposal_id": f"{proposal_id}-control",
        "proposal_type": "baseline_negative_control",
        "task_family": "real_paper_public_slice_patch",
        "based_on_failures": [],
        "change_surface": "baseline_negative_control",
        "target_scope": _real_paper_target_scope(archive),
        "executed": True,
        "accepted": False,
        "metric_delta": _real_paper_zero_delta(metric_names=metric_names),
        "regression": False,
        "rollback_triggered": False,
        "rollback_reasons": [],
        "failure_labels": ["no_improvement"],
        "outcome_summary": (
            f"Baseline negative control for {proposal_id}; no failure-driven patch applied."
        ),
        "artifact_refs": [],
        "claim_boundary": "local real-paper baseline negative control only; not public proof",
        "official_scores_claimed": False,
    }


def _real_paper_treatment_outcome(
    archive: dict[str, Any],
    *,
    metric_names: list[str],
) -> dict[str, Any]:
    proposal_id = _real_paper_proposal_id(archive)
    delta = _real_paper_metric_delta_with_zeros(archive, metric_names=metric_names)
    review_status = _string_value(archive.get("review_status")) or "approved_with_limitations"
    failure_labels = _real_paper_failure_labels(archive)
    accepted = review_status.startswith("approved") and any(value > 0 for value in delta.values())
    regression = any(value < 0 for value in delta.values())
    rollback_triggered = review_status.startswith("rejected") or regression
    rollback_reasons = [review_status] if rollback_triggered else []
    return {
        "schema_version": PROPOSAL_OUTCOME_SCHEMA_VERSION,
        "outcome_id": f"{proposal_id}-treatment",
        "proposal_id": proposal_id,
        "proposal_type": "real_paper_public_slice_patch",
        "task_family": "real_paper_public_slice_patch",
        "based_on_failures": failure_labels,
        "change_surface": _real_paper_change_surface(archive),
        "target_scope": _real_paper_target_scope(archive),
        "executed": True,
        "accepted": accepted,
        "metric_delta": delta,
        "regression": regression,
        "rollback_triggered": rollback_triggered,
        "rollback_reasons": rollback_reasons,
        "failure_labels": failure_labels,
        "outcome_summary": (
            f"real-paper public-slice patch {proposal_id} review_status={review_status}; "
            f"metric_delta={delta}."
        ),
        "artifact_refs": [],
        "claim_boundary": "local real-paper public-slice patch only; not public proof",
        "official_scores_claimed": False,
    }


def _real_paper_proposal_id(archive: dict[str, Any]) -> str:
    manifest = _real_paper_manifest(archive)
    paper_id = _string_value(manifest.get("paper_id"))
    if paper_id:
        normalized = paper_id.replace(":", "-").replace("/", "-").replace(".", "-")
        return f"real-paper-{normalized}"
    description = (_string_value(archive.get("description")) or "real-paper-proof").strip()
    slug = "-".join(part for part in description.lower().replace("/", " ").split() if part)
    return slug or "real-paper-proof"


def _real_paper_manifest(archive: dict[str, Any]) -> dict[str, Any]:
    manifest = archive.get("artifact_manifest")
    if isinstance(manifest, dict):
        return manifest
    return archive


def _real_paper_metric_summary(archive: dict[str, Any]) -> dict[str, Any]:
    manifest = _real_paper_manifest(archive)
    metric_summary = manifest.get("metric_summary")
    if isinstance(metric_summary, dict):
        return metric_summary
    return archive.get("metric_summary") if isinstance(archive.get("metric_summary"), dict) else {}


def _real_paper_metric_delta(archive: dict[str, Any]) -> dict[str, float]:
    summary = _real_paper_metric_summary(archive)
    metric_name = _string_value(summary.get("metric_name"))
    delta = summary.get("delta")
    if metric_name and _is_plain_number(delta):
        return {metric_name: round(float(delta), 4)}
    metric_before = summary.get("metric_before")
    metric_after = summary.get("metric_after")
    if metric_name and _is_plain_number(metric_before) and _is_plain_number(metric_after):
        return {metric_name: round(float(metric_after) - float(metric_before), 4)}
    return {}


def _real_paper_zero_delta(*, metric_names: list[str]) -> dict[str, float]:
    return {key: 0.0 for key in metric_names}


def _real_paper_metric_delta_with_zeros(
    archive: dict[str, Any],
    *,
    metric_names: list[str],
) -> dict[str, float]:
    delta = _real_paper_metric_delta(archive)
    return {metric_name: round(float(delta.get(metric_name, 0.0)), 4) for metric_name in metric_names}


def _real_paper_change_surface(archive: dict[str, Any]) -> str:
    method_family = _string_value(_real_paper_metric_summary(archive).get("method_family")) or ""
    mapping = {
        "routing": "routing_patch",
        "optimizer": "optimizer_patch",
    }
    return mapping.get(method_family, "public_slice_patch")


def _real_paper_target_scope(archive: dict[str, Any]) -> str:
    manifest = _real_paper_manifest(archive)
    paper_id = _string_value(manifest.get("paper_id")) or "unknown-paper"
    metric_name = _string_value(_real_paper_metric_summary(archive).get("metric_name")) or "unknown_metric"
    return f"real-paper public slice {paper_id} ({metric_name})"


def _real_paper_failure_labels(archive: dict[str, Any]) -> list[str]:
    summary = _real_paper_metric_summary(archive)
    delta = summary.get("delta")
    if _is_plain_number(delta) and float(delta) <= 0:
        return ["no_improvement"]
    return []


def _write_real_paper_effectiveness_markdown(
    *,
    effectiveness: dict[str, Any],
    archives: list[dict[str, Any]],
    path: Path,
) -> None:
    comparison = effectiveness.get("comparison", {})
    lines = [
        "# real-paper public-slice failure-driven proposal effectiveness bundle",
        "",
        "## Scope",
        "",
        f"- proof archives: {len(archives)}",
        f"- proposal_accept_rate_lift: {comparison.get('proposal_accept_rate_lift')}",
        f"- rollback_rate_reduction: {comparison.get('rollback_rate_reduction')}",
        f"- failure_repeat_rate_reduction: {comparison.get('failure_repeat_rate_reduction')}",
        f"- verdict: {comparison.get('verdict')}",
        "",
        "## Included proofs",
        "",
    ]
    for archive in archives:
        manifest = _real_paper_manifest(archive)
        metric_summary = _real_paper_metric_summary(archive)
        lines.append(
            (
                f"- `{_string_value(manifest.get('paper_id')) or _real_paper_proposal_id(archive)}`: "
                f"`{_string_value(metric_summary.get('metric_name')) or 'unknown_metric'}` "
                f"delta=`{_real_paper_metric_delta(archive)}`"
            )
        )
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            "本产物只证明本地 real-paper public-slice proof archives 可以被转换成",
            "control/treatment outcome，并用于 proposal effectiveness 的本地 A/B 评估。",
            "它不是官方 benchmark 分数、不是完整论文复现，也不证明 proposal 已跨任务稳定有效。",
            "",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _mixed_signal_task_audit(report: dict[str, Any]) -> dict[str, Any] | None:
    comparison = report.get("comparison") if isinstance(report.get("comparison"), dict) else {}
    verdict = _string_value(comparison.get("verdict")) or "unknown"
    if verdict != "mixed_signal":
        return None
    metric_lift = (
        comparison.get("avg_metric_delta_lift")
        if isinstance(comparison.get("avg_metric_delta_lift"), dict)
        else {}
    )
    treatment_summary = (
        report.get("treatment_summary") if isinstance(report.get("treatment_summary"), dict) else {}
    )
    task_family = _infer_task_family(metric_lift=metric_lift, treatment_summary=treatment_summary)
    proposal_accept_rate_lift = float(comparison.get("proposal_accept_rate_lift", 0.0))
    rollback_rate_reduction = float(comparison.get("rollback_rate_reduction", 0.0))
    failure_repeat_rate_reduction = float(comparison.get("failure_repeat_rate_reduction", 0.0))
    negative_metrics = [
        str(name)
        for name, value in metric_lift.items()
        if _is_plain_number(value) and float(value) < 0
    ]
    zero_metrics = [
        str(name)
        for name, value in metric_lift.items()
        if _is_plain_number(value) and float(value) == 0
    ]
    positive_metrics = [
        str(name)
        for name, value in metric_lift.items()
        if _is_plain_number(value) and float(value) > 0
    ]
    blocking_signals: list[str] = []
    recommendations: list[str] = []
    if rollback_rate_reduction < 0:
        blocking_signals.append("rollback_rate_worsened")
        recommendations.append("split_exploration_and_confirmation_arms")
    if proposal_accept_rate_lift <= 0:
        blocking_signals.append("proposal_accept_rate_not_improved")
        recommendations.append("tighten_candidate_selection_before_treatment")
    if failure_repeat_rate_reduction <= 0:
        blocking_signals.append("failure_repeat_not_reduced")
        recommendations.append("add_failure_slice_specific_control_arm")
    if negative_metrics:
        blocking_signals.append("negative_metric_delta_present")
        recommendations.append("separate_metric_optimization_targets")
    if not negative_metrics and rollback_rate_reduction < 0 and positive_metrics:
        blocking_signals.append("execution_tradeoff_without_metric_regression")
    if task_family == "smol_worldcup_prompt_routing":
        recommendations.append("tighten_canary_gate_before_prompt_profile_promotion")
    if task_family == "fasttext_text_classification":
        recommendations.append("separate_allowlist_rejections_from_effectiveness_arms")
    return {
        "task_family": task_family,
        "blocking_signals": sorted(set(blocking_signals)),
        "positive_metrics": sorted(set(positive_metrics)),
        "zero_metrics": sorted(set(zero_metrics)),
        "negative_metrics": sorted(set(negative_metrics)),
        "proposal_accept_rate_lift": proposal_accept_rate_lift,
        "rollback_rate_reduction": rollback_rate_reduction,
        "failure_repeat_rate_reduction": failure_repeat_rate_reduction,
        "recommended_actions": sorted(set(recommendations)),
        "claim_boundary": "mixed-signal task audit only; not public proof",
        "official_scores_claimed": False,
    }


def _write_mixed_signal_effectiveness_markdown(
    *,
    payload: dict[str, Any],
    path: Path,
) -> None:
    aggregate = payload.get("aggregate") if isinstance(payload.get("aggregate"), dict) else {}
    audits = payload.get("task_audits") if isinstance(payload.get("task_audits"), list) else []
    lines = [
        "# Mixed-signal proposal effectiveness audit",
        "",
        "## Summary",
        "",
        f"- mixed_signal_task_count: `{payload.get('mixed_signal_task_count')}`",
        f"- blocking_signal_counts: `{aggregate.get('blocking_signal_counts')}`",
        f"- recommended_actions: `{aggregate.get('recommended_actions')}`",
        "",
        "## Task audits",
        "",
    ]
    for audit in audits:
        if not isinstance(audit, dict):
            continue
        lines.extend(
            [
                f"### {audit.get('task_family')}",
                "",
                f"- blocking_signals: `{audit.get('blocking_signals')}`",
                f"- positive_metrics: `{audit.get('positive_metrics')}`",
                f"- zero_metrics: `{audit.get('zero_metrics')}`",
                f"- negative_metrics: `{audit.get('negative_metrics')}`",
                f"- rollback_rate_reduction: `{audit.get('rollback_rate_reduction')}`",
                f"- failure_repeat_rate_reduction: `{audit.get('failure_repeat_rate_reduction')}`",
                f"- recommended_actions: `{audit.get('recommended_actions')}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Claim boundary",
            "",
            "本产物只用于诊断 mixed-signal 任务族为什么还不能通过 claim audit。",
            "它不证明 proposal 已跨任务稳定有效，也不替代更严格的 control/treatment 重新设计。",
            "",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _smol_worldcup_gate_arm(
    *,
    report: dict[str, Any],
    arm: str,
) -> dict[str, Any]:
    comparison = report.get("comparison") if isinstance(report.get("comparison"), dict) else {}
    metric_lift = (
        comparison.get("avg_metric_delta_lift")
        if isinstance(comparison.get("avg_metric_delta_lift"), dict)
        else {}
    )
    negative_metrics = [
        str(name)
        for name, value in metric_lift.items()
        if _is_plain_number(value) and float(value) < 0
    ]
    proposal_accept_rate_lift = float(comparison.get("proposal_accept_rate_lift", 0.0))
    rollback_rate_reduction = float(comparison.get("rollback_rate_reduction", 0.0))
    verdict = _string_value(comparison.get("verdict")) or "unknown"
    passed = (
        verdict == "treatment_improved_on_measured_metrics"
        and proposal_accept_rate_lift > 0
        and rollback_rate_reduction >= 0
        and not negative_metrics
    )
    blockers = []
    if proposal_accept_rate_lift <= 0:
        blockers.append("proposal_accept_rate_not_positive")
    if rollback_rate_reduction < 0:
        blockers.append("rollback_rate_worsened")
    if negative_metrics:
        blockers.append("negative_metric_delta_present")
    if verdict != "treatment_improved_on_measured_metrics":
        blockers.append(f"verdict={verdict}")
    return {
        "arm": arm,
        "passed": passed,
        "verdict": verdict,
        "proposal_accept_rate_lift": proposal_accept_rate_lift,
        "rollback_rate_reduction": rollback_rate_reduction,
        "negative_metrics": sorted(negative_metrics),
        "blockers": blockers,
        "claim_boundary": "local Smol WorldCup gate arm only; not public proof",
        "official_scores_claimed": False,
    }


def _write_smol_worldcup_promotion_gate_markdown(
    *,
    payload: dict[str, Any],
    path: Path,
) -> None:
    dev_gate = payload.get("dev_gate") if isinstance(payload.get("dev_gate"), dict) else {}
    canary_gate = (
        payload.get("canary_gate") if isinstance(payload.get("canary_gate"), dict) else {}
    )
    lines = [
        "# Smol WorldCup Promotion Gate",
        "",
        "## Summary",
        "",
        f"- status: `{payload.get('status')}`",
        f"- promotion_ready: `{payload.get('promotion_ready')}`",
        f"- recommended_next_action: `{payload.get('recommended_next_action')}`",
        "",
        "## Dev gate",
        "",
        f"- passed: `{dev_gate.get('passed')}`",
        f"- verdict: `{dev_gate.get('verdict')}`",
        f"- proposal_accept_rate_lift: `{dev_gate.get('proposal_accept_rate_lift')}`",
        f"- rollback_rate_reduction: `{dev_gate.get('rollback_rate_reduction')}`",
        f"- negative_metrics: `{dev_gate.get('negative_metrics')}`",
        f"- blockers: `{dev_gate.get('blockers')}`",
        "",
        "## Canary gate",
        "",
        f"- passed: `{canary_gate.get('passed')}`",
        f"- verdict: `{canary_gate.get('verdict')}`",
        f"- proposal_accept_rate_lift: `{canary_gate.get('proposal_accept_rate_lift')}`",
        f"- rollback_rate_reduction: `{canary_gate.get('rollback_rate_reduction')}`",
        f"- negative_metrics: `{canary_gate.get('negative_metrics')}`",
        f"- blockers: `{canary_gate.get('blockers')}`",
        "",
        "## Claim boundary",
        "",
        "本产物只决定本地 Smol WorldCup prompt-profile proposal 是否具备 promotion 资格。",
        "它不声明任何官方榜单结果，也不证明该 proposal 已跨任务稳定有效。",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_smol_worldcup_canary_failure_slice_audit_markdown(
    *,
    payload: dict[str, Any],
    path: Path,
) -> None:
    control_arm_spec = (
        payload.get("control_arm_spec")
        if isinstance(payload.get("control_arm_spec"), dict)
        else {}
    )
    lines = [
        "# Smol WorldCup Canary Failure-slice Audit",
        "",
        "## Summary",
        "",
        f"- status: `{payload.get('status')}`",
        f"- gate_status: `{payload.get('gate_status')}`",
        f"- failure_slice_label: `{payload.get('failure_slice_label')}`",
        f"- recommended_next_action: `{payload.get('recommended_next_action')}`",
        "",
        "## Blocking evidence",
        "",
        f"- observed_failure_labels: `{payload.get('observed_failure_labels')}`",
        f"- rollback_reasons: `{payload.get('rollback_reasons')}`",
        f"- negative_metric_names: `{payload.get('negative_metric_names')}`",
        f"- canary_gate_blockers: `{payload.get('canary_gate_blockers')}`",
        "",
        "## Required control arm",
        "",
        f"- evaluation_split: `{control_arm_spec.get('evaluation_split')}`",
        f"- baseline_requirement: `{control_arm_spec.get('baseline_requirement')}`",
        f"- comparison_requirement: `{control_arm_spec.get('comparison_requirement')}`",
        f"- success_criteria: `{control_arm_spec.get('success_criteria')}`",
        f"- promotion_rule: `{control_arm_spec.get('promotion_rule')}`",
        "",
        "## Claim boundary",
        "",
        "本产物只把 Smol WorldCup canary 确认臂需要补的 failure-slice control arm",
        "转成可复跑审计对象。它不是公开成绩，也不证明 proposal 已跨任务稳定有效。",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_smol_worldcup_canary_control_arm_handoff_markdown(
    *,
    payload: dict[str, Any],
    path: Path,
) -> None:
    proposal_template = (
        payload.get("proposal_template")
        if isinstance(payload.get("proposal_template"), dict)
        else {}
    )
    validation_result = (
        payload.get("validation_result")
        if isinstance(payload.get("validation_result"), dict)
        else {}
    )
    lines = [
        "# Smol WorldCup Canary Control-arm Handoff",
        "",
        "## Summary",
        "",
        f"- status: `{payload.get('status')}`",
        f"- failure_slice_label: `{payload.get('failure_slice_label')}`",
        f"- gate_status: `{payload.get('gate_status')}`",
        f"- client_review_required: `{payload.get('client_review_required')}`",
        "",
        "## Proposal template",
        "",
        f"- proposal_id: `{proposal_template.get('proposal_id')}`",
        f"- change_surface: `{proposal_template.get('change_surface')}`",
        f"- first_split: `{proposal_template.get('validation_plan', {}).get('first_split') if isinstance(proposal_template.get('validation_plan'), dict) else None}`",
        f"- promotion_split: `{proposal_template.get('validation_plan', {}).get('promotion_split') if isinstance(proposal_template.get('validation_plan'), dict) else None}`",
        f"- next_if_success: `{proposal_template.get('next_if_success')}`",
        f"- next_if_failure: `{proposal_template.get('next_if_failure')}`",
        "",
        "## Validation",
        "",
        f"- status: `{validation_result.get('status')}`",
        f"- failure_labels: `{validation_result.get('failure_labels')}`",
        "",
        "## Claim boundary",
        "",
        "本产物只把 Smol WorldCup canary matched control arm 的下一轮实验模板",
        "收成可审阅 handoff。它不是执行结果，也不证明 proposal 已经有效。",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_smol_worldcup_canary_control_arm_execution_bundle_markdown(
    *,
    payload: dict[str, Any],
    path: Path,
) -> None:
    lines = [
        "# Smol WorldCup Canary Control-arm Execution Bundle",
        "",
        "## Summary",
        "",
        f"- status: `{payload.get('status')}`",
        f"- target_prompt_profile: `{payload.get('target_prompt_profile')}`",
        f"- evaluation_split: `{payload.get('evaluation_split')}`",
        f"- proposal_validation_status: `{payload.get('proposal_validation_status')}`",
        "",
        "## Next step",
        "",
        f"- mcp_tool: `{payload.get('recommended_next_step', {}).get('mcp_tool') if isinstance(payload.get('recommended_next_step'), dict) else None}`",
        f"- human_action: `{payload.get('recommended_next_step', {}).get('human_action') if isinstance(payload.get('recommended_next_step'), dict) else None}`",
        f"- recommended_command: `{payload.get('recommended_command')}`",
        "",
        "## Claim boundary",
        "",
        "本产物只把 Smol WorldCup canary control-arm handoff 变成 guarded execution 输入。",
        "它不会自动跑实验，也不证明 proposal 已经有效。",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_smol_worldcup_promotion_gate_refresh_markdown(
    *,
    payload: dict[str, Any],
    path: Path,
) -> None:
    canary_gate_refresh = (
        payload.get("canary_gate_refresh")
        if isinstance(payload.get("canary_gate_refresh"), dict)
        else {}
    )
    lines = [
        "# Smol WorldCup Promotion Gate Refresh",
        "",
        "## Summary",
        "",
        f"- status: `{payload.get('status')}`",
        f"- promotion_ready: `{payload.get('promotion_ready')}`",
        f"- previous_gate_status: `{payload.get('previous_gate_status')}`",
        f"- proposal_round_status: `{payload.get('proposal_round_status')}`",
        f"- proposal_validation_status: `{payload.get('proposal_validation_status')}`",
        f"- recommended_next_action: `{payload.get('recommended_next_action')}`",
        "",
        "## Canary refresh",
        "",
        f"- passed: `{canary_gate_refresh.get('passed')}`",
        f"- selected_prompt_profile: `{canary_gate_refresh.get('selected_prompt_profile')}`",
        f"- canary_delta: `{canary_gate_refresh.get('canary_delta')}`",
        f"- rollback_reasons: `{canary_gate_refresh.get('rollback_reasons')}`",
        f"- negative_metrics: `{canary_gate_refresh.get('negative_metrics')}`",
        "",
        "## Claim boundary",
        "",
        "本产物只把一条 guarded Smol proposal round 结果回写到 promotion gate。",
        "它不自动证明 proposal 有效，也不替代跨任务证据。",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _cross_task_entry(*, report: dict[str, Any]) -> dict[str, Any]:
    comparison = report.get("comparison") if isinstance(report.get("comparison"), dict) else {}
    treatment_summary = (
        report.get("treatment_summary") if isinstance(report.get("treatment_summary"), dict) else {}
    )
    control_summary = (
        report.get("control_summary") if isinstance(report.get("control_summary"), dict) else {}
    )
    metric_lift = comparison.get("avg_metric_delta_lift")
    task_family = _infer_task_family(
        metric_lift=metric_lift if isinstance(metric_lift, dict) else {},
        treatment_summary=treatment_summary,
    )
    return {
        "task_family": task_family,
        "verdict": _string_value(comparison.get("verdict")) or "unknown",
        "proposal_accept_rate_lift": float(comparison.get("proposal_accept_rate_lift", 0.0)),
        "rollback_rate_reduction": float(comparison.get("rollback_rate_reduction", 0.0)),
        "failure_repeat_rate_reduction": float(
            comparison.get("failure_repeat_rate_reduction", 0.0)
        ),
        "avg_metric_delta_lift": (
            metric_lift if isinstance(metric_lift, dict) else {}
        ),
        "control_outcome_count": int(control_summary.get("outcome_count", 0) or 0),
        "treatment_outcome_count": int(treatment_summary.get("outcome_count", 0) or 0),
        "claim_boundary": "cross-task summary entry only; not public proof",
        "official_scores_claimed": False,
    }


def _infer_task_family(
    *,
    metric_lift: dict[str, Any],
    treatment_summary: dict[str, Any],
) -> str:
    metric_names = set(metric_lift)
    if "p_at_1" in metric_names:
        return "fasttext_text_classification"
    if "final_solution_accuracy_percent" in metric_names:
        return "cp_bench_constraint_model_generation"
    if "selection_accuracy" in metric_names or "optimizer_progress_score" in metric_names:
        return "real_paper_public_slice_patch"
    if "SHIFT" in metric_names or "WCS_local_diagnostic" in metric_names:
        return "smol_worldcup_prompt_routing"
    best_outcome_id = _string_value(treatment_summary.get("best_outcome_id")) or ""
    if best_outcome_id.startswith("cp-bench-"):
        return "cp_bench_constraint_model_generation"
    if best_outcome_id.startswith("p5-") or "fasttext" in best_outcome_id:
        return "fasttext_text_classification"
    if best_outcome_id.startswith("real-paper-") or "real-paper" in best_outcome_id:
        return "real_paper_public_slice_patch"
    if "qwen3-8b" in best_outcome_id or "smol-worldcup" in best_outcome_id:
        return "smol_worldcup_prompt_routing"
    return "unknown_task_family"


def _cross_task_metric_aggregate(task_summaries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    values_by_metric: dict[str, list[float]] = {}
    for item in task_summaries:
        lifts = item.get("avg_metric_delta_lift")
        if not isinstance(lifts, dict):
            continue
        for metric_name, value in lifts.items():
            if _is_plain_number(value):
                values_by_metric.setdefault(str(metric_name), []).append(float(value))
    aggregate: dict[str, dict[str, Any]] = {}
    for metric_name, values in sorted(values_by_metric.items()):
        positives = sum(1 for value in values if value > 0)
        negatives = sum(1 for value in values if value < 0)
        zeros = sum(1 for value in values if value == 0)
        aggregate[metric_name] = {
            "task_count": len(values),
            "positive_count": positives,
            "negative_count": negatives,
            "zero_count": zeros,
            "mean_lift": round(sum(values) / len(values), 4) if values else 0.0,
            "min_lift": round(min(values), 4) if values else 0.0,
            "max_lift": round(max(values), 4) if values else 0.0,
        }
    return aggregate


def _cross_task_verdict_counts(task_summaries: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in task_summaries:
        verdict = _string_value(item.get("verdict")) or "unknown"
        counts[verdict] = counts.get(verdict, 0) + 1
    return dict(sorted(counts.items()))


def _consistent_positive_metrics(
    metric_aggregate: dict[str, dict[str, Any]],
) -> list[str]:
    return [
        metric_name
        for metric_name, stats in metric_aggregate.items()
        if int(stats.get("task_count", 0)) > 0
        and int(stats.get("negative_count", 0)) == 0
        and int(stats.get("positive_count", 0)) > 0
    ]


def _tradeoff_metrics(metric_aggregate: dict[str, dict[str, Any]]) -> list[str]:
    return [
        metric_name
        for metric_name, stats in metric_aggregate.items()
        if int(stats.get("positive_count", 0)) > 0 and int(stats.get("negative_count", 0)) > 0
    ]


def _write_cross_task_effectiveness_markdown(
    *,
    summary: dict[str, Any],
    path: Path,
) -> None:
    aggregate = summary.get("aggregate", {})
    lines = [
        "# Cross-task proposal effectiveness summary",
        "",
        "## Scope",
        "",
        f"- task_count: {summary.get('task_count')}",
        f"- verdict_counts: {aggregate.get('verdict_counts')}",
        f"- consistent_improvements: {aggregate.get('consistent_improvements')}",
        f"- tradeoff_metrics: {aggregate.get('tradeoff_metrics')}",
        "",
        "## Claim boundary",
        "",
        "本产物只汇总本地任务族 proposal effectiveness bundle，",
        "用于比较哪些指标在多任务上保持正向、哪些指标出现 tradeoff。",
        "它不是跨任务泛化证明，也不是官方 benchmark 结论。",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _proposal_effectiveness_claim_next_actions(
    *,
    gates: dict[str, dict[str, Any]],
    mixed_count: int,
    regressed_count: int,
) -> list[str]:
    actions = []
    if not gates["multiple_positive_task_families"]["passed"]:
        actions.append("add_more_task_families_with_real_control_treatment_artifacts")
    if mixed_count > 0:
        actions.append("tighten_control_treatment_design_for_mixed_signal_tasks")
        actions.append("run_mixed_signal_task_family_audit")
    if regressed_count > 0:
        actions.append("investigate_regressed_task_families_before_any_stronger_claim")
    if not actions:
        actions.append("prepare_bounded_manual_claim_review")
    return actions


def _write_proposal_effectiveness_claim_audit_markdown(
    *,
    payload: dict[str, Any],
    path: Path,
) -> None:
    snapshot = payload.get("evidence_snapshot", {})
    lines = [
        "# Proposal Effectiveness Claim Audit",
        "",
        "## Summary",
        "",
        f"- claim_readiness: `{payload.get('claim_readiness')}`",
        f"- task_count: `{snapshot.get('task_count')}`",
        f"- verdict_counts: `{snapshot.get('verdict_counts')}`",
        f"- consistent_improvements: `{snapshot.get('consistent_improvements')}`",
        f"- tradeoff_metrics: `{snapshot.get('tradeoff_metrics')}`",
        "",
        "## Allowed claims",
        "",
    ]
    for claim in payload.get("allowed_claims", []):
        lines.append(f"- `{claim}`")
    lines.extend(["", "## Blocked claims", ""])
    for claim in payload.get("blocked_claims", []):
        lines.append(f"- `{claim}`")
    lines.extend(["", "## Gaps", ""])
    gaps = payload.get("gaps", [])
    if gaps:
        for gap in gaps:
            lines.append(f"- {gap}")
    else:
        lines.append("- none")
    lines.extend(["", "## Next actions", ""])
    for action in payload.get("recommended_next_actions", []):
        lines.append(f"- `{action}`")
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            payload["claim_boundary"],
            "",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _context_failure_records(context_payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = context_payload.get("failure_summary", {}).get("records", [])
    if not isinstance(records, list):
        return []
    return [item for item in records if isinstance(item, dict)]


def _context_matched_patterns(context_payload: dict[str, Any]) -> list[dict[str, Any]]:
    patterns = context_payload.get("pattern_summary", {}).get("matched_patterns", [])
    if not isinstance(patterns, list):
        return []
    return [item for item in patterns if isinstance(item, dict)]


def _context_max_proposals(context_payload: dict[str, Any]) -> int:
    value = context_payload.get("max_proposals")
    if isinstance(value, int) and value > 0:
        return value
    return 3


def _group_failure_records_by_type(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        failure_type = _string_value(record.get("failure_type")) or "no_improvement"
        grouped.setdefault(failure_type, []).append(record)
    items = [
        {"failure_type": failure_type, "records": failure_items}
        for failure_type, failure_items in grouped.items()
    ]
    items.sort(
        key=lambda item: (
            -len(item["records"]),
            _severity_sort_key(item["records"][0].get("severity")),
            item["failure_type"],
        )
    )
    return items


def _patterns_by_failure_type(patterns: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for pattern in patterns:
        for failure_type in _string_list(pattern.get("applicable_when")):
            index.setdefault(failure_type, []).append(pattern)
    for items in index.values():
        items.sort(
            key=lambda item: (
                -float(item.get("historical_success_rate", 0.0)),
                str(item.get("pattern_id", "")),
            )
        )
    return index


def _best_pattern_for_failure(
    pattern_index: dict[str, list[dict[str, Any]]],
    failure_type: str,
) -> dict[str, Any] | None:
    items = pattern_index.get(failure_type) or []
    return items[0] if items else None


def _proposal_type_for_failure_group(
    *,
    failure_type: str,
    repeated_count: int,
    matched_pattern: dict[str, Any] | None,
) -> str:
    if matched_pattern is not None and float(matched_pattern.get("historical_success_rate", 0.0)) >= 0.5:
        return _string_value(matched_pattern.get("proposal_type")) or "failure_fix"
    if repeated_count >= 2 or failure_type in {"no_improvement", "metric_regression"}:
        return "strategy_shift"
    return "failure_fix"


def _proposal_change_surface(
    *,
    failure_type: str,
    records: list[dict[str, Any]],
    preferred_change_surfaces: list[str] | None,
) -> str:
    preferred = [item for item in (preferred_change_surfaces or []) if isinstance(item, str)]
    if failure_type in {"canary_not_confirmed", "holdout_not_confirmed"} and _has_broader_canary_failure_shape(records):
        inferred = "prompt_profile"
    else:
        mapping = {
            "canary_not_confirmed": "routing",
            "holdout_not_confirmed": "routing",
            "metric_regression": "prompt_profile",
            "no_improvement": "prompt_profile",
            "invalid_patch": "code_patch",
            "runtime_error": "code_patch",
            "timeout": "decoding",
            "scope_too_broad": "routing",
            "leakage_risk": "data",
            "cost_too_high": "decoding",
        }
        inferred = mapping.get(failure_type, "prompt_profile")
    if inferred in preferred:
        return inferred
    if preferred:
        return preferred[0]
    return inferred


def _proposal_intent(
    *,
    failure_type: str,
    change_surface: str,
    repeated_count: int,
    records: list[dict[str, Any]],
) -> str:
    broader_categories = _proposal_focus_categories(records)
    if failure_type == "canary_not_confirmed" and broader_categories:
        category_text = ", ".join(broader_categories)
        return (
            f"Address {failure_type} with one bounded {change_surface} change that "
            f"explicitly targets broader canary failures in {category_text}."
        )
    if repeated_count >= 2:
        return (
            f"Address repeated {failure_type} with one bounded {change_surface} change "
            "that can be validated and rolled back."
        )
    return f"Address {failure_type} with one bounded {change_surface} change."


def _proposal_target_scope(
    records: list[dict[str, Any]],
    *,
    change_surface: str,
    failure_type: str,
) -> str:
    if failure_type == "canary_not_confirmed":
        broader_categories = _proposal_focus_categories(records)
        if broader_categories:
            return (
                "canary broader failure categories within "
                f"{change_surface}: {', '.join(broader_categories)}"
            )
    for record in records:
        scope = _string_value(record.get("scope"))
        if scope:
            return scope
    return f"single {change_surface} surface"


def _proposal_expected_gain(
    matched_pattern: dict[str, Any] | None,
    *,
    failure_type: str,
) -> float:
    if matched_pattern is not None:
        success_rate = float(matched_pattern.get("historical_success_rate", 0.0))
        return round(max(0.2, min(0.95, success_rate)), 4)
    if failure_type in {"canary_not_confirmed", "holdout_not_confirmed"}:
        return 0.6
    if failure_type in {"no_improvement", "metric_regression"}:
        return 0.4
    return 0.5


def _proposal_risk_level(records: list[dict[str, Any]]) -> str:
    levels = {_string_value(item.get("severity")) or "medium" for item in records}
    if "critical" in levels or "high" in levels:
        return "high"
    if "medium" in levels:
        return "medium"
    return "low"


def _proposal_verification_plan(
    *,
    failure_type: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    promotion_split = "canary" if failure_type == "canary_not_confirmed" else None
    if failure_type == "holdout_not_confirmed":
        promotion_split = "holdout"
    first_split = "dev"
    if failure_type in {"canary_not_confirmed", "holdout_not_confirmed"} and _has_broader_canary_failure_shape(records):
        first_split = "canary" if failure_type == "canary_not_confirmed" else "holdout"
    plan = {"first_split": first_split, "max_rounds": 1, "requires_failure_regression_check": True}
    if promotion_split is not None:
        plan["promotion_split"] = promotion_split
    return plan


def _proposal_rollback_rule(*, failure_type: str) -> dict[str, Any]:
    mapping = {
        "canary_not_confirmed": ["canary_delta_lt_0"],
        "holdout_not_confirmed": ["holdout_delta_lt_0"],
        "metric_regression": ["primary_metric_delta_lt_0"],
        "no_improvement": ["no_metric_gain"],
        "timeout": ["runtime_budget_exceeded"],
        "invalid_patch": ["contract_validation_failed"],
        "leakage_risk": ["leakage_signal_detected"],
    }
    return {"if": mapping.get(failure_type, ["regression_detected"])}


def _proposal_rationale(
    *,
    failure_type: str,
    source_records: list[dict[str, Any]],
    matched_pattern: dict[str, Any] | None,
) -> str:
    repeated_count = len(source_records)
    if matched_pattern is not None:
        success_rate = float(matched_pattern.get("historical_success_rate", 0.0))
        pattern_id = _string_value(matched_pattern.get("pattern_id")) or "unknown-pattern"
        return (
            f"Derived from {repeated_count} {failure_type} records and matched pattern "
            f"{pattern_id} (historical_success_rate={success_rate:.2f})."
        )
    return (
        f"Derived from {repeated_count} {failure_type} records without a strong historical "
        "pattern; requires explicit client review."
    )


def _broader_failure_categories(records: list[dict[str, Any]]) -> list[str]:
    counts: dict[str, int] = {}
    for record in records:
        bad_cases = record.get("bad_cases")
        if not isinstance(bad_cases, list):
            continue
        for item in bad_cases:
            if not isinstance(item, dict):
                continue
            category = _string_value(item.get("category"))
            if not category:
                continue
            increment = int(item.get("count", 1) or 1)
            counts[category] = counts.get(category, 0) + max(1, increment)
    return [category for category, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


def _proposal_focus_categories(records: list[dict[str, Any]]) -> list[str]:
    categories = _broader_failure_categories(records)
    if not categories:
        return []
    if len(categories) <= 12:
        return categories
    selected = categories[:4]
    multilingual_non_arabic = [
        category
        for category in categories
        if category.startswith("multilingual_") and category != "multilingual_ar"
    ]
    tail_priority = [
        category
        for category in categories
        if category in {"knowledge_synthesis", "self_correction"}
    ]
    for category in multilingual_non_arabic:
        if category not in selected:
            selected.append(category)
    for category in tail_priority:
        if category not in selected:
            selected.append(category)
    return selected


def _has_broader_canary_failure_shape(records: list[dict[str, Any]]) -> bool:
    categories = _broader_failure_categories(records)
    if len(categories) < 2:
        return False
    return any(category != "multilingual_ar" for category in categories)


def _severity_sort_key(value: Any) -> int:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    if isinstance(value, str):
        return order.get(value, 4)
    return 4


def _effectiveness_arm_summary(items: list[dict[str, Any]], *, label: str) -> dict[str, Any]:
    outcome_count = len(items)
    accepted_count = sum(1 for item in items if item.get("accepted") is True)
    rollback_count = sum(1 for item in items if item.get("rollback_triggered") is True)
    best_index = _time_to_best_index(items)
    best_item = items[best_index - 1] if best_index is not None else None
    best_score = _outcome_score(best_item) if isinstance(best_item, dict) else None
    return {
        "label": label,
        "outcome_count": outcome_count,
        "accepted_count": accepted_count,
        "proposal_accept_rate": (
            round(accepted_count / outcome_count, 4) if outcome_count else 0.0
        ),
        "avg_metric_delta": _average_metric_delta(items),
        "rollback_count": rollback_count,
        "rollback_rate": round(rollback_count / outcome_count, 4) if outcome_count else 0.0,
        "time_to_best": best_index,
        "best_outcome_id": (
            _string_value(best_item.get("outcome_id"))
            if isinstance(best_item, dict)
            else None
        ),
        "best_score": round(best_score, 4) if best_score is not None else None,
        "failure_repeat_rate": _failure_repeat_rate(items),
        "claim_boundary": "local proposal effectiveness arm only; not public proof",
        "official_scores_claimed": False,
    }


def _effectiveness_comparison(
    *,
    control_summary: dict[str, Any],
    treatment_summary: dict[str, Any],
) -> dict[str, Any]:
    control_avg_raw = control_summary.get("avg_metric_delta")
    treatment_avg_raw = treatment_summary.get("avg_metric_delta")
    control_avg = control_avg_raw if isinstance(control_avg_raw, dict) else {}
    treatment_avg = treatment_avg_raw if isinstance(treatment_avg_raw, dict) else {}
    control_time = control_summary.get("time_to_best")
    treatment_time = treatment_summary.get("time_to_best")
    control_best_score = control_summary.get("best_score")
    treatment_best_score = treatment_summary.get("best_score")
    proposal_accept_rate_lift = round(
        float(treatment_summary.get("proposal_accept_rate", 0.0))
        - float(control_summary.get("proposal_accept_rate", 0.0)),
        4,
    )
    rollback_rate_reduction = round(
        float(control_summary.get("rollback_rate", 0.0))
        - float(treatment_summary.get("rollback_rate", 0.0)),
        4,
    )
    failure_repeat_rate_reduction = round(
        float(control_summary.get("failure_repeat_rate", 0.0))
        - float(treatment_summary.get("failure_repeat_rate", 0.0)),
        4,
    )
    avg_metric_delta_lift = {
        key: round(float(treatment_avg.get(key, 0.0)) - float(control_avg.get(key, 0.0)), 4)
        for key in sorted(set(control_avg) | set(treatment_avg))
    }
    time_to_best_reduction = None
    if (
        _is_plain_number(control_time)
        and _is_plain_number(treatment_time)
        and _is_plain_number(control_best_score)
        and _is_plain_number(treatment_best_score)
        and float(control_best_score) > 0
        and float(treatment_best_score) > 0
    ):
        time_to_best_reduction = int(control_time) - int(treatment_time)

    positives = 0
    negatives = 0
    for value in (
        proposal_accept_rate_lift,
        rollback_rate_reduction,
        failure_repeat_rate_reduction,
        time_to_best_reduction,
        *avg_metric_delta_lift.values(),
    ):
        if value is None:
            continue
        if value > 0:
            positives += 1
        elif value < 0:
            negatives += 1
    if positives > 0 and negatives == 0:
        verdict = "treatment_improved_on_measured_metrics"
    elif negatives > 0 and positives == 0:
        verdict = "treatment_regressed_on_measured_metrics"
    else:
        verdict = "mixed_signal"
    return {
        "control_label": control_summary.get("label"),
        "treatment_label": treatment_summary.get("label"),
        "proposal_accept_rate_lift": proposal_accept_rate_lift,
        "avg_metric_delta_lift": avg_metric_delta_lift,
        "rollback_rate_reduction": rollback_rate_reduction,
        "time_to_best_reduction": time_to_best_reduction,
        "failure_repeat_rate_reduction": failure_repeat_rate_reduction,
        "verdict": verdict,
        "claim_boundary": (
            "local A/B comparison only; does not prove proposal effectiveness across tasks"
        ),
        "official_scores_claimed": False,
    }


def _time_to_best_index(items: list[dict[str, Any]]) -> int | None:
    best_score: float | None = None
    best_index: int | None = None
    for index, item in enumerate(items, start=1):
        score = _outcome_score(item)
        if score is None:
            continue
        if best_score is None or score > best_score:
            best_score = score
            best_index = index
    return best_index


def _outcome_score(item: dict[str, Any] | None) -> float | None:
    if not isinstance(item, dict):
        return None
    metric_delta = item.get("metric_delta")
    if not isinstance(metric_delta, dict):
        return None
    values = [float(value) for value in metric_delta.values() if _is_plain_number(value)]
    if not values:
        return None
    return sum(values)


def _failure_repeat_rate(items: list[dict[str, Any]]) -> float:
    if not items:
        return 0.0
    seen_failures: set[str] = set()
    repeated_outcomes = 0
    for item in items:
        labels = {
            _normalize_failure_type(label)
            for label in _string_list(item.get("failure_labels"))
        }
        if labels and any(label in seen_failures for label in labels):
            repeated_outcomes += 1
        seen_failures.update(labels)
    return round(repeated_outcomes / len(items), 4)


def _load_failure_records(records: list[dict[str, Any]] | str | Path) -> list[dict[str, Any]]:
    if isinstance(records, list):
        return [item for item in records if isinstance(item, dict)]
    path = Path(records)
    if path.suffix == ".jsonl":
        return _load_jsonl_dicts(path)
    payload, _ = _load_object(path)
    if isinstance(payload.get("records"), list):
        return [item for item in payload["records"] if isinstance(item, dict)]
    return [payload]


def _load_pattern_memory(
    patterns: list[dict[str, Any]] | str | Path | None,
) -> list[dict[str, Any]]:
    if patterns is None:
        return []
    if isinstance(patterns, list):
        return [item for item in patterns if isinstance(item, dict)]
    path = Path(patterns)
    if path.suffix == ".jsonl":
        return _load_jsonl_dicts(path)
    payload, _ = _load_object(path)
    if isinstance(payload.get("patterns"), list):
        return [item for item in payload["patterns"] if isinstance(item, dict)]
    return [payload]


def _load_proposals(proposals: list[dict[str, Any]] | str | Path) -> list[dict[str, Any]]:
    if isinstance(proposals, list):
        return [item for item in proposals if isinstance(item, dict)]
    path = Path(proposals)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("proposals"), list):
            return [item for item in payload["proposals"] if isinstance(item, dict)]
        return [payload]
    raise ValueError(f"expected list or object in {path}")


def _load_method_trace_items(
    value: list[dict[str, Any]] | dict[str, Any] | str | Path,
    *,
    list_keys: tuple[str, ...],
) -> tuple[list[dict[str, Any]], Path | None]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)], None
    if isinstance(value, dict):
        return _method_trace_items_from_payload(value, list_keys=list_keys), None
    path = Path(value)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)], path
    if isinstance(payload, dict):
        return _method_trace_items_from_payload(payload, list_keys=list_keys), path
    raise ValueError(f"expected list or object in {path}")


def _method_search_write_payload(
    payload: dict[str, Any],
    *,
    output_path: str | Path | None,
    overwrite: bool,
) -> None:
    if output_path is None:
        return
    output = Path(output_path)
    _ensure_writable(output, overwrite=overwrite)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    payload["output_path"] = str(output)


def _multi_optimizer_candidate_sources(
    candidate_sources: list[dict[str, Any]] | dict[str, Any] | str | Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Path | None]:
    source_items, source_path = _method_search_load_items(
        candidate_sources,
        list_keys=("sources", "candidate_sources", "optimizer_sources"),
    )
    if not source_items:
        proposal_items, proposal_path = _method_search_load_items(
            candidate_sources,
            list_keys=("proposals", "candidates", "candidate_pool"),
        )
        if proposal_items:
            source_items = [{
                "source_id": "flat-candidate-source",
                "optimizer": "unknown",
                "proposals": proposal_items,
            }]
            source_path = proposal_path
    source_rows: list[dict[str, Any]] = []
    candidate_pool: list[dict[str, Any]] = []
    seen_proposal_ids: set[str] = set()
    for source_index, source in enumerate(source_items, start=1):
        source_id = (
            _string_value(source.get("source_id"))
            or _string_value(source.get("id"))
            or f"optimizer-source-{source_index:03d}"
        )
        optimizer = (
            _string_value(source.get("optimizer"))
            or _string_value(source.get("optimizer_name"))
            or _string_value(source.get("kind"))
            or source_id
        )
        proposal_items = _method_trace_items_from_payload(
            source,
            list_keys=("proposals", "candidates", "candidate_pool", "ranked_proposals"),
        )
        source_rows.append({
            "source_id": source_id,
            "optimizer": optimizer,
            "candidate_count": len(proposal_items),
            "executes_tool": bool(source.get("executes_tool", False)),
            "executes_experiment": bool(source.get("executes_experiment", False)),
            "official_scores_claimed": False,
        })
        for proposal_index, proposal in enumerate(proposal_items, start=1):
            normalized = dict(proposal)
            proposal_id = (
                _string_value(normalized.get("proposal_id"))
                or _string_value(normalized.get("patch_id"))
                or f"{source_id}-proposal-{proposal_index:03d}"
            )
            if proposal_id in seen_proposal_ids:
                raise ValueError(f"duplicate proposal_id in race: {proposal_id}")
            seen_proposal_ids.add(proposal_id)
            normalized["proposal_id"] = proposal_id
            normalized.setdefault("optimizer_source", source_id)
            normalized.setdefault("optimizer", optimizer)
            normalized.setdefault("adapter", optimizer)
            normalized.setdefault("source_rank", proposal_index)
            normalized["official_scores_claimed"] = False
            candidate_pool.append(normalized)
    return source_rows, candidate_pool, source_path


def _multi_optimizer_race_winner(
    *,
    study: dict[str, Any],
    candidates: dict[str, dict[str, Any]],
    direction: str,
) -> dict[str, Any] | None:
    completed_trials = [
        trial
        for trial in study.get("trials", [])
        if isinstance(trial, dict) and trial.get("state") == "COMPLETE"
    ]
    scored_trials = [
        trial for trial in completed_trials if _is_plain_number(trial.get("value"))
    ]
    if not scored_trials:
        return None
    reverse = direction != "minimize"
    ranked_trials = sorted(
        scored_trials,
        key=lambda trial: float(trial.get("value", 0.0)),
        reverse=reverse,
    )
    winner_trial = ranked_trials[0]
    proposal_id = str(winner_trial.get("proposal_id"))
    candidate = candidates.get(proposal_id, {})
    params = (
        winner_trial.get("params")
        if isinstance(winner_trial.get("params"), dict)
        else {}
    )
    return {
        "proposal_id": proposal_id,
        "trial_id": winner_trial.get("trial_id"),
        "trial_state": winner_trial.get("state"),
        "score": winner_trial.get("value"),
        "operator_id": params.get("operator"),
        "optimizer_source": candidate.get("optimizer_source"),
        "optimizer": candidate.get("optimizer"),
        "change_surface": candidate.get("change_surface"),
        "selected_by": "gate_score",
        "official_scores_claimed": False,
    }


def _multi_optimizer_race_acceptance_answers(
    *,
    candidate_sources: list[dict[str, Any]],
    candidate_pool: list[dict[str, Any]],
    winner: dict[str, Any] | None,
    study: dict[str, Any],
    missing_gate_proposal_ids: list[str],
) -> dict[str, Any]:
    trials = [
        trial for trial in study.get("trials", []) if isinstance(trial, dict)
    ]
    selected_proposal_ids = [
        str(trial.get("proposal_id"))
        for trial in trials
        if trial.get("state") == "COMPLETE"
    ]
    pruned_proposal_ids = [
        str(trial.get("proposal_id"))
        for trial in trials
        if trial.get("state") == "PRUNED"
    ]
    blocked_proposal_ids = [
        str(trial.get("proposal_id"))
        for trial in trials
        if trial.get("state") in {"FAIL", "WAITING"}
    ]
    return {
        "optimizer_sources_used": [
            source["optimizer"] for source in candidate_sources
        ],
        "candidate_count": len(candidate_pool),
        "method_search_trial_count": len(trials),
        "winner_selected_by_gate": winner is not None,
        "winner_proposal_id": winner.get("proposal_id") if winner else None,
        "selected_proposal_ids": selected_proposal_ids,
        "pruned_proposal_ids": pruned_proposal_ids,
        "blocked_proposal_ids": blocked_proposal_ids,
        "proposal_selection": {
            "winner_proposal_id": winner.get("proposal_id") if winner else None,
            "selected_candidate_ids": selected_proposal_ids,
            "pruned_candidate_ids": pruned_proposal_ids,
            "blocked_candidate_ids": blocked_proposal_ids,
        },
        "missing_gate_proposal_ids": missing_gate_proposal_ids,
        "gate_feedback_returned_to_sampler_memory": bool(
            study.get("sampler_state", {}).get("gate_feedback_memory")
            if isinstance(study.get("sampler_state"), dict)
            else False
        ),
        "claim_boundary": {
            "evidence_scope": "local_gate_only",
            "official_scores_claimed": False,
            "llm_may_claim_improvement": False,
        },
    }


def _multi_optimizer_source_names(source_names: list[str] | None) -> list[str]:
    raw_names = source_names or list(DEFAULT_MULTI_OPTIMIZER_SOURCES)
    normalized: list[str] = []
    seen: set[str] = set()
    aliases = {
        "llm-hexagon": "llm",
        "optuna-tpe": "optuna",
        "textgrad-package": "textgrad",
        "dspy-mipro": "dspy",
        "manual": "heuristic",
        "manual-template": "heuristic",
    }
    for raw in raw_names:
        source_name = aliases.get(str(raw).strip().lower(), str(raw).strip().lower())
        if not source_name or source_name in seen:
            continue
        seen.add(source_name)
        normalized.append(source_name)
    return normalized


def _multi_optimizer_run_mode(mode: str | None) -> str:
    normalized = (mode or "optimization-run").strip().lower()
    if normalized in {"review", "dry-run", "dry_run", "review/dry-run"}:
        return "review/dry-run"
    if normalized in {"optimization", "optimization-run", "optimize"}:
        return "optimization-run"
    raise ValueError(f"unsupported multi optimizer run mode: {mode}")


def _multi_optimizer_execute_runtime_default(
    *,
    mode: str,
    requested: bool | None,
) -> bool:
    if requested is not None:
        return bool(requested)
    return mode == "optimization-run"


def _multi_optimizer_execute_llm_default(
    *,
    mode: str,
    requested: bool | None,
    endpoint_configured: bool,
) -> bool:
    if requested is not None:
        return bool(requested)
    return mode == "optimization-run" and endpoint_configured


def _multi_optimizer_style_fallback_default(
    *,
    mode: str,
    requested: bool | None,
) -> bool:
    if requested is not None:
        return bool(requested)
    return mode == "review/dry-run"


def _run_multi_optimizer_candidate_source(
    *,
    source_name: str,
    source_index: int,
    objective: str,
    context: dict[str, Any],
    mode: str,
    operators: list[str | dict[str, Any]] | None,
    direction: str,
    max_candidates: int,
    execute_llm: bool,
    llm_proposals: list[dict[str, Any]] | dict[str, Any] | str | Path | None,
    llm_completion_fn: Callable[..., dict[str, Any]] | None,
    gate_feedback_memory: dict[str, Any] | str | Path | None,
    execute_optimizer_runtimes: bool,
    allow_style_fallback: bool,
    optimizer_gate_plugin_manifests: list[dict[str, Any] | str | Path] | None,
    optimizer_model: str | None,
    optimizer_base_url: str | None,
    optimizer_api_key: str | None,
    optimizer_timeout_seconds: int,
    optimizer_temperature: float,
    optimizer_max_tokens: int,
    output_dir: Path | None,
    overwrite: bool,
) -> dict[str, Any]:
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
    try:
        if source_name == "llm":
            return _multi_optimizer_llm_source(
                source_index=source_index,
                objective=objective,
                operators=operators,
                max_candidates=max_candidates,
                mode=mode,
                execute_llm=execute_llm,
                llm_proposals=llm_proposals,
                llm_completion_fn=llm_completion_fn,
                gate_feedback_memory=gate_feedback_memory,
                allow_style_fallback=allow_style_fallback,
                optimizer_model=optimizer_model,
                optimizer_base_url=optimizer_base_url,
                optimizer_api_key=optimizer_api_key,
                optimizer_timeout_seconds=optimizer_timeout_seconds,
                optimizer_temperature=optimizer_temperature,
                optimizer_max_tokens=optimizer_max_tokens,
                output_dir=output_dir,
                overwrite=overwrite,
            )
        if source_name == "optuna":
            return _multi_optimizer_optuna_source(
                source_index=source_index,
                objective=objective,
                operators=operators,
                direction=direction,
                execute_optimizer_runtimes=execute_optimizer_runtimes,
                allow_style_fallback=allow_style_fallback,
                output_dir=output_dir,
                overwrite=overwrite,
            )
        if source_name == "textgrad":
            return _multi_optimizer_slice_candidate_source(
                source_id="textgrad",
                source_index=source_index,
                optimizer="textgrad",
                operator_id="adapt",
                objective=objective,
                context=context,
                primary_adapter="textgrad-python-package",
                fallback_adapter="textgrad-local",
                execute_optimizer_runtimes=execute_optimizer_runtimes,
                allow_style_fallback=allow_style_fallback,
                max_candidates=max_candidates,
                optimizer_gate_plugin_manifests=optimizer_gate_plugin_manifests,
                optimizer_model=optimizer_model,
                optimizer_base_url=optimizer_base_url,
                optimizer_api_key=optimizer_api_key,
                optimizer_timeout_seconds=optimizer_timeout_seconds,
                optimizer_temperature=optimizer_temperature,
                optimizer_max_tokens=optimizer_max_tokens,
                output_dir=output_dir,
                overwrite=overwrite,
            )
        if source_name == "dspy":
            return _multi_optimizer_dspy_source(
                source_index=source_index,
                objective=objective,
                context=context,
                execute_optimizer_runtimes=execute_optimizer_runtimes,
                allow_style_fallback=allow_style_fallback,
                max_candidates=max_candidates,
                optimizer_gate_plugin_manifests=optimizer_gate_plugin_manifests,
                optimizer_timeout_seconds=optimizer_timeout_seconds,
                output_dir=output_dir,
                overwrite=overwrite,
            )
        if source_name == "promptwizard":
            return _multi_optimizer_slice_candidate_source(
                source_id="promptwizard",
                source_index=source_index,
                optimizer="promptwizard",
                operator_id="adapt",
                objective=objective,
                context=context,
                primary_adapter="promptwizard-python-package",
                fallback_adapter="promptwizard-adapter",
                execute_optimizer_runtimes=execute_optimizer_runtimes,
                allow_style_fallback=allow_style_fallback,
                max_candidates=max_candidates,
                optimizer_gate_plugin_manifests=optimizer_gate_plugin_manifests,
                optimizer_model=optimizer_model,
                optimizer_base_url=optimizer_base_url,
                optimizer_api_key=optimizer_api_key,
                optimizer_timeout_seconds=optimizer_timeout_seconds,
                optimizer_temperature=optimizer_temperature,
                optimizer_max_tokens=optimizer_max_tokens,
                output_dir=output_dir,
                overwrite=overwrite,
            )
        if source_name == "heuristic":
            return _multi_optimizer_slice_candidate_source(
                source_id="heuristic",
                source_index=source_index,
                optimizer="heuristic",
                operator_id="separate",
                objective=objective,
                context=context,
                primary_adapter="manual-template",
                fallback_adapter=None,
                execute_optimizer_runtimes=False,
                allow_style_fallback=True,
                max_candidates=max_candidates,
                optimizer_gate_plugin_manifests=optimizer_gate_plugin_manifests,
                optimizer_model=optimizer_model,
                optimizer_base_url=optimizer_base_url,
                optimizer_api_key=optimizer_api_key,
                optimizer_timeout_seconds=optimizer_timeout_seconds,
                optimizer_temperature=optimizer_temperature,
                optimizer_max_tokens=optimizer_max_tokens,
                output_dir=output_dir,
                overwrite=overwrite,
            )
        try:
            resolve_optimizer_adapter(
                source_name,
                plugin_manifests=optimizer_gate_plugin_manifests,
            )
        except ValueError:
            pass
        else:
            return _multi_optimizer_slice_candidate_source(
                source_id=source_name,
                source_index=source_index,
                optimizer=source_name,
                operator_id="adapt",
                objective=objective,
                context=context,
                primary_adapter=source_name,
                fallback_adapter=None,
                execute_optimizer_runtimes=execute_optimizer_runtimes,
                allow_style_fallback=False,
                max_candidates=max_candidates,
                optimizer_gate_plugin_manifests=optimizer_gate_plugin_manifests,
                optimizer_model=optimizer_model,
                optimizer_base_url=optimizer_base_url,
                optimizer_api_key=optimizer_api_key,
                optimizer_timeout_seconds=optimizer_timeout_seconds,
                optimizer_temperature=optimizer_temperature,
                optimizer_max_tokens=optimizer_max_tokens,
                output_dir=output_dir,
                overwrite=overwrite,
            )
        return _multi_optimizer_source_record(
            source_id=f"{source_name}-{source_index:03d}",
            optimizer=source_name,
            status="blocked",
            generator="unsupported_optimizer_source",
            proposals=[],
            hard_blockers=[f"unsupported_optimizer_source:{source_name}"],
        )
    except Exception as exc:
        return _multi_optimizer_source_record(
            source_id=f"{source_name}-{source_index:03d}",
            optimizer=source_name,
            status="source_failed",
            generator="multi_optimizer_source_runner",
            proposals=[],
            hard_blockers=[f"{type(exc).__name__}: {exc}"],
        )


def _multi_optimizer_llm_source(
    *,
    source_index: int,
    objective: str,
    operators: list[str | dict[str, Any]] | None,
    max_candidates: int,
    mode: str,
    execute_llm: bool,
    llm_proposals: list[dict[str, Any]] | dict[str, Any] | str | Path | None,
    llm_completion_fn: Callable[..., dict[str, Any]] | None,
    gate_feedback_memory: dict[str, Any] | str | Path | None,
    allow_style_fallback: bool,
    optimizer_model: str | None,
    optimizer_base_url: str | None,
    optimizer_api_key: str | None,
    optimizer_timeout_seconds: int,
    optimizer_temperature: float,
    optimizer_max_tokens: int,
    output_dir: Path | None,
    overwrite: bool,
) -> dict[str, Any]:
    source_id = f"llm-{source_index:03d}"
    if mode == "optimization-run" and not execute_llm and not allow_style_fallback:
        return _multi_optimizer_source_record(
            source_id=source_id,
            optimizer="llm",
            status="blocked",
            generator="HexagonGuidedLLMSampler",
            proposals=[],
            runtime={
                "execute_llm": False,
                "endpoint_configured": False,
                "input_mode": "not_configured",
            },
            hard_blockers=["llm_endpoint_not_configured"],
        )
    sampler_path = output_dir / "hexagon-guided-llm-sampler.json" if output_dir else None
    sampler = sample_hexagon_guided_llm_proposals(
        objective=objective,
        operators=operators,
        gate_feedback_memory=gate_feedback_memory,
        llm_proposals=llm_proposals,
        model=optimizer_model or "llm-method-search",
        execute_llm=execute_llm,
        llm_base_url=optimizer_base_url or DEFAULT_TEXTGRAD_OPTIMIZER_BASE_URL,
        llm_api_key_env=optimizer_api_key,
        llm_temperature=optimizer_temperature,
        llm_max_tokens=optimizer_max_tokens,
        llm_timeout_seconds=optimizer_timeout_seconds,
        llm_completion_fn=llm_completion_fn,
        max_selected=max(1, int(max_candidates)),
        output_path=sampler_path,
        overwrite=overwrite,
    )
    selected_ids = set(_string_list(sampler.get("selected_proposal_ids")))
    proposals = [
        _multi_optimizer_prepare_method_proposal(
            proposal,
            source_id=source_id,
            optimizer="llm",
            adapter="HexagonGuidedLLMSampler",
        )
        for proposal in _dict_list(sampler.get("proposals"))
        if str(proposal.get("proposal_id")) in selected_ids
    ]
    llm_generation = (
        sampler.get("llm_generation")
        if isinstance(sampler.get("llm_generation"), dict)
        else {}
    )
    counts_as_real = bool(
        execute_llm and llm_generation.get("input_mode") == "live_llm"
    )
    candidate_origin = (
        "real_optimizer" if counts_as_real else "provided_artifact_diagnostic"
    )
    return _multi_optimizer_source_record(
        source_id=source_id,
        optimizer="llm",
        status="generated" if proposals else "blocked",
        generator="HexagonGuidedLLMSampler",
        proposals=proposals,
        artifacts=_method_search_artifact_refs(sampler_path=sampler_path),
        executes_tool=bool(sampler.get("executes_tool", False)),
        executes_optimizer_runtime=bool(execute_llm),
        runtime={
            "input_mode": llm_generation.get("input_mode"),
            "uses_llm": bool(llm_generation.get("uses_llm", True)),
            "execute_llm": execute_llm,
        },
        hard_blockers=[] if proposals else ["llm_candidate_generation_empty"],
        candidate_origin=candidate_origin,
        counts_as_real_optimizer_candidate=counts_as_real,
    )


def _multi_optimizer_optuna_source(
    *,
    source_index: int,
    objective: str,
    operators: list[str | dict[str, Any]] | None,
    direction: str,
    execute_optimizer_runtimes: bool,
    allow_style_fallback: bool,
    output_dir: Path | None,
    overwrite: bool,
) -> dict[str, Any]:
    source_id = f"optuna-{source_index:03d}"
    operator_ids = [
        str(item["operator_id"])
        for item in _method_search_operator_taxonomy(operators)["operators"]
    ]
    selected_operator = "combine" if "combine" in operator_ids else operator_ids[0]
    runtime: dict[str, Any] = {
        "package_import": "optuna",
        "package_available": importlib.util.find_spec("optuna") is not None,
        "executed": False,
        "fallback_used": False,
        "optuna_package_integrated_as_main_path": False,
    }
    _ensure_optimizer_runtime_cache_paths("optuna")
    runtime["package_available"] = importlib.util.find_spec("optuna") is not None
    if runtime["package_available"]:
        try:
            runtime["package_version"] = importlib.metadata.version("optuna")
        except importlib.metadata.PackageNotFoundError:
            runtime["package_version"] = None
    hard_blockers: list[str] = []
    if execute_optimizer_runtimes and runtime["package_available"]:
        started = time.perf_counter()
        optuna_module = importlib.import_module("optuna")
        optuna_study = optuna_module.create_study(direction=direction)
        trial = optuna_study.ask()
        selected_operator = trial.suggest_categorical("operator", operator_ids)
        risk_budget = trial.suggest_float("risk_budget", 0.1, 1.0)
        optuna_study.tell(trial, 0.0)
        runtime.update({
            "status": "executed",
            "executed": True,
            "study_direction": direction,
            "trial_number": trial.number,
            "suggested_params": {
                "operator": selected_operator,
                "risk_budget": round(float(risk_budget), 4),
            },
            "duration_seconds": _duration_seconds_since(started),
        })
        status = "generated"
        executes_tool = True
    elif allow_style_fallback:
        runtime["status"] = "fallback_generated"
        runtime["fallback_used"] = True
        status = "fallback_generated"
        executes_tool = False
        if execute_optimizer_runtimes:
            hard_blockers.append("optuna_package_not_importable")
    else:
        runtime["status"] = "not_ready"
        status = "blocked"
        executes_tool = False
        hard_blockers.append("optuna_package_not_importable")
    proposals = []
    if status != "blocked":
        counts_as_real = bool(runtime.get("executed", False))
        proposals.append(
            _multi_optimizer_method_proposal(
                proposal_id="optuna-001",
                operator_id=selected_operator,
                optimizer="optuna",
                adapter="OptunaSamplerAdapter",
                objective=objective,
                why=(
                    "Optuna-style search applies because this candidate treats "
                    "operator and budget choices as trial parameters."
                ),
                hypothesis=(
                    "A gate-backed Optuna-style trial may reveal whether this "
                    "operator/budget setting is better than other sources."
                ),
                change_surface="method_search_trial_params",
                expected_effect="gate score decides whether the sampled setting helps",
                risk="local trial parameters may overfit the current validation slice",
                cheapest_validation="run the same local gate used by other candidates",
                rollback="prune on hard blocker or non-positive local gate delta",
                extra={
                    "optimizer_runtime": runtime,
                    "fallback_used": bool(runtime.get("fallback_used", False)),
                    "candidate_origin": (
                        "real_optimizer"
                        if counts_as_real
                        else "fallback_diagnostic"
                    ),
                    "counts_as_real_optimizer_candidate": counts_as_real,
                },
            )
        )
    source_path = output_dir / "optuna-source.json" if output_dir else None
    source = _multi_optimizer_source_record(
        source_id=source_id,
        optimizer="optuna",
        status=status,
        generator="OptunaSamplerAdapter",
        proposals=proposals,
        executes_tool=executes_tool,
        executes_optimizer_runtime=bool(runtime.get("executed", False)),
        fallback_used=bool(runtime.get("fallback_used", False)),
        runtime=runtime,
        hard_blockers=hard_blockers,
    )
    _method_search_write_payload(source, output_path=source_path, overwrite=overwrite)
    if source_path is not None:
        source["artifact_refs"] = _method_search_artifact_refs(source_path=source_path)
    return source


def _multi_optimizer_slice_candidate_source(
    *,
    source_id: str,
    source_index: int,
    optimizer: str,
    operator_id: str,
    objective: str,
    context: dict[str, Any],
    primary_adapter: str,
    fallback_adapter: str | None,
    execute_optimizer_runtimes: bool,
    allow_style_fallback: bool,
    max_candidates: int,
    optimizer_gate_plugin_manifests: list[dict[str, Any] | str | Path] | None,
    optimizer_model: str | None,
    optimizer_base_url: str | None,
    optimizer_api_key: str | None,
    optimizer_timeout_seconds: int,
    optimizer_temperature: float,
    optimizer_max_tokens: int,
    output_dir: Path | None,
    overwrite: bool,
) -> dict[str, Any]:
    full_source_id = f"{source_id}-{source_index:03d}"
    primary_path = output_dir / "slice-patch-candidates.primary.json" if output_dir else None
    primary_execute = bool(execute_optimizer_runtimes and primary_adapter != "manual-template")
    adapter_to_run = primary_adapter
    if primary_adapter == "manual-template":
        primary_execute = False
    primary = generate_slice_patch_candidates(
        context=context,
        optimizer=adapter_to_run,
        optimizer_gate_plugin_manifests=optimizer_gate_plugin_manifests,
        max_candidates=max(1, int(max_candidates)),
        execute_optimizer=primary_execute,
        optimizer_model=optimizer_model,
        optimizer_base_url=optimizer_base_url,
        optimizer_api_key=optimizer_api_key,
        optimizer_timeout_seconds=optimizer_timeout_seconds,
        optimizer_temperature=optimizer_temperature,
        optimizer_max_tokens=optimizer_max_tokens,
        output_path=primary_path,
        overwrite=overwrite,
    )
    candidate_payload = primary
    fallback_used = False
    hard_blockers = _string_list(
        primary.get("hard_blockers")
        if isinstance(primary.get("hard_blockers"), list)
        else []
    )
    optimizer_error = (
        primary.get("optimizer_error")
        if isinstance(primary.get("optimizer_error"), dict)
        else {}
    )
    if optimizer_error:
        hard_blockers.append(
            _string_value(optimizer_error.get("type")) or "optimizer_runtime_error"
        )
    if (
        not _dict_list(primary.get("candidates"))
        and allow_style_fallback
        and fallback_adapter
    ):
        fallback_path = (
            output_dir / "slice-patch-candidates.fallback.json" if output_dir else None
        )
        candidate_payload = generate_slice_patch_candidates(
            context=context,
            optimizer=fallback_adapter,
            optimizer_gate_plugin_manifests=optimizer_gate_plugin_manifests,
            max_candidates=max(1, int(max_candidates)),
            execute_optimizer=False,
            optimizer_model=optimizer_model,
            optimizer_base_url=optimizer_base_url,
            optimizer_api_key=optimizer_api_key,
            optimizer_timeout_seconds=optimizer_timeout_seconds,
            optimizer_temperature=optimizer_temperature,
            optimizer_max_tokens=optimizer_max_tokens,
            output_path=fallback_path,
            overwrite=overwrite,
        )
        fallback_used = True
    proposals = [
        _multi_optimizer_method_proposal_from_slice_candidate(
            candidate=candidate,
            proposal_id=f"{source_id}-{index:03d}",
            source_id=full_source_id,
            optimizer=optimizer,
            adapter=_string_value(candidate_payload.get("optimizer")) or primary_adapter,
            operator_id=operator_id,
            objective=objective,
            fallback_used=fallback_used,
            candidate_origin=(
                "real_optimizer"
                if bool(candidate_payload.get("executes_optimizer_runtime", False))
                and not fallback_used
                else (
                    "heuristic_control"
                    if primary_adapter == "manual-template"
                    else "fallback_diagnostic"
                )
            ),
            counts_as_real_optimizer_candidate=bool(
                candidate_payload.get("executes_optimizer_runtime", False)
            )
            and not fallback_used,
        )
        for index, candidate in enumerate(
            _dict_list(candidate_payload.get("candidates")),
            start=1,
        )
    ]
    status = "generated" if proposals else "blocked"
    if fallback_used and proposals:
        status = "fallback_generated"
    artifact_refs = _method_search_artifact_refs(
        primary_candidates_path=primary_path,
        fallback_candidates_path=(
            output_dir / "slice-patch-candidates.fallback.json"
            if output_dir is not None and fallback_used
            else None
        ),
    )
    return _multi_optimizer_source_record(
        source_id=full_source_id,
        optimizer=optimizer,
        status=status,
        generator=primary_adapter,
        proposals=proposals,
        artifacts=artifact_refs,
        executes_tool=bool(candidate_payload.get("executes_tool", False)),
        executes_optimizer_runtime=bool(
            candidate_payload.get("executes_optimizer_runtime", False)
        ),
        fallback_used=fallback_used,
        runtime=(
            candidate_payload.get("optimizer_runtime")
            if isinstance(candidate_payload.get("optimizer_runtime"), dict)
            else {}
        ),
        hard_blockers=[] if proposals else hard_blockers or ["candidate_generation_empty"],
    )


def _multi_optimizer_dspy_source(
    *,
    source_index: int,
    objective: str,
    context: dict[str, Any],
    execute_optimizer_runtimes: bool,
    allow_style_fallback: bool,
    max_candidates: int,
    optimizer_gate_plugin_manifests: list[dict[str, Any] | str | Path] | None,
    optimizer_timeout_seconds: int,
    output_dir: Path | None,
    overwrite: bool,
) -> dict[str, Any]:
    source_id = f"dspy-{source_index:03d}"
    proposals: list[dict[str, Any]] = []
    hard_blockers: list[str] = []
    runtime: dict[str, Any] = {
        "package_import": "dspy",
        "package_available": importlib.util.find_spec("dspy") is not None,
        "executed": False,
        "fallback_used": False,
    }
    artifact_refs: list[dict[str, str]] = []
    if execute_optimizer_runtimes:
        candidates_path = output_dir / "slice-patch-candidates.primary.json" if output_dir else None
        candidate_payload = generate_slice_patch_candidates(
            context=context,
            optimizer="dspy-mipro-package",
            optimizer_gate_plugin_manifests=optimizer_gate_plugin_manifests,
            max_candidates=max(1, int(max_candidates)),
            execute_optimizer=True,
            optimizer_timeout_seconds=optimizer_timeout_seconds,
            output_path=candidates_path,
            overwrite=overwrite,
        )
        artifact_refs.extend(_method_search_artifact_refs(candidates_path=candidates_path))
        runtime.update(
            candidate_payload.get("optimizer_runtime")
            if isinstance(candidate_payload.get("optimizer_runtime"), dict)
            else {}
        )
        optimizer_error = (
            candidate_payload.get("optimizer_error")
            if isinstance(candidate_payload.get("optimizer_error"), dict)
            else {}
        )
        if optimizer_error:
            hard_blockers.append(
                _string_value(optimizer_error.get("type")) or "dspy_runtime_error"
            )
        proposals.extend(
            _multi_optimizer_method_proposal_from_slice_candidate(
                candidate=candidate,
                proposal_id=f"dspy-{index:03d}",
                source_id=source_id,
                optimizer="dspy",
                adapter="dspy-mipro-package",
                operator_id="combine",
                objective=objective,
                fallback_used=False,
                candidate_origin="real_optimizer",
                counts_as_real_optimizer_candidate=True,
            )
            for index, candidate in enumerate(
                _dict_list(candidate_payload.get("candidates")),
                start=1,
            )
        )
    if not proposals and allow_style_fallback:
        contract = (
            context.get("recommended_patch_contract")
            if isinstance(context.get("recommended_patch_contract"), dict)
            else {}
        )
        for index in range(1, max(1, int(max_candidates)) + 1):
            proposals.append(
                _multi_optimizer_method_proposal(
                    proposal_id=f"dspy-{index:03d}",
                    operator_id="combine",
                    optimizer="dspy",
                    adapter="dspy-mipro-style-fallback",
                    objective=objective,
                    why=(
                        "DSPy/MIPRO-style composition applies because this "
                        "candidate combines a signature-like patch target with "
                        "bounded prompt-section constraints."
                    ),
                    hypothesis=(
                        "A DSPy-style structured prompt candidate may improve the "
                        "target slice if the shared gate validates it."
                    ),
                    change_surface="prompt_section",
                    expected_effect="gate score decides whether the structured candidate helps",
                    risk="style fallback is not a real DSPy package optimization run",
                    cheapest_validation="run the same local gate used by other candidates",
                    rollback="stop on hard blocker or non-positive local gate delta",
                    extra={
                        "target_slice": _string_value(contract.get("target_slice")),
                        "fallback_used": True,
                        "candidate_origin": "fallback_diagnostic",
                        "counts_as_real_optimizer_candidate": False,
                    },
                )
            )
        runtime["fallback_used"] = True
    status = "generated" if proposals else "blocked"
    if runtime.get("fallback_used") and proposals:
        status = "fallback_generated"
    return _multi_optimizer_source_record(
        source_id=source_id,
        optimizer="dspy",
        status=status,
        generator="dspy-mipro-package",
        proposals=proposals,
        artifacts=artifact_refs,
        executes_tool=bool(runtime.get("executed", False)),
        executes_optimizer_runtime=bool(runtime.get("executed", False)),
        fallback_used=bool(runtime.get("fallback_used", False)),
        runtime=runtime,
        hard_blockers=[] if proposals else hard_blockers or ["dspy_candidate_generation_empty"],
    )


def _multi_optimizer_prepare_method_proposal(
    proposal: dict[str, Any],
    *,
    source_id: str,
    optimizer: str,
    adapter: str,
) -> dict[str, Any]:
    normalized = dict(proposal)
    normalized["optimizer_source"] = source_id
    normalized["optimizer"] = optimizer
    normalized["adapter"] = adapter
    normalized["official_scores_claimed"] = False
    return normalized


def _multi_optimizer_method_proposal_from_slice_candidate(
    *,
    candidate: dict[str, Any],
    proposal_id: str,
    source_id: str,
    optimizer: str,
    adapter: str,
    operator_id: str,
    objective: str,
    fallback_used: bool,
    candidate_origin: str,
    counts_as_real_optimizer_candidate: bool,
) -> dict[str, Any]:
    module_id = _string_value(candidate.get("module_id")) or "module"
    section_id = _string_value(candidate.get("section_id")) or "section"
    expected = (
        candidate.get("expected_effect")
        if isinstance(candidate.get("expected_effect"), dict)
        else {}
    )
    based_on_slices = _string_list(candidate.get("based_on_slices"))
    target_slice = _string_value(expected.get("primary_slice"))
    if not target_slice and based_on_slices:
        target_slice = _slice_name_from_key(based_on_slices[0])
    if not target_slice:
        target_slice = "target slice"
    return _multi_optimizer_method_proposal(
        proposal_id=proposal_id,
        operator_id=operator_id,
        optimizer=optimizer,
        adapter=adapter,
        objective=objective,
        why=(
            f"{operator_id} applies because {optimizer} generated a bounded "
            f"{module_id}/{section_id} candidate for {target_slice}."
        ),
        hypothesis=(
            f"The {optimizer} candidate may improve {target_slice} only if the "
            "shared gate validates it."
        ),
        change_surface=_string_value(candidate.get("change_surface")) or "prompt_section",
        expected_effect=(
            f"target {target_slice}; gate result is the only accepted effect evidence"
        ),
        risk=(
            "candidate may overfit local slice evidence"
            if not fallback_used
            else "style fallback did not execute the real optimizer package"
        ),
        cheapest_validation="run the same local gate used by all optimizer sources",
        rollback="prune on hard blocker or non-positive local gate delta",
        extra={
            "slice_patch_candidate": candidate,
            "slice_patch_candidate_id": (
                _string_value(candidate.get("patch_id")) or proposal_id
            ),
            "fallback_used": fallback_used,
            "candidate_origin": candidate_origin,
            "counts_as_real_optimizer_candidate": counts_as_real_optimizer_candidate,
        },
    ) | {
        "optimizer_source": source_id,
    }


def _multi_optimizer_method_proposal(
    *,
    proposal_id: str,
    operator_id: str,
    optimizer: str,
    adapter: str,
    objective: str,
    why: str,
    hypothesis: str,
    change_surface: str,
    expected_effect: str,
    risk: str,
    cheapest_validation: str,
    rollback: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "proposal_id": proposal_id,
        "operator_id": operator_id,
        "why_this_operator_applies": why,
        "hypothesis": hypothesis,
        "change_surface": change_surface,
        "expected_effect": expected_effect,
        "risk": risk,
        "cheapest_validation": cheapest_validation,
        "rollback_or_stop_condition": rollback,
        "method": "multi_optimizer_candidate",
        "objective": objective,
        "optimizer": optimizer,
        "adapter": adapter,
        "target_scope": change_surface,
        "official_scores_claimed": False,
    }
    if extra:
        payload.update(extra)
    return payload


def _multi_optimizer_source_record(
    *,
    source_id: str,
    optimizer: str,
    status: str,
    generator: str,
    proposals: list[dict[str, Any]],
    artifacts: list[dict[str, str]] | None = None,
    executes_tool: bool = False,
    executes_optimizer_runtime: bool = False,
    fallback_used: bool = False,
    runtime: dict[str, Any] | None = None,
    hard_blockers: list[str] | None = None,
    candidate_origin: str | None = None,
    counts_as_real_optimizer_candidate: bool | None = None,
) -> dict[str, Any]:
    normalized_proposals = []
    for proposal in proposals:
        normalized = dict(proposal)
        if candidate_origin is not None:
            normalized.setdefault("candidate_origin", candidate_origin)
        if counts_as_real_optimizer_candidate is not None:
            normalized.setdefault(
                "counts_as_real_optimizer_candidate",
                bool(counts_as_real_optimizer_candidate),
            )
        normalized_proposals.append(normalized)
    real_candidate_count = _multi_optimizer_real_candidate_count(normalized_proposals)
    fallback_candidate_count = _multi_optimizer_fallback_candidate_count(
        normalized_proposals
    )
    return {
        "source_id": source_id,
        "optimizer": optimizer,
        "status": status,
        "generator": generator,
        "candidate_count": len(normalized_proposals),
        "real_optimizer_candidate_count": real_candidate_count,
        "fallback_candidate_count": fallback_candidate_count,
        "diagnostic_candidate_count": max(
            0,
            len(normalized_proposals) - real_candidate_count,
        ),
        "proposals": normalized_proposals,
        "artifact_refs": artifacts or [],
        "runtime": runtime or {},
        "fallback_used": fallback_used,
        "hard_blockers": _dedupe_strings(hard_blockers or []),
        "executes_tool": executes_tool,
        "executes_optimizer_runtime": executes_optimizer_runtime,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }


def _multi_optimizer_real_candidate_count(
    candidate_pool: list[dict[str, Any]],
) -> int:
    return sum(
        1
        for candidate in candidate_pool
        if bool(candidate.get("counts_as_real_optimizer_candidate", False))
    )


def _multi_optimizer_fallback_candidate_count(
    candidate_pool: list[dict[str, Any]],
) -> int:
    return sum(
        1
        for candidate in candidate_pool
        if bool(candidate.get("fallback_used", False))
        or _string_value(candidate.get("candidate_origin")) == "fallback_diagnostic"
    )


def _multi_optimizer_run_winner(
    *,
    race_payload: dict[str, Any] | None,
    candidate_pool: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not isinstance(race_payload, dict):
        return None
    winner = (
        race_payload.get("winner")
        if isinstance(race_payload.get("winner"), dict)
        else None
    )
    if winner is None:
        return None
    candidates = {
        str(candidate.get("proposal_id")): candidate
        for candidate in candidate_pool
        if isinstance(candidate, dict)
    }
    candidate = candidates.get(str(winner.get("proposal_id")), {})
    enriched = dict(winner)
    counts_as_real = bool(candidate.get("counts_as_real_optimizer_candidate", False))
    fallback_used = bool(candidate.get("fallback_used", False))
    candidate_origin = (
        _string_value(candidate.get("candidate_origin"))
        or ("fallback_diagnostic" if fallback_used else "unknown_candidate")
    )
    enriched["candidate_origin"] = candidate_origin
    enriched["fallback_used"] = fallback_used
    enriched["counts_as_real_optimizer_winner"] = counts_as_real
    enriched["winner_kind"] = (
        "optimizer_winner" if counts_as_real else "local_diagnostic_winner"
    )
    return enriched


def _multi_optimizer_generation_reasoning_trace(
    source_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "trace_kind": "multi_optimizer_structured_generation_trace",
        "records_private_chain_of_thought": False,
        "steps": [
            {
                "step_id": f"source-{index:03d}",
                "optimizer": _string_value(source.get("optimizer")),
                "source_id": _string_value(source.get("source_id")),
                "status": _string_value(source.get("status")),
                "proposal_ids": [
                    str(proposal.get("proposal_id"))
                    for proposal in _dict_list(source.get("proposals"))
                ],
                "summary": (
                    "source generated candidates for shared gate evaluation"
                    if _dict_list(source.get("proposals"))
                    else "source produced no candidate and cannot compete this round"
                ),
                "hard_blockers": _string_list(source.get("hard_blockers")),
                "fallback_used": bool(source.get("fallback_used", False)),
            }
            for index, source in enumerate(source_rows, start=1)
        ],
        "self_critique": [
            "source generation is not improvement evidence",
            "winner must be selected by downstream gate/tell result",
        ],
    }


def _multi_optimizer_generation_ranking_decisions(
    candidate_pool: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "proposal_id": str(candidate.get("proposal_id")),
            "rank": index,
            "decision": "selected_for_gate_race",
            "score": 0.0,
            "operator_id": str(candidate.get("operator_id")),
            "rationale": "all generated candidates enter the shared gate race",
        }
        for index, candidate in enumerate(candidate_pool, start=1)
    ]


def _multi_optimizer_run_status(
    *,
    race_payload: dict[str, Any] | None,
    candidate_count: int,
    blocked_source_count: int,
) -> str:
    if candidate_count <= 0:
        return "candidate_generation_blocked"
    if not isinstance(race_payload, dict):
        return "waiting_for_gate_feedback"
    if race_payload.get("status") != "completed":
        return str(race_payload.get("status") or "waiting_for_gate_feedback")
    if blocked_source_count:
        return "completed_with_source_gaps"
    return "completed"


def _multi_optimizer_run_acceptance_answers(
    *,
    source_rows: list[dict[str, Any]],
    candidate_pool: list[dict[str, Any]],
    race_payload: dict[str, Any] | None,
    mode: str,
    execute_optimizer_runtimes: bool,
    allow_style_fallback: bool,
) -> dict[str, Any]:
    race_answers = (
        race_payload.get("acceptance_answers")
        if isinstance(race_payload, dict)
        and isinstance(race_payload.get("acceptance_answers"), dict)
        else {}
    )
    proposal_selection = (
        race_answers.get("proposal_selection")
        if isinstance(race_answers.get("proposal_selection"), dict)
        else {
            "winner_proposal_id": race_answers.get("winner_proposal_id"),
            "selected_candidate_ids": _string_list(
                race_answers.get("selected_proposal_ids")
            ),
            "pruned_candidate_ids": _string_list(
                race_answers.get("pruned_proposal_ids")
            ),
            "blocked_candidate_ids": _string_list(
                race_answers.get("blocked_proposal_ids")
            ),
        }
    )
    return {
        "mode": mode,
        "optimizer_sources_tried": [
            _string_value(source.get("optimizer")) for source in source_rows
        ],
        "parallel_generation_used": len(source_rows) > 1,
        "execute_optimizer_runtimes_requested": execute_optimizer_runtimes,
        "style_fallback_allowed": allow_style_fallback,
        "real_optimizer_candidate_count": _multi_optimizer_real_candidate_count(
            candidate_pool
        ),
        "fallback_candidate_count": _multi_optimizer_fallback_candidate_count(
            candidate_pool
        ),
        "fallback_candidates_counted_as_real": False,
        "source_statuses": {
            _string_value(source.get("optimizer")): _string_value(source.get("status"))
            for source in source_rows
        },
        "fallback_sources": [
            _string_value(source.get("optimizer"))
            for source in source_rows
            if bool(source.get("fallback_used", False))
        ],
        "candidate_count": len(candidate_pool),
        "winner_selected_by_gate": bool(race_answers.get("winner_selected_by_gate")),
        "winner_proposal_id": race_answers.get("winner_proposal_id"),
        "proposal_selection": proposal_selection,
        "gate_feedback_returned_to_sampler_memory": bool(
            race_answers.get("gate_feedback_returned_to_sampler_memory")
        ),
        "official_scores_claimed": False,
        "evidence_scope": "local_gate_only",
    }


def _method_search_trajectory_round_payloads(
    value: list[dict[str, Any]] | dict[str, Any] | str | Path | None,
    *,
    list_keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    if value is None:
        return []
    payload: Any = value
    if isinstance(value, (str, Path)):
        payload, _ = _load_object(value)
    if isinstance(payload, list):
        items: list[dict[str, Any]] = []
        for item in payload:
            if isinstance(item, dict):
                items.append(item)
            elif isinstance(item, (str, Path)):
                loaded, _ = _load_object(item)
                if isinstance(loaded, dict):
                    items.append(loaded)
        return items
    if not isinstance(payload, dict):
        return []
    rounds = payload.get("rounds")
    if isinstance(rounds, list):
        round_payloads: list[dict[str, Any]] = []
        for item in rounds:
            if not isinstance(item, dict):
                continue
            nested = None
            for key in list_keys:
                if isinstance(item.get(key), list):
                    nested = {key: item[key]}
                    break
                if isinstance(item.get(key), dict):
                    nested = item[key]
                    break
            round_payloads.append(nested if isinstance(nested, dict) else item)
        return round_payloads
    for key in (
        "gate_results_by_round",
        "round_gate_results",
        "llm_proposals_by_round",
        "round_llm_proposals",
    ):
        items = payload.get(key)
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    if any(key in payload for key in list_keys):
        return [payload]
    return []


def _method_search_trajectory_operator_ids(
    operators: list[str | dict[str, Any]] | None,
) -> list[str]:
    return [
        str(item["operator_id"])
        for item in _method_search_operator_taxonomy(operators)["operators"]
    ]


def _method_search_trajectory_operator_order(
    *,
    operators: list[str | dict[str, Any]] | None,
    memory: dict[str, Any] | None,
) -> list[str]:
    base_ids = _method_search_trajectory_operator_ids(operators)
    shift = (
        memory.get("recommended_operator_shift")
        if isinstance(memory, dict)
        and isinstance(memory.get("recommended_operator_shift"), dict)
        else {}
    )
    ranked_ids = _string_list(shift.get("ranked_operator_ids"))
    ordered = [operator_id for operator_id in ranked_ids if operator_id in base_ids]
    ordered.extend(operator_id for operator_id in base_ids if operator_id not in ordered)
    return ordered


def _method_search_trajectory_weights(
    memory: dict[str, Any] | None,
    *,
    operator_ids: list[str],
) -> dict[str, float]:
    weights = (
        memory.get("operator_weights")
        if isinstance(memory, dict) and isinstance(memory.get("operator_weights"), dict)
        else {}
    )
    result = {
        operator_id: 1.0
        for operator_id in operator_ids
    }
    for operator_id, weight in weights.items():
        if _is_plain_number(weight):
            result[str(operator_id)] = float(weight)
    return result


def _method_search_trajectory_race_study(
    round_payload: dict[str, Any],
) -> dict[str, Any]:
    race = round_payload.get("race") if isinstance(round_payload.get("race"), dict) else {}
    study = race.get("study") if isinstance(race.get("study"), dict) else {}
    return study if isinstance(study, dict) and study else {
        "study_name": _string_value(round_payload.get("race_name")) or "method_search",
        "trials": [],
        "official_scores_claimed": False,
    }


def _method_search_trajectory_gate_results(
    round_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    study = _method_search_trajectory_race_study(round_payload)
    return _method_search_gate_results_from_trials(
        [item for item in study.get("trials", []) if isinstance(item, dict)]
    )


def _method_search_trajectory_used_operators(
    round_payload: dict[str, Any],
) -> list[str]:
    study = _method_search_trajectory_race_study(round_payload)
    return _dedupe_strings([
        _string_value(trial.get("params", {}).get("operator"))
        for trial in study.get("trials", [])
        if isinstance(trial, dict)
        and isinstance(trial.get("params"), dict)
        and _string_value(trial.get("params", {}).get("operator"))
    ])


def _method_search_trajectory_proposal_selection(
    round_payload: dict[str, Any],
) -> dict[str, Any]:
    answers = (
        round_payload.get("acceptance_answers")
        if isinstance(round_payload.get("acceptance_answers"), dict)
        else {}
    )
    selection = (
        answers.get("proposal_selection")
        if isinstance(answers.get("proposal_selection"), dict)
        else {}
    )
    return {
        "winner_proposal_id": selection.get("winner_proposal_id"),
        "selected_candidate_ids": _string_list(selection.get("selected_candidate_ids")),
        "pruned_candidate_ids": _string_list(selection.get("pruned_candidate_ids")),
        "blocked_candidate_ids": _string_list(selection.get("blocked_candidate_ids")),
    }


def _method_search_trajectory_gate_summary(
    round_payload: dict[str, Any],
) -> dict[str, Any]:
    study = _method_search_trajectory_race_study(round_payload)
    decisions = []
    state_counts: dict[str, int] = {}
    for trial in study.get("trials", []):
        if not isinstance(trial, dict):
            continue
        state = _string_value(trial.get("state")) or "UNKNOWN"
        state_counts[state] = state_counts.get(state, 0) + 1
        user_attrs = (
            trial.get("user_attrs")
            if isinstance(trial.get("user_attrs"), dict)
            else {}
        )
        gate_result = (
            user_attrs.get("gate_result")
            if isinstance(user_attrs.get("gate_result"), dict)
            else {}
        )
        decisions.append({
            "proposal_id": trial.get("proposal_id"),
            "operator_id": gate_result.get("operator_id"),
            "state": state,
            "score": trial.get("value"),
            "hard_blockers": _string_list(gate_result.get("hard_blockers")),
            "why_gate_passed_or_blocked": (
                "blocked by hard blockers"
                if _string_list(gate_result.get("hard_blockers"))
                else "passed by gate"
                if state == "COMPLETE"
                else "gate did not produce pass signal"
            ),
            "official_scores_claimed": False,
        })
    return {
        "trial_state_counts": state_counts,
        "decisions": decisions,
        "official_scores_claimed": False,
    }


def _method_search_trajectory_llm_rationales(
    round_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    rationales = []
    for candidate in _dict_list(round_payload.get("candidate_pool")):
        if _string_value(candidate.get("optimizer")) != "llm":
            continue
        rationales.append({
            "proposal_id": candidate.get("proposal_id"),
            "operator_id": candidate.get("operator_id"),
            "why_this_operator_applies": candidate.get("why_this_operator_applies"),
            "hypothesis": candidate.get("hypothesis"),
            "official_scores_claimed": False,
        })
    return rationales


def _method_search_trajectory_round_summary(
    *,
    round_number: int,
    round_payload: dict[str, Any],
    memory_before: dict[str, Any],
    memory_after: dict[str, Any],
) -> dict[str, Any]:
    source_generation = (
        round_payload.get("source_generation")
        if isinstance(round_payload.get("source_generation"), dict)
        else {}
    )
    operator_ids = sorted(
        set(_method_search_trajectory_used_operators(round_payload))
        | set(_method_search_trajectory_operator_ids(None))
    )
    memory_delta = _method_search_direction_change(
        _method_search_trajectory_weights(memory_before, operator_ids=operator_ids),
        _method_search_trajectory_weights(memory_after, operator_ids=operator_ids),
    )
    return {
        "round_number": round_number,
        "status": _string_value(round_payload.get("status")),
        "race_ref": _string_value(round_payload.get("output_path")),
        "mode": _string_value(round_payload.get("mode")),
        "used_operators": _method_search_trajectory_used_operators(round_payload),
        "optimizer_sources_tried": _string_list(
            round_payload.get("optimizer_sources_requested")
        ),
        "source_summary": {
            "source_count": source_generation.get("source_count"),
            "generated_candidate_count": source_generation.get(
                "generated_candidate_count"
            ),
            "real_optimizer_candidate_count": source_generation.get(
                "real_optimizer_candidate_count"
            ),
            "fallback_candidate_count": source_generation.get("fallback_candidate_count"),
            "blocked_source_count": source_generation.get("blocked_source_count"),
            "source_statuses": {
                _string_value(source.get("optimizer")): _string_value(source.get("status"))
                for source in _dict_list(source_generation.get("sources"))
            },
        },
        "llm_proposal_rationales": _method_search_trajectory_llm_rationales(
            round_payload
        ),
        "proposal_selection": _method_search_trajectory_proposal_selection(round_payload),
        "winner": (
            round_payload.get("winner")
            if isinstance(round_payload.get("winner"), dict)
            else None
        ),
        "gate_summary": _method_search_trajectory_gate_summary(round_payload),
        "memory_before": {
            "operator_weights": _method_search_trajectory_weights(
                memory_before,
                operator_ids=operator_ids,
            ),
            "recommended_operator_shift": memory_before.get(
                "recommended_operator_shift"
            ),
        },
        "memory_after": {
            "operator_weights": _method_search_trajectory_weights(
                memory_after,
                operator_ids=operator_ids,
            ),
            "recommended_operator_shift": memory_after.get(
                "recommended_operator_shift"
            ),
        },
        "memory_delta": memory_delta,
        "executes_tool": bool(round_payload.get("executes_tool", False)),
        "executes_optimizer_runtime": bool(
            round_payload.get("executes_optimizer_runtime", False)
        ),
        "official_scores_claimed": False,
    }


def _method_search_trajectory_best_path(
    *,
    round_winners: list[dict[str, Any]],
    direction: str,
) -> dict[str, Any]:
    scored = [
        winner for winner in round_winners if _is_plain_number(winner.get("score"))
    ]
    if not scored:
        return {
            "status": "no_gate_passed_path",
            "winner": None,
            "path_summary": {
                "local_evidence_only": True,
                "official_scores_claimed": False,
            },
            "official_scores_claimed": False,
        }
    reverse = direction != "minimize"
    best = sorted(
        scored,
        key=lambda winner: float(winner.get("score", 0.0)),
        reverse=reverse,
    )[0]
    return {
        "status": "best_gate_scored_path_found",
        "winning_round": best.get("round_number"),
        "winner": best,
        "path_summary": {
            "winning_optimizer": best.get("optimizer"),
            "winning_operator_id": best.get("operator_id"),
            "winning_score": best.get("score"),
            "winner_kind": best.get("winner_kind"),
            "local_evidence_only": True,
            "official_scores_claimed": False,
        },
        "official_scores_claimed": False,
    }


def _method_search_trajectory_acceptance_answers(
    *,
    rounds: list[dict[str, Any]],
    best_path: dict[str, Any],
    real_optimizer_candidate_count: int,
    fallback_candidate_count: int,
) -> dict[str, Any]:
    memory_changed = any(
        item.get("memory_delta", {}).get("upweighted_operator_ids")
        or item.get("memory_delta", {}).get("downweighted_operator_ids")
        for item in rounds
        if isinstance(item.get("memory_delta"), dict)
    )
    return {
        "rounds_executed": len(rounds),
        "optimizer_sources_tried": _dedupe_strings([
            source
            for item in rounds
            for source in _string_list(item.get("optimizer_sources_tried"))
        ]),
        "idea_hexagon_operators_used": _dedupe_strings([
            operator_id
            for item in rounds
            for operator_id in _string_list(item.get("used_operators"))
        ]),
        "llm_why_generated_these_proposals": [
            rationale
            for item in rounds
            for rationale in _dict_list(item.get("llm_proposal_rationales"))
        ],
        "proposal_selection_by_round": [
            {
                "round_number": item.get("round_number"),
                "proposal_selection": item.get("proposal_selection"),
            }
            for item in rounds
        ],
        "gate_decisions_by_round": [
            {
                "round_number": item.get("round_number"),
                "gate_summary": item.get("gate_summary"),
            }
            for item in rounds
        ],
        "sampler_changed_direction_across_rounds": bool(memory_changed),
        "why_sampler_changed_direction": [
            {
                "round_number": item.get("round_number"),
                "memory_delta": item.get("memory_delta"),
            }
            for item in rounds
            if isinstance(item.get("memory_delta"), dict)
            and (
                item["memory_delta"].get("upweighted_operator_ids")
                or item["memory_delta"].get("downweighted_operator_ids")
            )
        ],
        "best_path_selected_by_gate": best_path.get("winner") is not None,
        "real_optimizer_candidate_count": real_optimizer_candidate_count,
        "fallback_candidate_count": fallback_candidate_count,
        "fallback_candidates_counted_as_real": False,
        "current_evidence_scope": "local_gate_only",
        "official_scores_claimed": False,
    }


def _method_search_operator_taxonomy(
    operators: list[str | dict[str, Any]] | None = None,
) -> dict[str, Any]:
    defaults = {
        item["operator_id"]: dict(item) for item in DEFAULT_IDEA_HEXAGON_OPERATORS
    }
    aliases = {
        item.get("alias", ""): item["operator_id"] for item in DEFAULT_IDEA_HEXAGON_OPERATORS
    }
    if not operators:
        items = list(defaults.values())
    else:
        items = []
        seen: set[str] = set()
        for raw in operators:
            if isinstance(raw, dict):
                operator_id = (
                    _string_value(raw.get("operator_id"))
                    or _string_value(raw.get("id"))
                    or _string_value(raw.get("name"))
                )
                if not operator_id:
                    continue
                item = dict(defaults.get(operator_id, {}))
                item.update({key: value for key, value in raw.items() if value is not None})
                item["operator_id"] = operator_id
            elif isinstance(raw, str) and raw:
                operator_id = aliases.get(raw, raw)
                item = dict(defaults.get(operator_id, {
                    "operator_id": operator_id,
                    "label": f"custom Idea Hexagon operator {operator_id}",
                    "alias": operator_id,
                }))
            else:
                continue
            operator_id = str(item["operator_id"])
            if operator_id in seen:
                continue
            seen.add(operator_id)
            items.append(item)
    return {
        "source": "Idea Hexagon",
        "role": "operator taxonomy only",
        "not_a_rule_only_sampler": True,
        "operators": items,
    }


def _method_search_load_items(
    value: list[dict[str, Any]] | dict[str, Any] | str | Path | None,
    *,
    list_keys: tuple[str, ...],
) -> tuple[list[dict[str, Any]], Path | None]:
    if value is None:
        return [], None
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)], None
    if isinstance(value, dict):
        return _method_trace_items_from_payload(value, list_keys=list_keys), None
    path = Path(value)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)], path
    if isinstance(payload, dict):
        return _method_trace_items_from_payload(payload, list_keys=list_keys), path
    raise ValueError(f"expected list or object in {path}")


def _method_search_feedback_memory_payload(
    *,
    gate_feedback_memory: dict[str, Any] | str | Path | None,
    operator_ids: list[str],
    study: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if gate_feedback_memory is not None:
        payload, _ = _load_object(gate_feedback_memory)
        return payload
    if study is not None:
        sampler_state = study.get("sampler_state")
        if isinstance(sampler_state, dict):
            memory = sampler_state.get("gate_feedback_memory")
            if isinstance(memory, dict):
                return memory
    return build_gate_feedback_memory(gate_results=[], operators=operator_ids)


def _method_search_latest_memory_from_store(
    store: dict[str, Any] | str | Path | None,
) -> dict[str, Any] | None:
    if store is None:
        return None
    store_payload = _method_search_load_feedback_memory_store(store)
    latest = store_payload.get("latest_memory")
    if isinstance(latest, dict):
        return latest
    if store_payload.get("schema_version") == GATE_FEEDBACK_MEMORY_SCHEMA_VERSION:
        return store_payload
    return None


def _method_search_feedback_store_path(
    store: dict[str, Any] | str | Path | None,
) -> Path | None:
    if isinstance(store, str | Path):
        return Path(store)
    if isinstance(store, dict) and _string_value(store.get("path")):
        return Path(str(store["path"]))
    if isinstance(store, dict) and _string_value(store.get("output_path")):
        return Path(str(store["output_path"]))
    return None


def _method_search_load_feedback_memory_store(
    store: dict[str, Any] | str | Path | None,
) -> dict[str, Any]:
    if store is None:
        return {}
    if isinstance(store, dict):
        return store
    path = Path(store)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _method_search_feedback_store_record(
    *,
    memory: dict[str, Any],
    study: dict[str, Any],
    trial: dict[str, Any] | None,
    gate_result: dict[str, Any] | None,
    record_number: int,
    refs: list[dict[str, str]],
) -> dict[str, Any]:
    params = trial.get("params") if isinstance(trial, dict) and isinstance(trial.get("params"), dict) else {}
    proposal_id = (
        _string_value(trial.get("proposal_id")) if isinstance(trial, dict) else None
    ) or (
        _string_value(gate_result.get("proposal_id"))
        if isinstance(gate_result, dict)
        else None
    )
    operator_id = (
        _string_value(params.get("operator"))
        or (
            _method_search_gate_operator_id(gate_result)
            if isinstance(gate_result, dict)
            else None
        )
        or "unknown"
    )
    hard_blockers = (
        _method_search_hard_blockers(gate_result)
        if isinstance(gate_result, dict)
        else []
    )
    return {
        "record_id": f"gate-feedback-{record_number:04d}",
        "study_name": _string_value(study.get("study_name")) or "method_search",
        "trial_id": (
            _string_value(trial.get("trial_id")) if isinstance(trial, dict) else None
        ),
        "proposal_id": proposal_id,
        "operator_id": operator_id,
        "trial_state": (
            _string_value(trial.get("state")) if isinstance(trial, dict) else None
        ),
        "score": trial.get("value") if isinstance(trial, dict) else None,
        "hard_blockers": hard_blockers,
        "operator_weights": memory.get("operator_weights", {}),
        "blocked_patterns": memory.get("blocked_patterns", []),
        "promoted_patterns": memory.get("promoted_patterns", []),
        "recommended_operator_shift": memory.get("recommended_operator_shift", {}),
        "artifact_refs": refs,
        "claim_boundary": {
            "evidence_scope": "local_gate_only",
            "official_scores_claimed": False,
        },
        "official_scores_claimed": False,
    }


def _method_search_trial_rows(study: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trial in study.get("trials", []):
        if not isinstance(trial, dict):
            continue
        params = trial.get("params") if isinstance(trial.get("params"), dict) else {}
        user_attrs = (
            trial.get("user_attrs") if isinstance(trial.get("user_attrs"), dict) else {}
        )
        rows.append({
            "trial_id": trial.get("trial_id"),
            "trial_number": trial.get("trial_number"),
            "proposal_id": trial.get("proposal_id"),
            "state": trial.get("state"),
            "value": trial.get("value"),
            "operator": params.get("operator"),
            "adapter": params.get("adapter"),
            "slice": params.get("slice"),
            "patch_scope": params.get("patch_scope"),
            "model": params.get("model"),
            "hard_blockers": user_attrs.get("hard_blockers", []),
            "official_scores_claimed": False,
        })
    return rows


def _method_search_operator_weight_rows(memory: dict[str, Any]) -> list[dict[str, Any]]:
    weights = memory.get("operator_weights") if isinstance(memory, dict) else {}
    if not isinstance(weights, dict):
        return []
    shift = memory.get("recommended_operator_shift") if isinstance(memory.get("recommended_operator_shift"), dict) else {}
    downweighted = set(_string_list(shift.get("downweighted_operator_ids")))
    upweighted = set(_string_list(shift.get("upweighted_operator_ids")))
    rows = []
    for operator_id, weight in sorted(weights.items()):
        rows.append({
            "operator_id": str(operator_id),
            "weight": float(weight) if _is_plain_number(weight) else weight,
            "direction": (
                "downweighted"
                if str(operator_id) in downweighted
                else "upweighted"
                if str(operator_id) in upweighted
                else "unchanged"
            ),
            "official_scores_claimed": False,
        })
    return rows


def _method_search_operator_ids_from_study(
    study: dict[str, Any],
    operators: list[str | dict[str, Any]] | None,
) -> list[str]:
    if operators is not None:
        taxonomy = _method_search_operator_taxonomy(operators)
        return [item["operator_id"] for item in taxonomy["operators"]]
    sampler = study.get("sampler") if isinstance(study.get("sampler"), dict) else {}
    taxonomy = (
        sampler.get("operator_taxonomy")
        if isinstance(sampler.get("operator_taxonomy"), dict)
        else {}
    )
    items = taxonomy.get("operators") if isinstance(taxonomy.get("operators"), list) else []
    operator_ids = [
        str(item["operator_id"])
        for item in items
        if isinstance(item, dict) and _string_value(item.get("operator_id"))
    ]
    if operator_ids:
        return operator_ids
    return [item["operator_id"] for item in DEFAULT_IDEA_HEXAGON_OPERATORS]


def _method_search_gate_operator_id(gate_result: dict[str, Any]) -> str:
    if _string_value(gate_result.get("operator_id")):
        return str(gate_result["operator_id"])
    trial_params = gate_result.get("params")
    if isinstance(trial_params, dict) and _string_value(trial_params.get("operator")):
        return str(trial_params["operator"])
    trial = gate_result.get("trial")
    if isinstance(trial, dict):
        params = trial.get("params")
        if isinstance(params, dict) and _string_value(params.get("operator")):
            return str(params["operator"])
    return "unknown_operator"


def _method_search_gate_score(gate_result: dict[str, Any]) -> float:
    for key in ("score", "value", "gate_score"):
        value = gate_result.get(key)
        if _is_plain_number(value):
            return round(float(value), 4)
    metric_delta = _metric_delta_map(gate_result)
    if metric_delta:
        return round(max(metric_delta.values()), 4)
    return 0.0


def _method_search_hard_blockers(gate_result: dict[str, Any]) -> list[str]:
    hard_blockers = _string_list(gate_result.get("hard_blockers"))
    gate = gate_result.get("gate")
    if isinstance(gate, dict):
        hard_blockers.extend(_string_list(gate.get("hard_blockers")))
    if bool(gate_result.get("official_scores_claimed", False)):
        hard_blockers.append("source_claims_official_scores")
    return _dedupe_strings(hard_blockers)


def _method_search_gate_passed(
    gate_result: dict[str, Any],
    *,
    hard_blockers: list[str],
) -> bool:
    status = (
        _string_value(gate_result.get("status"))
        or _string_value(gate_result.get("gate_status"))
        or ""
    )
    gate = gate_result.get("gate") if isinstance(gate_result.get("gate"), dict) else {}
    return (
        status in {"passed", "passed_for_canary", "passed_for_promotion", "complete"}
        or bool(gate.get("canary_allowed", False))
        or bool(gate.get("promotion_ready", False))
    ) and not hard_blockers


def _method_search_operator_shift(operator_weights: dict[str, float]) -> dict[str, Any]:
    ranked = sorted(operator_weights.items(), key=lambda item: (-float(item[1]), item[0]))
    return {
        "ranked_operator_ids": [operator_id for operator_id, _ in ranked],
        "top_operator_id": ranked[0][0] if ranked else None,
        "downweighted_operator_ids": [
            operator_id
            for operator_id, weight in sorted(operator_weights.items())
            if weight < 1.0
        ],
        "upweighted_operator_ids": [
            operator_id
            for operator_id, weight in sorted(operator_weights.items())
            if weight > 1.0
        ],
        "reason": "gate feedback updates operator weights; LLM does not claim improvement",
    }


def _method_search_generate_llm_proposals(
    *,
    objective: str,
    operator_taxonomy: dict[str, Any],
    gate_feedback_memory: dict[str, Any],
    model: str,
    base_url: str,
    provider: str,
    api_key_env: str | None,
    temperature: float,
    max_tokens: int,
    timeout_seconds: int,
    completion_fn: Callable[..., dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    messages = _method_search_llm_messages(
        objective=objective,
        operator_taxonomy=operator_taxonomy,
        gate_feedback_memory=gate_feedback_memory,
    )
    completion = completion_fn or openai_compatible_chat_completion
    response = completion(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        base_url=base_url,
        provider=provider,
        api_key_env=api_key_env,
        extra_body={"response_format": {"type": "json_object"}},
    )
    payload = _method_search_json_payload_from_llm_response(response)
    proposals = payload.get("proposals")
    if not isinstance(proposals, list):
        raise ValueError("LLM method search response must contain proposals array")
    return [item for item in proposals if isinstance(item, dict)]


def _method_search_llm_messages(
    *,
    objective: str,
    operator_taxonomy: dict[str, Any],
    gate_feedback_memory: dict[str, Any],
) -> list[dict[str, str]]:
    required_fields = ", ".join(_METHOD_SEARCH_REQUIRED_PROPOSAL_FIELDS)
    compact_feedback = {
        "operator_weights": gate_feedback_memory.get("operator_weights"),
        "blocked_patterns": gate_feedback_memory.get("blocked_patterns"),
        "promoted_patterns": gate_feedback_memory.get("promoted_patterns"),
        "recommended_operator_shift": gate_feedback_memory.get(
            "recommended_operator_shift"
        ),
    }
    return [
        {
            "role": "system",
            "content": (
                "You generate method-search proposals as JSON only. "
                "Use Idea Hexagon only as an operator taxonomy. "
                "Do not claim that a proposal improves results; gate evidence decides. "
                f"Each proposal must include: {required_fields}."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "objective": objective,
                    "operator_taxonomy": operator_taxonomy,
                    "gate_feedback_memory": compact_feedback,
                    "output_schema": {
                        "type": "object",
                        "required": ["proposals"],
                        "proposal_required_fields": list(
                            _METHOD_SEARCH_REQUIRED_PROPOSAL_FIELDS
                        ),
                    },
                    "claim_boundary": {
                        "llm_may_claim_improvement": False,
                        "official_scores_claimed": False,
                    },
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        },
    ]


def _method_search_json_payload_from_llm_response(
    response: dict[str, Any],
) -> dict[str, Any]:
    if isinstance(response.get("payload"), dict):
        return response["payload"]
    content = response.get("content")
    if isinstance(content, dict):
        return content
    if isinstance(content, str):
        return _method_search_json_payload_from_text(content)
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return _method_search_json_payload_from_text(message["content"])
    raise ValueError("LLM method search response did not contain JSON content")


def _method_search_json_payload_from_text(content: str) -> dict[str, Any]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start < 0 or end <= start:
            raise
        payload = json.loads(content[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("LLM method search response JSON must be an object")
    return payload


def _method_search_placeholder_llm_proposal(
    *,
    operator_id: str,
    objective: str,
) -> dict[str, Any]:
    return {
        "proposal_id": f"proposal-{operator_id}-placeholder",
        "operator_id": operator_id,
        "why_this_operator_applies": (
            f"{operator_id} is the next available Idea Hexagon operator for {objective}."
        ),
        "hypothesis": "A bounded proposal may be generated by an LLM under this operator.",
        "change_surface": "method_design",
        "expected_effect": "requires local gate validation before any improvement claim",
        "risk": "no concrete proposal was supplied by the LLM fixture",
        "cheapest_validation": "generate concrete proposal fields, then run local gate",
        "rollback_or_stop_condition": "stop until a concrete LLM proposal is available",
    }


def _method_search_normalize_llm_proposal(
    *,
    proposal: dict[str, Any],
    index: int,
    operator_ids: list[str],
) -> dict[str, Any]:
    normalized = dict(proposal)
    proposal_id = (
        _string_value(normalized.get("proposal_id"))
        or _string_value(normalized.get("patch_id"))
        or f"proposal-{index:03d}"
    )
    normalized["proposal_id"] = proposal_id
    operator_id = _string_value(normalized.get("operator_id"))
    if not operator_id:
        operator_id = operator_ids[0] if operator_ids else "combine"
        normalized["operator_id"] = operator_id
    missing = [
        field
        for field in _METHOD_SEARCH_REQUIRED_PROPOSAL_FIELDS
        if not _string_value(normalized.get(field))
    ]
    if missing:
        raise ValueError(
            f"method search LLM proposal {proposal_id} missing fields: {', '.join(missing)}"
        )
    normalized.setdefault("method", "llm_method_proposal")
    normalized.setdefault("target_scope", normalized.get("change_surface"))
    normalized.setdefault("rationale", normalized.get("why_this_operator_applies"))
    normalized.setdefault("assumptions", [normalized["hypothesis"]])
    normalized.setdefault("self_critique", [normalized["risk"]])
    normalized["official_scores_claimed"] = False
    normalized["_input_order"] = index
    return normalized


def _method_search_ranking_decisions(
    *,
    ranked_proposals: list[dict[str, Any]],
    selected_ids: set[str],
    operator_weights: dict[str, float],
) -> list[dict[str, Any]]:
    decisions = []
    for rank, proposal in enumerate(ranked_proposals, start=1):
        operator_id = str(proposal["operator_id"])
        selected = str(proposal["proposal_id"]) in selected_ids
        decisions.append({
            "proposal_id": str(proposal["proposal_id"]),
            "rank": rank,
            "decision": "selected_for_validation" if selected else "pruned_by_sampler",
            "score": round(float(operator_weights.get(operator_id, 1.0)), 4),
            "operator_id": operator_id,
            "rationale": (
                "selected by gate-feedback-weighted Idea Hexagon operator"
                if selected
                else "not selected in this ask budget"
            ),
        })
    return decisions


def _method_search_sampler_reasoning_trace(
    *,
    proposals: list[dict[str, Any]],
    operator_weights: dict[str, float],
) -> dict[str, Any]:
    return {
        "trace_kind": "structured_rationale",
        "records_private_chain_of_thought": False,
        "steps": [
            {
                "step_id": f"hexagon-operator-{index:03d}",
                "operator_id": str(proposal["operator_id"]),
                "proposal_ids": [str(proposal["proposal_id"])],
                "summary": str(proposal["why_this_operator_applies"]),
                "hypothesis": str(proposal["hypothesis"]),
                "operator_weight": float(
                    operator_weights.get(str(proposal["operator_id"]), 1.0)
                ),
                "risks": [str(proposal["risk"])],
                "validation": str(proposal["cheapest_validation"]),
            }
            for index, proposal in enumerate(proposals, start=1)
        ],
    }


def _method_search_selected_sampler_proposals(
    sampler_output: dict[str, Any],
) -> list[dict[str, Any]]:
    selected_ids = set(_string_list(sampler_output.get("selected_proposal_ids")))
    return [
        proposal
        for proposal in sampler_output.get("proposals", [])
        if isinstance(proposal, dict) and str(proposal.get("proposal_id")) in selected_ids
    ]


def _method_search_build_trial(
    *,
    proposal: dict[str, Any],
    trial_number: int,
    adapter: str,
    slice_id: str,
    patch_scope: str,
    model: str,
    budget: dict[str, Any],
    trace_payload: dict[str, Any],
    sampler_output: dict[str, Any],
) -> dict[str, Any]:
    proposal_id = str(proposal["proposal_id"])
    operator_id = str(proposal["operator_id"])
    artifact_refs = []
    if _string_value(trace_payload.get("output_path")):
        artifact_refs.append({
            "name": "method_proposal_generation_trace",
            "path": trace_payload["output_path"],
        })
    if _string_value(sampler_output.get("output_path")):
        artifact_refs.append({
            "name": "hexagon_guided_llm_sampler",
            "path": sampler_output["output_path"],
        })
    return {
        "schema_version": METHOD_SEARCH_TRIAL_SCHEMA_VERSION,
        "trial_id": f"trial-{trial_number:04d}",
        "trial_number": trial_number,
        "proposal_id": proposal_id,
        "state": "WAITING",
        "value": None,
        "params": {
            "operator": operator_id,
            "adapter": _string_value(proposal.get("adapter")) or adapter,
            "slice": _string_value(proposal.get("slice")) or slice_id,
            "patch_scope": _string_value(proposal.get("patch_scope")) or patch_scope,
            "model": model,
            "budget": (
                proposal.get("budget")
                if isinstance(proposal.get("budget"), dict)
                else budget
            ),
        },
        "user_attrs": {
            "trace": {
                "schema_version": trace_payload.get("schema_version"),
                "method_proposal_generation_trace_ref": (
                    _string_value(trace_payload.get("output_path")) or "inline"
                ),
                "proposal_id": proposal_id,
                "records_private_chain_of_thought": False,
            },
            "artifact_refs": artifact_refs,
            "claim_boundary": {
                "evidence_scope": "local_gate_only",
                "llm_may_claim_improvement": False,
                "official_scores_claimed": False,
            },
            "hard_blockers": [],
            "hexagon_operator": {
                "operator_id": operator_id,
                "why_this_operator_applies": proposal["why_this_operator_applies"],
            },
            "proposal": {
                key: proposal[key]
                for key in _METHOD_SEARCH_REQUIRED_PROPOSAL_FIELDS
                if key in proposal
            },
        },
        "official_scores_claimed": False,
    }


def _method_search_artifact_refs(**paths: Any) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for name, value in paths.items():
        if isinstance(value, Path):
            refs.append({"name": name, "path": str(value)})
        elif isinstance(value, dict) and _string_value(value.get("output_path")):
            refs.append({"name": name, "path": str(value["output_path"])})
    return refs


def _method_search_trial_state(
    *,
    gate_payload: dict[str, Any],
    hard_blockers: list[str],
    passed: bool,
) -> str:
    status = (
        _string_value(gate_payload.get("status"))
        or _string_value(gate_payload.get("gate_status"))
        or ""
    )
    if hard_blockers:
        return "PRUNED"
    if passed:
        return "COMPLETE"
    if status in {"waiting", "pending"}:
        return "WAITING"
    if status in {"near_pass", "near-passed", "near_passed"}:
        return "PRUNED"
    return "FAIL"


def _method_search_gate_result_summary(
    *,
    gate_payload: dict[str, Any],
    gate_path: Path | None,
    state: str,
    score: float,
    hard_blockers: list[str],
) -> dict[str, Any]:
    return {
        "gate_result_ref": str(gate_path) if gate_path is not None else "inline",
        "proposal_id": _string_value(gate_payload.get("proposal_id")),
        "operator_id": _method_search_gate_operator_id(gate_payload),
        "status": (
            _string_value(gate_payload.get("status"))
            or _string_value(gate_payload.get("gate_status"))
            or "unknown"
        ),
        "trial_state": state,
        "score": score,
        "hard_blockers": hard_blockers,
        "metric_delta": _metric_delta_map(gate_payload),
        "official_scores_claimed": False,
    }


def _method_search_same_trial(existing: dict[str, Any], trial: dict[str, Any]) -> bool:
    return (
        _string_value(existing.get("trial_id")) == _string_value(trial.get("trial_id"))
        or (
            _string_value(existing.get("proposal_id"))
            == _string_value(trial.get("proposal_id"))
        )
    )


def _method_search_gate_results_from_trials(
    trials: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    results = []
    for trial in trials:
        user_attrs = trial.get("user_attrs") if isinstance(trial.get("user_attrs"), dict) else {}
        gate_result = user_attrs.get("gate_result") if isinstance(user_attrs, dict) else None
        if not isinstance(gate_result, dict):
            continue
        result = dict(gate_result)
        params = trial.get("params") if isinstance(trial.get("params"), dict) else {}
        if _string_value(params.get("operator")):
            result["operator_id"] = params["operator"]
        if _string_value(trial.get("proposal_id")):
            result["proposal_id"] = trial["proposal_id"]
        result["score"] = trial.get("value")
        results.append(result)
    return results


def _method_search_existing_operator_weights(study: dict[str, Any]) -> dict[str, float]:
    sampler_state = study.get("sampler_state") if isinstance(study.get("sampler_state"), dict) else {}
    weights = sampler_state.get("operator_weights") if isinstance(sampler_state, dict) else {}
    if isinstance(weights, dict):
        return {
            str(operator_id): float(weight)
            for operator_id, weight in weights.items()
            if _is_plain_number(weight)
        }
    return {}


def _method_search_direction_change(
    before: dict[str, float],
    after: dict[str, float],
) -> dict[str, Any]:
    all_ids = sorted(set(before) | set(after))
    upweighted = [
        operator_id
        for operator_id in all_ids
        if float(after.get(operator_id, 1.0)) > float(before.get(operator_id, 1.0))
    ]
    downweighted = [
        operator_id
        for operator_id in all_ids
        if float(after.get(operator_id, 1.0)) < float(before.get(operator_id, 1.0))
    ]
    return {
        "upweighted_operator_ids": upweighted,
        "downweighted_operator_ids": downweighted,
        "operator_weights_before": before,
        "operator_weights_after": after,
        "reason": "tell consumed gate feedback; hard blockers downweight and pass/near-pass upweight",
    }


def _method_search_best_trial(trials: list[dict[str, Any]]) -> dict[str, Any] | None:
    complete_trials = [
        trial
        for trial in trials
        if trial.get("state") == "COMPLETE" and _is_plain_number(trial.get("value"))
    ]
    if not complete_trials:
        return None
    best = max(complete_trials, key=lambda trial: float(trial["value"]))
    return {
        "trial_id": best.get("trial_id"),
        "proposal_id": best.get("proposal_id"),
        "value": best.get("value"),
        "params": best.get("params") if isinstance(best.get("params"), dict) else {},
        "official_scores_claimed": False,
    }


def _method_search_acceptance_answers(
    *,
    study: dict[str, Any],
    trial: dict[str, Any],
    gate_result: dict[str, Any],
    memory: dict[str, Any],
) -> dict[str, Any]:
    trials = [item for item in study.get("trials", []) if isinstance(item, dict)]
    selected = [
        item.get("proposal_id")
        for item in trials
        if item.get("state") in {"WAITING", "COMPLETE"}
    ]
    pruned = [
        item.get("proposal_id") for item in trials if item.get("state") == "PRUNED"
    ]
    params = trial.get("params") if isinstance(trial.get("params"), dict) else {}
    user_attrs = (
        trial.get("user_attrs") if isinstance(trial.get("user_attrs"), dict) else {}
    )
    proposal = (
        user_attrs.get("proposal") if isinstance(user_attrs.get("proposal"), dict) else {}
    )
    hard_blockers = _method_search_hard_blockers(gate_result)
    return {
        "idea_hexagon_operators_used": _dedupe_strings([
            str(item.get("params", {}).get("operator"))
            for item in trials
            if isinstance(item.get("params"), dict)
            and _string_value(item.get("params", {}).get("operator"))
        ]),
        "llm_proposal_rationales": [
            {
                "proposal_id": trial.get("proposal_id"),
                "operator_id": params.get("operator"),
                "why_this_operator_applies": proposal.get("why_this_operator_applies"),
                "hypothesis": proposal.get("hypothesis"),
            }
        ],
        "selected_and_pruned_proposals": {
            "selected_or_waiting": selected,
            "pruned": pruned,
            "current_trial_state": trial.get("state"),
        },
        "gate_decisions": [
            {
                "proposal_id": trial.get("proposal_id"),
                "operator_id": params.get("operator"),
                "state": trial.get("state"),
                "value": trial.get("value"),
                "hard_blockers": hard_blockers,
                "why_gate_passed_or_blocked": (
                    "blocked by hard blockers"
                    if hard_blockers
                    else "passed by gate"
                    if trial.get("state") == "COMPLETE"
                    else "gate did not produce pass signal"
                ),
            }
        ],
        "sampler_direction_change": memory.get("recommended_operator_shift"),
        "claim_boundary": {
            "evidence_scope": "local_gate_only",
            "official_scores_claimed": False,
            "llm_may_claim_improvement": False,
        },
    }


def _method_trace_items_from_payload(
    payload: dict[str, Any],
    *,
    list_keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    for key in list_keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return [payload]


def _method_trace_candidate_pool(proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, proposal in enumerate(proposals, start=1):
        proposal_id = (
            _string_value(proposal.get("proposal_id"))
            or _string_value(proposal.get("patch_id"))
            or f"proposal-{index:03d}"
        )
        if proposal_id in seen:
            proposal_id = f"{proposal_id}-{index:03d}"
        seen.add(proposal_id)
        module_id = _string_value(proposal.get("module_id"))
        section_id = _string_value(proposal.get("section_id"))
        target_scope = (
            _string_value(proposal.get("target_scope"))
            or (f"{module_id}/{section_id}" if module_id and section_id else None)
            or module_id
            or "unknown"
        )
        result.append({
            "proposal_id": proposal_id,
            "method": (
                _string_value(proposal.get("method"))
                or _string_value(proposal.get("proposal_type"))
                or _string_value(proposal.get("candidate_strategy"))
                or _string_value(proposal.get("optimizer"))
                or "unspecified"
            ),
            "target_scope": target_scope,
            "rationale": (
                _string_value(proposal.get("rationale"))
                or _string_value(proposal.get("planner_rationale"))
                or _string_value(proposal.get("intent"))
                or ""
            ),
            "assumptions": _string_list(proposal.get("assumptions")),
            "self_critique": _string_list(proposal.get("self_critique")),
            "expected_gain": (
                proposal.get("expected_gain")
                if isinstance(proposal.get("expected_gain"), dict)
                else {}
            ),
            "risk_level": _string_value(proposal.get("risk_level")),
            "source": _string_value(proposal.get("source")) or "method_search",
            "official_scores_claimed": False,
        })
    return result


def _method_trace_ranking_trace(
    ranking_decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []
    for index, decision in enumerate(ranking_decisions, start=1):
        proposal_id = (
            _string_value(decision.get("proposal_id"))
            or _string_value(decision.get("patch_id"))
            or f"proposal-{index:03d}"
        )
        normalized = {
            "proposal_id": proposal_id,
            "rank": _method_trace_int(decision.get("rank"), default=index),
            "decision": (
                _string_value(decision.get("decision"))
                or _string_value(decision.get("status"))
                or "ranked"
            ),
            "score": _method_trace_float(decision.get("score")),
            "rationale": (
                _string_value(decision.get("rationale"))
                or _string_value(decision.get("selection_rationale"))
                or ""
            ),
            "risk_notes": _string_list(decision.get("risk_notes")),
        }
        decisions.append(normalized)
    decisions.sort(key=lambda item: (item["rank"], item["proposal_id"]))
    return {
        "decision_count": len(decisions),
        "decisions": decisions,
        "selection_policy": "ranked_proposals_require_explicit_gate_validation",
    }


def _method_trace_selected_ids(
    *,
    selected_proposal_ids: list[str] | None,
    ranking_decisions: list[dict[str, Any]],
) -> list[str]:
    explicit = _dedupe_strings(selected_proposal_ids or [])
    if explicit:
        return explicit
    selected_decisions = {
        "selected",
        "selected_for_validation",
        "selected_for_execution",
        "validate",
    }
    return _dedupe_strings([
        decision["proposal_id"]
        for decision in ranking_decisions
        if _string_value(decision.get("decision")) in selected_decisions
    ])


def _method_trace_pruned_proposal(
    *,
    proposal: dict[str, Any],
    ranking_decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    ranking = _method_trace_ranking_for_proposal(
        proposal_id=proposal["proposal_id"],
        ranking_decisions=ranking_decisions,
    )
    return {
        "proposal_id": proposal["proposal_id"],
        "method": proposal["method"],
        "target_scope": proposal["target_scope"],
        "pruning_decision": (
            _string_value(ranking.get("decision")) if ranking else "not_selected"
        ),
        "pruning_rationale": (
            _string_value(ranking.get("rationale"))
            if ranking
            else "proposal was not selected for this validation batch"
        ),
    }


def _method_trace_ranking_for_proposal(
    *,
    proposal_id: str,
    ranking_decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    for decision in ranking_decisions:
        if decision.get("proposal_id") == proposal_id:
            return decision
    return {}


def _method_trace_validation_links(
    *,
    execution_links: list[dict[str, Any]],
    gate_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    proposal_ids = _dedupe_strings([
        *[
            _string_value(item.get("proposal_id")) or ""
            for item in execution_links
        ],
        *[
            _string_value(item.get("proposal_id")) or ""
            for item in gate_results
        ],
    ])
    links: list[dict[str, Any]] = []
    for proposal_id in proposal_ids:
        gate = _method_trace_gate_for_proposal(
            proposal_id=proposal_id,
            gate_results=gate_results,
        )
        links.append({
            "proposal_id": proposal_id,
            "execution_refs": _method_trace_execution_refs(
                proposal_id=proposal_id,
                execution_links=execution_links,
            ),
            "gate_status": (
                _string_value(gate.get("gate_status"))
                or _string_value(gate.get("status"))
                or "not_run"
            ),
            "metric_delta": _metric_delta_map(gate),
            "hard_blockers": _string_list(gate.get("hard_blockers")),
        })
    return links


def _method_trace_execution_refs(
    *,
    proposal_id: str,
    execution_links: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for item in execution_links:
        if _string_value(item.get("proposal_id")) != proposal_id:
            continue
        refs.append({
            "artifact": (
                _string_value(item.get("artifact"))
                or _string_value(item.get("name"))
                or "artifact"
            ),
            "path": _string_value(item.get("path")) or _string_value(item.get("ref")),
        })
    return refs


def _method_trace_gate_for_proposal(
    *,
    proposal_id: str,
    gate_results: list[dict[str, Any]],
) -> dict[str, Any]:
    for item in gate_results:
        if _string_value(item.get("proposal_id")) == proposal_id:
            return item
    return {}


def _method_trace_learning_updates(
    *,
    candidate_pool: list[dict[str, Any]],
    gate_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates = {item["proposal_id"]: item for item in candidate_pool}
    updates: list[dict[str, Any]] = []
    for gate in gate_results:
        proposal_id = _string_value(gate.get("proposal_id"))
        if proposal_id is None:
            continue
        blockers = _string_list(gate.get("hard_blockers"))
        gate_status = (
            _string_value(gate.get("gate_status"))
            or _string_value(gate.get("status"))
            or "unknown"
        )
        accepted = gate_status in {"passed", "passed_for_canary", "completed"} and not blockers
        candidate = candidates.get(proposal_id, {})
        updates.append({
            "proposal_id": proposal_id,
            "method": _string_value(candidate.get("method")) or "unknown",
            "target_scope": _string_value(candidate.get("target_scope")) or "unknown",
            "learning_signal": (
                "candidate_validated_positive"
                if accepted
                else "candidate_blocked_or_unverified"
            ),
            "gate_status": gate_status,
            "hard_blockers": blockers,
            "metric_delta": _metric_delta_map(gate),
        })
    return updates


def _method_trace_generation_context(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "trigger": _string_value(payload.get("trigger")),
        "task_family": _string_value(payload.get("task_family")) or "unknown",
        "failure_slice": _string_value(payload.get("failure_slice")),
        "objective": _string_value(payload.get("objective")) or "",
        "constraints": _string_list(payload.get("constraints")),
        "outcome_memory_refs": _string_list(payload.get("outcome_memory_refs")),
    }


def _method_trace_generation_run(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "generator": _string_value(payload.get("generator")) or "unknown_generator",
        "model": _string_value(payload.get("model")),
        "prompt_template_id": _string_value(payload.get("prompt_template_id")),
        "temperature": _method_trace_float(payload.get("temperature")),
        "seed": _method_trace_int(payload.get("seed")),
        "max_tokens": _method_trace_int(payload.get("max_tokens")),
        "tool_versions": (
            payload.get("tool_versions")
            if isinstance(payload.get("tool_versions"), dict)
            else {}
        ),
    }


def _method_trace_reasoning_trace(payload: dict[str, Any]) -> dict[str, Any]:
    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list):
        raw_steps = payload.get("reasoning_steps")
    steps = []
    for index, item in enumerate(_dict_list(raw_steps), start=1):
        steps.append({
            "step_id": _string_value(item.get("step_id")) or f"reason-{index:03d}",
            "summary": _string_value(item.get("summary")) or "",
            "proposal_ids": _string_list(item.get("proposal_ids")),
            "assumptions": _string_list(item.get("assumptions")),
            "risks": _string_list(item.get("risks")),
        })
    redacted_fields = [
        key
        for key in ("private_chain_of_thought", "chain_of_thought")
        if payload.get(key)
    ]
    return {
        "trace_kind": _string_value(payload.get("trace_kind")) or "structured_rationale",
        "records_private_chain_of_thought": False,
        "redacted_fields": redacted_fields,
        "steps": steps,
        "assumptions": _string_list(payload.get("assumptions")),
        "self_critique": _string_list(payload.get("self_critique")),
    }


def _method_trace_artifact_refs(paths: dict[str, Path | None]) -> list[dict[str, Any]]:
    return [
        {"name": name, "path": str(path)}
        for name, path in paths.items()
        if path is not None
    ]


def _method_trace_float(value: Any) -> float | None:
    if _is_plain_number(value):
        return float(value)
    return None


def _method_trace_int(value: Any, *, default: int | None = None) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    if _is_plain_number(value):
        return int(value)
    return default


def _source_pattern_ids(
    score_breakdown: dict[str, Any],
    *,
    context_payload: dict[str, Any],
) -> list[str]:
    if not score_breakdown or float(score_breakdown.get("pattern_prior", 0.0)) <= 0:
        return []
    matched_patterns = context_payload.get("pattern_summary", {}).get("matched_patterns", [])
    if not isinstance(matched_patterns, list):
        return []
    return [
        pattern_id
        for pattern_id in (
            _string_value(pattern.get("pattern_id"))
            for pattern in matched_patterns
            if isinstance(pattern, dict)
        )
        if pattern_id
    ]


def _client_template_from_selected(
    *,
    selected_item: dict[str, Any],
    failure_records: list[dict[str, Any]],
) -> dict[str, Any]:
    proposal_id = _string_value(selected_item.get("proposal_id")) or "selected-proposal"
    based_on_failures = _string_list(selected_item.get("based_on_failures"))
    matched_failures = [
        record
        for record in failure_records
        if _string_value(record.get("failure_id")) in based_on_failures
    ]
    failure_types = [
        failure_type
        for failure_type in (
            _string_value(record.get("failure_type")) for record in matched_failures
        )
        if failure_type
    ]
    target_scope = _string_value(selected_item.get("target_scope")) or "single bounded scope"
    change_surface = _string_value(selected_item.get("change_surface")) or "routing"
    verification_plan = (
        dict(selected_item.get("verification_plan"))
        if isinstance(selected_item.get("verification_plan"), dict)
        else {}
    )
    rollback_rule = (
        dict(selected_item.get("rollback_rule"))
        if isinstance(selected_item.get("rollback_rule"), dict)
        else {}
    )
    evidence_used = [
        {
            "artifact": "failure_record",
            "failure_id": record.get("failure_id"),
            "observation": record.get("symptom"),
        }
        for record in matched_failures
    ] or [{"artifact": "failure_record", "observation": "selected from ranked proposals"}]
    first_split = _string_value(verification_plan.get("first_split")) or "dev"
    promotion_split = _string_value(verification_plan.get("promotion_split")) or "canary"
    rollback_if = _string_list(rollback_rule.get("if")) or ["dev_delta_lt_0", "canary_delta_lt_0"]
    return {
        "proposal_id": f"{proposal_id}-client-template",
        "proposal_type": _string_value(selected_item.get("proposal_type")) or "failure_fix",
        "based_on_failures": based_on_failures,
        "hypothesis": (
            f"A bounded {change_surface} change within {target_scope} can reduce "
            f"{', '.join(failure_types) or 'observed failures'}."
        ),
        "intent": _string_value(selected_item.get("intent")),
        "evidence_used": evidence_used,
        "change_surface": change_surface,
        "change_spec": {
            "single_primary_variable": True,
            "target": target_scope,
            "allowed_scope": target_scope,
        },
        "expected_effect": {
            "primary_metric": _template_primary_metric(failure_types),
            "target_failures": failure_types,
            "expected_direction": "increase",
        },
        "validation_plan": {
            "first_split": first_split,
            "promotion_split": promotion_split,
            "max_rounds": int(verification_plan.get("max_rounds", 1) or 1),
            "rollback_if": rollback_if,
        },
        "risk_assessment": {
            "overfit_risk": _string_value(selected_item.get("risk_level"))
            or _risk_label_from_breakdown(selected_item.get("score_breakdown")),
            "leakage_risk": "low",
            "runtime_cost": "low",
        },
        "next_if_success": "record_proposal_outcome_and_review_promotion",
        "next_if_failure": "record_failure_and_revise_proposal",
        "claim_boundary": "local diagnostic proposal only",
        "official_scores_claimed": False,
        "target_scope": target_scope,
        "requires_client_review": True,
        "executes_tool": False,
    }


def _handoff_failure_records(handoff_payload: dict[str, Any]) -> list[dict[str, Any]]:
    records = handoff_payload.get("failure_summary", {}).get("records", [])
    if not isinstance(records, list):
        return []
    return [item for item in records if isinstance(item, dict)]


def _write_client_templates_markdown(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Failure-Driven Client Proposal Templates",
        "",
        f"- Status: `{payload['status']}`",
        f"- Executes tool: `{payload['executes_tool']}`",
        f"- Official scores claimed: `{payload['official_scores_claimed']}`",
        "",
        "## Templates",
        "",
    ]
    if not payload["proposal_templates"]:
        lines.append("- No selected proposals were available for templating.")
    for template in payload["proposal_templates"]:
        lines.extend(
            [
                f"### {template['proposal_id']}",
                "",
                template["hypothesis"],
                "",
                f"- Change surface: `{template['change_surface']}`",
                f"- Claim boundary: {template['claim_boundary']}",
                "",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _template_primary_metric(failure_types: list[str]) -> str:
    labels = {label for label in failure_types if isinstance(label, str)}
    if "canary_not_confirmed" in labels:
        return "SHIFT"
    if "holdout_not_confirmed" in labels:
        return "holdout_metric"
    return "local_metric"


def _load_optional_object(value: dict[str, Any] | str | Path | None) -> dict[str, Any] | None:
    if value is None:
        return None
    payload, _ = _load_object(value)
    return payload


def _handoff_selected_lookup(handoff_payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not handoff_payload:
        return {}
    selected = handoff_payload.get("selected_next_proposals", [])
    if not isinstance(selected, list):
        return {}
    return {
        proposal_id: item
        for item in selected
        if isinstance(item, dict)
        for proposal_id in [_string_value(item.get("proposal_id"))]
        if proposal_id
    }


def _handoff_failure_lookup(handoff_payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not handoff_payload:
        return {}
    return {
        failure_id: item
        for item in _handoff_failure_records(handoff_payload)
        for failure_id in [_string_value(item.get("failure_id"))]
        if failure_id
    }


def _memory_bridge_artifact_path(
    outcome_payload: dict[str, Any],
    *,
    source_path: Path | None,
) -> Path | None:
    candidate_paths = []
    if source_path is not None:
        candidate_paths.append(source_path)
    explicit = _string_value(outcome_payload.get("output_path"))
    if explicit:
        candidate_paths.append(Path(explicit))
    for artifact in outcome_payload.get("artifact_refs", []) if isinstance(
        outcome_payload.get("artifact_refs"), list
    ) else []:
        if isinstance(artifact, dict) and _string_value(artifact.get("path")):
            candidate_paths.append(Path(str(artifact["path"])))
    for candidate in candidate_paths:
        if candidate.exists():
            return candidate
    return None


def _bridge_failure_category(
    *,
    outcome_payload: dict[str, Any],
    based_on_failures: list[str],
    failure_lookup: dict[str, dict[str, Any]],
) -> str | None:
    failure_labels = _string_list(outcome_payload.get("failure_labels"))
    if failure_labels:
        return _normalize_failure_type(failure_labels[0])
    for failure_id in based_on_failures:
        failure = failure_lookup.get(failure_id)
        failure_type = _string_value(failure.get("failure_type")) if failure else None
        if failure_type:
            return failure_type
    return None


def _bridge_summary(
    *,
    proposal_id: str,
    accepted: bool,
    change_surface: str,
    failure_category: str | None,
    metric_delta: dict[str, Any],
) -> str:
    outcome = "accepted" if accepted else "not_accepted"
    return (
        f"Failure-driven proposal {proposal_id} outcome={outcome}; "
        f"surface={change_surface}; failure_category={failure_category or 'none'}; "
        f"metric_delta={metric_delta}."
    )


def _risk_label_from_breakdown(score_breakdown: Any) -> str:
    if not isinstance(score_breakdown, dict):
        return "medium"
    penalty = score_breakdown.get("risk_penalty")
    if not _is_plain_number(penalty):
        return "medium"
    if float(penalty) <= 0.3:
        return "low"
    if float(penalty) >= 0.8:
        return "high"
    return "medium"


def _write_failure_handoff_markdown(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# Failure-Driven Proposal Handoff",
        "",
        f"- Status: `{payload['status']}`",
        f"- Objective: `{payload.get('objective')}`",
        f"- Executes tool: `{payload['executes_tool']}`",
        f"- Official scores claimed: `{payload['official_scores_claimed']}`",
        "",
        "## Recommended Next Step",
        "",
        f"- MCP tool: `{payload['recommended_next_step']['mcp_tool']}`",
        f"- Human action: `{payload['recommended_next_step']['human_action']}`",
        "",
        "## Selected Proposals",
        "",
    ]
    if not payload["selected_next_proposals"]:
        lines.append("- No proposal passed ranking and gate selection.")
    for proposal in payload["selected_next_proposals"]:
        lines.extend(
            [
                f"### {proposal['proposal_id']}",
                "",
                f"- Rank: `{proposal['rank']}`",
                f"- Score: `{proposal['score']}`",
                f"- Based on failures: `{', '.join(proposal['based_on_failures'])}`",
                "",
            ]
        )
    lines.extend(["## Memory Bridge", ""])
    if not payload["memory_bridge"]:
        lines.append("- No advisory memory bridge entries.")
    for bridge in payload["memory_bridge"]:
        lines.extend(
            [
                f"- `{bridge['proposal_id']}` -> `{bridge['future_memory_type']}`",
                f"  - failures: `{', '.join(bridge['source_failure_ids'])}`",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _failure_type_counts(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for record in records:
        failure_type = _string_value(record.get("failure_type")) or "unknown"
        counts[failure_type] = counts.get(failure_type, 0) + 1
    return [
        {"failure_type": failure_type, "count": count}
        for failure_type, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _matched_patterns(
    records: list[dict[str, Any]],
    patterns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    failure_types = {
        _string_value(record.get("failure_type"))
        for record in records
        if _string_value(record.get("failure_type"))
    }
    matched = [
        pattern
        for pattern in patterns
        if failure_types.intersection(_string_list(pattern.get("applicable_when")))
    ]
    return sorted(
        matched,
        key=lambda item: (
            -float(item.get("historical_success_rate", 0.0)),
            str(item.get("pattern_id", "")),
        ),
    )


def _render_failure_driven_prompt(
    *,
    objective: str,
    failure_type_counts: list[dict[str, Any]],
    matched_patterns: list[dict[str, Any]],
    max_proposals: int,
) -> str:
    failure_lines = "\n".join(
        f"- {item['failure_type']}: {item['count']}" for item in failure_type_counts
    ) or "- none"
    pattern_lines = "\n".join(
        f"- {item.get('pattern_id')}: success_rate={item.get('historical_success_rate', 0.0)}"
        for item in matched_patterns[:5]
    ) or "- none"
    return (
        "# Failure-driven proposal context\n\n"
        f"Objective: {objective}\n\n"
        "Top failures:\n"
        f"{failure_lines}\n\n"
        "Relevant patterns:\n"
        f"{pattern_lines}\n\n"
        f"Generate up to {max_proposals} proposals. Each proposal must bind to observed failures, "
        "change one primary variable, include verification and rollback rules, and keep "
        "official_scores_claimed=false."
    )


def _failure_index(records: list[dict[str, Any]]) -> dict[str, Any]:
    id_map = {
        failure_id: failure_type
        for failure_id, failure_type in (
            (
                _string_value(record.get("failure_id")),
                _string_value(record.get("failure_type")),
            )
            for record in records
        )
        if failure_id and failure_type
    }
    type_set = {
        failure_type
        for failure_type in (_string_value(record.get("failure_type")) for record in records)
        if failure_type
    }
    return {"ids": set(id_map), "types": type_set, "id_to_type": id_map}


def _proposal_signature(proposal: dict[str, Any]) -> str:
    based_on = ",".join(sorted(_string_list(proposal.get("based_on_failures"))))
    return "|".join(
        [
            based_on,
            _string_value(proposal.get("change_surface")) or "",
            _string_value(proposal.get("target_scope")) or "",
        ]
    )


def _score_breakdown(
    *,
    proposal: dict[str, Any],
    based_on_failures: list[str],
    failure_index: dict[str, set[str]],
    patterns: list[dict[str, Any]],
    redundancy_count: int,
) -> dict[str, float]:
    return {
        "expected_gain": _expected_gain_score(proposal),
        "pattern_prior": _pattern_prior(
            proposal_type=_string_value(proposal.get("proposal_type")) or "failure_fix",
            based_on_failures=based_on_failures,
            failure_index=failure_index,
            patterns=patterns,
        ),
        "risk_penalty": _risk_penalty(proposal),
        "redundancy_penalty": _redundancy_penalty(redundancy_count),
    }


def _expected_gain_score(proposal: dict[str, Any]) -> float:
    expected_gain = proposal.get("expected_gain")
    if isinstance(expected_gain, dict):
        for key in ("score", "target_metric_gain", "expected_gain"):
            value = expected_gain.get(key)
            if _is_plain_number(value):
                return float(value)
        if expected_gain.get("expected_direction") == "increase":
            return 1.0
    return 0.0


def _pattern_prior(
    *,
    proposal_type: str,
    based_on_failures: list[str],
    failure_index: dict[str, set[str]],
    patterns: list[dict[str, Any]],
) -> float:
    mapped_failure_types = sorted(
        {
            failure_index["id_to_type"].get(failure)
            or (failure if failure in failure_index["types"] else _failure_type_from_reference(failure))
            for failure in based_on_failures
        }
    )
    priors = [
        float(pattern.get("historical_success_rate", 0.0))
        for pattern in patterns
        if _string_value(pattern.get("proposal_type")) == proposal_type
        and set(_string_list(pattern.get("applicable_when"))).intersection(mapped_failure_types)
    ]
    if not priors:
        return 0.0
    return round(sum(priors) / len(priors), 4)


def _failure_type_from_reference(reference: str) -> str:
    parts = reference.split(":")
    if len(parts) >= 2 and parts[1]:
        return _normalize_failure_type(parts[1])
    return _normalize_failure_type(reference)


def _risk_penalty(proposal: dict[str, Any]) -> float:
    base = {"low": 0.2, "medium": 0.5, "high": 0.9}.get(
        _string_value(proposal.get("risk_level")) or "medium",
        0.5,
    )
    change_surface = _string_value(proposal.get("change_surface")) or ""
    if change_surface in {"training_recipe", "code_patch"}:
        base += 0.2
    return round(base, 4)


def _redundancy_penalty(redundancy_count: int) -> float:
    if redundancy_count <= 1:
        return 0.0
    return round(0.5 * (redundancy_count - 1), 4)


def _gate_labels(
    proposal: dict[str, Any],
    based_on_failures: list[str],
    failure_index: dict[str, set[str]],
) -> list[str]:
    labels: list[str] = []
    if not based_on_failures:
        labels.append("missing_based_on_failures")
    elif not any(
        failure in failure_index["ids"] or _failure_type_from_reference(failure) in failure_index["types"]
        for failure in based_on_failures
    ):
        labels.append("not_failure_driven")
    if not _string_value(proposal.get("change_surface")):
        labels.append("missing_change_surface")
    if not _string_value(proposal.get("target_scope")):
        labels.append("missing_target_scope")
    if not isinstance(proposal.get("verification_plan"), dict):
        labels.append("missing_verification_plan")
    if not isinstance(proposal.get("rollback_rule"), dict):
        labels.append("missing_rollback_rule")
    return labels


def _load_jsonl_dicts(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                items.append(value)
    return items


def _load_outcome_items(outcomes: list[dict[str, Any]] | str | Path) -> list[dict[str, Any]]:
    if isinstance(outcomes, list):
        return [item for item in outcomes if isinstance(item, dict)]
    source_path = Path(outcomes)
    if source_path.suffix == ".jsonl":
        items: list[dict[str, Any]] = []
        for line in source_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    items.append(value)
        return items
    payload, _ = _load_object(source_path)
    if isinstance(payload.get("outcomes"), list):
        return [item for item in payload["outcomes"] if isinstance(item, dict)]
    if isinstance(payload.get("patterns"), list):
        raise ValueError("expected proposal outcomes, got patterns payload")
    return [payload]


def _load_optional_execution_artifact(
    value: dict[str, Any] | str | Path | None,
) -> tuple[dict[str, Any], str | None]:
    if value is None:
        return {}, None
    payload, path = _load_object(value)
    return payload, str(path) if path is not None else "inline"


def _registered_profile_artifact_status(artifact: dict[str, Any]) -> dict[str, Any]:
    if not artifact:
        return {
            "registered": False,
            "registered_profile_id": None,
            "registry_ref": None,
        }
    registered_profile = artifact.get("registered_profile")
    if not isinstance(registered_profile, dict):
        registered_profile = {}
    registered = bool(registered_profile.get("registered"))
    registered_profile_id = _string_value(
        registered_profile.get("registered_profile_id")
    )
    if registered and not registered_profile_id:
        registered_profile_id = _string_value(artifact.get("proposed_profile_id"))
    return {
        "registered": registered,
        "registered_profile_id": registered_profile_id,
        "registry_ref": _string_value(registered_profile.get("registry_ref")),
    }


def _load_gate_decision_items(
    value: list[dict[str, Any] | str | Path] | str | Path | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    if value is None:
        return [], []
    if isinstance(value, list):
        items: list[dict[str, Any]] = []
        refs: list[str] = []
        for item in value:
            if isinstance(item, dict):
                items.append(item)
                if "inline" not in refs:
                    refs.append("inline")
                continue
            payload, path = _load_object(item)
            items.append(payload)
            refs.append(str(path) if path is not None else "inline")
        return items, refs
    payload, path = _load_object(value)
    ref = str(path) if path is not None else "inline"
    if isinstance(payload.get("decisions"), list):
        return [item for item in payload["decisions"] if isinstance(item, dict)], [ref]
    if isinstance(payload.get("policy_results"), list):
        return [payload], [ref]
    return [payload], [ref]


def _execution_artifact_status(
    *,
    artifact: dict[str, Any],
    artifact_ref: str | None,
    expected_profile_id: str,
    artifact_type: str,
) -> dict[str, Any]:
    if not artifact:
        return {
            "status": "missing",
            "artifact_ref": None,
            "hard_blocker": f"{artifact_type}_missing",
        }
    profile_id = _artifact_prompt_profile(artifact)
    if profile_id and profile_id != expected_profile_id:
        return {
            "status": "profile_mismatch",
            "artifact_ref": artifact_ref or "inline",
            "prompt_profile": profile_id,
            "expected_profile_id": expected_profile_id,
            "hard_blocker": f"{artifact_type}_profile_mismatch",
        }
    if artifact_type == "prompt_leakage_audit":
        audit_status = _string_value(artifact.get("audit_status")) or _string_value(
            artifact.get("status")
        )
        leak_count = artifact.get("leak_count")
        if audit_status == "failed" or (
            _is_plain_number(leak_count) and float(leak_count) > 0
        ):
            return {
                "status": "failed",
                "artifact_ref": artifact_ref or "inline",
                "prompt_profile": profile_id,
                "hard_blocker": "prompt_leakage_audit_failed",
            }
        return {
            "status": "present",
            "artifact_ref": artifact_ref or "inline",
            "prompt_profile": profile_id,
        }
    artifact_status = _string_value(artifact.get("status")) or "unknown"
    if artifact_status not in {"completed", "written", "passed"}:
        return {
            "status": "failed",
            "artifact_ref": artifact_ref or "inline",
            "prompt_profile": profile_id,
            "artifact_status": artifact_status,
            "hard_blocker": f"{artifact_type}_failed",
        }
    runtime_error_count = _artifact_runtime_error_count(artifact)
    if runtime_error_count > 0:
        return {
            "status": "runtime_errors",
            "artifact_ref": artifact_ref or "inline",
            "prompt_profile": profile_id,
            "runtime_error_count": runtime_error_count,
            "hard_blocker": f"{artifact_type}_runtime_errors",
        }
    return {
        "status": "present",
        "artifact_ref": artifact_ref or "inline",
        "prompt_profile": profile_id,
        "row_count": _artifact_row_count(artifact),
    }


def _execution_gate_preflight(
    decisions: list[dict[str, Any]],
    decision_refs: list[str],
) -> dict[str, Any]:
    if not decisions:
        return {
            "status": "missing",
            "decision_refs": decision_refs,
            "decision_count": 0,
            "blocking": False,
            "hard_blockers": ["gate_decision_missing"],
            "canary_allowed": False,
        }
    hard_blockers: list[str] = []
    results = []
    for decision in decisions:
        gate = decision.get("gate") if isinstance(decision.get("gate"), dict) else {}
        policy_id = (
            _string_value(decision.get("policy_id"))
            or _string_value(decision.get("composition_id"))
            or _gate_policy_id_from_decision(decision)
        )
        status = _string_value(decision.get("status")) or "unknown"
        blockers = _string_list(decision.get("hard_blockers"))
        canary_allowed = bool(gate.get("canary_allowed", False))
        blocking = (
            status in {"blocked", "needs_paired_repeat", "variance_review_required"}
            or bool(blockers)
            or not canary_allowed
        )
        if blocking:
            hard_blockers.append(f"gate_policy_blocked:{policy_id}")
            hard_blockers.extend(blockers)
        results.append({
            "policy_id": policy_id,
            "status": status,
            "canary_allowed": canary_allowed,
            "blocking": blocking,
            "hard_blockers": blockers,
        })
    blocking = bool(hard_blockers)
    return {
        "status": "blocked" if blocking else "passed",
        "decision_refs": decision_refs,
        "decision_count": len(decisions),
        "policy_results": results,
        "blocking": blocking,
        "hard_blockers": _dedupe_strings(hard_blockers),
        "canary_allowed": not blocking,
    }


def _registered_profile_execution_artifact_stage(
    *,
    name: str,
    artifact_status: Any,
) -> dict[str, Any]:
    status = artifact_status if isinstance(artifact_status, dict) else {}
    return {
        "name": name,
        "status": _string_value(status.get("status")) or "missing",
        "artifact_ref": _string_value(status.get("artifact_ref")),
        "hard_blocker": _string_value(status.get("hard_blocker")),
        "row_count": status.get("row_count"),
        "executes_experiment": False,
    }


def _registered_profile_execution_gate_stage_status(
    gate_preflight: dict[str, Any],
) -> str:
    status = _string_value(gate_preflight.get("status")) or "missing"
    if status == "passed":
        return "passed"
    if status == "missing":
        return "missing"
    return "blocked"


def _artifact_ref_for_stage(artifact_status: Any) -> str | None:
    if not isinstance(artifact_status, dict):
        return None
    return _string_value(artifact_status.get("artifact_ref"))


def _load_prompt_leakage_rows(
    value: list[dict[str, Any]] | dict[str, Any] | str | Path | None,
) -> list[dict[str, Any]] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        rows = value.get("rows")
        if isinstance(rows, list):
            return [item for item in rows if isinstance(item, dict)]
        raise ValueError("prompt_leakage_rows object must contain rows list")
    source_path = Path(value)
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return [item for item in payload["rows"] if isinstance(item, dict)]
    raise ValueError("prompt_leakage_rows must be a JSON array or object with rows")


def _registered_profile_run_input_execution_status(
    artifact: dict[str, Any] | str | Path | None,
    *,
    artifact_name: str,
) -> dict[str, Any]:
    if artifact is None:
        return {
            "status": "missing",
            "artifact_ref": None,
            "required_before_canary": True,
        }
    ref = "inline" if isinstance(artifact, dict) else str(artifact)
    return {
        "status": "consumed",
        "artifact_ref": ref,
        "required_before_canary": True,
        "artifact": artifact_name,
    }


def _registered_profile_run_model_eval_execution_status(
    generated_artifact: dict[str, Any] | None,
    consumed_artifact: dict[str, Any] | str | Path | None,
    *,
    output_path: Path,
    artifact_name: str,
) -> dict[str, Any]:
    if generated_artifact is not None:
        return {
            "status": "generated",
            "output_path": str(output_path),
            "row_count": _artifact_row_count(generated_artifact),
            "prompt_profile": _artifact_prompt_profile(generated_artifact),
            "required_before_canary": True,
            "artifact": artifact_name,
        }
    return _registered_profile_run_input_execution_status(
        consumed_artifact,
        artifact_name=artifact_name,
    )


def _registered_profile_run_dev_gate_source_status(
    generated_artifact: dict[str, Any] | None,
    consumed_artifact: dict[str, Any] | str | Path | None,
    *,
    output_path: Path,
) -> dict[str, Any]:
    if generated_artifact is not None:
        slices = generated_artifact.get("slices")
        metric_delta = generated_artifact.get("metric_delta")
        return {
            "status": "generated",
            "output_path": str(output_path),
            "slice_count": len(slices) if isinstance(slices, list) else 0,
            "metric_count": len(metric_delta) if isinstance(metric_delta, dict) else 0,
            "required_before_auto_gate": True,
            "artifact": "dev_gate_source",
        }
    if consumed_artifact is None:
        return {
            "status": "missing",
            "artifact_ref": None,
            "required_before_auto_gate": True,
        }
    ref = "inline" if isinstance(consumed_artifact, dict) else str(consumed_artifact)
    return {
        "status": "consumed",
        "artifact_ref": ref,
        "required_before_auto_gate": True,
        "artifact": "dev_gate_source",
    }


def _registered_profile_run_gate_execution_status(
    gate_decisions: list[dict[str, Any] | str | Path] | str | Path | None,
) -> dict[str, Any]:
    decisions, refs = _load_gate_decision_items(gate_decisions)
    if not decisions:
        return {
            "status": "missing",
            "decision_count": 0,
            "decision_refs": [],
            "required_before_canary": True,
        }
    return {
        "status": "consumed",
        "decision_count": len(decisions),
        "decision_refs": refs,
        "required_before_canary": True,
    }


def _build_registered_profile_model_eval_from_rows(
    *,
    rows: list[dict[str, Any]],
    prompt_profile: str,
    prompt_profile_registration: dict[str, Any] | str | Path,
    chat_completion: Any | None,
    model: str,
    base_url: str,
    model_provider: str,
    api_key_env: str | None,
    timeout_seconds: int,
    temperature: float,
    max_tokens: int,
    judge_mode: str,
    round_id: str,
    evaluation_split: str = "all",
) -> dict[str, Any]:
    if not rows:
        raise ValueError("model eval rows must not be empty")
    return build_smol_worldcup_model_eval(
        fetcher=_smol_worldcup_rows_fetcher(rows),
        chat_completion=chat_completion,
        timeout_seconds=timeout_seconds,
        page_size=min(max(len(rows), 1), 100),
        limit=len(rows),
        model=model,
        base_url=base_url,
        model_provider=model_provider,
        api_key_env=api_key_env,
        temperature=temperature,
        max_tokens=max_tokens,
        round_id=round_id,
        prompt_profile=prompt_profile,
        prompt_profile_registration=prompt_profile_registration,
        evaluation_split=evaluation_split,
        judge_mode=judge_mode,
    )


def _smol_worldcup_rows_fetcher(rows: list[dict[str, Any]]) -> Any:
    def fetcher(url: str, timeout_seconds: int = 30) -> FetchedResource:
        del timeout_seconds
        offset, length = _rows_fetch_window(url)
        page_rows = rows[offset : offset + length]
        payload = {
            "num_rows_total": len(rows),
            "rows": [
                {"row_idx": offset + index, "row": row, "truncated_cells": []}
                for index, row in enumerate(page_rows)
            ],
        }
        return FetchedResource(
            url=url,
            status_code=200,
            content_type="application/json",
            text=json.dumps(payload),
            fetcher="registered-profile-inline-rows",
        )

    return fetcher


def _rows_fetch_window(url: str) -> tuple[int, int]:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    offset = _first_int_query_value(query, "offset", default=0)
    length = _first_int_query_value(query, "length", default=len(query) or 100)
    return max(offset, 0), max(length, 1)


def _first_int_query_value(
    query: dict[str, list[str]],
    key: str,
    *,
    default: int,
) -> int:
    values = query.get(key)
    if not values:
        return default
    try:
        return int(values[0])
    except (TypeError, ValueError):
        return default


def _registered_profile_gate_metric_table(
    dev_model_eval: dict[str, Any],
) -> list[dict[str, Any]]:
    direct_rows = _artifact_table_rows_from_keys(
        dev_model_eval,
        ("gate_metric_table", "metric_table"),
    )
    if direct_rows is not None:
        return direct_rows
    metric_delta = _metric_delta_map(dev_model_eval)
    return [
        {"metric": metric_name, "delta": delta}
        for metric_name, delta in sorted(metric_delta.items())
    ]


def _registered_profile_gate_slice_table(
    dev_model_eval: dict[str, Any],
) -> list[dict[str, Any]]:
    direct_rows = _artifact_table_rows_from_keys(
        dev_model_eval,
        ("gate_slice_table", "slice_table", "slices"),
    )
    if direct_rows is not None:
        return direct_rows
    regressions = _dict_list(dev_model_eval.get("slice_regressions"))
    if regressions:
        return regressions
    return _dict_list(dev_model_eval.get("top_regression_slices"))


def _artifact_table_rows_from_keys(
    artifact: dict[str, Any],
    keys: tuple[str, ...],
) -> list[dict[str, Any]] | None:
    for key in keys:
        value = artifact.get(key)
        if isinstance(value, list):
            if all(isinstance(item, dict) for item in value):
                return list(value)
            continue
        if isinstance(value, dict):
            rows = value.get("rows")
            if isinstance(rows, list) and all(isinstance(item, dict) for item in rows):
                return list(rows)
    return None


def _artifact_eval_split(artifact: dict[str, Any]) -> str | None:
    dataset = artifact.get("dataset") if isinstance(artifact.get("dataset"), dict) else {}
    return (
        _string_value(artifact.get("split"))
        or _string_value(dataset.get("evaluation_split"))
        or _string_value(dataset.get("split"))
    )


def _artifact_prompt_profile(artifact: dict[str, Any]) -> str | None:
    model = artifact.get("model") if isinstance(artifact.get("model"), dict) else {}
    return (
        _string_value(artifact.get("prompt_profile"))
        or _string_value(artifact.get("target_prompt_profile"))
        or _string_value(model.get("prompt_profile"))
    )


def _artifact_runtime_error_count(artifact: dict[str, Any]) -> int:
    failure_summary = (
        artifact.get("failure_summary")
        if isinstance(artifact.get("failure_summary"), dict)
        else {}
    )
    value = failure_summary.get("runtime_error_count")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return 0


def _registered_profile_gate_quality_constraints() -> dict[str, Any]:
    return {
        "min_metric_delta": {"SHIFT": 0.000001},
        "min_slice_score_percent": 1.0,
        "target_smoke_max_failure_count": 0,
        "target_smoke_max_runtime_error_count": 0,
        "dev_model_eval_max_runtime_error_count": 0,
    }


def _registered_profile_quality_gate_policy_ids() -> list[str]:
    return [
        "min-improvement-gate",
        "min-quality-gate",
        "target-smoke-success-gate",
    ]


def _registered_profile_required_gate_policy_ids() -> list[str]:
    return ["slice-dev-hard-gate", *_registered_profile_quality_gate_policy_ids()]


def _registered_profile_gate_execution_quality(
    *,
    target_smoke: dict[str, Any],
    dev_model_eval: dict[str, Any],
) -> dict[str, Any]:
    return {
        "target_smoke": _model_eval_quality_summary(target_smoke),
        "dev_model_eval": _model_eval_quality_summary(dev_model_eval),
    }


def _model_eval_quality_summary(artifact: dict[str, Any]) -> dict[str, Any]:
    failure_summary = (
        artifact.get("failure_summary")
        if isinstance(artifact.get("failure_summary"), dict)
        else {}
    )
    summary = {
        "failure_count": _summary_number(failure_summary, "failure_count"),
        "runtime_error_count": _summary_number(failure_summary, "runtime_error_count"),
    }
    if _is_plain_number(failure_summary.get("empty_output_count")):
        summary["empty_output_count"] = float(failure_summary["empty_output_count"])
    return summary


def _artifact_row_count(artifact: dict[str, Any]) -> int | None:
    value = artifact.get("row_count")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    dataset = artifact.get("dataset") if isinstance(artifact.get("dataset"), dict) else {}
    value = dataset.get("row_count")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _slice_score_breakdown(report: dict[str, Any]) -> dict[str, Any]:
    direct = report.get("score_breakdown")
    if isinstance(direct, dict):
        return direct
    if any(isinstance(report.get(key), dict) for key in ("by_category", "by_auto_grade", "by_axis")):
        return report
    path_value = _string_value(report.get("score_breakdown_path"))
    if path_value:
        path = Path(path_value)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    return {}


def _default_smol_prompt_modules() -> list[dict[str, Any]]:
    base_sections = {
        "role": "Act as a bounded local diagnostic prompt module.",
        "task_contract": "Answer the target slice while preserving benchmark-specific output contracts.",
        "output_format": "Return the requested answer format without unrelated commentary.",
        "constraints": "Avoid broad prompt-profile changes and preserve protected slices.",
    }
    return [
        _prompt_module(
            module_id="reasoning_math",
            target_slices=["reasoning", "math"],
            protected_slices=["hallucination_trap", "self_correction"],
            sections=base_sections,
        ),
        _prompt_module(
            module_id="hallucination_verification",
            target_slices=["hallucination_trap", "refusal_balance"],
            protected_slices=["knowledge_synthesis", "confidence_calibration"],
            sections=base_sections,
        ),
        _prompt_module(
            module_id="knowledge_synthesis",
            target_slices=["knowledge_synthesis"],
            protected_slices=["hallucination_trap", "reasoning"],
            sections=base_sections,
        ),
        _prompt_module(
            module_id="metacognition_calibration",
            target_slices=["metacognition", "confidence_calibration"],
            protected_slices=["reasoning", "self_correction"],
            sections=base_sections,
        ),
        _prompt_module(
            module_id="multilingual_translation",
            target_slices=["multilingual_bn", "multilingual_ko"],
            protected_slices=["multilingual_pt", "multilingual_th", "multilingual_tr"],
            sections=base_sections,
        ),
        _prompt_module(
            module_id="multilingual_variant_explanation",
            target_slices=["multilingual_pt", "multilingual_th", "multilingual_tr", "multilingual_ar"],
            protected_slices=["multilingual_bn", "multilingual_ko", "multilingual_th", "multilingual_tr", "multilingual_ar"],
            sections=base_sections,
        ),
        _prompt_module(
            module_id="self_correction",
            target_slices=["self_correction"],
            protected_slices=["reasoning", "metacognition"],
            sections=base_sections,
        ),
        _prompt_module(
            module_id="coding",
            target_slices=["coding"],
            protected_slices=["reasoning", "math"],
            sections=base_sections,
        ),
    ]


def _prompt_module(
    *,
    module_id: str,
    target_slices: list[str],
    protected_slices: list[str],
    sections: dict[str, str],
) -> dict[str, Any]:
    return {
        "module_id": module_id,
        "target_slices": target_slices,
        "sections": dict(sections),
        "protected_slices": protected_slices,
        "allowed_edit_sections": ["task_contract", "output_format", "constraints"],
        "rollback_rule": {
            "if": ["protected_slice_regression", "aggregate_dev_delta_lt_0"],
            "then": "block_candidate_before_canary",
        },
    }


def _default_smol_module_routing() -> list[dict[str, str]]:
    return [
        {"slice_prefix": target, "module_id": module["module_id"]}
        for module in _default_smol_prompt_modules()
        for target in module["target_slices"]
    ]


def _slice_rows_from_breakdowns(
    *,
    baseline_breakdown: dict[str, Any],
    candidate_breakdown: dict[str, Any],
    split: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    dimensions = [
        ("by_category", "category"),
        ("by_auto_grade", "auto_grade"),
        ("by_axis", "axis"),
    ]
    for source_key, dimension in dimensions:
        baseline_items = baseline_breakdown.get(source_key)
        candidate_items = candidate_breakdown.get(source_key)
        if not isinstance(candidate_items, dict):
            continue
        if not isinstance(baseline_items, dict):
            baseline_items = {}
        for slice_name in sorted(set(baseline_items) | set(candidate_items)):
            baseline_entry = baseline_items.get(slice_name)
            candidate_entry = candidate_items.get(slice_name)
            before = _slice_score_percent(baseline_entry)
            after = _slice_score_percent(candidate_entry)
            if after is None:
                continue
            delta = round(after - before, 6) if before is not None else None
            row = {
                "slice_key": f"{split}/{dimension}/{slice_name}",
                "dimension": dimension,
                "slice_name": str(slice_name),
                "metric": "score_percent",
                "before": round(before, 6) if before is not None else None,
                "after": round(after, 6),
                "delta": delta,
                "row_count": _slice_row_count(candidate_entry),
                "gate": (
                    "watch"
                    if delta is None
                    else ("blocked" if delta < 0 else "passed")
                ),
                "rollback_labels": ["slice_regression"] if delta is not None and delta < 0 else [],
            }
            rows.append(row)
    rows.sort(key=lambda item: (item["dimension"], item["slice_name"]))
    return rows


def _load_table_rows(
    value: list[dict[str, Any]] | dict[str, Any] | str | Path,
) -> tuple[list[dict[str, Any]], Path | None]:
    if isinstance(value, list):
        if all(isinstance(item, dict) for item in value):
            return list(value), None
        raise ValueError("table rows must be objects")
    if isinstance(value, dict):
        rows = value.get("rows")
        if isinstance(rows, list) and all(isinstance(item, dict) for item in rows):
            return list(rows), None
        raise ValueError("table object must contain rows as a list of objects")
    path = Path(value)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return list(payload), path
    if isinstance(payload, dict):
        rows = payload.get("rows")
        if isinstance(rows, list) and all(isinstance(item, dict) for item in rows):
            return list(rows), path
    raise ValueError(f"{path} must contain a JSON array or an object with rows")


def _load_optional_object_payload(
    value: dict[str, Any] | str | Path | None,
) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    payload, _ = _load_object(value)
    return payload


def _metric_delta_from_table_rows(rows: list[dict[str, Any]]) -> dict[str, float]:
    metric_delta: dict[str, float] = {}
    for row in rows:
        metric_name = (
            _string_value(row.get("metric"))
            or _string_value(row.get("metric_name"))
            or _string_value(row.get("name"))
        )
        if not metric_name:
            continue
        delta = _row_delta(row)
        if delta is not None:
            metric_delta[metric_name] = round(delta, 6)
    return metric_delta


def _slice_rows_from_table_rows(
    *,
    rows: list[dict[str, Any]],
    split: str,
) -> list[dict[str, Any]]:
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        dimension = _string_value(row.get("dimension")) or "slice"
        slice_name = (
            _string_value(row.get("slice_name"))
            or _string_value(row.get("slice"))
            or _string_value(row.get("name"))
            or "unknown"
        )
        metric = _string_value(row.get("metric")) or "score_percent"
        before = _row_number(row, "before", "baseline", "control")
        after = _row_number(row, "after", "candidate", "treatment")
        delta = _row_delta(row)
        explicit_gate = _string_value(row.get("gate"))
        gate = explicit_gate or (
            "watch" if delta is None else ("blocked" if delta < 0 else "passed")
        )
        normalized_rows.append({
            "slice_key": (
                _string_value(row.get("slice_key"))
                or f"{split}/{dimension}/{slice_name}"
            ),
            "dimension": dimension,
            "slice_name": slice_name,
            "metric": metric,
            "before": round(before, 6) if before is not None else None,
            "after": round(after, 6) if after is not None else None,
            "delta": round(delta, 6) if delta is not None else None,
            "row_count": _row_int(row, "row_count", "n"),
            "gate": gate,
            "rollback_labels": (
                ["slice_regression"]
                if gate == "blocked" or (delta is not None and delta < 0)
                else []
            ),
        })
    normalized_rows.sort(key=lambda item: (item["dimension"], item["slice_name"]))
    return normalized_rows


def _gate_quality_checks(
    *,
    metric_delta: dict[str, float],
    slices: list[dict[str, Any]],
    quality_constraints: dict[str, Any] | None,
    execution_quality: dict[str, Any] | None,
) -> dict[str, Any]:
    constraints = quality_constraints if isinstance(quality_constraints, dict) else {}
    hard_blockers: list[str] = []
    checks: dict[str, Any] = {}

    min_metric_delta = (
        constraints.get("min_metric_delta")
        if isinstance(constraints.get("min_metric_delta"), dict)
        else {}
    )
    metric_checks = []
    for metric_name, threshold_value in sorted(min_metric_delta.items()):
        if not _is_plain_number(threshold_value):
            continue
        threshold = float(threshold_value)
        observed = metric_delta.get(str(metric_name))
        passed = observed is not None and observed >= threshold
        if not passed:
            hard_blockers.append(f"min_metric_delta_not_met:{metric_name}")
        metric_checks.append({
            "metric": str(metric_name),
            "observed_delta": observed,
            "min_delta": threshold,
            "passed": passed,
        })
    if metric_checks:
        checks["min_metric_delta"] = metric_checks

    min_slice_score = constraints.get("min_slice_score_percent")
    if _is_plain_number(min_slice_score):
        threshold = float(min_slice_score)
        failing_slices = [
            {
                "slice_key": _string_value(item.get("slice_key")) or "unknown",
                "slice_name": _string_value(item.get("slice_name")) or "unknown",
                "metric": _string_value(item.get("metric")) or "score_percent",
                "after": item.get("after"),
                "min_score_percent": threshold,
            }
            for item in slices
            if (
                (_string_value(item.get("metric")) or "score_percent") == "score_percent"
                and _is_plain_number(item.get("after"))
                and float(item["after"]) < threshold
            )
        ]
        if failing_slices:
            hard_blockers.append("min_slice_score_percent_not_met")
        checks["min_slice_score_percent"] = {
            "min_score_percent": threshold,
            "failing_slice_count": len(failing_slices),
            "failing_slices": failing_slices[:5],
            "passed": not failing_slices,
        }

    execution_checks = _execution_quality_checks(
        execution_quality=execution_quality,
        constraints=constraints,
    )
    if execution_checks:
        hard_blockers.extend(_string_list(execution_checks.get("hard_blockers")))
        checks["execution_quality"] = execution_checks

    return {
        "passed": not hard_blockers,
        "constraints": constraints,
        "checks": checks,
        "hard_blockers": _dedupe_strings(hard_blockers),
    }


def _slice_dev_gate_input_without_quality_blockers(
    gate_input: dict[str, Any],
) -> dict[str, Any]:
    payload = dict(gate_input)
    payload["hard_blockers"] = [
        blocker
        for blocker in _string_list(gate_input.get("hard_blockers"))
        if not _is_quality_gate_blocker(blocker)
    ]
    return payload


def _evaluate_quality_gate_policy(
    *,
    policy_id: str,
    gate_input: dict[str, Any],
) -> dict[str, Any]:
    split = _string_value(gate_input.get("split")) or "unknown"
    quality_checks = (
        gate_input.get("quality_checks")
        if isinstance(gate_input.get("quality_checks"), dict)
        else {}
    )
    hard_blockers = _quality_gate_policy_blockers(
        policy_id=policy_id,
        hard_blockers=_string_list(gate_input.get("hard_blockers")),
    )
    canary_allowed = split == "dev" and not hard_blockers
    return {
        "status": "passed_for_canary" if canary_allowed else "blocked",
        "schema_version": GATE_POLICY_DECISION_SCHEMA_VERSION,
        "split": split,
        "metric_delta": gate_input.get("metric_delta", {}),
        "gate": {
            "dev_passed": canary_allowed,
            "canary_allowed": canary_allowed,
            "promotion_ready": False,
        },
        "hard_blockers": hard_blockers,
        "top_regression_slices": [],
        "slice_regressions": [],
        "quality_checks": quality_checks,
        "claim_boundary": "benchmark-agnostic quality gate decision only",
        "executes_tool": False,
        "official_scores_claimed": False,
    }


def _quality_gate_policy_blockers(
    *,
    policy_id: str,
    hard_blockers: list[str],
) -> list[str]:
    if policy_id == "min-improvement-gate":
        return _dedupe_strings([
            blocker
            for blocker in hard_blockers
            if blocker.startswith("min_metric_delta_not_met")
        ])
    if policy_id == "min-quality-gate":
        return _dedupe_strings([
            blocker
            for blocker in hard_blockers
            if blocker == "min_slice_score_percent_not_met"
        ])
    if policy_id == "target-smoke-success-gate":
        return _dedupe_strings([
            blocker
            for blocker in hard_blockers
            if blocker.startswith("target_smoke_")
            or blocker.startswith("dev_model_eval_")
        ])
    return []


def _is_quality_gate_blocker(blocker: str) -> bool:
    return bool(
        blocker.startswith("min_metric_delta_not_met")
        or blocker == "min_slice_score_percent_not_met"
        or blocker.startswith("target_smoke_")
        or blocker.startswith("dev_model_eval_")
    )


def _execution_quality_checks(
    *,
    execution_quality: dict[str, Any] | None,
    constraints: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(execution_quality, dict):
        return {}
    hard_blockers: list[str] = []
    checks: dict[str, Any] = {}
    for artifact_name in ("target_smoke", "dev_model_eval"):
        summary = (
            execution_quality.get(artifact_name)
            if isinstance(execution_quality.get(artifact_name), dict)
            else {}
        )
        artifact_checks: dict[str, Any] = {}
        for field, constraint_key, blocker in (
            ("failure_count", f"{artifact_name}_max_failure_count", f"{artifact_name}_failure_count_gt_max"),
            ("runtime_error_count", f"{artifact_name}_max_runtime_error_count", f"{artifact_name}_runtime_error_count_gt_max"),
            ("empty_output_count", f"{artifact_name}_max_empty_output_count", f"{artifact_name}_empty_output_count_gt_max"),
        ):
            if not _is_plain_number(constraints.get(constraint_key)):
                continue
            observed = _summary_number(summary, field)
            maximum = float(constraints[constraint_key])
            passed = observed <= maximum
            if not passed:
                hard_blockers.append(blocker)
            artifact_checks[field] = {
                "observed": observed,
                "max": maximum,
                "passed": passed,
            }
        if artifact_checks:
            checks[artifact_name] = artifact_checks
    return {
        "passed": not hard_blockers,
        "checks": checks,
        "hard_blockers": _dedupe_strings(hard_blockers),
    }


def _summary_number(summary: dict[str, Any], key: str) -> float:
    value = summary.get(key)
    if _is_plain_number(value):
        return float(value)
    return 0.0


def _slice_matrices_from_paired_repeat_manifest(
    manifest: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    matrices = manifest.get("slice_matrices")
    if not isinstance(matrices, list) or not all(
        isinstance(item, dict) for item in matrices
    ):
        raise ValueError("paired_repeat_manifest must contain slice_matrices")
    matrix_refs = _string_list(manifest.get("matrix_refs"))
    if len(matrix_refs) != len(matrices):
        matrix_refs = [
            f"inline#repeat-{index}"
            for index in range(1, len(matrices) + 1)
        ]
    return list(matrices), matrix_refs


def _slice_patch_outcome_failure_labels(
    *,
    gate_payload: dict[str, Any],
    accepted_for_next_stage: bool,
) -> list[str]:
    labels: list[str] = []
    for label in _string_list(gate_payload.get("hard_blockers")):
        if label not in labels:
            labels.append(label)
    for row in _dict_list(gate_payload.get("slice_regressions")):
        for label in _string_list(row.get("rollback_labels")):
            if label not in labels:
                labels.append(label)
        if _string_value(row.get("gate")) == "blocked" and "slice_regression" not in labels:
            labels.append("slice_regression")
    if not labels and not accepted_for_next_stage:
        status = _string_value(gate_payload.get("status")) or "gate_blocked"
        labels.append(status)
    return labels


def _slice_patch_outcome_next_actions(
    *,
    accepted_for_next_stage: bool,
) -> list[str]:
    if accepted_for_next_stage:
        return [
            "run canary only after required gates",
            "record canary outcome before promotion",
        ]
    return [
        "keep candidate blocked",
        "feed failure_labels into optimizer context",
        "generate narrower section-local candidate",
    ]


def _slice_optimizer_selection_score(
    *,
    optimizer: str,
    outcomes: list[dict[str, Any]],
    target_scope: str,
    failure_labels: list[str],
) -> dict[str, Any]:
    score = 0
    accepted_count = 0
    blocked_count = 0
    matching_failure_blocked_count = 0
    relevant_outcome_ids: list[str] = []
    for outcome in outcomes:
        if _string_value(outcome.get("optimizer")) != optimizer:
            continue
        outcome_scope = _slice_outcome_target_scope(outcome)
        if target_scope != "unknown" and outcome_scope != target_scope:
            continue
        relevant_outcome_ids.append(
            _string_value(outcome.get("outcome_id"))
            or _string_value(outcome.get("patch_id"))
            or "unknown-outcome"
        )
        if bool(outcome.get("accepted_for_next_stage")):
            accepted_count += 1
            score += 3
            continue
        blocked_count += 1
        score -= 1
        if _has_label_overlap(_slice_outcome_failure_labels(outcome), failure_labels):
            matching_failure_blocked_count += 1
            score -= 3
    return {
        "optimizer": optimizer,
        "score": score,
        "accepted_count": accepted_count,
        "blocked_count": blocked_count,
        "matching_failure_blocked_count": matching_failure_blocked_count,
        "relevant_outcome_ids": relevant_outcome_ids,
    }


def _slice_outcome_target_scope(outcome: dict[str, Any]) -> str:
    learning_signal = (
        outcome.get("learning_signal")
        if isinstance(outcome.get("learning_signal"), dict)
        else {}
    )
    explicit = _string_value(learning_signal.get("target_scope"))
    if explicit:
        return explicit
    module_id = _string_value(outcome.get("module_id")) or "unknown_module"
    section_id = _string_value(outcome.get("section_id")) or "unknown_section"
    return f"{module_id}/{section_id}"


def _slice_outcome_failure_labels(outcome: dict[str, Any]) -> list[str]:
    labels = _string_list(outcome.get("failure_labels"))
    if labels:
        return labels
    learning_signal = (
        outcome.get("learning_signal")
        if isinstance(outcome.get("learning_signal"), dict)
        else {}
    )
    return _string_list(learning_signal.get("failure_labels"))


def _has_label_overlap(left: list[str], right: list[str]) -> bool:
    if not right:
        return False
    return bool(set(left) & set(right))


def _dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = _string_value(value)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _row_delta(row: dict[str, Any]) -> float | None:
    if _is_plain_number(row.get("delta")):
        return float(row["delta"])
    before = _row_number(row, "before", "baseline", "control")
    after = _row_number(row, "after", "candidate", "treatment")
    if before is None or after is None:
        return None
    return after - before


def _row_number(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if _is_plain_number(value):
            return float(value)
    return None


def _row_int(row: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _slice_score_percent(entry: Any) -> float | None:
    if not isinstance(entry, dict):
        return None
    value = entry.get("score_percent")
    if _is_plain_number(value):
        return float(value)
    score = entry.get("score")
    max_score = entry.get("max_score")
    if _is_plain_number(score) and _is_plain_number(max_score) and float(max_score) != 0:
        return float(score) / float(max_score) * 100.0
    return None


def _slice_row_count(entry: Any) -> int | None:
    if not isinstance(entry, dict):
        return None
    value = entry.get("row_count")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _slice_metric_delta(
    *,
    baseline_payload: dict[str, Any],
    candidate_payload: dict[str, Any],
    evaluation_payload: dict[str, Any],
) -> dict[str, float]:
    if evaluation_payload:
        explicit = _slice_evaluation_metric_delta(evaluation_payload)
        if explicit:
            return {key: round(value, 6) for key, value in explicit.items()}
    baseline_metrics = _slice_metrics(baseline_payload)
    candidate_metrics = _slice_metrics(candidate_payload)
    deltas = {}
    for metric_name in sorted(set(baseline_metrics) & set(candidate_metrics)):
        deltas[metric_name] = round(
            candidate_metrics[metric_name] - baseline_metrics[metric_name],
            6,
        )
    return deltas


def _slice_evaluation_metric_delta(evaluation: dict[str, Any]) -> dict[str, float]:
    explicit = evaluation.get("metric_delta")
    if isinstance(explicit, dict):
        normalized = {
            str(key): float(value)
            for key, value in explicit.items()
            if _is_plain_number(value)
        }
        if normalized:
            return normalized
    for split in ("dev", "canary", "holdout", "external"):
        split_delta = evaluation.get(f"{split}_delta")
        if isinstance(split_delta, dict):
            normalized = {
                str(key): float(value)
                for key, value in split_delta.items()
                if _is_plain_number(value)
            }
            if normalized:
                return normalized
        if _is_plain_number(split_delta):
            return {split: float(split_delta)}
    return _metric_delta_map(evaluation)


def _slice_regression_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    regressions = []
    for item in value:
        if not isinstance(item, dict):
            continue
        delta = item.get("delta")
        gate = _string_value(item.get("gate"))
        if not _is_plain_number(delta) and gate != "blocked":
            continue
        if _is_plain_number(delta) and float(delta) >= 0 and gate != "blocked":
            continue
        regressions.append(
            {
                "slice_key": _string_value(item.get("slice_key")) or "unknown",
                "dimension": _string_value(item.get("dimension")),
                "slice_name": _string_value(item.get("slice_name")),
                "metric": _string_value(item.get("metric")) or "score_percent",
                "delta": round(float(delta), 6) if _is_plain_number(delta) else None,
                "gate": gate or "blocked",
            }
        )
    regressions.sort(
        key=lambda item: (
            item["delta"] if item["delta"] is not None else 0.0,
            item["slice_key"],
        )
    )
    return regressions


def _slice_variance_rows(
    *,
    matrices: list[dict[str, Any]],
    repeat_count: int,
    min_repeats: int,
    regression_delta_threshold: float,
    stable_support_ratio: float,
) -> list[dict[str, Any]]:
    observations: dict[str, list[dict[str, Any]]] = {}
    metadata: dict[str, dict[str, str | None]] = {}
    for matrix in matrices:
        rows = matrix.get("slices")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            slice_key = _string_value(row.get("slice_key")) or "unknown"
            delta = row.get("delta")
            gate = _string_value(row.get("gate"))
            observations.setdefault(slice_key, []).append({
                "delta": float(delta) if _is_plain_number(delta) else None,
                "gate": gate,
            })
            metadata.setdefault(slice_key, {
                "slice_key": slice_key,
                "dimension": _string_value(row.get("dimension")),
                "slice_name": _string_value(row.get("slice_name")),
                "metric": _string_value(row.get("metric")) or "score_percent",
            })
    rows: list[dict[str, Any]] = []
    for slice_key, items in observations.items():
        negative_count = sum(
            1
            for item in items
            if (
                item["delta"] is not None
                and float(item["delta"]) <= regression_delta_threshold
            )
            or (item["delta"] is None and item["gate"] == "blocked")
        )
        numeric_deltas = [
            float(item["delta"])
            for item in items
            if item["delta"] is not None
        ]
        support_ratio = negative_count / repeat_count if repeat_count else 0.0
        if repeat_count < min_repeats:
            classification = "inconclusive" if negative_count else "no_regression"
        elif support_ratio >= stable_support_ratio and negative_count > 0:
            classification = "stable_regression"
        elif negative_count:
            classification = "variance_suspect"
        else:
            classification = "no_regression"
        meta = metadata[slice_key]
        rows.append({
            "slice_key": slice_key,
            "dimension": meta.get("dimension"),
            "slice_name": meta.get("slice_name"),
            "metric": meta.get("metric") or "score_percent",
            "repeat_count": repeat_count,
            "observation_count": len(items),
            "negative_count": negative_count,
            "support_ratio": round(support_ratio, 6),
            "mean_delta": (
                round(sum(numeric_deltas) / len(numeric_deltas), 6)
                if numeric_deltas
                else None
            ),
            "min_delta": round(min(numeric_deltas), 6) if numeric_deltas else None,
            "max_delta": round(max(numeric_deltas), 6) if numeric_deltas else None,
            "classification": classification,
        })
    rows.sort(
        key=lambda item: (
            0 if item["classification"] == "stable_regression" else 1,
            item["mean_delta"] if item["mean_delta"] is not None else 0.0,
            item["slice_key"],
        )
    )
    return rows


def _metric_variance_rows(
    *,
    matrices: list[dict[str, Any]],
    repeat_count: int,
    min_repeats: int,
    regression_delta_threshold: float,
    stable_support_ratio: float,
) -> list[dict[str, Any]]:
    observations: dict[str, list[float]] = {}
    for matrix in matrices:
        metric_delta = matrix.get("metric_delta")
        if not isinstance(metric_delta, dict):
            continue
        for metric_name, value in metric_delta.items():
            if _is_plain_number(value):
                observations.setdefault(str(metric_name), []).append(float(value))
    rows: list[dict[str, Any]] = []
    for metric_name, values in observations.items():
        negative_count = sum(1 for value in values if value <= regression_delta_threshold)
        support_ratio = negative_count / repeat_count if repeat_count else 0.0
        if repeat_count < min_repeats:
            classification = "inconclusive" if negative_count else "no_regression"
        elif support_ratio >= stable_support_ratio and negative_count > 0:
            classification = "stable_regression"
        elif negative_count:
            classification = "variance_suspect"
        else:
            classification = "no_regression"
        rows.append({
            "metric": metric_name,
            "repeat_count": repeat_count,
            "observation_count": len(values),
            "negative_count": negative_count,
            "support_ratio": round(support_ratio, 6),
            "mean_delta": round(sum(values) / len(values), 6) if values else None,
            "min_delta": round(min(values), 6) if values else None,
            "max_delta": round(max(values), 6) if values else None,
            "classification": classification,
        })
    rows.sort(
        key=lambda item: (
            0 if item["classification"] == "stable_regression" else 1,
            item["mean_delta"] if item["mean_delta"] is not None else 0.0,
            item["metric"],
        )
    )
    return rows


def _slice_variance_next_actions(
    *,
    status: str,
    stable_targets: list[dict[str, Any]],
) -> list[str]:
    if status == "needs_paired_repeat":
        return [
            "run paired repeat on the same split for baseline and candidate",
            "rebuild slice matrices before generating another optimizer patch",
        ]
    if status == "blocked" and stable_targets:
        return [
            "build slice repair context from stable_repair_targets[0]",
            "generate only section-local optimizer candidates for the stable slice",
        ]
    if status == "variance_review_required":
        return [
            "do not treat variance_suspect slices as optimizer targets yet",
            "run one more paired repeat or inspect model and judge nondeterminism",
        ]
    return ["existing slice gate may decide canary eligibility"]


def _optimizer_gate_run_status(
    *,
    runtime_probe: dict[str, Any],
    candidates: dict[str, Any],
    materialization: dict[str, Any],
) -> str:
    runtime_ready = bool(runtime_probe.get("runtime_ready", False))
    runtime_probe_status = _string_value(runtime_probe.get("status")) or "unknown"
    if not runtime_ready:
        if runtime_probe_status == "probe_not_executed":
            return "needs_optimizer_runtime_probe"
        return "optimizer_runtime_not_ready"
    candidate_status = _string_value(candidates.get("status")) or "unknown"
    if candidate_status in {
        "optimizer_failed",
        "optimizer_runtime_unsupported",
        "needs_repair_context",
    }:
        return candidate_status
    if candidate_status == "needs_optimizer_execution":
        return "needs_optimizer_execution"
    materialization_status = _string_value(materialization.get("status"))
    if materialization_status:
        return materialization_status
    return "needs_slice_patch_candidate"


def _optimizer_runtime_probe_next_action(
    *,
    status: str,
    runtime_ready: bool,
    execute_probe: bool,
) -> str:
    if runtime_ready:
        return "generate_slice_patch_candidates"
    if not execute_probe:
        return "execute_optimizer_runtime_probe"
    if status == "probe_failed":
        return "fix_optimizer_runtime"
    return "configure_optimizer_runtime"


def _gate_policy_decision_payload(
    *,
    policy: GatePolicy,
    decision: dict[str, Any],
    gate_input_ref: str,
) -> dict[str, Any]:
    return {
        "status": decision["status"],
        "schema_version": GATE_POLICY_DECISION_SCHEMA_VERSION,
        "policy_id": policy.policy_id,
        "split": decision["split"],
        "gate_input_ref": gate_input_ref,
        "metric_delta": decision.get("metric_delta", {}),
        "gate": decision.get("gate", {}),
        "hard_blockers": decision.get("hard_blockers", []),
        "top_regression_slices": decision.get("top_regression_slices", []),
        "slice_regressions": decision.get("slice_regressions", []),
        "quality_checks": decision.get("quality_checks", {}),
        "underlying_decision_schema": decision.get("schema_version"),
        "claim_boundary": "benchmark-agnostic gate policy decision only",
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }


def _gate_policy_composition_result(
    *,
    decision: dict[str, Any],
    decision_ref: str,
) -> dict[str, Any]:
    gate = decision.get("gate") if isinstance(decision.get("gate"), dict) else {}
    status = _string_value(decision.get("status")) or "unknown"
    hard_blockers = _string_list(decision.get("hard_blockers"))
    canary_allowed = bool(gate.get("canary_allowed", False))
    blocking = (
        status in {"blocked", "needs_paired_repeat", "variance_review_required"}
        or bool(hard_blockers)
        or not canary_allowed
    )
    return {
        "policy_id": _gate_policy_id_from_decision(decision),
        "schema_version": _string_value(decision.get("schema_version")),
        "status": status,
        "decision_ref": decision_ref,
        "canary_allowed": canary_allowed,
        "promotion_ready": bool(gate.get("promotion_ready", False)),
        "hard_blockers": hard_blockers,
        "blocking": blocking,
    }


def _gate_policy_id_from_decision(decision: dict[str, Any]) -> str:
    explicit = _string_value(decision.get("policy_id"))
    if explicit:
        return explicit
    schema_version = _string_value(decision.get("schema_version")) or ""
    if schema_version == SLICE_VARIANCE_GATE_DECISION_SCHEMA_VERSION:
        return "paired-repeat-variance-gate"
    if schema_version == SLICE_GATE_DECISION_SCHEMA_VERSION:
        return "slice-dev-hard-gate"
    if schema_version == GATE_POLICY_DECISION_SCHEMA_VERSION:
        return "slice-dev-hard-gate"
    return "unknown-policy"


def _gate_policy_composition_next_action(status: str) -> str:
    if status == "passed_for_canary":
        return "proceed_to_canary"
    if status == "needs_paired_repeat":
        return "run_paired_repeat"
    if status == "review_required":
        return "review_gate_variance"
    return "keep_candidate_blocked"


def _gate_policy_graph_node(*, policy_id: str, required: bool) -> dict[str, Any]:
    return {
        "policy_id": policy_id,
        "node_role": "required" if required else "optional",
        "hard_blocking": required,
        "decision_required": required,
    }


def _gate_policy_graph_next_action(status: str) -> str:
    if status == "passed_for_canary":
        return "proceed_to_canary"
    if status == "passed_with_advisory_blockers":
        return "review_advisory_gate_before_canary"
    if status == "missing_required_decision":
        return "collect_missing_required_gate_decisions"
    return "keep_candidate_blocked"


def _optimizer_adapter_registry(
    *,
    plugin_manifests: list[dict[str, Any] | str | Path] | None = None,
) -> list[dict[str, Any]]:
    return [
        adapter.to_manifest()
        for adapter in _optimizer_adapter_registry_objects(
            plugin_manifests=plugin_manifests
        )
    ]


def _optimizer_adapter_registry_objects(
    *,
    plugin_manifests: list[dict[str, Any] | str | Path] | None = None,
) -> list[OptimizerAdapter]:
    adapters = [
        OptimizerAdapter(
            name="manual-template",
            adapter_type="deterministic_local",
            runtime_status="implemented",
            provider="builtin",
            candidate_surface="prompt_section",
            candidate_schema=SLICE_PATCH_CANDIDATE_SCHEMA_VERSION,
            supports_execute_optimizer=False,
            executes_tool_default=False,
            executes_experiment=False,
            module_scope="single_module_single_section",
            capabilities=("section_local_patch", "dependency_free"),
        ),
        OptimizerAdapter(
            name="textgrad-local",
            adapter_type="deterministic_local",
            runtime_status="style_adapter_only",
            provider="builtin",
            candidate_surface="prompt_section",
            candidate_schema=SLICE_PATCH_CANDIDATE_SCHEMA_VERSION,
            supports_execute_optimizer=False,
            executes_tool_default=False,
            executes_experiment=False,
            module_scope="single_module_single_section",
            capabilities=("section_local_patch", "critic_feedback"),
        ),
        OptimizerAdapter(
            name="textgrad-openai-compatible",
            adapter_type="openai_compatible_critic",
            runtime_status="implemented_explicit_execution",
            provider="openai-compatible",
            candidate_surface="prompt_section",
            candidate_schema=SLICE_PATCH_CANDIDATE_SCHEMA_VERSION,
            supports_execute_optimizer=True,
            executes_tool_default=False,
            executes_experiment=False,
            module_scope="single_module_single_section",
            capabilities=(
                "section_local_patch",
                "critic_feedback",
                "structured_json_candidate",
            ),
            default_model=DEFAULT_TEXTGRAD_OPTIMIZER_MODEL,
            default_base_url=DEFAULT_TEXTGRAD_OPTIMIZER_BASE_URL,
        ),
        OptimizerAdapter(
            name="promptwizard-adapter",
            adapter_type="deterministic_local",
            runtime_status="style_adapter_only",
            provider="builtin",
            candidate_surface="prompt_section",
            candidate_schema=SLICE_PATCH_CANDIDATE_SCHEMA_VERSION,
            supports_execute_optimizer=False,
            executes_tool_default=False,
            executes_experiment=False,
            module_scope="single_module_single_section",
            capabilities=("self_critique_variant", "example_synthesis_variant"),
        ),
        OptimizerAdapter(
            name="promptwizard-constrained",
            adapter_type="deterministic_local",
            runtime_status="style_adapter_only",
            provider="builtin",
            candidate_surface="prompt_section",
            candidate_schema=SLICE_PATCH_CANDIDATE_SCHEMA_VERSION,
            supports_execute_optimizer=False,
            executes_tool_default=False,
            executes_experiment=False,
            module_scope="single_module_single_section",
            capabilities=("constraint_guard_variant", "protected_slice_guard"),
        ),
        OptimizerAdapter(
            name="textgrad-python-package",
            adapter_type="python_package_optimizer",
            runtime_status="requires_package_runtime",
            provider="textgrad",
            candidate_surface="prompt_section",
            candidate_schema=SLICE_PATCH_CANDIDATE_SCHEMA_VERSION,
            supports_execute_optimizer=True,
            executes_tool_default=False,
            executes_experiment=False,
            module_scope="single_module_single_section",
            capabilities=(
                "section_local_patch",
                "textgrad_variable_api",
                "structured_json_candidate",
            ),
            runtime_entrypoint={
                "kind": "python-package",
                "package_import": "textgrad",
                "package_name": "textgrad",
                "candidate_method": "textgrad_generate_slice_patch_candidate",
            },
        ),
        OptimizerAdapter(
            name="promptwizard-python-package",
            adapter_type="python_package_optimizer",
            runtime_status="requires_package_runtime",
            provider="promptwizard",
            candidate_surface="prompt_section",
            candidate_schema=SLICE_PATCH_CANDIDATE_SCHEMA_VERSION,
            supports_execute_optimizer=True,
            executes_tool_default=False,
            executes_experiment=False,
            module_scope="single_module_single_section",
            capabilities=(
                "section_local_patch",
                "promptwizard_optimizer_api",
                "structured_json_candidate",
            ),
            runtime_entrypoint={
                "kind": "python-package",
                "package_import": "promptwizard",
                "package_name": "promptwizard",
                "candidate_method": "promptwizard_generate_slice_patch_candidate",
            },
        ),
        OptimizerAdapter(
            name="dspy-mipro-package",
            adapter_type="python_package_optimizer",
            runtime_status="requires_package_runtime",
            provider="dspy",
            candidate_surface="prompt_section",
            candidate_schema=SLICE_PATCH_CANDIDATE_SCHEMA_VERSION,
            supports_execute_optimizer=True,
            executes_tool_default=False,
            executes_experiment=False,
            module_scope="single_module_single_section",
            capabilities=(
                "section_local_patch",
                "dspy_signature_predict",
                "mipro_optimizer_metadata",
                "structured_json_candidate",
            ),
            runtime_entrypoint={
                "kind": "python-package",
                "package_import": "dspy",
                "package_name": "dspy",
                "candidate_method": "dspy_mipro_generate_slice_patch_candidate",
            },
        ),
    ]
    _append_plugin_optimizer_adapters(adapters, plugin_manifests=plugin_manifests)
    return adapters


def _gate_policy_registry(
    *,
    plugin_manifests: list[dict[str, Any] | str | Path] | None = None,
) -> list[dict[str, Any]]:
    return [
        policy.to_manifest()
        for policy in _gate_policy_registry_objects(plugin_manifests=plugin_manifests)
    ]


def _gate_policy_registry_objects(
    *,
    plugin_manifests: list[dict[str, Any] | str | Path] | None = None,
) -> list[GatePolicy]:
    policies = [
        GatePolicy(
            policy_id="slice-dev-hard-gate",
            function="evaluate_gate_policy",
            input_schema=GATE_POLICY_INPUT_SCHEMA_VERSION,
            decision_schema=GATE_POLICY_DECISION_SCHEMA_VERSION,
            underlying_decision_schema=SLICE_GATE_DECISION_SCHEMA_VERSION,
            required_inputs=("gate_input",),
            blocks_on=("negative_metric_delta", "slice_regression"),
            decision_outputs=(
                "hard_blockers",
                "slice_regressions",
                "canary_allowed",
            ),
            canary_allowed_when="split is dev and hard_blockers is empty",
            executes_experiment=False,
        ),
        GatePolicy(
            policy_id="min-improvement-gate",
            function="evaluate_gate_policy",
            input_schema=GATE_POLICY_INPUT_SCHEMA_VERSION,
            decision_schema=GATE_POLICY_DECISION_SCHEMA_VERSION,
            required_inputs=("gate_input",),
            blocks_on=("min_metric_delta_not_met",),
            decision_outputs=("hard_blockers", "quality_checks", "canary_allowed"),
            canary_allowed_when="required min metric deltas are met",
            executes_experiment=False,
        ),
        GatePolicy(
            policy_id="min-quality-gate",
            function="evaluate_gate_policy",
            input_schema=GATE_POLICY_INPUT_SCHEMA_VERSION,
            decision_schema=GATE_POLICY_DECISION_SCHEMA_VERSION,
            required_inputs=("gate_input",),
            blocks_on=("min_slice_score_percent_not_met",),
            decision_outputs=("hard_blockers", "quality_checks", "canary_allowed"),
            canary_allowed_when="all required slices meet min quality threshold",
            executes_experiment=False,
        ),
        GatePolicy(
            policy_id="target-smoke-success-gate",
            function="evaluate_gate_policy",
            input_schema=GATE_POLICY_INPUT_SCHEMA_VERSION,
            decision_schema=GATE_POLICY_DECISION_SCHEMA_VERSION,
            required_inputs=("gate_input",),
            blocks_on=(
                "target_smoke_failure",
                "target_smoke_runtime_error",
                "dev_model_eval_runtime_error",
            ),
            decision_outputs=("hard_blockers", "quality_checks", "canary_allowed"),
            canary_allowed_when="target smoke succeeds and model eval runtime has no blocking errors",
            executes_experiment=False,
        ),
        GatePolicy(
            policy_id="paired-repeat-variance-gate",
            function="evaluate_slice_variance_gate",
            decision_schema=SLICE_VARIANCE_GATE_DECISION_SCHEMA_VERSION,
            required_inputs=("paired_repeat_manifest",),
            default_min_repeats=2,
            blocks_on=("insufficient_repeats", "stable_slice_regression"),
            decision_outputs=(
                "hard_blockers",
                "slice_stability",
                "stable_repair_targets",
                "canary_allowed",
            ),
            canary_allowed_when="repeat_count >= min_repeats and no stable regressions",
            executes_experiment=False,
        ),
    ]
    _append_plugin_gate_policies(policies, plugin_manifests=plugin_manifests)
    return policies


def _benchmark_adapter_registry() -> list[dict[str, Any]]:
    return [adapter.to_manifest() for adapter in _benchmark_adapter_registry_objects()]


def _benchmark_adapter_registry_objects() -> list[BenchmarkAdapter]:
    return [
        BenchmarkAdapter(
            benchmark_id="smol_worldcup",
            task_family="smol_worldcup_prompt_routing",
            runner_function="build_optimizer_gate_execution_plan",
            supported_splits=("dev", "canary"),
            required_artifacts=(
                "registered_prompt_profile",
                "baseline_report",
                "candidate_report",
                "candidate_evaluation",
                "paired_repeat_manifest",
            ),
            planned_execution_stages=(
                "target_smoke",
                "dev_model_eval",
                "build_slice_eval_matrix",
                "evaluate_gate_policy",
                "evaluate_slice_variance_gate",
                "build_gate_policy_composition",
            ),
            gate_outputs=(
                "gate_policy_decision",
                "slice_variance_gate_decision",
                "gate_policy_composition",
            ),
            executes_experiment=False,
        )
    ]


def _append_plugin_optimizer_adapters(
    adapters: list[OptimizerAdapter],
    *,
    plugin_manifests: list[dict[str, Any] | str | Path] | None,
) -> None:
    seen = {adapter.name for adapter in adapters}
    for manifest in _load_optimizer_gate_plugin_manifests(plugin_manifests):
        for item in _optimizer_adapters_from_plugin_manifest(manifest):
            if item.name in seen:
                raise ValueError(f"duplicate optimizer adapter: {item.name}")
            seen.add(item.name)
            adapters.append(item)


def _append_plugin_gate_policies(
    policies: list[GatePolicy],
    *,
    plugin_manifests: list[dict[str, Any] | str | Path] | None,
) -> None:
    seen = {policy.policy_id for policy in policies}
    for manifest in _load_optimizer_gate_plugin_manifests(plugin_manifests):
        for item in _gate_policies_from_plugin_manifest(manifest):
            if item.policy_id in seen:
                raise ValueError(f"duplicate gate policy: {item.policy_id}")
            seen.add(item.policy_id)
            policies.append(item)


def _load_optimizer_gate_plugin_manifests(
    plugin_manifests: list[dict[str, Any] | str | Path] | None,
) -> list[dict[str, Any]]:
    if not plugin_manifests:
        return []
    return [load_optimizer_gate_plugin_manifest(item) for item in plugin_manifests]


def _normalize_optimizer_gate_plugin_manifest(
    payload: dict[str, Any],
    *,
    manifest_ref: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("plugin_manifest must be an object")
    schema_version = (
        _string_value(payload.get("schema_version"))
        or OPTIMIZER_GATE_PLUGIN_MANIFEST_SCHEMA_VERSION
    )
    if schema_version != OPTIMIZER_GATE_PLUGIN_MANIFEST_SCHEMA_VERSION:
        raise ValueError(f"unsupported optimizer/gate plugin schema: {schema_version}")
    plugin_id = _string_value(payload.get("plugin_id"))
    if plugin_id is None:
        raise ValueError("plugin_id is required")
    if payload.get("official_scores_claimed") is True:
        raise ValueError("plugin manifest cannot claim official scores")
    optimizer_adapters = [
        adapter.to_manifest()
        for adapter in _optimizer_adapters_from_plugin_manifest(payload)
    ]
    gate_policies = [
        policy.to_manifest()
        for policy in _gate_policies_from_plugin_manifest(payload)
    ]
    runtime_capable_optimizer_count = sum(
        1 for adapter in optimizer_adapters if adapter.get("supports_execute_optimizer")
    )
    return {
        "status": "completed",
        "schema_version": OPTIMIZER_GATE_PLUGIN_MANIFEST_SCHEMA_VERSION,
        "plugin_id": plugin_id,
        "plugin_ref": manifest_ref,
        "optimizer_adapters": optimizer_adapters,
        "gate_policies": gate_policies,
        "plugin_summary": {
            "optimizer_adapter_count": len(optimizer_adapters),
            "gate_policy_count": len(gate_policies),
            "runtime_capable_optimizer_count": runtime_capable_optimizer_count,
            "manifest_only": runtime_capable_optimizer_count == 0,
        },
        "claim_boundary": (
            _string_value(payload.get("claim_boundary"))
            or "optimizer/gate plugin manifest contract only; load does not execute tools"
        ),
        "executes_tool": False,
        "executes_experiment": False,
        "official_scores_claimed": False,
    }


def _optimizer_adapters_from_plugin_manifest(
    manifest: dict[str, Any],
) -> list[OptimizerAdapter]:
    plugin_id = _string_value(manifest.get("plugin_id"))
    if plugin_id is None:
        raise ValueError("plugin_id is required")
    adapter_items = manifest.get("optimizer_adapters")
    if adapter_items is None:
        adapter_items = []
    if not isinstance(adapter_items, list) or not all(
        isinstance(item, dict) for item in adapter_items
    ):
        raise ValueError("optimizer_adapters must be a list of objects")
    return [
        _optimizer_adapter_from_plugin_item(item, plugin_id=plugin_id)
        for item in adapter_items
    ]


def _optimizer_runtime_entrypoint_from_plugin_item(
    item: dict[str, Any],
    *,
    adapter_name: str,
    required: bool,
) -> dict[str, Any] | None:
    value = item.get("runtime_entrypoint")
    if value is None:
        if required:
            raise ValueError(
                f"plugin optimizer adapter {adapter_name} requires runtime_entrypoint"
            )
        return None
    if not isinstance(value, dict):
        raise ValueError(
            f"plugin optimizer adapter {adapter_name} runtime_entrypoint must be an object"
        )
    kind = _required_string(value, "kind", kind="runtime entrypoint")
    if kind == "local-subprocess-json":
        command = value.get("command")
        if not isinstance(command, list) or not all(
            isinstance(item, str) and item for item in command
        ):
            raise ValueError(
                f"plugin optimizer adapter {adapter_name} subprocess command must be a list of strings"
            )
        return {
            "kind": kind,
            "command": list(command),
        }
    if kind == "python-package":
        package_import = _required_string(
            value,
            "package_import",
            kind="runtime entrypoint",
        )
        payload: dict[str, Any] = {
            "kind": kind,
            "package_import": package_import,
        }
        for key in ("package_name", "adapter_class", "probe_method", "candidate_method"):
            item_value = _string_value(value.get(key))
            if item_value:
                payload[key] = item_value
        return payload
    if kind != "openai-compatible-chat-completions":
        raise ValueError(
            f"unsupported optimizer runtime entrypoint kind for {adapter_name}: {kind}"
        )
    default_model = _required_string(value, "default_model", kind="runtime entrypoint")
    default_base_url = _required_string(
        value,
        "default_base_url",
        kind="runtime entrypoint",
    )
    payload: dict[str, Any] = {
        "kind": kind,
        "default_model": default_model,
        "default_base_url": default_base_url,
    }
    for key in ("api_key_env", "model_env", "base_url_env"):
        item_value = _string_value(value.get(key))
        if item_value:
            payload[key] = item_value
    return payload


def _optimizer_adapter_from_plugin_item(
    item: dict[str, Any],
    *,
    plugin_id: str,
) -> OptimizerAdapter:
    name = _required_string(item, "name", kind="optimizer adapter")
    executes_experiment = bool(item.get("executes_experiment", False))
    executes_tool_default = bool(item.get("executes_tool_default", False))
    supports_execute_optimizer = bool(item.get("supports_execute_optimizer", False))
    if executes_experiment or executes_tool_default:
        raise ValueError(
            f"plugin optimizer adapter {name} must not execute by default or run experiments"
        )
    runtime_entrypoint = _optimizer_runtime_entrypoint_from_plugin_item(
        item,
        adapter_name=name,
        required=supports_execute_optimizer,
    )
    return OptimizerAdapter(
        name=name,
        adapter_type=_required_string(item, "adapter_type", kind="optimizer adapter"),
        runtime_status=(
            _string_value(item.get("runtime_status")) or "plugin_manifest_only"
        ),
        provider=_string_value(item.get("provider")) or "plugin",
        candidate_surface=(
            _string_value(item.get("candidate_surface")) or "prompt_section"
        ),
        candidate_schema=(
            _string_value(item.get("candidate_schema"))
            or SLICE_PATCH_CANDIDATE_SCHEMA_VERSION
        ),
        supports_execute_optimizer=supports_execute_optimizer,
        executes_tool_default=False,
        executes_experiment=False,
        module_scope=(
            _string_value(item.get("module_scope"))
            or "single_module_single_section"
        ),
        capabilities=tuple(_string_list(item.get("capabilities"))),
        default_model=(
            _string_value(item.get("default_model"))
            or (
                _string_value(runtime_entrypoint.get("default_model"))
                if runtime_entrypoint
                else None
            )
        ),
        default_base_url=(
            _string_value(item.get("default_base_url"))
            or (
                _string_value(runtime_entrypoint.get("default_base_url"))
                if runtime_entrypoint
                else None
            )
        ),
        runtime_entrypoint=runtime_entrypoint,
        source="plugin",
        plugin_id=plugin_id,
    )


def _gate_policies_from_plugin_manifest(manifest: dict[str, Any]) -> list[GatePolicy]:
    plugin_id = _string_value(manifest.get("plugin_id"))
    if plugin_id is None:
        raise ValueError("plugin_id is required")
    policy_items = manifest.get("gate_policies")
    if policy_items is None:
        policy_items = []
    if not isinstance(policy_items, list) or not all(
        isinstance(item, dict) for item in policy_items
    ):
        raise ValueError("gate_policies must be a list of objects")
    return [
        _gate_policy_from_plugin_item(item, plugin_id=plugin_id)
        for item in policy_items
    ]


def _gate_policy_from_plugin_item(
    item: dict[str, Any],
    *,
    plugin_id: str,
) -> GatePolicy:
    policy_id = _required_string(item, "policy_id", kind="gate policy")
    if bool(item.get("executes_experiment", False)):
        raise ValueError(f"plugin gate policy {policy_id} must be non-executing")
    return GatePolicy(
        policy_id=policy_id,
        function=_required_string(item, "function", kind="gate policy"),
        decision_schema=(
            _string_value(item.get("decision_schema"))
            or GATE_POLICY_DECISION_SCHEMA_VERSION
        ),
        required_inputs=tuple(_string_list(item.get("required_inputs"))),
        blocks_on=tuple(_string_list(item.get("blocks_on"))),
        decision_outputs=tuple(_string_list(item.get("decision_outputs"))),
        canary_allowed_when=(
            _string_value(item.get("canary_allowed_when"))
            or "hard_blockers is empty"
        ),
        executes_experiment=False,
        underlying_decision_schema=_string_value(item.get("underlying_decision_schema")),
        input_schema=_string_value(item.get("input_schema")),
        source="plugin",
        plugin_id=plugin_id,
    )


def _required_string(payload: dict[str, Any], key: str, *, kind: str) -> str:
    value = _string_value(payload.get(key))
    if value is None:
        raise ValueError(f"{kind} {key} is required")
    return value


def _slice_candidate_watch_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows = []
    for item in value:
        if not isinstance(item, dict) or _string_value(item.get("gate")) != "watch":
            continue
        after = item.get("after")
        if not _is_plain_number(after):
            continue
        rows.append(
            {
                "slice_key": _string_value(item.get("slice_key")) or "unknown",
                "dimension": _string_value(item.get("dimension")),
                "slice_name": _string_value(item.get("slice_name")),
                "metric": _string_value(item.get("metric")) or "score_percent",
                "delta": None,
                "after": round(float(after), 6),
                "gate": "watch",
                "reason": "aggregate_regression_without_baseline_slice_delta",
            }
        )
    rows.sort(
        key=lambda item: (
            _slice_dimension_priority(item.get("dimension")),
            item["after"],
            item["slice_key"],
        )
    )
    return rows


def _slice_dimension_priority(value: Any) -> int:
    if value == "category":
        return 0
    if value == "auto_grade":
        return 1
    if value == "axis":
        return 2
    return 3


def _slice_name_from_key(slice_key: str | None) -> str | None:
    if not slice_key:
        return None
    parts = slice_key.split("/")
    return parts[-1] if parts else None


def _slice_module_for_target(
    modules_payload: dict[str, Any],
    target_slice: str | None,
) -> dict[str, Any]:
    modules = modules_payload.get("modules")
    if not isinstance(modules, list):
        return {}
    fallback = {}
    for item in modules:
        if not isinstance(item, dict):
            continue
        if not fallback:
            fallback = item
        targets = _string_list(item.get("target_slices"))
        if target_slice and target_slice in targets:
            return item
    return fallback


def _slice_patch_contract(
    *,
    target: dict[str, Any],
    target_slice: str | None,
    module: dict[str, Any],
) -> dict[str, Any]:
    if not target or not module:
        return {}
    allowed_sections = _string_list(module.get("allowed_edit_sections"))
    sections = module.get("sections") if isinstance(module.get("sections"), dict) else {}
    section_id = allowed_sections[0] if allowed_sections else _first_string_key(sections)
    module_id = _string_value(module.get("module_id")) or "unmapped_slice_module"
    before_text = ""
    if section_id and isinstance(sections.get(section_id), str):
        before_text = sections[section_id]
    return {
        "module_id": module_id,
        "section_id": section_id or "constraints",
        "edit_scope": "single_section",
        "change_surface": "prompt_section",
        "based_on_slices": [_string_value(target.get("slice_key")) or "unknown"],
        "target_slice": target_slice,
        "before_text": before_text,
        "protected_slices": _string_list(module.get("protected_slices")),
        "allowed_edit_sections": allowed_sections or ([section_id] if section_id else []),
        "disallowed_change_surfaces": ["prompt_profile"],
    }


def _first_string_key(value: dict[str, Any]) -> str | None:
    for key in value:
        if isinstance(key, str) and key:
            return key
    return None


def _manual_slice_patch_candidate(
    *,
    contract: dict[str, Any],
    optimizer: str,
    index: int,
) -> dict[str, Any]:
    module_id = _string_value(contract.get("module_id")) or "module"
    section_id = _string_value(contract.get("section_id")) or "section"
    before_text = _string_value(contract.get("before_text")) or ""
    based_on_slices = _string_list(contract.get("based_on_slices"))
    target_slice = _string_value(contract.get("target_slice")) or _slice_name_from_key(
        based_on_slices[0] if based_on_slices else None
    )
    protected_slices = _string_list(contract.get("protected_slices"))
    protected_sections = _string_list(contract.get("protected_sections")) or ["role"]
    protected = ", ".join(protected_slices) if protected_slices else "none"
    strategy = _slice_candidate_strategy(optimizer=optimizer, index=index)
    after_text = _slice_candidate_after_text(
        before_text=before_text,
        based_on_slices=based_on_slices,
        protected=protected,
        optimizer=optimizer,
        strategy=strategy,
    )
    safe_module = module_id.replace("_", "-")
    safe_section = section_id.replace("_", "-")
    candidate = {
        "schema_version": SLICE_PATCH_CANDIDATE_SCHEMA_VERSION,
        "patch_id": f"slice-patch-{safe_module}-{safe_section}-{index:03d}",
        "module_id": module_id,
        "section_id": section_id,
        "based_on_slices": based_on_slices,
        "before_text": before_text,
        "after_text": after_text,
        "edit_scope": "single_section",
        "change_surface": "prompt_section",
        "optimizer": optimizer,
        "candidate_strategy": strategy,
        "protected_slices": protected_slices,
        "protected_sections": protected_sections,
        "expected_effect": {
            "primary_slice": target_slice,
            "protected_slices": protected_slices,
        },
        "claim_boundary": "local section patch candidate only",
        "executes_tool": False,
        "official_scores_claimed": False,
    }
    if optimizer == "textgrad-local":
        candidate["critic_feedback"] = (
            "Local textual critique: patch only this section, target the negative slice, "
            "and preserve protected slices/sections."
        )
    elif optimizer == "promptwizard-adapter":
        candidate["critic_feedback"] = (
            "PromptWizard-style deterministic proposal variant; gate must decide acceptance."
        )
    elif optimizer == "promptwizard-constrained":
        candidate["critic_feedback"] = (
            "PromptWizard constrained variant: propose the smallest local rewrite that targets "
            "the failed slice while preserving accepted base profile behavior and protected slices."
        )
    return candidate


def _textgrad_openai_compatible_candidate(
    *,
    contract: dict[str, Any],
    index: int,
    optimizer_model: str,
    optimizer_base_url: str,
    optimizer_api_key: str | None,
    optimizer_timeout_seconds: int,
    optimizer_temperature: float,
    optimizer_max_tokens: int,
) -> dict[str, Any]:
    return _openai_compatible_optimizer_candidate(
        contract=contract,
        index=index,
        optimizer="textgrad-openai-compatible",
        candidate_strategy="textgrad_openai_compatible",
        optimizer_model=optimizer_model,
        optimizer_base_url=optimizer_base_url,
        optimizer_api_key=optimizer_api_key,
        optimizer_timeout_seconds=optimizer_timeout_seconds,
        optimizer_temperature=optimizer_temperature,
        optimizer_max_tokens=optimizer_max_tokens,
    )


def _openai_compatible_optimizer_candidate(
    *,
    contract: dict[str, Any],
    index: int,
    optimizer: str,
    candidate_strategy: str,
    optimizer_model: str,
    optimizer_base_url: str,
    optimizer_api_key: str | None,
    optimizer_timeout_seconds: int,
    optimizer_temperature: float,
    optimizer_max_tokens: int,
) -> dict[str, Any]:
    candidate = _manual_slice_patch_candidate(
        contract=contract,
        optimizer=optimizer,
        index=index,
    )
    response = _call_openai_compatible_chat(
        base_url=optimizer_base_url,
        model=optimizer_model,
        messages=_textgrad_candidate_messages(contract=contract),
        api_key=optimizer_api_key,
        temperature=optimizer_temperature,
        max_tokens=optimizer_max_tokens,
        timeout_seconds=optimizer_timeout_seconds,
    )
    parsed = _parse_textgrad_candidate_response(response.get("content"))
    after_text = _string_value(parsed.get("after_text"))
    critic_feedback = _string_value(parsed.get("critic_feedback"))
    if after_text:
        candidate["after_text"] = after_text
    if critic_feedback:
        candidate["critic_feedback"] = critic_feedback
    else:
        candidate["critic_feedback"] = _string_value(response.get("content")) or (
            "OpenAI-compatible TextGrad critic returned no structured feedback."
        )
    candidate["candidate_strategy"] = candidate_strategy
    candidate["optimizer_model"] = optimizer_model
    candidate["optimizer_base_url"] = optimizer_base_url
    candidate["optimizer_runtime"] = {
        "status": "executed",
        "provider": "openai-compatible",
        "model": optimizer_model,
        "base_url": optimizer_base_url,
        "response_id": _response_id(response.get("raw_response")),
    }
    return candidate


def _subprocess_json_optimizer_candidate(
    *,
    contract: dict[str, Any],
    index: int,
    optimizer: str,
    command: list[str],
    optimizer_timeout_seconds: int,
) -> dict[str, Any]:
    candidate = _manual_slice_patch_candidate(
        contract=contract,
        optimizer=optimizer,
        index=index,
    )
    response = _call_subprocess_json_optimizer(
        command=command,
        payload={
            "task": "Generate a section-local prompt repair.",
            "optimizer": optimizer,
            "index": index,
            "contract": _subprocess_optimizer_contract_payload(contract),
            "strict_output": {
                "format": "json_object",
                "required_fields": ["critic_feedback", "after_text"],
            },
            "claim_boundary": "optimizer plugin subprocess input only",
            "official_scores_claimed": False,
        },
        timeout_seconds=optimizer_timeout_seconds,
    )
    parsed = response["payload"]
    after_text = _string_value(parsed.get("after_text"))
    critic_feedback = _string_value(parsed.get("critic_feedback"))
    if after_text:
        candidate["after_text"] = after_text
    if critic_feedback:
        candidate["critic_feedback"] = critic_feedback
    else:
        candidate["critic_feedback"] = "Subprocess optimizer returned no critic feedback."
    candidate["candidate_strategy"] = "plugin_subprocess_json"
    candidate["optimizer_runtime"] = {
        "status": "executed",
        "provider": "local-subprocess-json",
        "response_id": (
            _string_value(parsed.get("response_id"))
            or _response_id(response.get("raw_response"))
        ),
    }
    return candidate


def _python_package_optimizer_candidate(
    *,
    contract: dict[str, Any],
    index: int,
    optimizer: str,
    adapter: OptimizerAdapter,
    optimizer_timeout_seconds: int,
) -> tuple[dict[str, Any] | None, dict[str, Any], dict[str, str] | None]:
    entrypoint = _python_package_runtime_entrypoint(adapter)
    package_import = _string_value(entrypoint.get("package_import")) or ""
    package_name = _string_value(entrypoint.get("package_name")) or package_import
    adapter_class_name = _string_value(entrypoint.get("adapter_class"))
    candidate_method_name = _string_value(entrypoint.get("candidate_method"))
    started = time.perf_counter()
    runtime_record: dict[str, Any] = {
        "status": "not_ready",
        "executed": False,
        "provider": "python-package",
        "kind": "python-package",
        "package_import": package_import,
        "package_name": package_name,
        "adapter_class": adapter_class_name,
        "candidate_method": candidate_method_name,
        "timeout_seconds": max(1, int(optimizer_timeout_seconds)),
        "runtime_ready": False,
        "fallback_used": False,
    }
    runtime_record["runtime_cache_paths"] = _ensure_optimizer_runtime_cache_paths(
        package_import
    )

    if not candidate_method_name:
        runtime_record["status"] = "unsupported"
        return (
            None,
            runtime_record,
            {
                "type": "UnsupportedOptimizerRuntime",
                "message": (
                    f"optimizer adapter {adapter.name} python-package runtime "
                    "requires candidate_method"
                ),
            },
        )

    try:
        module = importlib.import_module(package_import)
    except Exception as exc:
        runtime_record["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
        runtime_record["duration_seconds"] = _duration_seconds_since(started)
        return (
            None,
            runtime_record,
            {
                "type": "OptimizerRuntimeNotReady",
                "message": (
                    f"python package optimizer runtime is not importable: "
                    f"{package_import}"
                ),
            },
        )

    runtime_record["import_available"] = True
    runtime_record["runtime_ready"] = True
    runtime_record["package_version"] = _python_package_version(
        module=module,
        package_name=package_name,
        package_import=package_import,
    )
    if _adapter_uses_builtin_dspy_mipro(adapter):
        return _dspy_mipro_package_candidate(
            contract=contract,
            index=index,
            optimizer=optimizer,
            module=module,
            package_import=package_import,
            package_name=package_name,
            package_version=runtime_record.get("package_version"),
            runtime_record=runtime_record,
            started=started,
        )
    if _adapter_uses_builtin_textgrad_package(adapter):
        return _textgrad_package_candidate(
            contract=contract,
            index=index,
            optimizer=optimizer,
            module=module,
            package_import=package_import,
            package_name=package_name,
            package_version=runtime_record.get("package_version"),
            runtime_record=runtime_record,
            started=started,
        )
    if _adapter_uses_builtin_promptwizard_package(adapter):
        return _promptwizard_package_candidate(
            contract=contract,
            index=index,
            optimizer=optimizer,
            module=module,
            package_import=package_import,
            package_name=package_name,
            package_version=runtime_record.get("package_version"),
            runtime_record=runtime_record,
            started=started,
        )
    try:
        target: Any = module
        if adapter_class_name:
            adapter_class = getattr(module, adapter_class_name)
            target = adapter_class()
        candidate_method = getattr(target, candidate_method_name)
    except Exception as exc:
        runtime_record["status"] = "failed"
        runtime_record["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
        runtime_record["duration_seconds"] = _duration_seconds_since(started)
        return (
            None,
            runtime_record,
            {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        )

    runtime_input = {
        "task": "generate_slice_patch_candidate",
        "optimizer": optimizer,
        "index": index,
        "contract": _subprocess_optimizer_contract_payload(contract),
        "strict_output": {
            "format": "json_object",
            "required_fields": ["after_text"],
        },
        "claim_boundary": "python package optimizer runtime input only",
        "official_scores_claimed": False,
    }
    runtime_record["input"] = runtime_input
    try:
        raw_output = candidate_method(runtime_input)
        if not isinstance(raw_output, dict):
            raise ValueError("python package optimizer candidate output must be an object")
        after_text = _string_value(raw_output.get("after_text"))
        if not after_text:
            raise ValueError(
                "python package optimizer candidate output requires after_text"
            )
    except Exception as exc:
        runtime_record["status"] = "failed"
        runtime_record["executed"] = True
        runtime_record["output"] = (
            raw_output if isinstance(locals().get("raw_output"), dict) else None
        )
        runtime_record["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
        runtime_record["duration_seconds"] = _duration_seconds_since(started)
        return (
            None,
            runtime_record,
            {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        )

    runtime_record["status"] = "executed"
    runtime_record["executed"] = True
    runtime_record["output"] = dict(raw_output)
    runtime_record["duration_seconds"] = _duration_seconds_since(started)
    candidate = _manual_slice_patch_candidate(
        contract=contract,
        optimizer=optimizer,
        index=index,
    )
    candidate["after_text"] = after_text
    critic_feedback = _string_value(raw_output.get("critic_feedback"))
    if critic_feedback:
        candidate["critic_feedback"] = critic_feedback
    candidate["candidate_strategy"] = (
        _string_value(raw_output.get("candidate_strategy"))
        or "python_package_runtime"
    )
    for key in ("patch_id", "expected_effect"):
        value = raw_output.get(key)
        if value is not None:
            candidate[key] = value
    candidate["executes_tool"] = True
    candidate["executes_optimizer_runtime"] = True
    candidate["optimizer_runtime"] = {
        "status": runtime_record["status"],
        "provider": runtime_record["provider"],
        "kind": runtime_record["kind"],
        "package_import": package_import,
        "package_name": package_name,
        "package_version": runtime_record.get("package_version"),
        "adapter_class": adapter_class_name,
        "candidate_method": candidate_method_name,
        "duration_seconds": runtime_record["duration_seconds"],
        "fallback_used": False,
    }
    return candidate, runtime_record, None


def _dspy_mipro_package_candidate(
    *,
    contract: dict[str, Any],
    index: int,
    optimizer: str,
    module: Any,
    package_import: str,
    package_name: str,
    package_version: str | None,
    runtime_record: dict[str, Any],
    started: float,
) -> tuple[dict[str, Any] | None, dict[str, Any], dict[str, str] | None]:
    try:
        dspy_api = _dspy_mipro_api_summary(module)
        dummy_lm_class = importlib.import_module("dspy.utils.dummies").DummyLM
        mipro_class = importlib.import_module("dspy.teleprompt").MIPROv2

        class SlicePatchSignature(module.Signature):
            before_text = module.InputField()
            target_slice = module.InputField()
            protected_slices = module.InputField()
            after_text = module.OutputField()
            critic_feedback = module.OutputField()

        contract_payload = _subprocess_optimizer_contract_payload(contract)
        before_text = _string_value(contract_payload.get("before_text")) or ""
        target_slice = _string_value(contract_payload.get("target_slice")) or "target_slice"
        protected = ", ".join(_string_list(contract_payload.get("protected_slices")))
        if not protected:
            protected = "none"
        generated_after_text = (
            f"{before_text}\n"
            f"DSPy/MIPRO package candidate: add a bounded guard for "
            f"{target_slice}; preserve protected slices: {protected}."
        )
        generated_feedback = (
            "DSPy Predict executed with DummyLM and MIPROv2 was instantiated for "
            "package optimizer metadata; no benchmark or MIPRO compile was run."
        )
        runtime_input = {
            "task": "generate_slice_patch_candidate",
            "optimizer": optimizer,
            "index": index,
            "contract": contract_payload,
            "dspy_signature": "SlicePatchSignature",
            "mipro_mode": "metadata_only",
            "strict_output": {
                "format": "json_object",
                "required_fields": ["after_text", "critic_feedback"],
            },
            "claim_boundary": "dspy package optimizer runtime input only",
            "official_scores_claimed": False,
        }
        runtime_record["input"] = runtime_input
        dummy_lm = dummy_lm_class(
            [
                {
                    "after_text": generated_after_text,
                    "critic_feedback": generated_feedback,
                }
            ]
        )
        with module.context(lm=dummy_lm):
            prediction = module.Predict(SlicePatchSignature)(
                before_text=before_text,
                target_slice=target_slice,
                protected_slices=protected,
            )
        mipro = mipro_class(
            metric=lambda *args, **kwargs: 1.0,
            prompt_model=dummy_lm,
            task_model=dummy_lm,
            auto="light",
            num_candidates=1,
            max_bootstrapped_demos=0,
            max_labeled_demos=0,
        )
        raw_output = {
            "after_text": _string_value(getattr(prediction, "after_text", None))
            or generated_after_text,
            "critic_feedback": _string_value(
                getattr(prediction, "critic_feedback", None)
            )
            or generated_feedback,
            "candidate_strategy": "dspy_mipro_package_runtime",
            "dspy_api": dspy_api,
            "mipro": {
                "class": type(mipro).__name__,
                "auto": "light",
                "num_candidates": 1,
                "compile_executed": False,
            },
        }
        if not _string_value(raw_output.get("after_text")):
            raise ValueError("DSPy package optimizer output requires after_text")
    except Exception as exc:
        runtime_record["status"] = "failed"
        runtime_record["executed"] = True
        runtime_record["runtime_ready"] = False
        runtime_record["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
        runtime_record["duration_seconds"] = _duration_seconds_since(started)
        return (
            None,
            runtime_record,
            {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        )

    runtime_record["status"] = "executed"
    runtime_record["executed"] = True
    runtime_record["runtime_ready"] = True
    runtime_record["output"] = dict(raw_output)
    runtime_record["dspy_api"] = dspy_api
    runtime_record["duration_seconds"] = _duration_seconds_since(started)
    candidate = _manual_slice_patch_candidate(
        contract=contract,
        optimizer=optimizer,
        index=index,
    )
    candidate["after_text"] = _string_value(raw_output.get("after_text"))
    candidate["critic_feedback"] = _string_value(raw_output.get("critic_feedback"))
    candidate["candidate_strategy"] = "dspy_mipro_package_runtime"
    candidate["executes_tool"] = True
    candidate["executes_optimizer_runtime"] = True
    candidate["optimizer_runtime"] = {
        "status": runtime_record["status"],
        "provider": runtime_record["provider"],
        "kind": runtime_record["kind"],
        "package_import": package_import,
        "package_name": package_name,
        "package_version": package_version,
        "candidate_method": runtime_record.get("candidate_method"),
        "duration_seconds": runtime_record["duration_seconds"],
        "fallback_used": False,
        "dspy_api": dspy_api,
        "mipro": raw_output["mipro"],
    }
    return candidate, runtime_record, None


def _textgrad_package_candidate(
    *,
    contract: dict[str, Any],
    index: int,
    optimizer: str,
    module: Any,
    package_import: str,
    package_name: str,
    package_version: str | None,
    runtime_record: dict[str, Any],
    started: float,
) -> tuple[dict[str, Any] | None, dict[str, Any], dict[str, str] | None]:
    try:
        textgrad_api = _textgrad_api_summary(module)
        variable_class = getattr(module, "Variable")
        contract_payload = _subprocess_optimizer_contract_payload(contract)
        before_text = _string_value(contract_payload.get("before_text")) or ""
        target_slice = _string_value(contract_payload.get("target_slice")) or "target_slice"
        protected = ", ".join(_string_list(contract_payload.get("protected_slices")))
        if not protected:
            protected = "none"
        runtime_input = {
            "task": "generate_slice_patch_candidate",
            "optimizer": optimizer,
            "index": index,
            "contract": contract_payload,
            "textgrad_mode": "variable_api_metadata",
            "strict_output": {
                "format": "json_object",
                "required_fields": ["after_text", "critic_feedback"],
            },
            "claim_boundary": "textgrad package optimizer runtime input only",
            "official_scores_claimed": False,
        }
        runtime_record["input"] = runtime_input
        variable = variable_class(
            before_text,
            requires_grad=True,
            role_description=f"prompt section for {target_slice}",
        )
        variable_value = (
            variable.get_value()
            if hasattr(variable, "get_value")
            else getattr(variable, "value", before_text)
        )
        raw_output = {
            "after_text": (
                f"{_string_value(variable_value) or before_text}\n"
                f"TextGrad package candidate: add a bounded guard for {target_slice}; "
                f"preserve protected slices: {protected}."
            ),
            "critic_feedback": (
                "TextGrad Variable API was instantiated for package runtime "
                "candidate generation; no benchmark eval or official scoring was run."
            ),
            "candidate_strategy": "textgrad_python_package_runtime",
            "textgrad_api": textgrad_api,
        }
        if not _string_value(raw_output.get("after_text")):
            raise ValueError("TextGrad package optimizer output requires after_text")
    except Exception as exc:
        runtime_record["status"] = "failed"
        runtime_record["executed"] = True
        runtime_record["runtime_ready"] = False
        runtime_record["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
        runtime_record["duration_seconds"] = _duration_seconds_since(started)
        return None, runtime_record, {"type": type(exc).__name__, "message": str(exc)}

    runtime_record["status"] = "executed"
    runtime_record["executed"] = True
    runtime_record["runtime_ready"] = True
    runtime_record["output"] = dict(raw_output)
    runtime_record["textgrad_api"] = textgrad_api
    runtime_record["duration_seconds"] = _duration_seconds_since(started)
    candidate = _manual_slice_patch_candidate(
        contract=contract,
        optimizer=optimizer,
        index=index,
    )
    candidate["after_text"] = _string_value(raw_output.get("after_text"))
    candidate["critic_feedback"] = _string_value(raw_output.get("critic_feedback"))
    candidate["candidate_strategy"] = "textgrad_python_package_runtime"
    candidate["executes_tool"] = True
    candidate["executes_optimizer_runtime"] = True
    candidate["optimizer_runtime"] = {
        "status": runtime_record["status"],
        "provider": runtime_record["provider"],
        "kind": runtime_record["kind"],
        "package_import": package_import,
        "package_name": package_name,
        "package_version": package_version,
        "candidate_method": runtime_record.get("candidate_method"),
        "duration_seconds": runtime_record["duration_seconds"],
        "fallback_used": False,
        "textgrad_api": textgrad_api,
    }
    return candidate, runtime_record, None


def _promptwizard_package_candidate(
    *,
    contract: dict[str, Any],
    index: int,
    optimizer: str,
    module: Any,
    package_import: str,
    package_name: str,
    package_version: str | None,
    runtime_record: dict[str, Any],
    started: float,
) -> tuple[dict[str, Any] | None, dict[str, Any], dict[str, str] | None]:
    try:
        promptwizard_api = _promptwizard_api_summary(module)
        contract_payload = _subprocess_optimizer_contract_payload(contract)
        runtime_input = {
            "task": "generate_slice_patch_candidate",
            "optimizer": optimizer,
            "index": index,
            "contract": contract_payload,
            "promptwizard_mode": "package_api",
            "strict_output": {
                "format": "json_object",
                "required_fields": ["after_text", "critic_feedback"],
            },
            "claim_boundary": "promptwizard package optimizer runtime input only",
            "official_scores_claimed": False,
        }
        runtime_record["input"] = runtime_input
        if promptwizard_api.get("candidate_method") == (
            "prompt_generation.generate_candidate_prompts"
        ):
            generation_module = _promptwizard_generation_module(module)
            restore_openai_call = _install_promptwizard_local_openai_stub(
                generation_module=generation_module,
                contract_payload=contract_payload,
            )
            try:
                generated = generation_module.generate_candidate_prompts(
                    (
                        "Generate one bounded section-local prompt rewrite. "
                        "Return only the rewritten section text."
                    ),
                    [
                        {
                            "input": contract_payload.get("target_slice") or "target_slice",
                            "output": "preserve protected slices",
                        }
                    ],
                    (
                        f"Rewrite this prompt section for {contract_payload.get('target_slice')}: "
                        f"{contract_payload.get('before_text')}"
                    ),
                    number_of_prompts=1,
                )
            finally:
                restore_openai_call()
            prompts = generated[0] if isinstance(generated, tuple) else generated
            if not isinstance(prompts, list) or not prompts:
                raise ValueError("PromptWizard generate_candidate_prompts returned no prompts")
            raw_output = {
                "after_text": _string_value(prompts[0]) or str(prompts[0]),
                "critic_feedback": (
                    "PromptWizard prompt_generation.generate_candidate_prompts "
                    "returned a bounded rewrite."
                ),
                "candidate_strategy": "promptwizard_generate_candidate_prompts_runtime",
                "promptwizard_generation_result": {
                    "prompt_count": len(prompts),
                    "raw_result_items": len(generated)
                    if isinstance(generated, tuple)
                    else 1,
                    "openai_call_mode": "local_stubbed_for_package_api",
                },
            }
        else:
            optimizer_class = getattr(module, "PromptOptimizer")
            optimizer_instance = optimizer_class()
            if hasattr(optimizer_instance, "generate_slice_patch_candidate"):
                raw_output = optimizer_instance.generate_slice_patch_candidate(
                    runtime_input
                )
            elif hasattr(optimizer_instance, "optimize_prompt"):
                optimized = optimizer_instance.optimize_prompt(
                    contract_payload.get("before_text"),
                    task=runtime_input,
                )
                raw_output = {
                    "after_text": optimized,
                    "critic_feedback": "PromptWizard optimize_prompt returned a rewrite.",
                    "candidate_strategy": "promptwizard_python_package_runtime",
                }
            else:
                raise AttributeError("PromptOptimizer has no supported candidate method")
        if not isinstance(raw_output, dict):
            raise ValueError("PromptWizard package optimizer output must be an object")
        if not _string_value(raw_output.get("after_text")):
            raise ValueError("PromptWizard package optimizer output requires after_text")
    except Exception as exc:
        runtime_record["status"] = "failed"
        runtime_record["executed"] = True
        runtime_record["runtime_ready"] = False
        runtime_record["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
        runtime_record["duration_seconds"] = _duration_seconds_since(started)
        return None, runtime_record, {"type": type(exc).__name__, "message": str(exc)}

    runtime_record["status"] = "executed"
    runtime_record["executed"] = True
    runtime_record["runtime_ready"] = True
    runtime_record["output"] = dict(raw_output)
    runtime_record["promptwizard_api"] = promptwizard_api
    runtime_record["duration_seconds"] = _duration_seconds_since(started)
    candidate = _manual_slice_patch_candidate(
        contract=contract,
        optimizer=optimizer,
        index=index,
    )
    candidate["after_text"] = _string_value(raw_output.get("after_text"))
    candidate["critic_feedback"] = _string_value(raw_output.get("critic_feedback"))
    candidate["candidate_strategy"] = (
        _string_value(raw_output.get("candidate_strategy"))
        or "promptwizard_python_package_runtime"
    )
    candidate["executes_tool"] = True
    candidate["executes_optimizer_runtime"] = True
    candidate["optimizer_runtime"] = {
        "status": runtime_record["status"],
        "provider": runtime_record["provider"],
        "kind": runtime_record["kind"],
        "package_import": package_import,
        "package_name": package_name,
        "package_version": package_version,
        "candidate_method": runtime_record.get("candidate_method"),
        "duration_seconds": runtime_record["duration_seconds"],
        "fallback_used": False,
        "promptwizard_api": promptwizard_api,
    }
    if isinstance(raw_output.get("promptwizard_generation_result"), dict):
        candidate["optimizer_runtime"]["promptwizard_generation_result"] = raw_output[
            "promptwizard_generation_result"
        ]
    return candidate, runtime_record, None


def _duration_seconds_since(started: float) -> float:
    return round(max(time.perf_counter() - started, 0.000001), 6)


def _python_package_version(
    *,
    module: Any,
    package_name: str,
    package_import: str,
) -> str | None:
    for name in (package_name, package_import):
        if not name:
            continue
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    version = getattr(module, "__version__", None)
    return _string_value(version)


def _subprocess_optimizer_contract_payload(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "module_id": _string_value(contract.get("module_id")) or "unknown_module",
        "section_id": _string_value(contract.get("section_id")) or "unknown_section",
        "target_slice": _string_value(contract.get("target_slice")),
        "based_on_slices": _string_list(contract.get("based_on_slices")),
        "protected_slices": _string_list(contract.get("protected_slices")),
        "protected_sections": _string_list(contract.get("protected_sections")),
        "before_text": _string_value(contract.get("before_text")) or "",
    }


def _call_subprocess_json_optimizer(
    *,
    command: list[str],
    payload: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    if not command:
        raise ValueError("subprocess optimizer command is required")
    proc = subprocess.run(
        command,
        input=json.dumps(payload, ensure_ascii=False),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=max(1, int(timeout_seconds)),
        check=False,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or proc.stdout.strip()
        raise ValueError(
            f"subprocess optimizer exited {proc.returncode}: {stderr[:500]}"
        )
    stdout = proc.stdout.strip()
    if not stdout:
        raise ValueError("subprocess optimizer returned empty stdout")
    parsed = json.loads(stdout)
    if not isinstance(parsed, dict):
        raise ValueError("subprocess optimizer stdout must be a JSON object")
    return {
        "payload": parsed,
        "raw_response": {
            "returncode": proc.returncode,
            "stdout_chars": len(proc.stdout),
            "stderr_chars": len(proc.stderr),
        },
    }


def _adapter_uses_openai_compatible_runtime(adapter: OptimizerAdapter) -> bool:
    entrypoint = (
        adapter.runtime_entrypoint
        if isinstance(adapter.runtime_entrypoint, dict)
        else {}
    )
    return (
        adapter.supports_execute_optimizer
        and _string_value(entrypoint.get("kind"))
        == "openai-compatible-chat-completions"
    )


def _adapter_uses_subprocess_json_runtime(adapter: OptimizerAdapter) -> bool:
    entrypoint = (
        adapter.runtime_entrypoint
        if isinstance(adapter.runtime_entrypoint, dict)
        else {}
    )
    return (
        adapter.supports_execute_optimizer
        and _string_value(entrypoint.get("kind")) == "local-subprocess-json"
    )


def _adapter_uses_python_package_runtime(adapter: OptimizerAdapter) -> bool:
    entrypoint = (
        adapter.runtime_entrypoint
        if isinstance(adapter.runtime_entrypoint, dict)
        else {}
    )
    return (
        adapter.supports_execute_optimizer
        and _string_value(entrypoint.get("kind")) == "python-package"
    )


def _adapter_uses_builtin_dspy_mipro(adapter: OptimizerAdapter) -> bool:
    entrypoint = (
        adapter.runtime_entrypoint
        if isinstance(adapter.runtime_entrypoint, dict)
        else {}
    )
    return (
        adapter.name == "dspy-mipro-package"
        or (
            _string_value(entrypoint.get("kind")) == "python-package"
            and _string_value(entrypoint.get("package_import")) == "dspy"
            and _string_value(entrypoint.get("candidate_method"))
            == "dspy_mipro_generate_slice_patch_candidate"
        )
    )


def _adapter_uses_builtin_textgrad_package(adapter: OptimizerAdapter) -> bool:
    entrypoint = (
        adapter.runtime_entrypoint
        if isinstance(adapter.runtime_entrypoint, dict)
        else {}
    )
    return (
        adapter.name == "textgrad-python-package"
        or (
            _string_value(entrypoint.get("kind")) == "python-package"
            and _string_value(entrypoint.get("package_import")) == "textgrad"
            and _string_value(entrypoint.get("candidate_method"))
            == "textgrad_generate_slice_patch_candidate"
        )
    )


def _adapter_uses_builtin_promptwizard_package(adapter: OptimizerAdapter) -> bool:
    entrypoint = (
        adapter.runtime_entrypoint
        if isinstance(adapter.runtime_entrypoint, dict)
        else {}
    )
    return (
        adapter.name == "promptwizard-python-package"
        or (
            _string_value(entrypoint.get("kind")) == "python-package"
            and _string_value(entrypoint.get("package_import")) == "promptwizard"
            and _string_value(entrypoint.get("candidate_method"))
            == "promptwizard_generate_slice_patch_candidate"
        )
    )


def _dspy_mipro_api_summary(module: Any) -> dict[str, str]:
    predict_class = getattr(module, "Predict")
    signature_class = getattr(module, "Signature")
    input_field = getattr(module, "InputField")
    output_field = getattr(module, "OutputField")
    mipro_class = getattr(importlib.import_module("dspy.teleprompt"), "MIPROv2")
    dummy_lm_class = getattr(importlib.import_module("dspy.utils.dummies"), "DummyLM")
    return {
        "predict_class": getattr(predict_class, "__name__", type(predict_class).__name__),
        "signature_class": getattr(
            signature_class,
            "__name__",
            type(signature_class).__name__,
        ),
        "input_field": getattr(input_field, "__name__", type(input_field).__name__),
        "output_field": getattr(output_field, "__name__", type(output_field).__name__),
        "mipro_class": getattr(mipro_class, "__name__", type(mipro_class).__name__),
        "dummy_lm_class": getattr(
            dummy_lm_class,
            "__name__",
            type(dummy_lm_class).__name__,
        ),
    }


def _textgrad_api_summary(module: Any) -> dict[str, str]:
    variable_class = getattr(module, "Variable")
    summary = {
        "variable_class": getattr(
            variable_class,
            "__name__",
            type(variable_class).__name__,
        ),
        "variable_signature": _callable_signature(variable_class),
    }
    tgd_class = getattr(module, "TGD", None) or getattr(
        module,
        "TextualGradientDescent",
        None,
    )
    if tgd_class is not None:
        summary["optimizer_class"] = getattr(
            tgd_class,
            "__name__",
            type(tgd_class).__name__,
        )
        summary["optimizer_signature"] = _callable_signature(tgd_class)
    for function_name in ("get_engine", "set_backward_engine"):
        function = getattr(module, function_name, None)
        if function is not None:
            summary[f"{function_name}_signature"] = _callable_signature(function)
    return summary


def _promptwizard_api_summary(module: Any) -> dict[str, str]:
    optimizer_class = getattr(module, "PromptOptimizer", None)
    if optimizer_class is not None:
        candidate_method = getattr(
            optimizer_class,
            "generate_slice_patch_candidate",
            None,
        )
        optimize_prompt = getattr(optimizer_class, "optimize_prompt", None)
        if candidate_method is not None or optimize_prompt is not None:
            return {
                "package_style": "prompt_optimizer",
                "optimizer_class": getattr(
                    optimizer_class,
                    "__name__",
                    type(optimizer_class).__name__,
                ),
                "candidate_method": (
                    "generate_slice_patch_candidate"
                    if candidate_method is not None
                    else "optimize_prompt"
                ),
                "candidate_signature": _callable_signature(
                    candidate_method or optimize_prompt
                ),
            }
    generation_module = _promptwizard_generation_module(module)
    generator = getattr(generation_module, "generate_candidate_prompts")
    return {
        "package_style": "prompt_generation",
        "optimizer_class": "",
        "candidate_method": "prompt_generation.generate_candidate_prompts",
        "candidate_signature": _callable_signature(generator),
    }


def _promptwizard_generation_module(module: Any) -> Any:
    package_name = getattr(module, "__name__", "promptwizard")
    with _temporary_env_default(
        "OPENAI_API_KEY",
        "ml-research-loop-local-promptwizard-stub",
    ):
        direct_module = _promptwizard_generation_module_from_file(
            module=module,
            package_name=package_name,
        )
        if direct_module is not None:
            return direct_module
        try:
            return importlib.import_module(f"{package_name}.prompt_generation.generation")
        except Exception as import_error:
            raise import_error


def _promptwizard_generation_module_from_file(
    *,
    module: Any,
    package_name: str,
) -> Any | None:
    module_file = _string_value(getattr(module, "__file__", None))
    if not module_file:
        return None
    generation_path = (
        Path(module_file).resolve().parent / "prompt_generation" / "generation.py"
    )
    if not generation_path.exists():
        return None
    parent_name = f"{package_name}.prompt_generation"
    parent_module = types.ModuleType(parent_name)
    parent_module.__path__ = [str(generation_path.parent)]  # type: ignore[attr-defined]
    sys.modules[parent_name] = parent_module
    module_name = f"{parent_name}.generation"
    spec = importlib.util.spec_from_file_location(module_name, generation_path)
    if spec is None or spec.loader is None:
        return None
    generation_module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = generation_module
    spec.loader.exec_module(generation_module)
    return generation_module


def _install_promptwizard_local_openai_stub(
    *,
    generation_module: Any,
    contract_payload: dict[str, Any],
) -> Callable[[], None]:
    openai_call = getattr(generation_module, "openai_call", None)
    original = getattr(openai_call, "create_chat_completion", None)
    if openai_call is None or original is None:
        return lambda: None

    def local_create_chat_completion(
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
        n: int,
        **kwargs: Any,
    ) -> Any:
        del model, messages, max_tokens, temperature, kwargs
        target_slice = _string_value(contract_payload.get("target_slice")) or "target slice"
        before_text = _string_value(contract_payload.get("before_text"))
        content = (
            f"{before_text}\n"
            f"PromptWizard package local candidate: add a bounded guard for "
            f"{target_slice}; preserve protected slices."
        )
        choices = [
            types.SimpleNamespace(message=types.SimpleNamespace(content=content))
            for _ in range(max(1, int(n)))
        ]
        return types.SimpleNamespace(
            usage=types.SimpleNamespace(
                prompt_tokens=12,
                completion_tokens=18,
            ),
            choices=choices,
        )

    setattr(openai_call, "create_chat_completion", local_create_chat_completion)

    def restore() -> None:
        setattr(openai_call, "create_chat_completion", original)

    return restore


class _temporary_env_default:
    def __init__(self, key: str, value: str) -> None:
        self.key = key
        self.value = value
        self._had_key = False
        self._old_value: str | None = None

    def __enter__(self) -> None:
        self._had_key = self.key in os.environ
        self._old_value = os.environ.get(self.key)
        if not self._had_key:
            os.environ[self.key] = self.value

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        del exc_type, exc, tb
        if self._had_key:
            if self._old_value is not None:
                os.environ[self.key] = self._old_value
        else:
            os.environ.pop(self.key, None)


def _callable_signature(value: Any) -> str:
    try:
        return str(inspect.signature(value))
    except (TypeError, ValueError):
        return ""


def _subprocess_json_runtime_command(adapter: OptimizerAdapter) -> list[str]:
    entrypoint = (
        adapter.runtime_entrypoint
        if isinstance(adapter.runtime_entrypoint, dict)
        else {}
    )
    command = entrypoint.get("command")
    if not isinstance(command, list) or not all(
        isinstance(item, str) and item for item in command
    ):
        raise ValueError(f"optimizer adapter {adapter.name} subprocess command is invalid")
    return list(command)


def _python_package_runtime_entrypoint(adapter: OptimizerAdapter) -> dict[str, Any]:
    entrypoint = (
        adapter.runtime_entrypoint
        if isinstance(adapter.runtime_entrypoint, dict)
        else {}
    )
    package_import = _string_value(entrypoint.get("package_import"))
    if not package_import:
        raise ValueError(f"optimizer adapter {adapter.name} package_import is invalid")
    return {
        "kind": "python-package",
        "supports_execute_optimizer": bool(adapter.supports_execute_optimizer),
        "package_import": package_import,
        **(
            {"package_name": _string_value(entrypoint.get("package_name"))}
            if _string_value(entrypoint.get("package_name"))
            else {}
        ),
        **(
            {"adapter_class": _string_value(entrypoint.get("adapter_class"))}
            if _string_value(entrypoint.get("adapter_class"))
            else {}
        ),
        **(
            {"probe_method": _string_value(entrypoint.get("probe_method"))}
            if _string_value(entrypoint.get("probe_method"))
            else {}
        ),
        **(
            {"candidate_method": _string_value(entrypoint.get("candidate_method"))}
            if _string_value(entrypoint.get("candidate_method"))
            else {}
        ),
    }


def _ensure_optimizer_runtime_cache_paths(package_import: str) -> list[str]:
    """Expose locally cached optimizer packages without requiring PYTHONPATH."""
    package_name = _string_value(package_import)
    if not package_name:
        return []
    added: list[str] = []
    for path in _optimizer_runtime_cache_paths(package_name):
        path_ref = str(path)
        if path_ref not in sys.path:
            sys.path.append(path_ref)
            added.append(path_ref)
    return added


def _optimizer_runtime_cache_paths(package_import: str) -> list[Path]:
    package_top = package_import.split(".", 1)[0]
    seen: set[Path] = set()
    paths: list[Path] = []
    for root in _optimizer_runtime_cache_roots():
        if not root.exists():
            continue
        direct_names = [
            package_import,
            package_top,
            f"{package_top}-real",
        ]
        for name in direct_names:
            candidate = root / name
            if _optimizer_runtime_cache_path_matches(candidate, package_top):
                resolved = candidate.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    paths.append(resolved)
        for candidate in sorted(root.glob(f"{package_top}*")):
            if _optimizer_runtime_cache_path_matches(candidate, package_top):
                resolved = candidate.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    paths.append(resolved)
    return paths


def _optimizer_runtime_cache_roots() -> list[Path]:
    workspace_root = Path(__file__).resolve().parents[1]
    roots: list[Path] = []
    for base in (Path.cwd(), workspace_root):
        root = base / ".research_cache" / "optimizer-runtime-packages"
        if root not in roots:
            roots.append(root)
    return roots


def _optimizer_runtime_cache_path_matches(path: Path, package_top: str) -> bool:
    return path.is_dir() and (path / package_top).exists()


def _probe_python_package_runtime(adapter: OptimizerAdapter) -> dict[str, Any]:
    entrypoint = _python_package_runtime_entrypoint(adapter)
    package_import = _string_value(entrypoint.get("package_import")) or ""
    package_name = _string_value(entrypoint.get("package_name")) or package_import
    adapter_class_name = _string_value(entrypoint.get("adapter_class"))
    probe_method_name = _string_value(entrypoint.get("probe_method"))
    candidate_method_name = _string_value(entrypoint.get("candidate_method"))
    runtime_cache_paths = _ensure_optimizer_runtime_cache_paths(package_import)
    try:
        spec = importlib.util.find_spec(package_import)
    except (ImportError, AttributeError, ValueError) as exc:
        return {
            "status": "not_ready",
            "runtime_ready": False,
            "package_import": package_import,
            "runtime_cache_paths": runtime_cache_paths,
            "import_available": False,
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        }
    if spec is None:
        return {
            "status": "not_ready",
            "runtime_ready": False,
            "package_import": package_import,
            "package_name": package_name,
            "runtime_cache_paths": runtime_cache_paths,
            "adapter_class": adapter_class_name,
            "probe_method": probe_method_name,
            "candidate_method": candidate_method_name,
            "import_available": False,
            "origin": None,
        }
    try:
        module = importlib.import_module(package_import)
    except Exception as exc:
        return {
            "status": "not_ready",
            "runtime_ready": False,
            "package_import": package_import,
            "package_name": package_name,
            "runtime_cache_paths": runtime_cache_paths,
            "adapter_class": adapter_class_name,
            "probe_method": probe_method_name,
            "candidate_method": candidate_method_name,
            "import_available": False,
            "origin": _path_ref(_string_value(getattr(spec, "origin", None))),
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        }
    result: dict[str, Any] = {
        "status": "ready",
        "runtime_ready": True,
        "package_import": package_import,
        "package_name": package_name,
        "runtime_cache_paths": runtime_cache_paths,
        "package_version": _python_package_version(
            module=module,
            package_name=package_name,
            package_import=package_import,
        ),
        "adapter_class": adapter_class_name,
        "probe_method": probe_method_name,
        "candidate_method": candidate_method_name,
        "import_available": True,
        "origin": _path_ref(_string_value(getattr(spec, "origin", None))),
    }
    if _adapter_uses_builtin_dspy_mipro(adapter):
        try:
            result["dspy_api"] = _dspy_mipro_api_summary(module)
        except Exception as exc:
            result["status"] = "not_ready"
            result["runtime_ready"] = False
            result["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
            return result
    if _adapter_uses_builtin_textgrad_package(adapter):
        try:
            result["textgrad_api"] = _textgrad_api_summary(module)
        except Exception as exc:
            result["status"] = "not_ready"
            result["runtime_ready"] = False
            result["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
            return result
    if _adapter_uses_builtin_promptwizard_package(adapter):
        try:
            result["promptwizard_api"] = _promptwizard_api_summary(module)
        except Exception as exc:
            result["status"] = "not_ready"
            result["runtime_ready"] = False
            result["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
            return result
    if probe_method_name:
        try:
            target: Any = module
            if adapter_class_name:
                adapter_class = getattr(module, adapter_class_name)
                target = adapter_class()
            probe_method = getattr(target, probe_method_name)
            probe_output = probe_method({
                "package_import": package_import,
                "package_name": package_name,
                "adapter_class": adapter_class_name,
                "probe_method": probe_method_name,
                "candidate_method": candidate_method_name,
                "claim_boundary": "python package optimizer runtime readiness probe only",
                "official_scores_claimed": False,
            })
            if not isinstance(probe_output, dict):
                raise ValueError("python package optimizer probe output must be an object")
            result.update(probe_output)
            result["package_import"] = package_import
            result["package_name"] = package_name
            result["package_version"] = _python_package_version(
                module=module,
                package_name=package_name,
                package_import=package_import,
            )
            result["adapter_class"] = adapter_class_name
            result["probe_method"] = probe_method_name
            result["candidate_method"] = candidate_method_name
            result["import_available"] = True
            result["runtime_ready"] = bool(result.get("runtime_ready", False))
            result["status"] = _string_value(result.get("status")) or (
                "ready" if result["runtime_ready"] else "not_ready"
            )
        except Exception as exc:
            result["status"] = "not_ready"
            result["runtime_ready"] = False
            result["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
    return result


def _optimizer_runtime_api_key(
    *,
    adapter: OptimizerAdapter,
    optimizer_api_key: str | None,
) -> str | None:
    if optimizer_api_key:
        return optimizer_api_key
    entrypoint = (
        adapter.runtime_entrypoint
        if isinstance(adapter.runtime_entrypoint, dict)
        else {}
    )
    api_key_env = _string_value(entrypoint.get("api_key_env"))
    if api_key_env:
        return os.environ.get(api_key_env)
    return None


def _slice_optimizer_runtime(
    *,
    optimizer: str,
    execute_optimizer: bool,
    optimizer_model: str | None,
    optimizer_base_url: str | None,
    optimizer_timeout_seconds: int,
    optimizer_temperature: float,
    optimizer_max_tokens: int,
    supports_execute_optimizer: bool = False,
    default_model: str | None = None,
    default_base_url: str | None = None,
    runtime_entrypoint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entrypoint = runtime_entrypoint if isinstance(runtime_entrypoint, dict) else None
    entrypoint_kind = _string_value(entrypoint.get("kind")) if entrypoint else None
    if entrypoint_kind == "python-package":
        package_import = _string_value(entrypoint.get("package_import")) or ""
        runtime_entrypoint_payload: dict[str, Any] = {
            "kind": "python-package",
            "supports_execute_optimizer": bool(supports_execute_optimizer),
            "package_import": package_import,
        }
        for key in ("package_name", "adapter_class", "probe_method", "candidate_method"):
            value = _string_value(entrypoint.get(key)) if entrypoint else None
            if value:
                runtime_entrypoint_payload[key] = value
        return {
            "status": "configured" if execute_optimizer else "not_executed",
            "executed": bool(execute_optimizer),
            "provider": "python-package",
            "timeout_seconds": max(1, int(optimizer_timeout_seconds)),
            "requires_explicit_execution": not execute_optimizer,
            "runtime_entrypoint": runtime_entrypoint_payload,
        }
    if entrypoint_kind == "local-subprocess-json":
        command = entrypoint.get("command") if entrypoint else None
        return {
            "status": "configured" if execute_optimizer else "not_executed",
            "executed": bool(execute_optimizer),
            "provider": "local-subprocess-json",
            "timeout_seconds": max(1, int(optimizer_timeout_seconds)),
            "requires_explicit_execution": not execute_optimizer,
            "runtime_entrypoint": {
                "kind": "local-subprocess-json",
                "supports_execute_optimizer": bool(supports_execute_optimizer),
                "command_length": len(command) if isinstance(command, list) else 0,
            },
        }
    uses_openai_compatible = (
        optimizer == "textgrad-openai-compatible"
        or entrypoint_kind == "openai-compatible-chat-completions"
    )
    if not uses_openai_compatible:
        return {
            "status": "not_required",
            "executed": False,
            "provider": "deterministic-local",
        }
    model_env = _string_value(entrypoint.get("model_env")) if entrypoint else None
    base_url_env = _string_value(entrypoint.get("base_url_env")) if entrypoint else None
    model = (
        optimizer_model
        or (os.environ.get(model_env) if model_env else None)
        or os.environ.get("ML_RESEARCH_LOOP_TEXTGRAD_MODEL")
        or (entrypoint.get("default_model") if entrypoint else None)
        or default_model
        or DEFAULT_TEXTGRAD_OPTIMIZER_MODEL
    )
    base_url = (
        optimizer_base_url
        or (os.environ.get(base_url_env) if base_url_env else None)
        or os.environ.get("ML_RESEARCH_LOOP_TEXTGRAD_BASE_URL")
        or (entrypoint.get("default_base_url") if entrypoint else None)
        or default_base_url
        or DEFAULT_TEXTGRAD_OPTIMIZER_BASE_URL
    )
    payload = {
        "status": "configured" if execute_optimizer else "not_executed",
        "executed": bool(execute_optimizer),
        "provider": "openai-compatible",
        "model": model,
        "base_url": base_url,
        "timeout_seconds": max(1, int(optimizer_timeout_seconds)),
        "temperature": float(optimizer_temperature),
        "max_tokens": max(1, int(optimizer_max_tokens)),
        "requires_explicit_execution": not execute_optimizer,
    }
    if entrypoint_kind:
        payload["runtime_entrypoint"] = {
            "kind": entrypoint_kind,
            "supports_execute_optimizer": bool(supports_execute_optimizer),
        }
    return payload


def _textgrad_candidate_messages(*, contract: dict[str, Any]) -> list[dict[str, str]]:
    module_id = _string_value(contract.get("module_id")) or "unknown_module"
    section_id = _string_value(contract.get("section_id")) or "unknown_section"
    prompt = {
        "task": "Generate a TextGrad-style section-local prompt repair.",
        "strict_output": {
            "format": "json_object",
            "required_fields": ["critic_feedback", "after_text"],
        },
        "constraints": [
            "Edit only the requested section.",
            "Do not rewrite the full prompt profile.",
            "Preserve protected slices and protected sections.",
            "Do not claim benchmark or leaderboard scores.",
        ],
        "contract": {
            "module_id": module_id,
            "section_id": section_id,
            "target_slice": _string_value(contract.get("target_slice")),
            "based_on_slices": _string_list(contract.get("based_on_slices")),
            "protected_slices": _string_list(contract.get("protected_slices")),
            "protected_sections": _string_list(contract.get("protected_sections")),
            "before_text": _string_value(contract.get("before_text")) or "",
        },
    }
    return [
        {
            "role": "system",
            "content": (
                "/no_think\n"
                "You are a prompt repair critic. Return only compact JSON with "
                "critic_feedback and after_text."
            ),
        },
        {"role": "user", "content": "/no_think\n" + json.dumps(prompt, ensure_ascii=False)},
    ]


def _call_openai_compatible_chat(
    *,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    api_key: str | None,
    temperature: float,
    max_tokens: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    resolved_api_key = api_key or os.environ.get("ML_RESEARCH_LOOP_TEXTGRAD_API_KEY")
    if resolved_api_key is None:
        resolved_api_key = os.environ.get("OPENAI_API_KEY")
    if resolved_api_key:
        headers["Authorization"] = f"Bearer {resolved_api_key}"
    body = {
        "model": model,
        "messages": messages,
        "temperature": float(temperature),
        "max_tokens": max(1, int(max_tokens)),
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=max(1, int(timeout_seconds)),
        ) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"textgrad optimizer HTTP {exc.code}: {error_text}") from exc
    payload = json.loads(raw)
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("textgrad optimizer response missing choices")
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first.get("message"), dict) else {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("textgrad optimizer response missing message content")
    return {
        "content": content,
        "raw_response": {
            "id": payload.get("id"),
            "model": payload.get("model"),
            "usage": payload.get("usage"),
        },
    }


def _parse_textgrad_candidate_response(content: Any) -> dict[str, Any]:
    if not isinstance(content, str):
        return {}
    text = content.strip()
    if text.startswith("```"):
        text = _strip_json_code_fence(text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"critic_feedback": text}
    return payload if isinstance(payload, dict) else {}


def _strip_json_code_fence(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _response_id(value: Any) -> str | None:
    if isinstance(value, dict):
        return _string_value(value.get("id"))
    return None


def _slice_candidate_strategy(*, optimizer: str, index: int) -> str:
    if optimizer == "textgrad-local":
        return "section_local_textual_gradient"
    if optimizer == "textgrad-openai-compatible":
        return "textgrad_openai_compatible_pending"
    if optimizer == "promptwizard-adapter":
        strategies = ["self_critique_variant", "example_synthesis_variant"]
        return strategies[(index - 1) % len(strategies)]
    if optimizer == "promptwizard-constrained":
        return "constraint_guard_variant"
    return "manual_template"


def _slice_candidate_after_text(
    *,
    before_text: str,
    based_on_slices: list[str],
    protected: str,
    optimizer: str,
    strategy: str,
) -> str:
    target = ", ".join(based_on_slices or ["the target slice"])
    if optimizer == "textgrad-local":
        suffix = (
            "Textual-gradient repair: identify the failing slice contract, adjust only "
            f"this section for {target}, and explicitly preserve protected slices: {protected}."
        )
    elif optimizer == "promptwizard-adapter" and strategy == "self_critique_variant":
        suffix = (
            "Self-critique variant: rewrite the local instruction to reduce the observed "
            f"failure on {target}, without changing other modules or protected slices: {protected}."
        )
    elif optimizer == "promptwizard-adapter":
        suffix = (
            "Example-synthesis variant: add a compact local format cue for "
            f"{target}, while keeping protected slices unchanged: {protected}."
        )
    elif optimizer == "promptwizard-constrained":
        suffix = (
            "PromptWizard constrained variant: preserve the accepted base profile behavior, "
            f"add only a local guard for {target}, and explicitly keep protected slices "
            f"unchanged: {protected}."
        )
    else:
        suffix = f"Slice-local repair: address {target} while preserving protected slices: {protected}."
    return (before_text.rstrip() + "\n\n" + suffix).strip()


def _slice_metrics(report: dict[str, Any]) -> dict[str, float]:
    metrics = report.get("metrics")
    if not isinstance(metrics, dict):
        return {}
    return {
        str(key): float(value)
        for key, value in metrics.items()
        if _is_plain_number(value)
    }


def _slice_report_split(report: dict[str, Any]) -> str | None:
    explicit = _string_value(report.get("evaluation_split"))
    if explicit:
        return explicit
    dataset = report.get("dataset") if isinstance(report.get("dataset"), dict) else {}
    dataset_split = _string_value(dataset.get("evaluation_split"))
    if dataset_split:
        return dataset_split
    return _evaluation_split_from_evaluation(report)


def _slice_task_family(*reports: dict[str, Any]) -> str:
    for report in reports:
        explicit = _string_value(report.get("task_family"))
        if explicit:
            return explicit
        proposal = report.get("proposal") if isinstance(report.get("proposal"), dict) else {}
        change_spec = (
            proposal.get("change_spec")
            if isinstance(proposal.get("change_spec"), dict)
            else {}
        )
        task_family = _string_value(change_spec.get("task_family"))
        if task_family:
            return task_family
    return "smol_worldcup_prompt_routing"


def _load_object(value: dict[str, Any] | str | Path) -> tuple[dict[str, Any], Path | None]:
    if isinstance(value, dict):
        return value, None
    path = Path(value)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload, path


def _json_clone(value: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _load_slice_candidate(value: dict[str, Any] | str | Path) -> tuple[dict[str, Any], Path | None]:
    payload, path = _load_object(value)
    if isinstance(payload.get("candidates"), list) and payload["candidates"]:
        first = payload["candidates"][0]
        if isinstance(first, dict):
            return first, path
    return payload, path


def _metric_delta_map(evaluation: dict[str, Any]) -> dict[str, float]:
    explicit = evaluation.get("metric_delta")
    if isinstance(explicit, dict):
        normalized = {
            str(key): float(value)
            for key, value in explicit.items()
            if _is_plain_number(value)
        }
        if normalized:
            return normalized
    deltas: dict[str, float] = {}
    for split in ("dev", "canary", "holdout", "external"):
        numeric = _metric_value(evaluation.get(f"{split}_delta"))
        if numeric is not None:
            deltas[split] = numeric
    return deltas


def _numeric_metric_map(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): float(item)
        for key, item in value.items()
        if _is_plain_number(item)
    }


def _metric_map(value: Any) -> dict[str, float]:
    if _is_plain_number(value):
        return {"primary": float(value)}
    if not isinstance(value, dict):
        return {}
    return {
        str(key): float(metric)
        for key, metric in value.items()
        if _is_plain_number(metric)
    }


def _metric_value(value: Any) -> float | None:
    if _is_plain_number(value):
        return float(value)
    if not isinstance(value, dict):
        return None
    if _is_plain_number(value.get("SHIFT")):
        return float(value["SHIFT"])
    for item in value.values():
        if _is_plain_number(item):
            return float(item)
    return None


def _outcome_failure_labels(
    evaluation: dict[str, Any],
    metric_delta: dict[str, float],
    *,
    evaluation_split: str | None = None,
) -> list[str]:
    labels = _string_list(evaluation.get("failure_labels"))
    if labels:
        return [
            _normalize_failure_type(label, evaluation_split=evaluation_split) for label in labels
        ]
    rollback_reasons = _string_list(evaluation.get("rollback_reasons"))
    if rollback_reasons:
        return [
            _normalize_failure_type(reason, evaluation_split=evaluation_split)
            for reason in rollback_reasons
        ]
    return [
        f"{split}_not_confirmed" if split in {"canary", "holdout"} else "metric_regression"
        for split, value in metric_delta.items()
        if value < 0
    ]


def _accepted(metric_delta: dict[str, float], rollback_reasons: list[str]) -> bool:
    if rollback_reasons:
        return False
    return any(value > 0 for value in metric_delta.values())


def _artifact_refs_from_evaluation(evaluation: dict[str, Any]) -> list[dict[str, Any]]:
    refs = evaluation.get("artifact_refs")
    if not isinstance(refs, list):
        return []
    return [ref for ref in refs if isinstance(ref, dict)]


def _failure_labels_from_payload(payload: dict[str, Any]) -> list[str]:
    labels = _string_list(payload.get("failure_labels"))
    proposal = payload.get("proposal") if isinstance(payload.get("proposal"), dict) else {}
    evaluation = payload.get("evaluation") if isinstance(payload.get("evaluation"), dict) else {}
    evaluation_split = (
        _string_value(payload.get("evaluation_split"))
        or _evaluation_split_from_evaluation(evaluation)
        or _proposal_evaluation_split(proposal)
    )
    if labels:
        return [
            _normalize_failure_type(label, evaluation_split=evaluation_split) for label in labels
        ]
    rollback_reasons = _string_list(evaluation.get("rollback_reasons"))
    if rollback_reasons:
        return [
            _normalize_failure_type(reason, evaluation_split=evaluation_split)
            for reason in rollback_reasons
        ]
    status = _string_value(payload.get("status"))
    if status in {"needs_rollback_or_more_evidence", "insufficient_evidence"}:
        return ["no_improvement"]
    if status == "invalid_proposal":
        return ["invalid_patch"]
    return []


def _normalize_failure_type(label: str, *, evaluation_split: str | None = None) -> str:
    if label in KNOWN_FAILURE_TYPES:
        return label
    if label == "canary_delta_lt_0":
        return "canary_not_confirmed"
    if label == "holdout_delta_lt_0":
        return "holdout_not_confirmed"
    if label.endswith("_delta_lt_0"):
        if evaluation_split == "canary":
            return "canary_not_confirmed"
        if evaluation_split == "holdout":
            return "holdout_not_confirmed"
        return "metric_regression"
    if label.endswith("_regression"):
        return "metric_regression"
    if label in {"needs_rollback_or_more_evidence", "insufficient_evidence"}:
        return "no_improvement"
    if label == "invalid_proposal":
        return "invalid_patch"
    return "no_improvement"


def _evaluation_split_from_evaluation(evaluation: dict[str, Any]) -> str | None:
    explicit = _string_value(evaluation.get("evaluation_split"))
    if explicit:
        return explicit
    current_dataset = (
        evaluation.get("current_dataset")
        if isinstance(evaluation.get("current_dataset"), dict)
        else {}
    )
    current_split = _string_value(current_dataset.get("evaluation_split"))
    if current_split:
        return current_split
    if isinstance(evaluation.get("dev_delta"), dict):
        return "dev"
    if isinstance(evaluation.get("canary_delta"), dict):
        return "canary"
    if isinstance(evaluation.get("holdout_delta"), dict):
        return "holdout"
    return None


def _proposal_evaluation_split(proposal: dict[str, Any]) -> str | None:
    validation_plan = (
        proposal.get("validation_plan")
        if isinstance(proposal.get("validation_plan"), dict)
        else {}
    )
    return _string_value(validation_plan.get("promotion_split")) or _string_value(
        validation_plan.get("first_split")
    )


def _failure_symptom(
    label: str,
    *,
    payload: dict[str, Any],
    evaluation: dict[str, Any],
) -> str:
    if label in {"canary_not_confirmed", "holdout_not_confirmed"}:
        return f"{label} after local gain; promotion split regressed or failed to confirm."
    if label == "metric_regression":
        return "Primary metric regressed against the baseline or prior best."
    if label == "timeout":
        return "Experiment exceeded the allowed runtime budget."
    if label == "invalid_patch":
        return "Proposal or patch failed contract or guard validation."
    if label == "leakage_risk":
        return "Proposal introduced data or benchmark leakage risk."
    return (
        _string_value(payload.get("symptom"))
        or _string_value(evaluation.get("summary"))
        or f"Observed failure label: {label}."
    )


def _severity_for_failure(label: str) -> str:
    mapping = {
        "leakage_risk": "critical",
        "invalid_patch": "high",
        "runtime_error": "high",
        "timeout": "high",
        "scope_too_broad": "high",
        "canary_not_confirmed": "medium",
        "holdout_not_confirmed": "medium",
        "metric_regression": "medium",
        "no_improvement": "low",
        "cost_too_high": "medium",
    }
    return mapping.get(label, "medium")


def _outcome_summary(
    *,
    proposal_id: str,
    accepted: bool,
    regression: bool,
    rollback_reasons: list[str],
    metric_delta: dict[str, float],
) -> str:
    if rollback_reasons:
        return (
            f"Proposal {proposal_id} triggered rollback reasons {', '.join(rollback_reasons)}; "
            f"metric_delta={metric_delta}."
        )
    if accepted:
        return f"Proposal {proposal_id} produced bounded gain; metric_delta={metric_delta}."
    if regression:
        return f"Proposal {proposal_id} regressed; metric_delta={metric_delta}."
    return f"Proposal {proposal_id} completed without accepted gain; metric_delta={metric_delta}."


def _string_value(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _select_primary_failure_slice_label(labels: list[str]) -> str | None:
    preferred = [
        label
        for label in labels
        if label not in {"no_improvement", "metric_regression"}
    ]
    if preferred:
        return preferred[0]
    return labels[0] if labels else None


def _infer_smol_prompt_profile_from_outcome_ids(outcome_ids: list[str]) -> str | None:
    for outcome_id in outcome_ids:
        if not isinstance(outcome_id, str):
            continue
        lowered = outcome_id.lower()
        for suffix in ("dev-v2", "semantic-v2", "semantic-v1", "routing-v1"):
            if suffix in lowered:
                return f"p3-{suffix}"
        if "p3-" in lowered:
            start = lowered.find("p3-")
            candidate = lowered[start:].split("-202", 1)[0].split("-failure-driven", 1)[0]
            if candidate:
                return candidate
    return None


def _infer_smol_model_hint_from_outcome_ids(outcome_ids: list[str]) -> dict[str, Any]:
    joined = " ".join(
        outcome_id.lower() for outcome_id in outcome_ids if isinstance(outcome_id, str)
    )
    if "qwen3-8b" in joined:
        return {
            "model": "qwen/qwen3-8b",
            "base_url": "http://127.0.0.1:1234/v1",
            "model_provider": "openai-compatible",
            "judge_mode": "openai-compatible",
            "judge_model": "openai/gpt-oss-20b",
            "judge_base_url": "http://127.0.0.1:1234/v1",
            "model_size_billion": 8.0,
            "estimated_ram_gb": 16.0,
        }
    if "gpt-oss-20b" in joined:
        return {
            "model": "openai/gpt-oss-20b",
            "base_url": "http://127.0.0.1:1234/v1",
            "model_provider": "openai-compatible",
            "judge_mode": "heuristic",
            "model_size_billion": 20.0,
            "estimated_ram_gb": 32.0,
        }
    return {}


def _resolve_smol_worldcup_current_report(
    *,
    evidence_root: Path | None,
    prompt_profile: str,
    evaluation_split: str,
    model_id: str | None = None,
) -> Path | None:
    workspace_root = Path(__file__).resolve().parents[1]
    root = evidence_root or workspace_root / "docs" / "evidence"
    search_roots = [root]
    if evidence_root is None:
        search_roots.append(workspace_root / ".demo_runs")
    fallback_root = workspace_root / ".demo_runs"

    def _collect(search_root: Path) -> list[Path]:
        matches: list[Path] = []
        seen: set[Path] = set()
        if not search_root.exists():
            return matches
        for candidate in search_root.rglob("*model-eval-report.json"):
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            model = payload.get("model") if isinstance(payload.get("model"), dict) else {}
            dataset = payload.get("dataset") if isinstance(payload.get("dataset"), dict) else {}
            if _string_value(model.get("prompt_profile")) != prompt_profile:
                continue
            if _string_value(dataset.get("evaluation_split")) != evaluation_split:
                continue
            if model_id and _string_value(model.get("id")) != model_id:
                continue
            matches.append(resolved)
        return matches

    matches: list[Path] = []
    for search_root in search_roots:
        matches.extend(_collect(search_root))
    if not matches:
        if evidence_root is not None and fallback_root.exists():
            matches = _collect(fallback_root)
        if not matches:
            return None
    matches.sort(key=lambda path: (".demo_runs" not in str(path), str(path)))
    return matches[0]


def _smol_runtime_config_from_report_or_hint(
    *,
    report_path: Path | None,
    model_hint: dict[str, Any],
) -> dict[str, Any]:
    config = dict(model_hint)
    if report_path is None or not report_path.exists():
        return config
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return config
    model = payload.get("model") if isinstance(payload.get("model"), dict) else {}
    config["model"] = _string_value(model.get("id")) or config.get("model")
    config["base_url"] = _string_value(model.get("base_url")) or config.get("base_url")
    config["model_provider"] = _string_value(model.get("provider")) or config.get(
        "model_provider"
    )
    config["judge_mode"] = _string_value(model.get("judge_mode")) or config.get("judge_mode")
    config["judge_model"] = _string_value(model.get("judge_model")) or config.get("judge_model")
    config["judge_base_url"] = _string_value(model.get("judge_base_url")) or config.get(
        "judge_base_url"
    )
    if _is_plain_number(model.get("estimated_size_billion")):
        config["model_size_billion"] = float(model["estimated_size_billion"])
    if _is_plain_number(model.get("estimated_ram_gb")):
        config["estimated_ram_gb"] = float(model["estimated_ram_gb"])
    return config


def _is_plain_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _ensure_writable(path: Path, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists; pass overwrite=True to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_jsonl(items: list[dict[str, Any]], output: Path) -> None:
    with output.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
