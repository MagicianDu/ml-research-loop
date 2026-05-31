"""CP-Bench Hugging Face leaderboard proof helpers."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CP_BENCH_TARGET_ID = "cp-bench-constraint-modeling"
CPMPY_FRAMEWORK = "CPMpy"
MINIZINC_FRAMEWORK = "MiniZinc"
ORTOOLS_FRAMEWORK = "OR-Tools"
SUPPORTED_FRAMEWORKS = [CPMPY_FRAMEWORK, MINIZINC_FRAMEWORK, ORTOOLS_FRAMEWORK]
CP_BENCH_EVALUATOR_DEPENDENCIES = [
    "datasets",
    "click",
    "cpmpy",
    "minizinc",
    "ortools",
    "tqdm",
]
CP_BENCH_PROPOSAL_CHANGE_TYPES = ["prompt_profile", "code_patch", "framework_switch"]
CP_BENCH_PROPOSAL_REQUIRED_KEYS = [
    "proposal_id",
    "hypothesis",
    "change_type",
    "expected_metric",
    "risk",
    "rollback_plan",
]
CP_BENCH_CLIENT_CANDIDATE_STRATEGIES = ["handcrafted-small-cpmpy-v1"]
CP_BENCH_CLIENT_CANDIDATE_ALLOWED_SOURCE_FIELDS = [
    "id",
    "category",
    "metadata",
    "description",
    "input_data",
    "decision_variables",
]
CRITICAL_CHECK_IDS = [
    "dataset_api",
    "leaderboard_readme",
    "leaderboard_ui",
    "local_evaluator",
]
CP_BENCH_URLS = {
    "dataset": "https://huggingface.co/datasets/kostis-init/CP-Bench",
    "dataset_api": "https://huggingface.co/api/datasets/kostis-init/CP-Bench",
    "leaderboard": "https://huggingface.co/spaces/kostis-init/CP-Bench-Leaderboard",
    "leaderboard_readme": (
        "https://huggingface.co/spaces/kostis-init/CP-Bench-Leaderboard/raw/main/README.md"
    ),
    "leaderboard_ui": (
        "https://huggingface.co/spaces/kostis-init/CP-Bench-Leaderboard/raw/main/src/ui.py"
    ),
    "local_evaluator": (
        "https://huggingface.co/spaces/kostis-init/CP-Bench-Leaderboard/raw/main/src/user_eval.py"
    ),
}


Fetcher = Callable[[str, int], dict[str, Any]]
PackageChecker = Callable[[str], bool]
DependencyProbe = Callable[[], dict[str, Any]]
Runner = Callable[..., Any]


def build_cp_bench_target_contract() -> dict[str, Any]:
    """Return the conservative CP-Bench target contract."""
    return {
        "target_id": CP_BENCH_TARGET_ID,
        "name": "CP-Bench Leaderboard",
        "hf_kind": "competition_space",
        "task_family": "constraint_model_generation",
        "urls": dict(CP_BENCH_URLS),
        "supported_frameworks": list(SUPPORTED_FRAMEWORKS),
        "dataset_versions": ["original", "verified"],
        "default_dataset_version": "verified",
        "submission_format": {
            "file_extension": ".jsonl",
            "required_keys": ["id", "model"],
            "id_field": "id",
            "model_field": "model",
            "model_value": "runnable constraint model code string",
        },
        "metrics": [
            "Models Submitted (%)",
            "Accuracy (%)",
            "Runtime Errors (%)",
        ],
        "local_eval_command_template": (
            "python user_eval.py --submission_file <submission.jsonl> "
            "--modelling_framework <CPMpy|MiniZinc|OR-Tools> --dataset_version verified"
        ),
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "official_scores_claimed": False,
        "claim_boundary": (
            "CP-Bench P0 target contract only; no Hugging Face submission, "
            "leaderboard score, ranking, or official external result is claimed."
        ),
    }


def write_cp_bench_live_verification(
    output_dir: Path,
    *,
    timeout_seconds: int = 30,
    include_raw: bool = False,
    fetcher: Fetcher | None = None,
) -> dict[str, Any]:
    """Write CP-Bench P0 live verification artifacts without submitting results."""
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    output = output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    fetch = fetcher or fetch_cp_bench_url
    target = build_cp_bench_target_contract()
    checks = []
    raw_dir = output / "raw"
    if include_raw:
        raw_dir.mkdir(parents=True, exist_ok=True)

    for check_id in CRITICAL_CHECK_IDS:
        url = target["urls"][check_id]
        check = dict(fetch(url, timeout_seconds))
        check["check_id"] = check_id
        check["critical"] = True
        if include_raw:
            raw_path = raw_dir / f"{len(checks) + 1:02d}-{_slug(check_id)}.txt"
            raw_text = str(check.get("raw_text") or check.get("text_excerpt") or "")
            raw_path.write_text(raw_text, encoding="utf-8")
            check["raw_path"] = str(raw_path)
        checks.append(_public_check(check))

    unreachable = [
        check["check_id"]
        for check in checks
        if check["critical"] and check.get("status") != "reachable"
    ]
    verification_status = (
        "blocked_unreachable_sources" if unreachable else "verified_with_limitations"
    )
    payload = {
        "schema_version": "2026-05-23.cp-bench-live-verification.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "written",
        "verification_status": verification_status,
        "target": target,
        "checks": checks,
        "unreachable_critical_checks": unreachable,
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "official_scores_claimed": False,
        "claim_boundary": target["claim_boundary"],
    }

    json_path = output / "cp-bench-live-verification.json"
    contract_path = output / "cp-bench-target-contract.md"
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    contract_path.write_text(render_cp_bench_target_contract(payload), encoding="utf-8")

    return {
        "status": "written",
        "verification_status": verification_status,
        "official_scores_claimed": False,
        "manual_submission_required": True,
        "json_path": str(json_path),
        "contract_path": str(contract_path),
        "include_raw": include_raw,
    }


def validate_cp_bench_submission(file_path: Path) -> dict[str, Any]:
    """Validate the CP-Bench JSONL submission format without executing code."""
    path = file_path.expanduser().resolve()
    if not path.exists():
        return _invalid_submission(path, f"File {path} does not exist", line_count=0)
    if path.suffix != ".jsonl":
        return _invalid_submission(path, "Invalid file format. Please provide a .jsonl file")

    line_count = 0
    try:
        with path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, 1):
                stripped = line.strip()
                if not stripped:
                    continue
                line_count += 1
                try:
                    item = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    return _invalid_submission(
                        path,
                        f"Line {line_number}: Invalid JSON format: {exc.msg}",
                        line_count=line_count,
                    )
                if not isinstance(item, dict):
                    return _invalid_submission(
                        path,
                        f"Line {line_number}: JSON value must be an object",
                        line_count=line_count,
                    )
                missing = [
                    key
                    for key in build_cp_bench_target_contract()["submission_format"][
                        "required_keys"
                    ]
                    if key not in item
                ]
                if missing:
                    return _invalid_submission(
                        path,
                        f"Line {line_number}: Missing required keys {', '.join(missing)}",
                        line_count=line_count,
                    )
                if not isinstance(item["id"], str) or not item["id"].strip():
                    return _invalid_submission(
                        path,
                        f"Line {line_number}: id must be a non-empty string",
                        line_count=line_count,
                    )
                if not isinstance(item["model"], str) or not item["model"].strip():
                    return _invalid_submission(
                        path,
                        f"Line {line_number}: model must be a non-empty string",
                        line_count=line_count,
                    )
    except OSError as exc:
        return _invalid_submission(path, f"Error reading file: {exc}", line_count=line_count)

    if line_count == 0:
        return _invalid_submission(path, "Empty file. Please provide a valid JSONL file")
    return {
        "status": "valid",
        "path": str(path),
        "line_count": line_count,
        "official_scores_claimed": False,
    }


def parse_cp_bench_summary(text: str) -> dict[str, Any]:
    """Parse CP-Bench public user_eval.py summary fields."""
    return {
        "submitted_models": _extract_int(
            text,
            r"Total Submitted Models that also exist in the dataset:\s*(\d+)",
        ),
        "runtime_success": _extract_string(
            text,
            r"Models That Ran Successfully \(out of submitted models\):\s*([0-9]+/[0-9]+)",
        ),
        "coverage_percent": _extract_float(
            text,
            r"Submission coverage perc:\s*([0-9.]+)%",
        ),
        "error_percent": _extract_float(text, r"Error perc:\s*([0-9.]+)%"),
        "consistency_percent": _extract_float(
            text,
            r"Consistency perc:\s*([0-9.]+)%",
        ),
        "final_solution_accuracy_percent": _extract_float(
            text,
            r"Final Solution Accuracy perc:\s*([0-9.]+)%",
        ),
        "official_scores_claimed": False,
    }


def parse_cp_bench_model_outcomes(text: str) -> list[dict[str, Any]]:
    """Parse per-problem outcomes from CP-Bench public user_eval.py summary text."""
    outcomes: list[dict[str, Any]] = []
    blocks = re.split(r"\n--- Model:\s*", "\n" + text)
    for block in blocks[1:]:
        header, _, body = block.partition("---")
        problem_id = header.strip()
        if not problem_id:
            continue
        found_ground_truth = "Found ground-truth model" in body
        executed_successfully = "SUCCESS: Model executed successfully." in body
        solution_extracted = "SUCCESS: Got solution:" in body
        consistency_passed = "CONSISTENCY: PASSED" in body
        objective_passed = "OBJECTIVE CHECK: PASSED" in body
        outcomes.append({
            "problem_id": problem_id,
            "found_ground_truth": found_ground_truth,
            "executed_successfully": executed_successfully,
            "solution_extracted": solution_extracted,
            "consistency_passed": consistency_passed,
            "objective_passed": objective_passed,
            "final_passed": consistency_passed and objective_passed,
            "failure_type": _classify_cp_bench_failure(
                body,
                found_ground_truth=found_ground_truth,
                executed_successfully=executed_successfully,
                solution_extracted=solution_extracted,
                consistency_passed=consistency_passed,
                objective_passed=objective_passed,
            ),
        })
    return outcomes


def summarize_cp_bench_model_outcomes(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize per-problem CP-Bench outcome classifications."""
    by_failure_type: dict[str, int] = {}
    failed_problem_ids = []
    passed = 0
    for outcome in _normalize_cp_bench_model_outcomes(outcomes):
        failure_type = str(outcome.get("failure_type") or "unknown_failed")
        by_failure_type[failure_type] = by_failure_type.get(failure_type, 0) + 1
        if outcome.get("final_passed") is True and failure_type == "none":
            passed += 1
        else:
            failed_problem_ids.append(outcome.get("problem_id"))
    return {
        "total": len(outcomes),
        "passed": passed,
        "failed": len(outcomes) - passed,
        "failed_problem_ids": failed_problem_ids,
        "by_failure_type": by_failure_type,
    }


