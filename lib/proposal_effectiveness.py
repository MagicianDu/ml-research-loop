"""Proposal-effectiveness measurement: compares failure-driven-context arms
against control arms across cp_bench, fasttext, smol_worldcup, real_paper,
cross-task, and mixed-signal benchmark reports, and builds the resulting
claim-audit / promotion-gate / handoff artifacts.

Extracted from lib/failure_driven_proposal.py. The six helpers that stay
behind there (_extract_failure_records_from_payload, _failure_bad_cases,
_pattern_from_group, _average_metric_delta, _pattern_match,
_most_common_string) are called directly by that module's core
extract_failure_records/build_proposal_pattern_memory/retrieve_proposal_patterns
functions and have no dependency on anything in this module, so they were
deliberately left out of this extraction to avoid a circular import.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from lib.benchmarks.smol_worldcup import _build_model_messages
from lib.fdp_common import (
    _ensure_writable,
    _is_plain_number,
    _load_object,
    _string_list,
    _string_value,
    _write_jsonl,
)
from lib.proposal_contract import validate_client_proposal
from lib.research_memory import MemoryArtifactRef, MemoryEvidenceRef, ResearchMemoryCard
from lib.failure_driven_proposal import (
    CP_BENCH_EFFECTIVENESS_BUNDLE_SCHEMA_VERSION,
    CROSS_TASK_EFFECTIVENESS_SUMMARY_SCHEMA_VERSION,
    FAILURE_DRIVEN_CONTEXT_SCHEMA_VERSION,
    FAILURE_DRIVEN_GENERATION_SCHEMA_VERSION,
    FAILURE_DRIVEN_HANDOFF_SCHEMA_VERSION,
    FAILURE_DRIVEN_MEMORY_BRIDGE_SCHEMA_VERSION,
    FAILURE_DRIVEN_RANKING_SCHEMA_VERSION,
    FAILURE_DRIVEN_TEMPLATE_SCHEMA_VERSION,
    FASTTEXT_EFFECTIVENESS_BUNDLE_SCHEMA_VERSION,
    MIXED_SIGNAL_EFFECTIVENESS_AUDIT_SCHEMA_VERSION,
    PROPOSAL_EFFECTIVENESS_CLAIM_AUDIT_SCHEMA_VERSION,
    PROPOSAL_EFFECTIVENESS_SCHEMA_VERSION,
    PROPOSAL_OUTCOME_SCHEMA_VERSION,
    REAL_PAPER_EFFECTIVENESS_BUNDLE_SCHEMA_VERSION,
    SMOL_WORLDCUP_CACHED_CONFIDENCE_SCORING_GATE_SCHEMA_VERSION,
    SMOL_WORLDCUP_CANARY_CONTROL_ARM_EXECUTION_BUNDLE_SCHEMA_VERSION,
    SMOL_WORLDCUP_CANARY_CONTROL_ARM_HANDOFF_SCHEMA_VERSION,
    SMOL_WORLDCUP_CANARY_FAILURE_SLICE_AUDIT_SCHEMA_VERSION,
    SMOL_WORLDCUP_CONFIDENCE_VARIANCE_GATE_SCHEMA_VERSION,
    SMOL_WORLDCUP_EFFECTIVENESS_BUNDLE_SCHEMA_VERSION,
    SMOL_WORLDCUP_PROMOTION_GATE_REFRESH_SCHEMA_VERSION,
    SMOL_WORLDCUP_PROMOTION_GATE_SCHEMA_VERSION,
    SMOL_WORLDCUP_RESULT_ANALYSIS_SCHEMA_VERSION,
    _average_metric_delta,
    _bridge_failure_category,
    _bridge_summary,
    _client_template_from_selected,
    _failure_index,
    _failure_type_counts,
    _gate_labels,
    _handoff_failure_lookup,
    _handoff_failure_records,
    _handoff_selected_lookup,
    _infer_smol_model_hint_from_outcome_ids,
    _infer_smol_prompt_profile_from_outcome_ids,
    _load_failure_records,
    _load_optional_object,
    _load_outcome_items,
    _load_pattern_memory,
    _load_proposals,
    _matched_patterns,
    _memory_bridge_artifact_path,
    _normalize_failure_type,
    _proposal_signature,
    _render_failure_driven_prompt,
    _resolve_smol_worldcup_current_report,
    _score_breakdown,
    _select_primary_failure_slice_label,
    _smol_runtime_config_from_report_or_hint,
    _source_pattern_ids,
    _write_client_templates_markdown,
    _write_failure_handoff_markdown,
)


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