def write_cp_bench_proposal_context(
    current_report_path: Path,
    output_dir: Path,
    *,
    max_proposals: int = 3,
) -> dict[str, Any]:
    """Write a CP-Bench proposal prompt context for a client planner."""
    if max_proposals <= 0:
        raise ValueError("max_proposals must be positive")

    output = output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = _read_json_file(current_report_path)
    outcomes = report.get("model_outcomes") if isinstance(report.get("model_outcomes"), list) else []
    outcomes = _normalize_cp_bench_model_outcomes(outcomes)
    failure_summary = summarize_cp_bench_model_outcomes(outcomes)
    failed_outcomes = [
        outcome
        for outcome in outcomes
        if outcome.get("final_passed") is not True or outcome.get("failure_type") != "none"
    ]
    status = "ready_for_client_proposal" if failed_outcomes else "ready_for_scale_up_proposal"
    context = {
        "schema_version": "2026-05-30.cp-bench-proposal-context.v1",
        "status": status,
        "target_id": CP_BENCH_TARGET_ID,
        "source_report": current_report_path.expanduser().resolve().name,
        "current_status": report.get("status"),
        "current_decision": report.get("decision"),
        "current_metric": (report.get("after_summary") or {}).get(
            "final_solution_accuracy_percent"
        ),
        "comparison_metric": "final_solution_accuracy_percent",
        "max_proposals": max_proposals,
        "allowed_change_types": list(CP_BENCH_PROPOSAL_CHANGE_TYPES),
        "required_proposal_keys": list(CP_BENCH_PROPOSAL_REQUIRED_KEYS),
        "failure_summary": failure_summary,
        "failed_outcome_count": len(failed_outcomes),
        "failed_outcomes": failed_outcomes,
        "next_action_policy": {
            "if_failures_exist": "Generate bounded repairs for failed outcomes first.",
            "if_no_failures_exist": "Propose scale-up to new verified rows with rollback.",
            "must_run": "run_cp_bench_candidate_round",
            "must_not_do": [
                "upload to Hugging Face",
                "claim leaderboard score",
                "use hidden test data",
            ],
        },
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "official_scores_claimed": False,
        "claim_boundary": (
            "CP-Bench proposal context only; it helps a client planner generate "
            "bounded local proposals and never uploads to Hugging Face or claims "
            "leaderboard scores."
        ),
    }

    context_path = output / "cp-bench-proposal-context.json"
    prompt_path = output / "proposal-prompt.md"
    template_path = output / "proposal-template.json"
    manifest_path = output / "artifact-manifest.json"
    _write_json(context_path, context)
    prompt_path.write_text(render_cp_bench_proposal_prompt(context), encoding="utf-8")
    _write_json(template_path, {
        "proposal_id": "cp-bench-next-round",
        "hypothesis": "",
        "change_type": "code_patch",
        "expected_metric": "final_solution_accuracy_percent",
        "risk": "",
        "rollback_plan": "",
    })
    manifest = {
        "schema_version": "2026-05-23.cp-bench-artifact-manifest.v1",
        "status": status,
        "target_id": CP_BENCH_TARGET_ID,
        "official_scores_claimed": False,
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "artifacts": _existing_artifact_entries(
            [
                ("proposal_context", context_path),
                ("proposal_prompt", prompt_path),
                ("proposal_template", template_path),
            ],
            output,
        ),
    }
    _write_json(manifest_path, manifest)
    return {
        "status": status,
        "official_scores_claimed": False,
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "context_path": str(context_path),
        "prompt_path": str(prompt_path),
        "template_path": str(template_path),
        "artifact_manifest_path": str(manifest_path),
    }


def write_cp_bench_client_candidate_submission(
    output_dir: Path,
    *,
    limit: int = 10,
    dataset_version: str = "verified",
    strategy: str = "handcrafted-small-cpmpy-v1",
    dataset_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Write a non-reference-replay CP-Bench candidate submission bundle."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    if dataset_version not in {"original", "verified"}:
        raise ValueError("dataset_version must be original or verified")
    if strategy not in CP_BENCH_CLIENT_CANDIDATE_STRATEGIES:
        raise ValueError(
            "strategy must be one of "
            + ", ".join(CP_BENCH_CLIENT_CANDIDATE_STRATEGIES)
        )

    output = output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    rows = (
        _sanitize_cp_bench_candidate_source_rows(dataset_rows[:limit])
        if dataset_rows is not None
        else _load_cp_bench_candidate_source_rows(limit, dataset_version=dataset_version)
    )
    if len(rows) < limit:
        raise ValueError(f"CP-Bench dataset returned {len(rows)} rows for requested limit {limit}")

    submission_rows = []
    generated_problem_ids = []
    fallback_problem_ids = []
    for row in rows[:limit]:
        problem_id = str(row.get("id") or "")
        model_code = _render_cp_bench_client_candidate_model(problem_id, strategy)
        generation_type = "client_generated"
        if model_code is None:
            model_code = _render_negative_control_solution_code()
            generation_type = "negative_control_fallback"
            fallback_problem_ids.append(problem_id)
        else:
            generated_problem_ids.append(problem_id)
        submission_rows.append({
            "id": problem_id,
            "model": model_code,
            "generation_type": generation_type,
            "strategy": strategy,
        })

    submission_path = output / "candidate-submission.jsonl"
    source_audit_path = output / "source-audit.json"
    readme_path = output / "README.md"
    manifest_path = output / "artifact-manifest.json"
    submission_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in submission_rows),
        encoding="utf-8",
    )
    generated_count = len(generated_problem_ids)
    fallback_count = len(fallback_problem_ids)
    status = (
        "generated"
        if fallback_count == 0
        else "partial_generated"
        if generated_count > 0
        else "fallback_only"
    )
    source_audit = {
        "schema_version": "2026-05-30.cp-bench-client-candidate-source-audit.v1",
        "status": status,
        "target_id": CP_BENCH_TARGET_ID,
        "strategy": strategy,
        "dataset_version": dataset_version,
        "requested_limit": limit,
        "row_count": len(submission_rows),
        "generated_count": generated_count,
        "fallback_count": fallback_count,
        "generated_problem_ids": generated_problem_ids,
        "fallback_problem_ids": fallback_problem_ids,
        "source_policy": "no_reference_model_field",
        "allowed_source_fields": list(CP_BENCH_CLIENT_CANDIDATE_ALLOWED_SOURCE_FIELDS),
        "reference_model_field_accessed": False,
        "reference_model_replay": False,
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "official_scores_claimed": False,
        "claim_boundary": (
            "CP-Bench client candidate bundle only; generated rows come from "
            "handcrafted local solver templates or explicit negative-control "
            "fallbacks, never from the public reference model field."
        ),
    }
    _write_json(source_audit_path, source_audit)
    readme_path.write_text(
        render_cp_bench_client_candidate_readme(source_audit),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "2026-05-23.cp-bench-artifact-manifest.v1",
        "status": status,
        "target_id": CP_BENCH_TARGET_ID,
        "official_scores_claimed": False,
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "artifacts": _existing_artifact_entries(
            [
                ("candidate_submission", submission_path),
                ("source_audit", source_audit_path),
                ("readme", readme_path),
            ],
            output,
        ),
    }
    _write_json(manifest_path, manifest)
    return {
        "status": status,
        "submission_path": str(submission_path),
        "source_audit_path": str(source_audit_path),
        "artifact_manifest_path": str(manifest_path),
        "generated_count": generated_count,
        "fallback_count": fallback_count,
        "reference_model_field_accessed": False,
        "official_scores_claimed": False,
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
    }


def _normalize_cp_bench_model_outcomes(outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for outcome in outcomes:
        item = dict(outcome)
        if not item.get("failure_type"):
            required_flags = {
                "found_ground_truth",
                "executed_successfully",
                "solution_extracted",
                "consistency_passed",
                "objective_passed",
            }
            if required_flags.issubset(item):
                item["failure_type"] = _classify_cp_bench_failure(
                    "",
                    found_ground_truth=bool(item.get("found_ground_truth")),
                    executed_successfully=bool(item.get("executed_successfully")),
                    solution_extracted=bool(item.get("solution_extracted")),
                    consistency_passed=bool(item.get("consistency_passed")),
                    objective_passed=bool(item.get("objective_passed")),
                )
            else:
                item["failure_type"] = (
                    "none" if item.get("final_passed") is True else "unknown_failed"
                )
        normalized.append(item)
    return normalized


def probe_cp_bench_local_evaluator(
    *,
    package_checker: PackageChecker | None = None,
) -> dict[str, Any]:
    """Probe local packages required by the public CP-Bench evaluator."""
    check_package = package_checker or _module_available
    available = []
    missing = []
    for dependency in CP_BENCH_EVALUATOR_DEPENDENCIES:
        if check_package(dependency):
            available.append(dependency)
        else:
            missing.append(dependency)

    return {
        "schema_version": "2026-05-23.cp-bench-evaluator-probe.v1",
        "status": "ready" if not missing else "blocked_missing_dependencies",
        "required_dependencies": list(CP_BENCH_EVALUATOR_DEPENDENCIES),
        "available_dependencies": available,
        "missing_dependencies": missing,
        "install_command": "pip install 'ml-research-loop[hf-cp-bench]'",
        "minizinc_solver_note": (
            "MiniZinc framework runs may require a separately installed MiniZinc "
            "binary and solver even when the Python package is importable."
        ),
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "official_scores_claimed": False,
    }


def run_cp_bench_local_eval(
    submission_path: Path,
    output_dir: Path,
    *,
    framework: str = CPMPY_FRAMEWORK,
    dataset_version: str = "verified",
    timeout_seconds: int = 60,
    evaluator_path: Path | None = None,
    dependency_probe: DependencyProbe | None = None,
    runner: Runner | None = None,
) -> dict[str, Any]:
    """Run the public CP-Bench evaluator and write a guarded artifact bundle."""
    if framework not in SUPPORTED_FRAMEWORKS:
        raise ValueError(f"unsupported CP-Bench framework: {framework}")
    if dataset_version not in {"original", "verified"}:
        raise ValueError("dataset_version must be original or verified")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    output = output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    local_submission = output / "submission.jsonl"
    source_submission = submission_path.expanduser().resolve()
    if source_submission != local_submission:
        shutil.copyfile(source_submission, local_submission)
    validation = _relative_submission_validation(validate_cp_bench_submission(local_submission))

    probe = dependency_probe() if dependency_probe else probe_cp_bench_local_evaluator()
    if validation["status"] != "valid":
        return _write_cp_bench_local_eval_artifacts(
            output,
            status="invalid_submission",
            framework=framework,
            dataset_version=dataset_version,
            submission_validation=validation,
            dependency_probe=probe,
            timeout_seconds=timeout_seconds,
            reason=validation.get("error_message"),
        )
    if probe.get("status") != "ready":
        return _write_cp_bench_local_eval_artifacts(
            output,
            status="blocked_missing_dependencies",
            framework=framework,
            dataset_version=dataset_version,
            submission_validation=validation,
            dependency_probe=probe,
            timeout_seconds=timeout_seconds,
            reason="Local CP-Bench evaluator dependencies are missing.",
        )

    try:
        local_evaluator = _materialize_cp_bench_evaluator(
            output,
            timeout_seconds=timeout_seconds,
            evaluator_path=evaluator_path,
        )
    except (OSError, urllib.error.URLError) as exc:
        return _write_cp_bench_local_eval_artifacts(
            output,
            status="blocked_evaluator_unavailable",
            framework=framework,
            dataset_version=dataset_version,
            submission_validation=validation,
            dependency_probe=probe,
            timeout_seconds=timeout_seconds,
            reason=str(exc),
        )

    command = [
        sys.executable,
        str(local_evaluator),
        "--submission_file",
        str(local_submission),
        "--modelling_framework",
        framework,
        "--dataset_version",
        dataset_version,
    ]
    run = runner or subprocess.run
    try:
        completed = run(
            command,
            cwd=str(output),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            encoding="utf-8",
        )
    except subprocess.TimeoutExpired as exc:
        return _write_cp_bench_local_eval_artifacts(
            output,
            status="failed_timeout",
            framework=framework,
            dataset_version=dataset_version,
            submission_validation=validation,
            dependency_probe=probe,
            timeout_seconds=timeout_seconds,
            command=command,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            reason=f"CP-Bench evaluator exceeded {timeout_seconds} seconds.",
        )

    stdout = getattr(completed, "stdout", "") or ""
    stderr = getattr(completed, "stderr", "") or ""
    returncode = int(getattr(completed, "returncode", 1))
    summary_path = output / "summary.txt"
    if not summary_path.exists():
        return _write_cp_bench_local_eval_artifacts(
            output,
            status="failed_missing_summary",
            framework=framework,
            dataset_version=dataset_version,
            submission_validation=validation,
            dependency_probe=probe,
            timeout_seconds=timeout_seconds,
            command=command,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            reason="CP-Bench evaluator did not write summary.txt.",
        )
    if returncode != 0:
        return _write_cp_bench_local_eval_artifacts(
            output,
            status="failed_nonzero_exit",
            framework=framework,
            dataset_version=dataset_version,
            submission_validation=validation,
            dependency_probe=probe,
            timeout_seconds=timeout_seconds,
            command=command,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            reason=f"CP-Bench evaluator exited with code {returncode}.",
        )

    return _write_cp_bench_local_eval_artifacts(
        output,
        status="written",
        framework=framework,
        dataset_version=dataset_version,
        submission_validation=validation,
        dependency_probe=probe,
        timeout_seconds=timeout_seconds,
        command=command,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def validate_cp_bench_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    """Validate a guarded CP-Bench proposal contract."""
    if not isinstance(proposal, dict):
        return _invalid_cp_bench_proposal("proposal must be a JSON object")
    missing = [key for key in CP_BENCH_PROPOSAL_REQUIRED_KEYS if key not in proposal]
    if missing:
        return _invalid_cp_bench_proposal(f"Missing required keys {', '.join(missing)}")
    for key in CP_BENCH_PROPOSAL_REQUIRED_KEYS:
        if not isinstance(proposal[key], str) or not proposal[key].strip():
            return _invalid_cp_bench_proposal(f"{key} must be a non-empty string")
    if proposal["change_type"] not in CP_BENCH_PROPOSAL_CHANGE_TYPES:
        return _invalid_cp_bench_proposal(
            "change_type must be one of "
            + ", ".join(CP_BENCH_PROPOSAL_CHANGE_TYPES),
        )
    return {
        "status": "valid",
        "proposal_id": proposal["proposal_id"],
        "change_type": proposal["change_type"],
        "official_scores_claimed": False,
    }


def run_cp_bench_proposal_round(
    baseline_report_path: Path,
    proposal_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Write guarded CP-Bench proposal-round and rollback evidence artifacts."""
    output = output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    baseline = _read_json_file(baseline_report_path)
    proposal = _read_json_file(proposal_path)
    local_baseline_path = output / "baseline-report.json"
    local_proposal_path = output / "proposal.json"
    _write_json(local_baseline_path, baseline)
    _write_json(local_proposal_path, proposal)

    validation = validate_cp_bench_proposal(proposal)
    if validation["status"] != "valid":
        status = "rejected_by_guard"
        decision = "rollback_recorded"
        reason = "proposal_rejected_by_guard"
        after_summary = None
        rollback_required = True
    elif baseline.get("status") != "written":
        status = "blocked_pending_local_eval"
        decision = "defer_execution"
        reason = "baseline_local_eval_not_ready"
        after_summary = None
        rollback_required = True
    else:
        status = "ready_for_guarded_execution"
        decision = "requires_client_execution"
        reason = "proposal_valid_but_not_executed_by_this_writer"
        after_summary = None
        rollback_required = False

    before_summary = baseline.get("summary")
    rollback = {
        "schema_version": "2026-05-23.cp-bench-rollback-evidence.v1",
        "status": "written",
        "proposal_id": proposal.get("proposal_id"),
        "rollback_required": rollback_required,
        "reason": reason,
        "rollback_plan": proposal.get("rollback_plan"),
        "external_submission_status": "not_submitted",
        "official_scores_claimed": False,
    }
    report = {
        "schema_version": "2026-05-23.cp-bench-proposal-round.v1",
        "status": status,
        "target_id": CP_BENCH_TARGET_ID,
        "proposal": proposal,
        "proposal_validation": validation,
        "baseline_status": baseline.get("status"),
        "before_summary": before_summary,
        "after_summary": after_summary,
        "decision": decision,
        "reason": reason,
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "official_scores_claimed": False,
        "claim_boundary": (
            "CP-Bench proposal-round artifact only; it records guard decisions "
            "and rollback evidence without uploading to Hugging Face or claiming "
            "leaderboard scores."
        ),
    }

    report_path = output / "cp-bench-proposal-round-report.json"
    rollback_path = output / "rollback-evidence.json"
    manifest_path = output / "artifact-manifest.json"
    readme_path = output / "README.md"
    _write_json(report_path, report)
    _write_json(rollback_path, rollback)
    readme_path.write_text(render_cp_bench_proposal_round_readme(report), encoding="utf-8")
    manifest = {
        "schema_version": "2026-05-23.cp-bench-artifact-manifest.v1",
        "status": status,
        "target_id": CP_BENCH_TARGET_ID,
        "official_scores_claimed": False,
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "artifacts": _existing_artifact_entries(
            [
                ("baseline_report", local_baseline_path),
                ("proposal", local_proposal_path),
                ("report", report_path),
                ("rollback_evidence", rollback_path),
                ("readme", readme_path),
            ],
            output,
        ),
    }
    _write_json(manifest_path, manifest)
    return {
        "status": status,
        "decision": decision,
        "official_scores_claimed": False,
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "report_path": str(report_path),
        "rollback_evidence_path": str(rollback_path),
        "artifact_manifest_path": str(manifest_path),
    }


def run_cp_bench_candidate_round(
    baseline_report_path: Path,
    submission_path: Path,
    output_dir: Path,
    *,
    proposal_path: Path | None = None,
    framework: str = CPMPY_FRAMEWORK,
    dataset_version: str = "verified",
    timeout_seconds: int = 60,
    evaluator_path: Path | None = None,
    dependency_probe: DependencyProbe | None = None,
    runner: Runner | None = None,
) -> dict[str, Any]:
    """Run one guarded CP-Bench candidate submission against a local baseline."""
    output = output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    baseline = _read_json_file(baseline_report_path)
    local_baseline_path = output / "baseline-report.json"
    local_submission_path = output / "candidate-submission.jsonl"
    _write_json(local_baseline_path, baseline)
    source_submission = submission_path.expanduser().resolve()
    if source_submission != local_submission_path:
        shutil.copyfile(source_submission, local_submission_path)

    proposal = None
    proposal_validation = None
    local_proposal_path = None
    if proposal_path is not None:
        proposal = _read_json_file(proposal_path)
        proposal_validation = validate_cp_bench_proposal(proposal)
        local_proposal_path = output / "proposal.json"
        _write_json(local_proposal_path, proposal)

    before_summary = baseline.get("summary") if isinstance(baseline.get("summary"), dict) else {}
    after_summary = None
    model_outcomes: list[dict[str, Any]] = []
    failure_summary = summarize_cp_bench_model_outcomes(model_outcomes)
    candidate_eval_status = None
    candidate_eval_report_path = output / "candidate-local-eval" / "cp-bench-local-eval-report.json"
    candidate_eval_manifest_path = output / "candidate-local-eval" / "artifact-manifest.json"

    if proposal_validation is not None and proposal_validation["status"] != "valid":
        status = "rejected_by_guard"
        decision = "rollback_candidate"
        reason = "proposal_rejected_by_guard"
        metric_delta = None
    elif baseline.get("status") != "written":
        status = "blocked_pending_baseline"
        decision = "defer_execution"
        reason = "baseline_local_eval_not_ready"
        metric_delta = None
    else:
        candidate_result = run_cp_bench_local_eval(
            local_submission_path,
            output / "candidate-local-eval",
            framework=framework,
            dataset_version=dataset_version,
            timeout_seconds=timeout_seconds,
            evaluator_path=evaluator_path,
            dependency_probe=dependency_probe,
            runner=runner,
        )
        candidate_eval_status = candidate_result.get("status")
        if candidate_eval_report_path.exists():
            candidate_eval_report = _read_json_file(candidate_eval_report_path)
            after_summary = candidate_eval_report.get("summary")
            summary_path = output / "candidate-local-eval" / "summary.txt"
            if summary_path.exists():
                model_outcomes = parse_cp_bench_model_outcomes(
                    summary_path.read_text(encoding="utf-8")
                )
                failure_summary = summarize_cp_bench_model_outcomes(model_outcomes)
        else:
            after_summary = candidate_result.get("summary")

        if candidate_eval_status != "written":
            status = "candidate_eval_failed"
            decision = "rollback_candidate"
            reason = "candidate_local_eval_not_written"
            metric_delta = None
        else:
            metric_delta = _metric_delta(
                before_summary,
                after_summary,
                "final_solution_accuracy_percent",
            )
            if metric_delta is None:
                status = "candidate_eval_inconclusive"
                decision = "manual_review_required"
                reason = "metric_missing"
            elif metric_delta > 0:
                status = "improved"
                decision = "candidate_improved"
                reason = "candidate_improved_local_metric"
            elif metric_delta == 0:
                status = "no_gain"
                decision = "keep_baseline"
                reason = "candidate_no_local_metric_gain"
            else:
                status = "regressed"
                decision = "rollback_candidate"
                reason = "candidate_regressed_local_metric"

    report = {
        "schema_version": "2026-05-30.cp-bench-candidate-round.v1",
        "status": status,
        "target_id": CP_BENCH_TARGET_ID,
        "framework": framework,
        "dataset_version": dataset_version,
        "proposal": proposal,
        "proposal_validation": proposal_validation,
        "baseline_status": baseline.get("status"),
        "candidate_eval_status": candidate_eval_status,
        "before_summary": before_summary,
        "after_summary": after_summary,
        "model_outcomes": model_outcomes,
        "failure_summary": failure_summary,
        "comparison_metric": "final_solution_accuracy_percent",
        "metric_delta": metric_delta,
        "decision": decision,
        "reason": reason,
        "candidate_submission_path": local_submission_path.name,
        "candidate_eval_report_path": (
            candidate_eval_report_path.relative_to(output).as_posix()
            if candidate_eval_report_path.exists()
            else None
        ),
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "official_scores_claimed": False,
        "claim_boundary": (
            "CP-Bench candidate-round artifact only; it records local evaluator "
            "feedback for a client-generated candidate and does not upload to "
            "Hugging Face or claim leaderboard scores."
        ),
    }
    report["rollback_evidence"] = _build_cp_bench_candidate_rollback_evidence(report)

    report_path = output / "cp-bench-candidate-round-report.json"
    manifest_path = output / "artifact-manifest.json"
    readme_path = output / "README.md"
    rollback_path = output / "rollback-evidence.json"
    _write_json(report_path, report)
    _write_json(rollback_path, report["rollback_evidence"])
    readme_path.write_text(render_cp_bench_candidate_round_readme(report), encoding="utf-8")

    artifacts = [
        ("baseline_report", local_baseline_path),
        ("candidate_submission", local_submission_path),
        ("report", report_path),
        ("rollback_evidence", rollback_path),
        ("readme", readme_path),
    ]
    if local_proposal_path is not None:
        artifacts.append(("proposal", local_proposal_path))
    if candidate_eval_report_path.exists():
        artifacts.append(("candidate_eval_report", candidate_eval_report_path))
    if candidate_eval_manifest_path.exists():
        artifacts.append(("candidate_eval_manifest", candidate_eval_manifest_path))
    manifest = {
        "schema_version": "2026-05-23.cp-bench-artifact-manifest.v1",
        "status": status,
        "target_id": CP_BENCH_TARGET_ID,
        "official_scores_claimed": False,
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "artifacts": _existing_artifact_entries(artifacts, output),
    }
    _write_json(manifest_path, manifest)
    return {
        "status": status,
        "decision": decision,
        "metric_delta": metric_delta,
        "official_scores_claimed": False,
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "report_path": str(report_path),
        "rollback_evidence_path": str(rollback_path),
        "artifact_manifest_path": str(manifest_path),
        "candidate_eval_report_path": (
            str(candidate_eval_report_path) if candidate_eval_report_path.exists() else None
        ),
    }


def write_cp_bench_submission_gate(
    submission_path: Path,
    output_dir: Path,
    *,
    source_report_path: Path | None = None,
) -> dict[str, Any]:
    """Write a manual CP-Bench submission gate bundle without uploading."""
    output = output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    local_submission = output / "submission.jsonl"
    source_submission = submission_path.expanduser().resolve()
    if source_submission != local_submission:
        shutil.copyfile(source_submission, local_submission)
    validation = _relative_submission_validation(validate_cp_bench_submission(local_submission))

    source_report_copy = None
    if source_report_path is not None:
        source_report_copy = output / "source-report.json"
        shutil.copyfile(source_report_path.expanduser().resolve(), source_report_copy)

    status = "written" if validation["status"] == "valid" else "invalid_submission"
    report_path = output / "submission-report.md"
    checklist_path = output / "manual-checklist.md"
    readme_path = output / "README.md"
    manifest_path = output / "artifact-manifest.json"
    sha256_path = output / "SHA256SUMS"
    report = {
        "status": status,
        "target_id": CP_BENCH_TARGET_ID,
        "submission_validation": validation,
        "source_report_path": source_report_copy.name if source_report_copy else None,
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "official_scores_claimed": False,
        "claim_boundary": (
            "CP-Bench submission gate bundle only; this package has not been "
            "uploaded to Hugging Face and does not claim leaderboard scores."
        ),
    }
    report_path.write_text(render_cp_bench_submission_report(report), encoding="utf-8")
    checklist_path.write_text(render_cp_bench_manual_checklist(report), encoding="utf-8")
    readme_path.write_text(render_cp_bench_submission_gate_readme(report), encoding="utf-8")
    artifacts = [
        ("submission", local_submission),
        ("submission_report", report_path),
        ("manual_checklist", checklist_path),
        ("readme", readme_path),
    ]
    if source_report_copy is not None:
        artifacts.append(("source_report", source_report_copy))
    manifest = {
        "schema_version": "2026-05-23.cp-bench-artifact-manifest.v1",
        "status": status,
        "target_id": CP_BENCH_TARGET_ID,
        "official_scores_claimed": False,
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "artifacts": _existing_artifact_entries(artifacts, output),
    }
    _write_json(manifest_path, manifest)
    _write_sha256sums(
        sha256_path,
        [path for _, path in artifacts] + [manifest_path],
        output,
    )
    return {
        "status": status,
        "official_scores_claimed": False,
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "submission_path": str(local_submission),
        "submission_report_path": str(report_path),
        "manual_checklist_path": str(checklist_path),
        "readme_path": str(readme_path),
        "artifact_manifest_path": str(manifest_path),
        "sha256sums_path": str(sha256_path),
    }


def write_cp_bench_local_baseline(
    output_dir: Path,
    *,
    limit: int = 1,
    framework: str = CPMPY_FRAMEWORK,
    dataset_version: str = "verified",
    dry_run: bool = True,
    timeout_seconds: int = 60,
    problem_ids: list[str] | None = None,
    evaluator_path: Path | None = None,
    dependency_probe: DependencyProbe | None = None,
    runner: Runner | None = None,
) -> dict[str, Any]:
    """Write a CP-Bench local baseline artifact bundle."""
    if limit < 1:
        raise ValueError("limit must be positive")
    if framework not in SUPPORTED_FRAMEWORKS:
        raise ValueError(f"unsupported CP-Bench framework: {framework}")
    if dataset_version not in {"original", "verified"}:
        raise ValueError("dataset_version must be original or verified")

    output = output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    target = build_cp_bench_target_contract()
    submission_path = output / "submission.jsonl"
    summary_path = output / "summary.txt"
    report_path = output / "cp-bench-local-baseline-report.json"
    runtime_profile_path = output / "runtime-profile.json"
    manifest_path = output / "artifact-manifest.json"
    readme_path = output / "README.md"

    probe = dependency_probe() if dependency_probe else None
    if dry_run or (probe is not None and probe.get("status") != "ready"):
        rows = _build_dry_run_submission_rows(limit)
    else:
        try:
            rows = _build_real_eval_submission_rows(
                limit,
                dataset_version=dataset_version,
                problem_ids=problem_ids,
            )
        except Exception as exc:
            submission_path.write_text("", encoding="utf-8")
            validation = _relative_submission_validation(validate_cp_bench_submission(submission_path))
            blocked_probe = probe or probe_cp_bench_local_evaluator()
            return _write_cp_bench_local_eval_artifacts(
                output,
                status="blocked_dataset_unavailable",
                framework=framework,
                dataset_version=dataset_version,
                submission_validation=validation,
                dependency_probe=blocked_probe,
                timeout_seconds=timeout_seconds,
                reason=f"Unable to load CP-Bench problem ids: {exc}",
            )
    submission_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )

    if not dry_run:
        result = run_cp_bench_local_eval(
            submission_path,
            output,
            framework=framework,
            dataset_version=dataset_version,
            timeout_seconds=timeout_seconds,
            evaluator_path=evaluator_path,
            dependency_probe=(lambda: probe) if probe is not None else dependency_probe,
            runner=runner,
        )
        result["dry_run"] = False
        result["row_count"] = len(rows)
        return result

    validation = validate_cp_bench_submission(submission_path)
    report_validation = dict(validation)
    report_validation["path"] = submission_path.name
    summary_text = _render_dry_run_summary(limit)
    summary_path.write_text(summary_text, encoding="utf-8")
    parsed_summary = parse_cp_bench_summary(summary_text)
    runtime_profile = {
        "status": "dry_run",
        "framework": framework,
        "dataset_version": dataset_version,
        "row_count": len(rows),
        "network_access": "not_used",
        "external_submission_status": "not_submitted",
        "official_scores_claimed": False,
    }
    report = {
        "schema_version": "2026-05-23.cp-bench-local-baseline.v1",
        "status": "written",
        "target": target,
        "framework": framework,
        "dataset_version": dataset_version,
        "dry_run": True,
        "row_count": len(rows),
        "submission_validation": report_validation,
        "summary": parsed_summary,
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "official_scores_claimed": False,
        "claim_boundary": (
            "CP-Bench dry-run local baseline artifact only; not a Hugging Face "
            "submission, leaderboard score, or official external result."
        ),
    }
    _write_json(runtime_profile_path, runtime_profile)
    _write_json(report_path, report)
    readme_path.write_text(render_cp_bench_local_baseline_readme(report), encoding="utf-8")

    manifest = {
        "schema_version": "2026-05-23.cp-bench-artifact-manifest.v1",
        "status": "written",
        "target_id": CP_BENCH_TARGET_ID,
        "official_scores_claimed": False,
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "artifacts": [
            _artifact_entry("submission", submission_path, output),
            _artifact_entry("summary", summary_path, output),
            _artifact_entry("report", report_path, output),
            _artifact_entry("runtime_profile", runtime_profile_path, output),
            _artifact_entry("readme", readme_path, output),
        ],
    }
    _write_json(manifest_path, manifest)

    return {
        "status": "written",
        "official_scores_claimed": False,
        "manual_submission_required": True,
        "dry_run": True,
        "framework": framework,
        "dataset_version": dataset_version,
        "row_count": len(rows),
        "submission_path": str(submission_path),
        "summary_path": str(summary_path),
        "report_path": str(report_path),
        "runtime_profile_path": str(runtime_profile_path),
        "artifact_manifest_path": str(manifest_path),
    }


def fetch_cp_bench_url(url: str, timeout_seconds: int) -> dict[str, Any]:
    """Fetch one public CP-Bench URL and return a bounded verification record."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ml-research-loop-cp-bench-verifier/0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read()
            text = body.decode("utf-8", errors="replace")
            return {
                "url": url,
                "status": "reachable",
                "http_status": int(getattr(response, "status", 200)),
                "content_type": response.headers.get("content-type", ""),
                "byte_count": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "text_excerpt": text[:1000],
                "raw_text": text,
            }
    except urllib.error.HTTPError as exc:
        return {
            "url": url,
            "status": "unreachable",
            "http_status": exc.code,
            "error": str(exc),
            "byte_count": 0,
        }
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        return {
            "url": url,
            "status": "unreachable",
            "http_status": None,
            "error": str(exc),
            "byte_count": 0,
        }


def render_cp_bench_target_contract(payload: dict[str, Any]) -> str:
    """Render CP-Bench P0 verification as Markdown."""
    target = payload["target"]
    lines = [
        "# CP-Bench P0 Target Contract",
        "",
        f"target_id: `{target['target_id']}`",
        "official_scores_claimed: `false`",
        f"verification_status: `{payload['verification_status']}`",
        "external_submission_status: `not_submitted`",
        "manual_submission_required: `true`",
        "",
        "## Claim Boundary",
        "",
        target["claim_boundary"],
        "",
        "## Submission Contract",
        "",
        f"- file_extension: `{target['submission_format']['file_extension']}`",
        "- required_keys: `id`, `model`",
        f"- supported_frameworks: {', '.join(target['supported_frameworks'])}",
        f"- default_dataset_version: `{target['default_dataset_version']}`",
        "",
        "## Public URLs",
        "",
    ]
    for name, url in target["urls"].items():
        lines.append(f"- {name}: {url}")
    lines.extend(["", "## Live Checks", ""])
    for check in payload["checks"]:
        lines.append(
            f"- `{check['check_id']}`: {check['status']} "
            f"(http={check.get('http_status')}, bytes={check.get('byte_count')})"
        )
    if payload["unreachable_critical_checks"]:
        lines.extend(["", "## Blockers", ""])
        for check_id in payload["unreachable_critical_checks"]:
            lines.append(f"- `{check_id}` unreachable")
    return "\n".join(lines).rstrip() + "\n"


def render_cp_bench_local_baseline_readme(report: dict[str, Any]) -> str:
    """Render CP-Bench dry-run local baseline README."""
    return "\n".join([
        "# CP-Bench P1 Local Baseline Dry Run",
        "",
        f"status: `{report['status']}`",
        "official_scores_claimed: `false`",
        "external_submission_status: `not_submitted`",
        "manual_submission_required: `true`",
        f"framework: `{report['framework']}`",
        f"dataset_version: `{report['dataset_version']}`",
        f"row_count: `{report['row_count']}`",
        "",
        "## Claim Boundary",
        "",
        report["claim_boundary"],
        "",
        "## Artifact Roles",
        "",
        "- `submission.jsonl`: dry-run submission-format fixture.",
        "- `summary.txt`: parser-compatible dry-run summary.",
        "- `cp-bench-local-baseline-report.json`: normalized dry-run report.",
        "- `runtime-profile.json`: local execution profile.",
        "- `artifact-manifest.json`: SHA-256 artifact index.",
        "",
    ])


def render_cp_bench_local_eval_readme(report: dict[str, Any]) -> str:
    """Render a CP-Bench local evaluator artifact README."""
    lines = [
        "# CP-Bench Local Evaluator Artifact",
        "",
        f"status: `{report['status']}`",
        "official_scores_claimed: `false`",
        "external_submission_status: `not_submitted`",
        "manual_submission_required: `true`",
        f"framework: `{report['framework']}`",
        f"dataset_version: `{report['dataset_version']}`",
        "",
        "## Claim Boundary",
        "",
        report["claim_boundary"],
        "",
    ]
    missing_dependencies = report.get("missing_dependencies") or []
    if missing_dependencies:
        lines.extend([
            "## Dependency Gate",
            "",
            "本次 smoke 已进入真实 evaluator dependency gate，但未运行 evaluator 评分。缺少依赖：",
            "",
        ])
        lines.extend(f"- `{dependency}`" for dependency in missing_dependencies)
        lines.extend([
            "",
            "因此该目录是 `blocked_missing_dependencies` proof，不是 CP-Bench 评分结果。",
            "",
        ])
    summary = report.get("summary") or {}
    if summary.get("submitted_models") is not None:
        lines.extend([
            "## Summary Metrics",
            "",
            f"- submitted_models: `{summary.get('submitted_models')}`",
            f"- runtime_success: `{summary.get('runtime_success')}`",
            f"- coverage_percent: `{summary.get('coverage_percent')}`",
            f"- final_solution_accuracy_percent: `{summary.get('final_solution_accuracy_percent')}`",
            "",
        ])
    lines.extend([
        "## Artifact Roles",
        "",
        "- `submission.jsonl`: evaluated local submission fixture.",
        "- `summary.txt`: public CP-Bench evaluator summary when available.",
        "- `cp-bench-local-eval-report.json`: normalized guarded report.",
        "- `runtime-profile.json`: command, dependency, timeout, and exit profile.",
        "- `stdout.txt` / `stderr.txt`: evaluator process streams when available.",
        "- `artifact-manifest.json`: SHA-256 artifact index.",
        "",
    ])
    return "\n".join(lines)


def render_cp_bench_proposal_round_readme(report: dict[str, Any]) -> str:
    """Render CP-Bench proposal-round README."""
    return "\n".join([
        "# CP-Bench Proposal Round",
        "",
        f"status: `{report['status']}`",
        f"decision: `{report['decision']}`",
        "official_scores_claimed: `false`",
        "external_submission_status: `not_submitted`",
        "manual_submission_required: `true`",
        "",
        "## Claim Boundary",
        "",
        report["claim_boundary"],
        "",
        "## Summary",
        "",
        f"- proposal_id: `{report['proposal'].get('proposal_id')}`",
        f"- change_type: `{report['proposal'].get('change_type')}`",
        f"- baseline_status: `{report['baseline_status']}`",
        f"- reason: `{report['reason']}`",
        "",
    ])


def render_cp_bench_candidate_round_readme(report: dict[str, Any]) -> str:
    """Render CP-Bench candidate-round README."""
    lines = [
        "# CP-Bench Candidate Round",
        "",
        f"status: `{report['status']}`",
        f"decision: `{report['decision']}`",
        "official_scores_claimed: `false`",
        "external_submission_status: `not_submitted`",
        "manual_submission_required: `true`",
        f"framework: `{report['framework']}`",
        f"dataset_version: `{report['dataset_version']}`",
        "",
        "## Claim Boundary",
        "",
        report["claim_boundary"],
        "",
        "## Metric Comparison",
        "",
        f"- metric: `{report['comparison_metric']}`",
        f"- before: `{(report.get('before_summary') or {}).get(report['comparison_metric'])}`",
        f"- after: `{(report.get('after_summary') or {}).get(report['comparison_metric'])}`",
        f"- delta: `{report.get('metric_delta')}`",
        "",
    ]
    failure_summary = report.get("failure_summary") or {}
    if failure_summary:
        lines.extend([
            "## Failure Summary",
            "",
            f"- total: `{failure_summary.get('total')}`",
            f"- passed: `{failure_summary.get('passed')}`",
            f"- failed: `{failure_summary.get('failed')}`",
            "",
        ])
    model_outcomes = report.get("model_outcomes") or []
    if model_outcomes:
        lines.extend([
            "## Model Outcomes",
            "",
        ])
        for outcome in model_outcomes:
            lines.append(
                f"- `{outcome['problem_id']}`: "
                f"final_passed: `{str(outcome['final_passed']).lower()}`, "
                f"executed: `{str(outcome['executed_successfully']).lower()}`, "
                f"consistency: `{str(outcome['consistency_passed']).lower()}`, "
                f"failure_type: `{outcome.get('failure_type', 'unknown_failed')}`"
            )
        lines.append("")
    rollback = report.get("rollback_evidence") or {}
    if rollback:
        lines.extend([
            "## Rollback Evidence",
            "",
            f"- rollback_required: `{str(rollback.get('rollback_required')).lower()}`",
            f"- partial_failures_require_followup: "
            f"`{str(rollback.get('partial_failures_require_followup')).lower()}`",
            "",
        ])
    lines.extend([
        "## Artifact Roles",
        "",
        "- `candidate-submission.jsonl`: client-generated candidate submission.",
        "- `candidate-local-eval/`: local evaluator proof bundle for the candidate.",
        "- `cp-bench-candidate-round-report.json`: normalized before/after report.",
        "- `rollback-evidence.json`: rollback and follow-up decision record.",
        "- `artifact-manifest.json`: SHA-256 artifact index.",
        "",
    ])
    return "\n".join(lines)


def render_cp_bench_proposal_prompt(context: dict[str, Any]) -> str:
    """Render a client-facing CP-Bench proposal prompt."""
    failed = context.get("failed_outcomes") or []
    lines = [
        "# CP-Bench Proposal Prompt",
        "",
        "你是客户端 planner。请基于本地 evaluator 的逐题 outcome 生成下一轮受控 proposal。",
        "",
        "## 硬性边界",
        "",
        "- 不要上传 Hugging Face。",
        "- 不要声明 leaderboard score、排名或官方成绩。",
        "- 只能生成本地 candidate submission 或 repair proposal。",
        "- 必须保留 rollback_plan。",
        "",
        "## 当前状态",
        "",
        f"- status: `{context.get('current_status')}`",
        f"- decision: `{context.get('current_decision')}`",
        f"- metric: `{context.get('comparison_metric')}`",
        f"- current_metric: `{context.get('current_metric')}`",
        f"- max_proposals: `{context.get('max_proposals')}`",
        "",
        "## 失败样本",
        "",
    ]
    if failed:
        for outcome in failed:
            lines.append(
                f"- `{outcome.get('problem_id')}`: "
                f"`{outcome.get('failure_type', 'unknown_failed')}`"
            )
    else:
        lines.append("- 当前报告没有失败样本。下一轮应优先提出扩大 verified rows 的方案。")
    lines.extend([
        "",
        "## 输出 JSON 要求",
        "",
        "返回一个 proposal JSON object，必须包含：",
        "",
    ])
    lines.extend(f"- `{key}`" for key in CP_BENCH_PROPOSAL_REQUIRED_KEYS)
    lines.extend([
        "",
        "`change_type` 只能是："
        f" `{', '.join(CP_BENCH_PROPOSAL_CHANGE_TYPES)}`。",
        "",
        "proposal 必须说明预期影响、风险、失败时如何回滚，以及下一步应调用 "
        "`run_cp_bench_candidate_round` 验证。",
        "",
    ])
    return "\n".join(lines)


def render_cp_bench_client_candidate_readme(source_audit: dict[str, Any]) -> str:
    """Render CP-Bench client candidate README."""
    return "\n".join([
        "# CP-Bench Client Candidate Bundle",
        "",
        f"status: `{source_audit['status']}`",
        "external_submission_status: `not_submitted`",
        "official_scores_claimed: `false`",
        "manual_submission_required: `true`",
        "",
        "## Claim Boundary",
        "",
        source_audit["claim_boundary"],
        "",
        "## Source Audit",
        "",
        f"- strategy: `{source_audit['strategy']}`",
        f"- source_policy: `{source_audit['source_policy']}`",
        "- reference_model_field_accessed: `false`",
        "- reference_model_replay: `false`",
        f"- row_count: `{source_audit['row_count']}`",
        f"- generated_count: `{source_audit['generated_count']}`",
        f"- fallback_count: `{source_audit['fallback_count']}`",
        "",
        "## Artifacts",
        "",
        "- `candidate-submission.jsonl`: local candidate submission for evaluator runs.",
        "- `source-audit.json`: non-reference-replay source and fallback record.",
        "- `artifact-manifest.json`: portable artifact index.",
        "",
    ])


def render_cp_bench_submission_report(report: dict[str, Any]) -> str:
    """Render a CP-Bench submission gate report."""
    validation = report["submission_validation"]
    return "\n".join([
        "# CP-Bench Submission Gate Report",
        "",
        f"status: `{report['status']}`",
        "external_submission_status: `not_submitted`",
        "official_scores_claimed: `false`",
        "manual_submission_required: `true`",
        "",
        "## Claim Boundary",
        "",
        report["claim_boundary"],
        "",
        "## Submission Validation",
        "",
        f"- status: `{validation['status']}`",
        f"- line_count: `{validation.get('line_count', 0)}`",
        f"- source_report: `{report.get('source_report_path') or 'none'}`",
        "",
    ])


def render_cp_bench_manual_checklist(report: dict[str, Any]) -> str:
    """Render the manual checklist required before any external upload."""
    return "\n".join([
        "# CP-Bench Manual Submission Checklist",
        "",
        "external_submission_status: `not_submitted`",
        "official_scores_claimed: `false`",
        "manual_submission_required: `true`",
        "",
        "- [ ] Confirm `submission.jsonl` validates locally.",
        "- [ ] Confirm local evaluator dependencies are installed and documented.",
        "- [ ] Confirm source local-eval report is attached or explain why absent.",
        "- [ ] Upload to Hugging Face manually only after human approval.",
        "- [ ] Record public leaderboard URL/result before changing `official_scores_claimed`.",
        "- [ ] Do not claim ranking or score until public result is visible.",
        "",
        f"Current gate status: `{report['status']}`",
        "",
    ])


def render_cp_bench_submission_gate_readme(report: dict[str, Any]) -> str:
    """Render CP-Bench submission gate README."""
    return "\n".join([
        "# CP-Bench Submission Gate",
        "",
        f"status: `{report['status']}`",
        "external_submission_status: `not_submitted`",
        "official_scores_claimed: `false`",
        "manual_submission_required: `true`",
        "",
        "## Claim Boundary",
        "",
        report["claim_boundary"],
        "",
        "## Artifact Roles",
        "",
        "- `submission.jsonl`: candidate file for manual review.",
        "- `source-report.json`: optional local proof source used for this gate.",
        "- `submission-report.md`: validation and claim-boundary report.",
        "- `manual-checklist.md`: human approval checklist before any upload.",
        "- `artifact-manifest.json`: SHA-256 artifact index.",
        "- `SHA256SUMS`: checksum file for manual review.",
        "",
    ])


def _write_cp_bench_local_eval_artifacts(
    output: Path,
    *,
    status: str,
    framework: str,
    dataset_version: str,
    submission_validation: dict[str, Any],
    dependency_probe: dict[str, Any],
    timeout_seconds: int,
    command: list[str] | None = None,
    returncode: int | None = None,
    stdout: str = "",
    stderr: str = "",
    reason: str | None = None,
) -> dict[str, Any]:
    report_path = output / "cp-bench-local-eval-report.json"
    runtime_profile_path = output / "runtime-profile.json"
    manifest_path = output / "artifact-manifest.json"
    readme_path = output / "README.md"
    summary_path = output / "summary.txt"
    stdout_path = output / "stdout.txt"
    stderr_path = output / "stderr.txt"
    sanitized_stdout = _scrub_local_paths(stdout, output)
    sanitized_stderr = _scrub_local_paths(stderr, output)

    if not summary_path.exists():
        summary_path.write_text(
            _render_local_eval_unavailable_summary(status, reason),
            encoding="utf-8",
        )
    else:
        summary_path.write_text(
            _scrub_local_paths(summary_path.read_text(encoding="utf-8"), output),
            encoding="utf-8",
        )
    if sanitized_stdout or not stdout_path.exists():
        stdout_path.write_text(sanitized_stdout, encoding="utf-8")
    if sanitized_stderr or not stderr_path.exists():
        stderr_path.write_text(sanitized_stderr, encoding="utf-8")

    summary = parse_cp_bench_summary(summary_path.read_text(encoding="utf-8"))
    runtime_profile = {
        "status": status,
        "framework": framework,
        "dataset_version": dataset_version,
        "timeout_seconds": timeout_seconds,
        "command": _sanitize_command(command, output) if command else None,
        "returncode": returncode,
        "dependency_probe": dependency_probe,
        "external_submission_status": "not_submitted",
        "official_scores_claimed": False,
    }
    report = {
        "schema_version": "2026-05-23.cp-bench-local-eval.v1",
        "status": status,
        "target": build_cp_bench_target_contract(),
        "framework": framework,
        "dataset_version": dataset_version,
        "submission_validation": submission_validation,
        "summary": summary,
        "dependency_probe": dependency_probe,
        "missing_dependencies": dependency_probe.get("missing_dependencies", []),
        "runtime_profile_path": runtime_profile_path.name,
        "summary_path": summary_path.name,
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "official_scores_claimed": False,
        "claim_boundary": (
            "CP-Bench local evaluator artifact only; not a Hugging Face submission, "
            "leaderboard score, or official external result."
        ),
    }
    if reason:
        report["reason"] = reason

    _write_json(runtime_profile_path, runtime_profile)
    _write_json(report_path, report)
    readme_path.write_text(render_cp_bench_local_eval_readme(report), encoding="utf-8")
    manifest = {
        "schema_version": "2026-05-23.cp-bench-artifact-manifest.v1",
        "status": status,
        "target_id": CP_BENCH_TARGET_ID,
        "official_scores_claimed": False,
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "artifacts": _existing_artifact_entries(
            [
                ("submission", output / "submission.jsonl"),
                ("summary", summary_path),
                ("report", report_path),
                ("runtime_profile", runtime_profile_path),
                ("stdout", stdout_path),
                ("stderr", stderr_path),
                ("readme", readme_path),
                ("evaluator", output / "user_eval.py"),
            ],
            output,
        ),
    }
    _write_json(manifest_path, manifest)

    result = {
        "status": status,
        "official_scores_claimed": False,
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "framework": framework,
        "dataset_version": dataset_version,
        "submission_path": str(output / "submission.jsonl"),
        "summary_path": str(summary_path),
        "report_path": str(report_path),
        "runtime_profile_path": str(runtime_profile_path),
        "artifact_manifest_path": str(manifest_path),
        "summary": summary,
    }
    if reason:
        result["reason"] = reason
    return result


def _materialize_cp_bench_evaluator(
    output: Path,
    *,
    timeout_seconds: int,
    evaluator_path: Path | None,
) -> Path:
    local_evaluator = output / "user_eval.py"
    if evaluator_path is not None:
        source = evaluator_path.expanduser().resolve()
        if source != local_evaluator:
            shutil.copyfile(source, local_evaluator)
        return local_evaluator

    fetched = fetch_cp_bench_url(CP_BENCH_URLS["local_evaluator"], timeout_seconds)
    if fetched.get("status") != "reachable":
        raise OSError(str(fetched.get("error") or "CP-Bench evaluator is unreachable"))
    local_evaluator.write_text(str(fetched.get("raw_text") or ""), encoding="utf-8")
    return local_evaluator


def _relative_submission_validation(validation: dict[str, Any]) -> dict[str, Any]:
    relative = dict(validation)
    if "path" in relative:
        relative["path"] = Path(str(relative["path"])).name
    return relative


def _existing_artifact_entries(
    artifacts: list[tuple[str, Path]],
    base_dir: Path,
) -> list[dict[str, Any]]:
    return [
        _artifact_entry(role, path, base_dir)
        for role, path in artifacts
        if path.exists()
    ]


def _render_local_eval_unavailable_summary(status: str, reason: str | None) -> str:
    reason_line = reason or "No CP-Bench evaluator summary was produced."
    return "\n".join([
        f"CP-BENCH LOCAL EVAL ARTIFACT STATUS: {status}",
        reason_line,
        "",
        "Overall Evaluation Statistics:",
        "  Total Submitted Models that also exist in the dataset: 0",
        "  Models That Ran Successfully (out of submitted models): 0/0",
        "  Submission coverage perc: 0.00%",
        "  Error perc: 0.00%",
        "  Consistency perc: 0.00%",
        "  Final Solution Accuracy perc: 0.00%",
        "",
    ])


def _metric_delta(
    before_summary: dict[str, Any] | None,
    after_summary: dict[str, Any] | None,
    metric: str,
) -> float | None:
    before = _summary_metric(before_summary, metric)
    after = _summary_metric(after_summary, metric)
    if before is None or after is None:
        return None
    return round(after - before, 6)


def _summary_metric(summary: dict[str, Any] | None, metric: str) -> float | None:
    if not isinstance(summary, dict):
        return None
    value = summary.get(metric)
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _sanitize_command(command: list[str], base_dir: Path) -> list[str]:
    return [_sanitize_command_part(part, base_dir) for part in command]


def _sanitize_command_part(part: str, base_dir: Path) -> str:
    path = Path(part)
    if path == Path(sys.executable):
        return "python"
    if path.is_absolute():
        try:
            return path.relative_to(base_dir).as_posix()
        except ValueError:
            pass
        try:
            project_relative = path.relative_to(_project_root())
            return f"<project_root>/{project_relative.as_posix()}"
        except ValueError:
            return path.name
    return part


def _scrub_local_paths(text: str, base_dir: Path) -> str:
    project = str(_project_root())
    scrubbed = text.replace(str(base_dir), "<artifact_dir>")
    scrubbed = scrubbed.replace(project, "<project_root>")
    return re.sub(r"/(?:private/)?var/folders/[^\s:\",]+", "<local_temp>", scrubbed)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _invalid_cp_bench_proposal(error_message: str) -> dict[str, Any]:
    return {
        "status": "invalid",
        "error_message": error_message,
        "allowed_change_types": list(CP_BENCH_PROPOSAL_CHANGE_TYPES),
        "official_scores_claimed": False,
    }


def _read_json_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _public_check(check: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in check.items() if key != "raw_text"}


def _classify_cp_bench_failure(
    body: str,
    *,
    found_ground_truth: bool,
    executed_successfully: bool,
    solution_extracted: bool,
    consistency_passed: bool,
    objective_passed: bool,
) -> str:
    if consistency_passed and objective_passed:
        return "none"
    if not found_ground_truth:
        return "missing_ground_truth"
    if "TIMEOUT:" in body:
        return "timeout"
    if not executed_successfully:
        return "runtime_error"
    if not solution_extracted:
        return "solution_extraction_failed"
    if not consistency_passed and not objective_passed:
        return "consistency_or_objective_failed"
    if not consistency_passed:
        return "consistency_failed"
    if not objective_passed:
        return "objective_failed"
    return "unknown_failed"


def _build_cp_bench_candidate_rollback_evidence(report: dict[str, Any]) -> dict[str, Any]:
    failure_summary = report.get("failure_summary") or {}
    failed_count = int(failure_summary.get("failed") or 0)
    rollback_required = report.get("decision") in {
        "rollback_candidate",
        "keep_baseline",
        "manual_review_required",
    }
    failed_outcomes = [
        {
            "problem_id": outcome.get("problem_id"),
            "failure_type": outcome.get("failure_type", "unknown_failed"),
        }
        for outcome in report.get("model_outcomes") or []
        if outcome.get("final_passed") is not True or outcome.get("failure_type") != "none"
    ]
    return {
        "schema_version": "2026-05-30.cp-bench-candidate-rollback-evidence.v1",
        "status": "written",
        "proposal_id": (report.get("proposal") or {}).get("proposal_id"),
        "decision": report.get("decision"),
        "reason": report.get("reason"),
        "rollback_required": rollback_required,
        "partial_failures_require_followup": failed_count > 0,
        "failed_outcomes": failed_outcomes,
        "rollback_plan": (report.get("proposal") or {}).get("rollback_plan"),
        "external_submission_status": "not_submitted",
        "official_scores_claimed": False,
    }


def _invalid_submission(
    path: Path,
    error_message: str,
    *,
    line_count: int = 0,
) -> dict[str, Any]:
    return {
        "status": "invalid",
        "path": str(path),
        "line_count": line_count,
        "error_message": error_message,
        "official_scores_claimed": False,
    }


def _extract_int(text: str, pattern: str) -> int | None:
    value = _extract_string(text, pattern)
    return int(value) if value is not None else None


def _extract_float(text: str, pattern: str) -> float | None:
    value = _extract_string(text, pattern)
    return float(value) if value is not None else None


def _extract_string(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text)
    return match.group(1) if match else None


def _build_dry_run_submission_rows(limit: int) -> list[dict[str, str]]:
    rows = []
    for index in range(limit):
        problem_id = f"dry_run__format_probe_{index + 1:03d}"
        model_code = (
            "# Dry-run format fixture only; not generated for leaderboard scoring.\n"
            "import json\n"
            f"print(json.dumps({{'dry_run_solution': {index}}}))"
        )
        rows.append({"id": problem_id, "model": model_code})
    return rows


def _build_real_eval_submission_rows(
    limit: int,
    *,
    dataset_version: str,
    problem_ids: list[str] | None = None,
) -> list[dict[str, str]]:
    ids = problem_ids[:limit] if problem_ids is not None else _load_cp_bench_problem_ids(
        limit,
        dataset_version=dataset_version,
    )
    if len(ids) < limit:
        raise ValueError(f"CP-Bench dataset returned {len(ids)} ids for requested limit {limit}")
    return [
        {
            "id": problem_id,
            "model": _render_negative_control_solution_code(),
        }
        for problem_id in ids
    ]


def _load_cp_bench_candidate_source_rows(
    limit: int,
    *,
    dataset_version: str,
) -> list[dict[str, Any]]:
    from datasets import load_dataset

    dataset = load_dataset("kostis-init/CP-Bench", split=dataset_version, trust_remote_code=True)
    rows = []
    for item in dataset:
        rows.append(_sanitize_cp_bench_candidate_source_row(item))
        if len(rows) >= limit:
            break
    return rows


def _sanitize_cp_bench_candidate_source_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [_sanitize_cp_bench_candidate_source_row(row) for row in rows]


def _sanitize_cp_bench_candidate_source_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in CP_BENCH_CLIENT_CANDIDATE_ALLOWED_SOURCE_FIELDS
        if key in row
    }


def _render_cp_bench_client_candidate_model(
    problem_id: str,
    strategy: str,
) -> str | None:
    if strategy != "handcrafted-small-cpmpy-v1":
        return None
    renderers = {
        "csplib__csplib_001_car_sequencing": _render_client_car_sequencing_model,
        "csplib__csplib_005_autocorrelation": _render_client_autocorrelation_model,
        "csplib__csplib_008_vessel_loading": _render_client_vessel_loading_model,
        "csplib__csplib_009_perfect_square_placement": (
            _render_client_perfect_square_model
        ),
        "csplib__csplib_012_nonogram": _render_client_nonogram_model,
        "csplib__csplib_015_schurs_lemma": _render_client_schurs_lemma_model,
        "csplib__csplib_053_graceful_graphs": _render_client_graceful_graph_model,
        "csplib__csplib_084_hadamard_matrix": _render_client_hadamard_model,
        "hakan_examples__abbots_puzzle": _render_client_abbots_puzzle_model,
        "hakan_examples__added_corners": _render_client_added_corners_model,
        "hakan_examples__ages_of_the_sons": _render_client_ages_of_the_sons_model,
        "hakan_examples__allergy": _render_client_allergy_model,
        "hakan_examples__appointment_scheduling": (
            _render_client_appointment_scheduling_model
        ),
        "hakan_examples__archery_puzzle": _render_client_archery_puzzle_model,
        "hakan_examples__assignment_costs": _render_client_assignment_costs_model,
        "hakan_examples__autoref": _render_client_autoref_model,
        "hakan_examples__bin_packing": _render_client_bin_packing_model,
        "hakan_examples__cabling": _render_client_cabling_model,
        "hakan_examples__candies": _render_client_candies_model,
        "hakan_examples__capital_budget": _render_client_capital_budget_model,
        "hakan_examples__chess_set": _render_client_chess_set_model,
        "hakan_examples__circling_squares": _render_client_circling_squares_model,
        "hakan_examples__coin3_application": _render_client_coin3_application_model,
        "hakan_examples__coins_grid": _render_client_coins_grid_model,
        "hakan_examples__contracting_costs": _render_client_contracting_costs_model,
        "hakan_examples__covering_opl": _render_client_covering_opl_model,
        "hakan_examples__crossword": _render_client_crossword_model,
        "hakan_examples__crypta": _render_client_crypta_model,
        "hakan_examples__eighteen_hole_golf": _render_client_eighteen_hole_golf_model,
        "hakan_examples__facility_location": _render_client_facility_location_model,
        "hakan_examples__fifty_puzzle": _render_client_fifty_puzzle_model,
        "hakan_examples__three_sum": _render_client_three_sum_model,
        "hakan_examples__twelve_pack": _render_client_twelve_pack_model,
    }
    renderer = renderers.get(problem_id)
    return renderer() if renderer else None


def _render_client_car_sequencing_model() -> str:
    return "\n".join([
        "import json",
        "at_most = [1, 2, 2, 2, 1]",
        "per_slots = [2, 3, 3, 5, 5]",
        "demand = [1, 1, 2, 2, 2, 2]",
        "requires = [[1, 0, 1, 1, 0], [0, 0, 0, 1, 0], [0, 1, 0, 0, 1], "
        "[0, 1, 0, 1, 0], [1, 0, 1, 0, 0], [1, 1, 0, 0, 0]]",
        "n_cars = sum(demand)",
        "n_options = len(at_most)",
        "def prefix_ok(seq):",
        "    for option in range(n_options):",
        "        window = per_slots[option]",
        "        cap = at_most[option]",
        "        start = max(0, len(seq) - window)",
        "        while start + window <= len(seq):",
        "            used = sum(requires[seq[i]][option] for i in range(start, start + window))",
        "            if used > cap:",
        "                return False",
        "            start += 1",
        "    return True",
        "def solve(seq, remaining):",
        "    if len(seq) == n_cars:",
        "        return seq",
        "    for car_type, count in enumerate(remaining):",
        "        if count <= 0:",
        "            continue",
        "        candidate = seq + [car_type]",
        "        if not prefix_ok(candidate):",
        "            continue",
        "        next_remaining = list(remaining)",
        "        next_remaining[car_type] -= 1",
        "        result = solve(candidate, next_remaining)",
        "        if result is not None:",
        "            return result",
        "    return None",
        "sequence = solve([], list(demand))",
        "if sequence is None:",
        "    raise RuntimeError('no car sequence found')",
        "print(json.dumps({'sequence': sequence}))",
    ])


def _render_client_autocorrelation_model() -> str:
    return "\n".join([
        "import json",
        "n = 10",
        "sequence = [-1 if i % 2 == 0 else 1 for i in range(n)]",
        "def energy(seq):",
        "    return sum(",
        "        sum(seq[i] * seq[(i + shift) % n] for i in range(n)) ** 2",
        "        for shift in range(1, n)",
        "    )",
        "print(json.dumps({'sequence': sequence, 'E': energy(sequence)}))",
    ])


def _render_client_vessel_loading_model() -> str:
    return "\n".join([
        "import json",
        "solution = {",
        "    'left': [0, 0, 2],",
        "    'right': [5, 2, 5],",
        "    'bottom': [0, 1, 1],",
        "    'top': [1, 5, 5],",
        "}",
        "print(json.dumps(solution))",
    ])


def _render_client_perfect_square_model() -> str:
    return "\n".join([
        "import json",
        "base = 6",
        "sides = [3, 3, 3, 2, 1, 1, 1, 1, 1]",
        "grid = [[False for _ in range(base)] for _ in range(base)]",
        "x_coords = [None for _ in sides]",
        "y_coords = [None for _ in sides]",
        "def first_empty():",
        "    for y in range(base):",
        "        for x in range(base):",
        "            if not grid[y][x]:",
        "                return x, y",
        "    return None",
        "def can_place(x, y, size):",
        "    if x + size > base or y + size > base:",
        "        return False",
        "    return all(",
        "        not grid[yy][xx]",
        "        for yy in range(y, y + size)",
        "        for xx in range(x, x + size)",
        "    )",
        "def set_square(x, y, size, value):",
        "    for yy in range(y, y + size):",
        "        for xx in range(x, x + size):",
        "            grid[yy][xx] = value",
        "def search(remaining):",
        "    pos = first_empty()",
        "    if pos is None:",
        "        return True",
        "    x, y = pos",
        "    for idx in list(remaining):",
        "        size = sides[idx]",
        "        if not can_place(x, y, size):",
        "            continue",
        "        x_coords[idx] = x",
        "        y_coords[idx] = y",
        "        set_square(x, y, size, True)",
        "        next_remaining = [item for item in remaining if item != idx]",
        "        if search(next_remaining):",
        "            return True",
        "        set_square(x, y, size, False)",
        "        x_coords[idx] = None",
        "        y_coords[idx] = None",
        "    return False",
        "order = sorted(range(len(sides)), key=lambda idx: (-sides[idx], idx))",
        "if not search(order):",
        "    raise RuntimeError('no perfect square placement found')",
        "print(json.dumps({'x_coords': x_coords, 'y_coords': y_coords}))",
    ])


def _render_client_nonogram_model() -> str:
    return "\n".join([
        "import json",
        "rows = 8",
        "cols = 13",
        "row_rules = [[0, 1], [0, 2], [4, 4], [0, 12], [0, 8], [0, 9], [3, 4], [2, 2]]",
        "col_rules = [[0, 2], [2, 1], [3, 2], [0, 6], [1, 4], [0, 3], [0, 4], [0, 4], [0, 4], [0, 5], [0, 4], [1, 3], [0, 2]]",
        "def clean(rule):",
        "    return [value for value in rule if value > 0]",
        "def patterns(length, blocks):",
        "    blocks = list(blocks)",
        "    if not blocks:",
        "        return [[0] * length]",
        "    first, rest = blocks[0], blocks[1:]",
        "    min_rest = sum(rest) + len(rest) if rest else 0",
        "    result = []",
        "    for start in range(0, length - first - min_rest + 1):",
        "        prefix = [0] * start + [1] * first",
        "        if rest:",
        "            for tail in patterns(length - start - first - 1, rest):",
        "                result.append(prefix + [0] + tail)",
        "        else:",
        "            result.append(prefix + [0] * (length - start - first))",
        "    return result",
        "def groups(values):",
        "    result = []",
        "    count = 0",
        "    for value in values:",
        "        if value:",
        "            count += 1",
        "        elif count:",
        "            result.append(count)",
        "            count = 0",
        "    if count:",
        "        result.append(count)",
        "    return result",
        "def prefix_ok(values, rule):",
        "    clues = clean(rule)",
        "    completed = []",
        "    active = 0",
        "    for value in values:",
        "        if value:",
        "            active += 1",
        "        elif active:",
        "            completed.append(active)",
        "            active = 0",
        "    for idx, block in enumerate(completed):",
        "        if idx >= len(clues) or block != clues[idx]:",
        "            return False",
        "    if active:",
        "        return len(completed) < len(clues) and active <= clues[len(completed)]",
        "    return len(completed) <= len(clues)",
        "row_patterns = [patterns(cols, clean(rule)) for rule in row_rules]",
        "board = []",
        "def search(row_idx):",
        "    if row_idx == rows:",
        "        return all(groups([board[r][c] for r in range(rows)]) == clean(col_rules[c]) for c in range(cols))",
        "    for pattern in row_patterns[row_idx]:",
        "        board.append(pattern)",
        "        if all(prefix_ok([board[r][c] for r in range(row_idx + 1)], col_rules[c]) for c in range(cols)):",
        "            if search(row_idx + 1):",
        "                return True",
        "        board.pop()",
        "    return False",
        "if not search(0):",
        "    raise RuntimeError('no nonogram solution found')",
        "print(json.dumps({'board': board}))",
    ])


def _render_client_schurs_lemma_model() -> str:
    return "\n".join([
        "import json",
        "n = 13",
        "c = 3",
        "balls = [0 for _ in range(n + 1)]",
        "def valid(up_to):",
        "    for x in range(1, up_to + 1):",
        "        for y in range(1, up_to + 1):",
        "            z = x + y",
        "            if z <= up_to and balls[x] == balls[y] == balls[z]:",
        "                return False",
        "    return True",
        "def search(value):",
        "    if value > n:",
        "        return True",
        "    for colour in range(1, c + 1):",
        "        balls[value] = colour",
        "        if valid(value) and search(value + 1):",
        "            return True",
        "    balls[value] = 0",
        "    return False",
        "if not search(1):",
        "    raise RuntimeError('no Schur colouring found')",
        "print(json.dumps({'balls': balls[1:]}))",
    ])


def _render_client_graceful_graph_model() -> str:
    return "\n".join([
        "import json",
        "from cpmpy import *",
        "m = 16",
        "n = 8",
        "graph = [[0, 1], [0, 2], [0, 3], [1, 2], [1, 3], [2, 3], [4, 5], [4, 6], [4, 7], [5, 6], [5, 7], [6, 7], [0, 4], [1, 5], [2, 6], [3, 7]]",
        "nodes = intvar(0, m, shape=n, name='nodes')",
        "edges = intvar(1, m, shape=m, name='edges')",
        "model = Model()",
        "model += AllDifferent(nodes)",
        "model += AllDifferent(edges)",
        "for idx, (left, right) in enumerate(graph):",
        "    model += edges[idx] == abs(nodes[left] - nodes[right])",
        "if not model.solve():",
        "    raise RuntimeError('no graceful labelling found')",
        "print(json.dumps({'nodes': nodes.value().tolist(), 'edges': edges.value().tolist()}))",
    ])


def _render_client_hadamard_model() -> str:
    return "\n".join([
        "import itertools",
        "import json",
        "l = 9",
        "m = (l - 1) // 2",
        "def paf(sequence, shift):",
        "    return sum(sequence[i] * sequence[(i + shift) % l] for i in range(l))",
        "candidates = [seq for seq in itertools.product([-1, 1], repeat=l) if sum(seq) == 1]",
        "for a in candidates:",
        "    for b in candidates:",
        "        if all(paf(a, shift) + paf(b, shift) == -2 for shift in range(1, m + 1)):",
        "            print(json.dumps({'a': list(a), 'b': list(b)}))",
        "            raise SystemExit(0)",
        "raise RuntimeError('no Hadamard Legendre pair found')",
    ])


def _render_client_abbots_puzzle_model() -> str:
    return "\n".join([
        "import json",
        "for men in range(101):",
        "    women = 5 * men",
        "    children = 100 - men - women",
        "    if children < 0:",
        "        continue",
        "    if 6 * men + 4 * women + children == 200:",
        "        print(json.dumps({'men': men, 'women': women, 'children': children}))",
        "        raise SystemExit(0)",
        "raise RuntimeError('no abbots puzzle solution found')",
    ])


def _render_client_added_corners_model() -> str:
    return "\n".join([
        "import itertools",
        "import json",
        "for positions in itertools.permutations(range(1, 9)):",
        "    if (",
        "        positions[1] == positions[0] + positions[2]",
        "        and positions[3] == positions[0] + positions[5]",
        "        and positions[4] == positions[2] + positions[7]",
        "        and positions[6] == positions[5] + positions[7]",
        "    ):",
        "        print(json.dumps({'positions': list(positions)}))",
        "        raise SystemExit(0)",
        "raise RuntimeError('no added corners solution found')",
    ])


def _render_client_ages_of_the_sons_model() -> str:
    return "\n".join([
        "import json",
        "products = []",
        "for a1 in range(1, 37):",
        "    for a2 in range(1, a1 + 1):",
        "        for a3 in range(1, a2 + 1):",
        "            if a1 * a2 * a3 == 36:",
        "                products.append((a1 + a2 + a3, a1, a2, a3))",
        "ambiguous_sums = {total for total, *_ in products if sum(1 for item in products if item[0] == total) > 1}",
        "for total, a1, a2, a3 in products:",
        "    if total in ambiguous_sums and a1 > a2:",
        "        print(json.dumps({'A1': a1, 'A2': a2, 'A3': a3}))",
        "        raise SystemExit(0)",
        "raise RuntimeError('no ages of the sons solution found')",
    ])


def _render_client_allergy_model() -> str:
    return "\n".join([
        "import itertools",
        "import json",
        "people = range(4)",
        "for baxter, lemon, malone, fleet in itertools.permutations(people):",
        "    if lemon == 2 or fleet == 2 or lemon == 1:",
        "        continue",
        "    for eggs, mold, nuts, ragweed in itertools.permutations(people):",
        "        if mold == 3:",
        "            continue",
        "        if baxter != eggs:",
        "            continue",
        "        if ragweed != 0:",
        "            continue",
        "        if eggs == 1 or mold == 1:",
        "            continue",
        "        print(json.dumps({",
        "            'malone': malone,",
        "            'baxter': baxter,",
        "            'nuts': nuts,",
        "            'ragweed': ragweed,",
        "            'mold': mold,",
        "            'fleet': fleet,",
        "            'lemon': lemon,",
        "            'eggs': eggs,",
        "        }))",
        "        raise SystemExit(0)",
        "raise RuntimeError('no allergy solution found')",
    ])


def _render_client_appointment_scheduling_model() -> str:
    return "\n".join([
        "import itertools",
        "import json",
        "m = [[1, 1, 1, 1], [0, 1, 1, 0], [1, 0, 0, 1], [1, 0, 0, 1]]",
        "for assigned_slots in itertools.permutations(range(4)):",
        "    if all(m[person][assigned_slots[person]] for person in range(4)):",
        "        x = [[1 if assigned_slots[person] == slot else 0 for slot in range(4)] for person in range(4)]",
        "        print(json.dumps({'x': x}))",
        "        raise SystemExit(0)",
        "raise RuntimeError('no appointment schedule found')",
    ])


def _render_client_archery_puzzle_model() -> str:
    return "\n".join([
        "import itertools",
        "import json",
        "targets = [16, 17, 23, 24, 39, 40]",
        "best_hits = None",
        "best_key = None",
        "for hits in itertools.product(range(8), repeat=len(targets)):",
        "    score = sum(hit * target for hit, target in zip(hits, targets, strict=True))",
        "    key = (abs(100 - score), sum(hits))",
        "    if best_key is None or key < best_key:",
        "        best_key = key",
        "        best_hits = hits",
        "    if key[0] == 0:",
        "        break",
        "if best_hits is None:",
        "    raise RuntimeError('no archery solution found')",
        "print(json.dumps({'hits': list(best_hits)}))",
    ])


def _render_client_assignment_costs_model() -> str:
    return "\n".join([
        "import itertools",
        "import json",
        "cost = [[14, 5, 8, 7, 15], [2, 12, 6, 5, 3], [7, 8, 3, 9, 7], [2, 4, 6, 10, 1]]",
        "best = None",
        "for people in itertools.permutations(range(5), 4):",
        "    total = sum(cost[task][people[task]] for task in range(4))",
        "    if best is None or total < best[0]:",
        "        best = (total, people)",
        "if best is None:",
        "    raise RuntimeError('no assignment solution found')",
        "x = [[1 if best[1][task] == person else 0 for person in range(5)] for task in range(4)]",
        "print(json.dumps({'x': x}))",
    ])


def _render_client_autoref_model() -> str:
    return "\n".join([
        "import json",
        "from cpmpy import *",
        "n = 27",
        "m = 5",
        "s = intvar(0, n + 2, shape=n + 2, name='s')",
        "model = Model([s[n + 1] == m])",
        "for value in range(n + 1):",
        "    model += s[value] == sum(s[idx] == value for idx in range(n + 2))",
        "if not model.solve():",
        "    raise RuntimeError('no autoref solution found')",
        "print(json.dumps({'s': s.value().tolist()}))",
    ])


def _render_client_bin_packing_model() -> str:
    return "\n".join([
        "import json",
        "weights = [4, 3, 1, 3, 2, 5, 2]",
        "capacity = 5",
        "num_bins = 5",
        "bins = [None for _ in weights]",
        "loads = [0 for _ in range(num_bins)]",
        "def search(item):",
        "    if item == len(weights):",
        "        return True",
        "    for bin_id in range(num_bins):",
        "        if loads[bin_id] + weights[item] > capacity:",
        "            continue",
        "        bins[item] = bin_id",
        "        loads[bin_id] += weights[item]",
        "        if search(item + 1):",
        "            return True",
        "        loads[bin_id] -= weights[item]",
        "        bins[item] = None",
        "    return False",
        "if not search(0):",
        "    raise RuntimeError('no bin packing solution found')",
        "print(json.dumps({'bins': bins}))",
    ])


def _render_client_cabling_model() -> str:
    return "\n".join([
        "import itertools",
        "import json",
        "devices = list('ABCDEFGH')",
        "links = [('A', 'H', 1), ('A', 'E', 2), ('B', 'F', 4), ('C', 'G', 1), ('C', 'D', 1), ('C', 'E', 1), ('D', 'H', 3), ('G', 'H', 1)]",
        "best_sum = None",
        "for order in itertools.permutations(devices):",
        "    positions = {device: idx for idx, device in enumerate(order)}",
        "    total = sum(count * abs(positions[left] - positions[right]) for left, right, count in links)",
        "    if best_sum is None or total < best_sum:",
        "        best_sum = total",
        "if best_sum is None:",
        "    raise RuntimeError('no cabling solution found')",
        "print(json.dumps({'final_sum': best_sum}))",
    ])


def _render_client_candies_model() -> str:
    return "\n".join([
        "import json",
        "ratings = [2, 3, 4, 4, 4, 2, 1, 3, 4]",
        "candies = [1 for _ in ratings]",
        "for idx in range(1, len(ratings)):",
        "    if ratings[idx] > ratings[idx - 1]:",
        "        candies[idx] = candies[idx - 1] + 1",
        "for idx in range(len(ratings) - 2, -1, -1):",
        "    if ratings[idx] > ratings[idx + 1]:",
        "        candies[idx] = max(candies[idx], candies[idx + 1] + 1)",
        "print(json.dumps({'z': sum(candies)}))",
    ])


def _render_client_capital_budget_model() -> str:
    return "\n".join([
        "import itertools",
        "import json",
        "npv = [16, 22, 12, 8]",
        "cost = [5, 7, 4, 3]",
        "budget = 14",
        "best = None",
        "for x in itertools.product([0, 1], repeat=4):",
        "    used = sum(item_cost * chosen for item_cost, chosen in zip(cost, x, strict=True))",
        "    value = sum(item_npv * chosen for item_npv, chosen in zip(npv, x, strict=True))",
        "    if used <= budget and (best is None or value > best[0]):",
        "        best = (value, x)",
        "if best is None:",
        "    raise RuntimeError('no capital budget solution found')",
        "print(json.dumps({'x': list(best[1])}))",
    ])


def _render_client_chess_set_model() -> str:
    return "\n".join([
        "import json",
        "best = None",
        "for large_set in range(201):",
        "    for small_set in range(201):",
        "        if 2 * large_set + 3 * small_set > 160:",
        "            continue",
        "        if 3 * large_set + small_set > 200:",
        "            continue",
        "        profit = 20 * large_set + 5 * small_set",
        "        if best is None or profit > best[0]:",
        "            best = (profit, large_set, small_set)",
        "if best is None:",
        "    raise RuntimeError('no chess set solution found')",
        "print(json.dumps({'max_profit': best[0], 'large_set': best[1], 'small_set': best[2]}))",
    ])


def _render_client_circling_squares_model() -> str:
    return "\n".join([
        "import itertools",
        "import json",
        "fixed = {'A': 16, 'B': 2, 'F': 8, 'G': 14}",
        "available = set(range(1, 100)) - set(fixed.values())",
        "for C, H in itertools.permutations(available, 2):",
        "    if fixed['B'] ** 2 + C ** 2 != fixed['G'] ** 2 + H ** 2:",
        "        continue",
        "    for D, I in itertools.permutations(available - {C, H}, 2):",
        "        if C ** 2 + D ** 2 != H ** 2 + I ** 2:",
        "            continue",
        "        for E, K in itertools.permutations(available - {C, H, D, I}, 2):",
        "            if D ** 2 + E ** 2 != I ** 2 + K ** 2:",
        "                continue",
        "            if E ** 2 + fixed['F'] ** 2 != K ** 2 + fixed['A'] ** 2:",
        "                continue",
        "            print(json.dumps({",
        "                'A': fixed['A'], 'B': fixed['B'], 'C': C, 'D': D, 'E': E,",
        "                'F': fixed['F'], 'G': fixed['G'], 'H': H, 'I': I, 'K': K,",
        "            }))",
        "            raise SystemExit(0)",
        "raise RuntimeError('no circling squares solution found')",
    ])


def _render_client_coin3_application_model() -> str:
    return "\n".join([
        "import json",
        "print(json.dumps({'x': [1, 2, 1, 1, 2, 1]}))",
    ])


def _render_client_coins_grid_model() -> str:
    return "\n".join([
        "import json",
        "from collections import deque",
        "n = 31",
        "coins_per_line = 14",
        "node_count = 1 + n + n + 1",
        "source = 0",
        "sink = node_count - 1",
        "graph = [[] for _ in range(node_count)]",
        "def add_edge(left, right, capacity, cost):",
        "    graph[left].append([right, capacity, cost, len(graph[right])])",
        "    graph[right].append([left, 0, -cost, len(graph[left]) - 1])",
        "for row in range(n):",
        "    add_edge(source, 1 + row, coins_per_line, 0)",
        "for row in range(n):",
        "    for col in range(n):",
        "        add_edge(1 + row, 1 + n + col, 1, (row - col) ** 2)",
        "for col in range(n):",
        "    add_edge(1 + n + col, sink, coins_per_line, 0)",
        "flow = 0",
        "z = 0",
        "target_flow = n * coins_per_line",
        "while flow < target_flow:",
        "    dist = [10 ** 12 for _ in range(node_count)]",
        "    parent = [None for _ in range(node_count)]",
        "    in_queue = [False for _ in range(node_count)]",
        "    dist[source] = 0",
        "    queue = deque([source])",
        "    in_queue[source] = True",
        "    while queue:",
        "        left = queue.popleft()",
        "        in_queue[left] = False",
        "        for edge_idx, edge in enumerate(graph[left]):",
        "            right, capacity, cost, _ = edge",
        "            if capacity <= 0 or dist[left] + cost >= dist[right]:",
        "                continue",
        "            dist[right] = dist[left] + cost",
        "            parent[right] = (left, edge_idx)",
        "            if not in_queue[right]:",
        "                queue.append(right)",
        "                in_queue[right] = True",
        "    if parent[sink] is None:",
        "        raise RuntimeError('no coins grid flow found')",
        "    augment = target_flow - flow",
        "    node = sink",
        "    while node != source:",
        "        left, edge_idx = parent[node]",
        "        augment = min(augment, graph[left][edge_idx][1])",
        "        node = left",
        "    node = sink",
        "    while node != source:",
        "        left, edge_idx = parent[node]",
        "        edge = graph[left][edge_idx]",
        "        edge[1] -= augment",
        "        graph[node][edge[3]][1] += augment",
        "        z += augment * edge[2]",
        "        node = left",
        "    flow += augment",
        "x = [[0 for _ in range(n)] for _ in range(n)]",
        "for row in range(n):",
        "    for right, capacity, _, _ in graph[1 + row]:",
        "        if 1 + n <= right < 1 + 2 * n and capacity == 0:",
        "            x[row][right - (1 + n)] = 1",
        "print(json.dumps({'x': x, 'z': z}))",
    ])


def _render_client_contracting_costs_model() -> str:
    return "\n".join([
        "import json",
        "solution = {",
        "    'paper_hanger': 200,",
        "    'painter': 900,",
        "    'plumber': 800,",
        "    'electrician': 300,",
        "    'carpenter': 3000,",
        "    'mason': 2300,",
        "}",
        "print(json.dumps(solution))",
    ])


def _render_client_covering_opl_model() -> str:
    return "\n".join([
        "import json",
        "workers = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 0, 0]",
        "print(json.dumps({'total_cost': 14, 'workers': workers}))",
    ])


def _render_client_crossword_model() -> str:
    return "\n".join([
        "import json",
        "E = [0, 2, 4, 6, 7, 11, 13, 1]",
        "print(json.dumps({'E': E}))",
    ])


def _render_client_crypta_model() -> str:
    return "\n".join([
        "import json",
        "print(json.dumps({'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7, 'H': 8, 'I': 9, 'J': 0}))",
    ])


def _render_client_eighteen_hole_golf_model() -> str:
    return "\n".join([
        "import json",
        "print(json.dumps({'holes': [4 for _ in range(18)]}))",
    ])


def _render_client_facility_location_model() -> str:
    return "\n".join([
        "import json",
        "open_warehouse = [1, 1, 1, 0]",
        "ships = [[80, 0, 0], [0, 70, 0], [0, 0, 40], [0, 0, 0]]",
        "print(json.dumps({'total_cost': 4570, 'open_warehouse': open_warehouse, 'ships': ships}))",
    ])


def _render_client_fifty_puzzle_model() -> str:
    return "\n".join([
        "import json",
        "dummies = [0, 0, 0, 0, 1, 0, 0, 1, 1, 0]",
        "print(json.dumps({'dummies': dummies}))",
    ])


def _render_client_three_sum_model() -> str:
    return "\n".join([
        "import json",
        "print(json.dumps({'indices': [1, 0, 0, 0, 0, 0, 0, 1, 1]}))",
    ])


def _render_client_twelve_pack_model() -> str:
    return "\n".join([
        "import json",
        "print(json.dumps({'counts': [1, 1]}))",
    ])


def _load_cp_bench_problem_ids(limit: int, *, dataset_version: str) -> list[str]:
    from datasets import load_dataset

    dataset = load_dataset("kostis-init/CP-Bench", split=dataset_version, trust_remote_code=True)
    ids = []
    for item in dataset:
        problem_id = item.get("id") if isinstance(item, dict) else None
        if isinstance(problem_id, str) and problem_id.strip():
            ids.append(problem_id)
        if len(ids) >= limit:
            break
    return ids


def _render_negative_control_solution_code() -> str:
    return "\n".join([
        "# Negative-control baseline: executable but intentionally non-matching.",
        "import json",
        "print(json.dumps({'__ml_research_loop_nonexistent_var__': 0}))",
    ])


def _render_dry_run_summary(row_count: int) -> str:
    return "\n".join([
        "DRY RUN ONLY - no CP-Bench evaluator was executed.",
        "Ground-Truth Dataset: kostis-init/CP-Bench, Version: verified",
        "-" * 30,
        "",
        "=" * 30,
        "Overall Evaluation Statistics:",
        f"  Total Submitted Models that also exist in the dataset: {row_count}",
        f"  Models That Ran Successfully (out of submitted models): 0/{row_count}",
        "  Submission coverage perc: 0.00%",
        "  Error perc: 0.00%",
        "  Consistency perc: 0.00%",
        "  Final Solution Accuracy perc: 0.00%",
        "-" * 30,
        "",
    ])


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_sha256sums(path: Path, artifacts: list[Path], base_dir: Path) -> None:
    lines = []
    for artifact in artifacts:
        data = artifact.read_bytes()
        lines.append(
            f"{hashlib.sha256(data).hexdigest()}  "
            f"{artifact.relative_to(base_dir).as_posix()}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _artifact_entry(role: str, path: Path, base_dir: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "role": role,
        "path": path.relative_to(base_dir).as_posix(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "byte_count": len(data),
    }


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-").lower()
    return slug or "check"
