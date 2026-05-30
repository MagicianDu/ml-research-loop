from __future__ import annotations

import json
from pathlib import Path

from lib.benchmarks.cp_bench import (
    build_cp_bench_target_contract,
    parse_cp_bench_model_outcomes,
    parse_cp_bench_summary,
    probe_cp_bench_local_evaluator,
    run_cp_bench_candidate_round,
    run_cp_bench_local_eval,
    run_cp_bench_proposal_round,
    summarize_cp_bench_model_outcomes,
    validate_cp_bench_proposal,
    validate_cp_bench_submission,
    write_cp_bench_client_candidate_submission,
    write_cp_bench_proposal_context,
    write_cp_bench_local_baseline,
    write_cp_bench_live_verification,
    write_cp_bench_submission_gate,
)


def test_cp_bench_target_contract_preserves_claim_boundary() -> None:
    contract = build_cp_bench_target_contract()

    assert contract["target_id"] == "cp-bench-constraint-modeling"
    assert contract["official_scores_claimed"] is False
    assert contract["submission_format"]["file_extension"] == ".jsonl"
    assert contract["submission_format"]["required_keys"] == ["id", "model"]
    assert "CPMpy" in contract["supported_frameworks"]
    assert "MiniZinc" in contract["supported_frameworks"]
    assert "OR-Tools" in contract["supported_frameworks"]
    assert contract["manual_submission_required"] is True


def test_cp_bench_live_verification_writes_artifacts(tmp_path: Path) -> None:
    seen_urls: list[str] = []

    def fake_fetch(url: str, timeout_seconds: int) -> dict[str, object]:
        seen_urls.append(url)
        assert timeout_seconds == 5
        return {
            "url": url,
            "status": "reachable",
            "http_status": 200,
            "content_type": "text/plain",
            "byte_count": 128,
            "sha256": "abc123",
            "text_excerpt": "CP-Bench Leaderboard local evaluator id model jsonl",
        }

    result = write_cp_bench_live_verification(
        tmp_path,
        timeout_seconds=5,
        include_raw=True,
        fetcher=fake_fetch,
    )

    assert result["status"] == "written"
    assert result["official_scores_claimed"] is False
    assert result["verification_status"] == "verified_with_limitations"
    assert result["manual_submission_required"] is True
    assert seen_urls

    payload_path = Path(result["json_path"])
    contract_path = Path(result["contract_path"])
    raw_dir = tmp_path / "raw"
    assert payload_path.exists()
    assert contract_path.exists()
    assert raw_dir.exists()

    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["target"]["target_id"] == "cp-bench-constraint-modeling"
    assert payload["external_submission_status"] == "not_submitted"
    assert payload["official_scores_claimed"] is False
    assert all(check["status"] == "reachable" for check in payload["checks"])


def test_cp_bench_submission_validation_accepts_valid_jsonl(tmp_path: Path) -> None:
    submission = tmp_path / "submission.jsonl"
    submission.write_text(
        '{"id":"csplib__csplib_001_car_sequencing","model":"print({\\"sequence\\": [0]})"}\n',
        encoding="utf-8",
    )

    result = validate_cp_bench_submission(submission)

    assert result["status"] == "valid"
    assert result["line_count"] == 1
    assert result["official_scores_claimed"] is False


def test_cp_bench_submission_validation_rejects_missing_model_and_empty_file(
    tmp_path: Path,
) -> None:
    missing_model = tmp_path / "missing-model.jsonl"
    missing_model.write_text('{"id":"problem-1"}\n', encoding="utf-8")
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")

    missing_result = validate_cp_bench_submission(missing_model)
    empty_result = validate_cp_bench_submission(empty)

    assert missing_result["status"] == "invalid"
    assert "model" in missing_result["error_message"]
    assert empty_result["status"] == "invalid"
    assert "Empty file" in empty_result["error_message"]


def test_cp_bench_summary_parser_uses_public_evaluator_fields() -> None:
    summary = """
Overall Evaluation Statistics:
  Total Submitted Models that also exist in the dataset: 2
  Models That Ran Successfully (out of submitted models): 1/2
  Submission coverage perc: 1.23%
  Error perc: 50.00%
  Consistency perc: 0.62%
  Final Solution Accuracy perc: 0.62%
"""

    parsed = parse_cp_bench_summary(summary)

    assert parsed["submitted_models"] == 2
    assert parsed["runtime_success"] == "1/2"
    assert parsed["coverage_percent"] == 1.23
    assert parsed["error_percent"] == 50.0
    assert parsed["consistency_percent"] == 0.62
    assert parsed["final_solution_accuracy_percent"] == 0.62
    assert parsed["official_scores_claimed"] is False


def test_cp_bench_model_outcome_parser_extracts_per_problem_statuses() -> None:
    summary = """
--- Model: problem_ok ---
    0. Found ground-truth model for 'problem_ok' in dataset.
    1. Running submitted model...
      - SUCCESS: Model executed successfully.
      - SUCCESS: Got solution: {'sequence': [0, 1]}
    2. Performing solution check on ground-truth model...
      - CONSISTENCY: PASSED
      - OBJECTIVE CHECK: PASSED fully

--- Model: problem_bad_solution ---
    0. Found ground-truth model for 'problem_bad_solution' in dataset.
    1. Running submitted model...
      - SUCCESS: Model executed successfully.
      - SUCCESS: Got solution: {'x': 1}
    2. Performing solution check on ground-truth model...
      - CONSISTENCY: FAILED, stdout: boom

--- Model: problem_runtime_error ---
    0. Found ground-truth model for 'problem_runtime_error' in dataset.
    1. Running submitted model...
      - FAILED: Execution failed with error: Traceback
"""

    outcomes = parse_cp_bench_model_outcomes(summary)

    assert outcomes == [
        {
            "problem_id": "problem_ok",
            "found_ground_truth": True,
            "executed_successfully": True,
            "solution_extracted": True,
            "consistency_passed": True,
            "objective_passed": True,
            "final_passed": True,
            "failure_type": "none",
        },
        {
            "problem_id": "problem_bad_solution",
            "found_ground_truth": True,
            "executed_successfully": True,
            "solution_extracted": True,
            "consistency_passed": False,
            "objective_passed": False,
            "final_passed": False,
            "failure_type": "consistency_or_objective_failed",
        },
        {
            "problem_id": "problem_runtime_error",
            "found_ground_truth": True,
            "executed_successfully": False,
            "solution_extracted": False,
            "consistency_passed": False,
            "objective_passed": False,
            "final_passed": False,
            "failure_type": "runtime_error",
        },
    ]
    summary_counts = summarize_cp_bench_model_outcomes(outcomes)
    assert summary_counts["total"] == 3
    assert summary_counts["passed"] == 1
    assert summary_counts["failed"] == 2
    assert summary_counts["by_failure_type"]["runtime_error"] == 1


def test_cp_bench_local_baseline_dry_run_writes_artifact_bundle(tmp_path: Path) -> None:
    result = write_cp_bench_local_baseline(
        tmp_path,
        limit=1,
        framework="CPMpy",
        dry_run=True,
    )

    assert result["status"] == "written"
    assert result["official_scores_claimed"] is False
    assert result["manual_submission_required"] is True
    assert result["dry_run"] is True

    submission_path = Path(result["submission_path"])
    summary_path = Path(result["summary_path"])
    manifest_path = Path(result["artifact_manifest_path"])
    report_path = Path(result["report_path"])
    assert submission_path.exists()
    assert summary_path.exists()
    assert manifest_path.exists()
    assert report_path.exists()

    validation = validate_cp_bench_submission(submission_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    parsed_summary = parse_cp_bench_summary(summary_path.read_text(encoding="utf-8"))
    assert validation["status"] == "valid"
    assert parsed_summary["submitted_models"] == 1
    assert manifest["official_scores_claimed"] is False
    assert {artifact["role"] for artifact in manifest["artifacts"]} >= {
        "submission",
        "summary",
        "report",
    }


def test_cp_bench_evaluator_probe_reports_missing_dependencies() -> None:
    def fake_checker(module_name: str) -> bool:
        return module_name in {"datasets", "click"}

    result = probe_cp_bench_local_evaluator(package_checker=fake_checker)

    assert result["status"] == "blocked_missing_dependencies"
    assert result["official_scores_claimed"] is False
    assert result["manual_submission_required"] is True
    assert "cpmpy" in result["missing_dependencies"]
    assert "minizinc" in result["missing_dependencies"]
    assert "ortools" in result["missing_dependencies"]
    assert "datasets" not in result["missing_dependencies"]


def test_cp_bench_local_eval_writes_blocked_artifact_when_dependencies_missing(
    tmp_path: Path,
) -> None:
    submission = tmp_path / "submission.jsonl"
    submission.write_text(
        '{"id":"csplib__csplib_001_car_sequencing","model":"print(0)"}\n',
        encoding="utf-8",
    )

    result = run_cp_bench_local_eval(
        submission,
        tmp_path / "eval",
        framework="CPMpy",
        dependency_probe=lambda: {
            "status": "blocked_missing_dependencies",
            "missing_dependencies": ["cpmpy"],
            "available_dependencies": ["datasets", "click"],
            "official_scores_claimed": False,
            "manual_submission_required": True,
        },
    )

    assert result["status"] == "blocked_missing_dependencies"
    assert result["official_scores_claimed"] is False
    assert result["manual_submission_required"] is True

    report_path = Path(result["report_path"])
    manifest_path = Path(result["artifact_manifest_path"])
    assert report_path.exists()
    assert manifest_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert report["missing_dependencies"] == ["cpmpy"]
    assert report["submission_validation"]["status"] == "valid"
    assert manifest["official_scores_claimed"] is False


def test_cp_bench_local_eval_invokes_evaluator_with_list_command_and_parses_summary(
    tmp_path: Path,
) -> None:
    submission = tmp_path / "submission.jsonl"
    evaluator = tmp_path / "user_eval.py"
    submission.write_text(
        '{"id":"csplib__csplib_001_car_sequencing","model":"print(0)"}\n',
        encoding="utf-8",
    )
    evaluator.write_text("# evaluator placeholder\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_runner(command: list[str], **kwargs: object):
        captured["command"] = command
        captured["kwargs"] = kwargs
        summary_path = Path(kwargs["cwd"]) / "summary.txt"
        summary_path.write_text(
            """
--- Model: csplib__csplib_001_car_sequencing ---
    0. Found ground-truth model for 'csplib__csplib_001_car_sequencing' in dataset.
    1. Running submitted model...
      - SUCCESS: Model executed successfully.
      - SUCCESS: Got solution: {'sequence': [0]}
    2. Performing solution check on ground-truth model...
      - CONSISTENCY: PASSED
      - OBJECTIVE CHECK: PASSED fully

Overall Evaluation Statistics:
  Total Submitted Models that also exist in the dataset: 1
  Models That Ran Successfully (out of submitted models): 1/1
  Submission coverage perc: 0.62%
  Error perc: 0.00%
  Consistency perc: 0.62%
  Final Solution Accuracy perc: 0.62%
""",
            encoding="utf-8",
        )

        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return Result()

    result = run_cp_bench_local_eval(
        submission,
        tmp_path / "eval",
        framework="CPMpy",
        evaluator_path=evaluator,
        dependency_probe=lambda: {
            "status": "ready",
            "missing_dependencies": [],
            "available_dependencies": ["datasets", "click", "cpmpy", "minizinc", "ortools"],
            "official_scores_claimed": False,
            "manual_submission_required": True,
        },
        runner=fake_runner,
        timeout_seconds=7,
    )

    assert result["status"] == "written"
    assert result["official_scores_claimed"] is False
    assert result["summary"]["final_solution_accuracy_percent"] == 0.62
    runtime_profile = json.loads(
        Path(result["runtime_profile_path"]).read_text(encoding="utf-8")
    )
    assert runtime_profile["command"][0] == "python"
    assert runtime_profile["command"][1] == "user_eval.py"
    assert runtime_profile["command"][3] == "submission.jsonl"
    command = captured["command"]
    assert isinstance(command, list)
    assert command[:2]
    assert "--submission_file" in command
    assert "--modelling_framework" in command
    assert captured["kwargs"]["timeout"] == 7


def test_cp_bench_local_eval_scrubs_local_temp_paths_from_summary_and_streams(
    tmp_path: Path,
) -> None:
    submission = tmp_path / "submission.jsonl"
    evaluator = tmp_path / "user_eval.py"
    submission.write_text(
        '{"id":"csplib__csplib_001_car_sequencing","model":"print(0)"}\n',
        encoding="utf-8",
    )
    evaluator.write_text("# evaluator placeholder\n", encoding="utf-8")

    def fake_runner(command: list[str], **kwargs: object):
        summary_path = Path(kwargs["cwd"]) / "summary.txt"
        summary_path.write_text(
            """
--- Model: csplib__csplib_001_car_sequencing ---
stderr: File "/var/folders/aa/bb/T/cp_bench_eval_x/tmp.py", line 1

Overall Evaluation Statistics:
  Total Submitted Models that also exist in the dataset: 1
  Models That Ran Successfully (out of submitted models): 1/1
  Submission coverage perc: 1.59%
  Error perc: 0.00%
  Consistency perc: 0.00%
  Final Solution Accuracy perc: 0.00%
""",
            encoding="utf-8",
        )

        class Result:
            returncode = 0
            stdout = "ok /private/var/folders/cc/dd/T/cp_bench_eval_y/tmp.py"
            stderr = "err /var/folders/ee/ff/T/cp_bench_eval_z/tmp.py"

        return Result()

    result = run_cp_bench_local_eval(
        submission,
        tmp_path / "eval",
        framework="CPMpy",
        evaluator_path=evaluator,
        dependency_probe=lambda: {
            "status": "ready",
            "missing_dependencies": [],
            "available_dependencies": ["datasets", "click", "cpmpy", "minizinc", "ortools"],
            "official_scores_claimed": False,
            "manual_submission_required": True,
        },
        runner=fake_runner,
    )

    summary_text = Path(result["summary_path"]).read_text(encoding="utf-8")
    stdout_text = (tmp_path / "eval" / "stdout.txt").read_text(encoding="utf-8")
    stderr_text = (tmp_path / "eval" / "stderr.txt").read_text(encoding="utf-8")
    assert "/var/folders" not in summary_text
    assert "/private/var/folders" not in stdout_text
    assert "/var/folders" not in stderr_text
    assert 'File "<local_temp>", line 1' in summary_text
    assert "<local_temp>" in summary_text
    assert "<local_temp>" in stdout_text
    assert "<local_temp>" in stderr_text


def test_cp_bench_local_baseline_real_mode_uses_dataset_problem_ids(
    tmp_path: Path,
) -> None:
    evaluator = tmp_path / "user_eval.py"
    evaluator.write_text("# evaluator placeholder\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_runner(command: list[str], **kwargs: object):
        submission_path = Path(command[command.index("--submission_file") + 1])
        row = json.loads(submission_path.read_text(encoding="utf-8").strip())
        captured["row"] = row
        summary_path = Path(kwargs["cwd"]) / "summary.txt"
        summary_path.write_text(
            """
--- Model: csplib__csplib_001_car_sequencing ---
    0. Found ground-truth model for 'csplib__csplib_001_car_sequencing' in dataset.
    1. Running submitted model...
      - SUCCESS: Model executed successfully.
      - SUCCESS: Got solution: {'sequence': [0]}
    2. Performing solution check on ground-truth model...
      - CONSISTENCY: PASSED
      - OBJECTIVE CHECK: PASSED fully

Overall Evaluation Statistics:
  Total Submitted Models that also exist in the dataset: 1
  Models That Ran Successfully (out of submitted models): 1/1
  Submission coverage perc: 0.62%
  Error perc: 0.00%
  Consistency perc: 0.00%
  Final Solution Accuracy perc: 0.00%
""",
            encoding="utf-8",
        )

        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return Result()

    result = write_cp_bench_local_baseline(
        tmp_path / "real-baseline",
        limit=1,
        framework="CPMpy",
        dry_run=False,
        timeout_seconds=7,
        problem_ids=["real_problem_001"],
        evaluator_path=evaluator,
        dependency_probe=lambda: {
            "status": "ready",
            "missing_dependencies": [],
            "available_dependencies": ["datasets", "click", "cpmpy", "minizinc", "ortools"],
            "official_scores_claimed": False,
            "manual_submission_required": True,
        },
        runner=fake_runner,
    )

    assert result["status"] == "written"
    assert result["dry_run"] is False
    assert result["row_count"] == 1
    assert result["summary"]["runtime_success"] == "1/1"
    assert captured["row"]["id"] == "real_problem_001"
    assert "__ml_research_loop_nonexistent_var__" in captured["row"]["model"]


def test_cp_bench_candidate_round_compares_against_baseline_without_path_leaks(
    tmp_path: Path,
) -> None:
    baseline_report = tmp_path / "baseline.json"
    candidate_submission = tmp_path / "candidate.jsonl"
    proposal = tmp_path / "proposal.json"
    evaluator = tmp_path / "user_eval.py"
    baseline_report.write_text(
        json.dumps({
            "status": "written",
            "summary": {
                "final_solution_accuracy_percent": 0.0,
                "coverage_percent": 1.59,
                "official_scores_claimed": False,
            },
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    candidate_submission.write_text(
        '{"id":"csplib__csplib_001_car_sequencing","model":"print({\\"sequence\\": [0]})"}\n',
        encoding="utf-8",
    )
    proposal.write_text(
        json.dumps({
            "proposal_id": "cp-prop-003",
            "hypothesis": "Use a direct CPMpy model for the first verified problem.",
            "change_type": "code_patch",
            "expected_metric": "final_solution_accuracy_percent",
            "risk": "May only improve one-problem coverage.",
            "rollback_plan": "Keep the negative-control baseline if local eval does not improve.",
        }),
        encoding="utf-8",
    )
    evaluator.write_text("# evaluator placeholder\n", encoding="utf-8")

    def fake_runner(command: list[str], **kwargs: object):
        summary_path = Path(kwargs["cwd"]) / "summary.txt"
        summary_path.write_text(
            """
--- Model: csplib__csplib_001_car_sequencing ---
    0. Found ground-truth model for 'csplib__csplib_001_car_sequencing' in dataset.
    1. Running submitted model...
      - SUCCESS: Model executed successfully.
      - SUCCESS: Got solution: {'sequence': [0]}
    2. Performing solution check on ground-truth model...
      - CONSISTENCY: PASSED
      - OBJECTIVE CHECK: PASSED fully

Overall Evaluation Statistics:
  Total Submitted Models that also exist in the dataset: 1
  Models That Ran Successfully (out of submitted models): 1/1
  Submission coverage perc: 1.59%
  Error perc: 0.00%
  Consistency perc: 1.59%
  Final Solution Accuracy perc: 1.59%
""",
            encoding="utf-8",
        )

        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return Result()

    result = run_cp_bench_candidate_round(
        baseline_report,
        candidate_submission,
        tmp_path / "candidate-round",
        proposal_path=proposal,
        evaluator_path=evaluator,
        dependency_probe=lambda: {
            "status": "ready",
            "missing_dependencies": [],
            "available_dependencies": ["datasets", "click", "cpmpy", "minizinc", "ortools"],
            "official_scores_claimed": False,
            "manual_submission_required": True,
        },
        runner=fake_runner,
    )

    assert result["status"] == "improved"
    assert result["decision"] == "candidate_improved"
    assert result["metric_delta"] == 1.59
    assert result["official_scores_claimed"] is False

    report_path = Path(result["report_path"])
    manifest_path = Path(result["artifact_manifest_path"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    readme = (tmp_path / "candidate-round" / "README.md").read_text(encoding="utf-8")
    assert report["before_summary"]["final_solution_accuracy_percent"] == 0.0
    assert report["after_summary"]["final_solution_accuracy_percent"] == 1.59
    assert report["model_outcomes"][0]["problem_id"] == "csplib__csplib_001_car_sequencing"
    assert report["model_outcomes"][0]["final_passed"] is True
    assert report["model_outcomes"][0]["failure_type"] == "none"
    assert report["failure_summary"]["passed"] == 1
    assert report["rollback_evidence"]["rollback_required"] is False
    assert "csplib__csplib_001_car_sequencing" in readme
    assert "final_passed: `true`" in readme
    assert "candidate_eval_report" in {artifact["role"] for artifact in manifest["artifacts"]}
    assert "rollback_evidence" in {artifact["role"] for artifact in manifest["artifacts"]}
    assert str(tmp_path) not in report_path.read_text(encoding="utf-8")


def test_cp_bench_proposal_context_uses_failure_types_for_client_prompt(
    tmp_path: Path,
) -> None:
    current_report = tmp_path / "candidate-report.json"
    current_report.write_text(
        json.dumps({
            "status": "improved",
            "target_id": "cp-bench-constraint-modeling",
            "after_summary": {"final_solution_accuracy_percent": 3.17},
            "model_outcomes": [
                {
                    "problem_id": "csplib__csplib_001_car_sequencing",
                    "final_passed": True,
                    "failure_type": "none",
                },
                {
                    "problem_id": "csplib__csplib_005_autocorrelation",
                    "final_passed": False,
                    "failure_type": "consistency_or_objective_failed",
                },
            ],
            "official_scores_claimed": False,
            "external_submission_status": "not_submitted",
        }),
        encoding="utf-8",
    )

    result = write_cp_bench_proposal_context(
        current_report,
        tmp_path / "proposal-context",
        max_proposals=2,
    )

    assert result["status"] == "ready_for_client_proposal"
    assert result["official_scores_claimed"] is False
    context = json.loads(Path(result["context_path"]).read_text(encoding="utf-8"))
    prompt = Path(result["prompt_path"]).read_text(encoding="utf-8")
    assert context["failed_outcome_count"] == 1
    assert context["failure_summary"]["by_failure_type"][
        "consistency_or_objective_failed"
    ] == 1
    assert "csplib__csplib_005_autocorrelation" in prompt
    assert "consistency_or_objective_failed" in prompt
    assert "不要上传 Hugging Face" in prompt


def test_cp_bench_proposal_context_infers_legacy_outcome_failure_types(
    tmp_path: Path,
) -> None:
    current_report = tmp_path / "legacy-candidate-report.json"
    current_report.write_text(
        json.dumps({
            "status": "improved",
            "decision": "candidate_improved",
            "after_summary": {"final_solution_accuracy_percent": 3.17},
            "model_outcomes": [
                {"problem_id": "passed_legacy", "final_passed": True},
                {"problem_id": "failed_legacy", "final_passed": False},
            ],
            "official_scores_claimed": False,
            "external_submission_status": "not_submitted",
        }),
        encoding="utf-8",
    )

    result = write_cp_bench_proposal_context(
        current_report,
        tmp_path / "legacy-context",
    )

    context = json.loads(Path(result["context_path"]).read_text(encoding="utf-8"))
    prompt = Path(result["prompt_path"]).read_text(encoding="utf-8")
    assert context["failed_outcome_count"] == 1
    assert context["failed_outcomes"][0]["problem_id"] == "failed_legacy"
    assert context["failed_outcomes"][0]["failure_type"] == "unknown_failed"
    assert "passed_legacy" not in prompt
    assert "failed_legacy" in prompt


def test_cp_bench_client_candidate_submission_records_non_reference_source(
    tmp_path: Path,
) -> None:
    dataset_rows = [
        {
            "id": "csplib__csplib_001_car_sequencing",
            "description": "Car sequencing fixture",
            "input_data": "at_most = [1]",
            "decision_variables": ["sequence"],
            "model": "REFERENCE_MODEL_SHOULD_NOT_BE_COPIED",
        },
        {
            "id": "csplib__csplib_005_autocorrelation",
            "description": "Autocorrelation fixture",
            "input_data": "n = 10",
            "decision_variables": ["sequence", "E"],
            "model": "REFERENCE_MODEL_SHOULD_NOT_BE_COPIED",
        },
        {
            "id": "csplib__csplib_008_vessel_loading",
            "description": "Vessel loading fixture",
            "input_data": "deck_width = 5",
            "decision_variables": ["left", "right", "bottom", "top"],
            "model": "REFERENCE_MODEL_SHOULD_NOT_BE_COPIED",
        },
        {
            "id": "unknown_problem",
            "description": "Uncovered fixture",
            "input_data": "",
            "decision_variables": ["x"],
            "model": "REFERENCE_MODEL_SHOULD_NOT_BE_COPIED",
        },
    ]

    result = write_cp_bench_client_candidate_submission(
        tmp_path / "p13-client-candidate",
        limit=4,
        dataset_rows=dataset_rows,
        strategy="handcrafted-small-cpmpy-v1",
    )

    assert result["status"] == "partial_generated"
    assert result["generated_count"] == 3
    assert result["fallback_count"] == 1
    assert result["reference_model_field_accessed"] is False
    assert result["official_scores_claimed"] is False

    submission_text = Path(result["submission_path"]).read_text(encoding="utf-8")
    source_audit = json.loads(Path(result["source_audit_path"]).read_text(encoding="utf-8"))
    manifest = json.loads(Path(result["artifact_manifest_path"]).read_text(encoding="utf-8"))
    assert len([line for line in submission_text.splitlines() if line.strip()]) == 4
    assert "REFERENCE_MODEL_SHOULD_NOT_BE_COPIED" not in submission_text
    assert source_audit["reference_model_field_accessed"] is False
    assert source_audit["generated_count"] == 3
    assert source_audit["fallback_problem_ids"] == ["unknown_problem"]
    assert source_audit["source_policy"] == "no_reference_model_field"
    assert "source_audit" in {artifact["role"] for artifact in manifest["artifacts"]}


def test_cp_bench_proposal_contract_rejects_disallowed_change_type() -> None:
    proposal = {
        "proposal_id": "cp-prop-001",
        "hypothesis": "Try uploading directly.",
        "change_type": "external_upload",
        "expected_metric": "final_solution_accuracy_percent",
        "risk": "Would bypass manual gate.",
        "rollback_plan": "Do not upload.",
    }

    result = validate_cp_bench_proposal(proposal)

    assert result["status"] == "invalid"
    assert result["official_scores_claimed"] is False
    assert "change_type" in result["error_message"]


def test_cp_bench_proposal_round_writes_rejection_and_rollback_evidence(
    tmp_path: Path,
) -> None:
    baseline_report = tmp_path / "baseline.json"
    proposal = tmp_path / "proposal.json"
    baseline_report.write_text(
        json.dumps({
            "status": "blocked_missing_dependencies",
            "summary": {"final_solution_accuracy_percent": 0.0},
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    proposal.write_text(
        json.dumps({
            "proposal_id": "cp-prop-001",
            "hypothesis": "Upload directly.",
            "change_type": "external_upload",
            "expected_metric": "final_solution_accuracy_percent",
            "risk": "Bypass manual gate.",
            "rollback_plan": "Reject before execution.",
        }),
        encoding="utf-8",
    )

    result = run_cp_bench_proposal_round(
        baseline_report,
        proposal,
        tmp_path / "proposal-round",
    )

    assert result["status"] == "rejected_by_guard"
    assert result["official_scores_claimed"] is False
    assert result["decision"] == "rollback_recorded"

    report = json.loads(Path(result["report_path"]).read_text(encoding="utf-8"))
    rollback = json.loads(Path(result["rollback_evidence_path"]).read_text(encoding="utf-8"))
    assert report["proposal_validation"]["status"] == "invalid"
    assert rollback["rollback_required"] is True
    assert rollback["reason"] == "proposal_rejected_by_guard"


def test_cp_bench_proposal_round_blocks_execution_until_local_eval_exists(
    tmp_path: Path,
) -> None:
    baseline_report = tmp_path / "baseline.json"
    proposal = tmp_path / "proposal.json"
    baseline_report.write_text(
        json.dumps({
            "status": "blocked_missing_dependencies",
            "summary": {"final_solution_accuracy_percent": 0.0},
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    proposal.write_text(
        json.dumps({
            "proposal_id": "cp-prop-002",
            "hypothesis": "Switch to MiniZinc for clearer global constraints.",
            "change_type": "framework_switch",
            "expected_metric": "final_solution_accuracy_percent",
            "risk": "MiniZinc solver may be unavailable.",
            "rollback_plan": "Return to CPMpy baseline if dependency gate fails.",
        }),
        encoding="utf-8",
    )

    result = run_cp_bench_proposal_round(
        baseline_report,
        proposal,
        tmp_path / "proposal-round",
    )

    assert result["status"] == "blocked_pending_local_eval"
    assert result["decision"] == "defer_execution"
    assert result["official_scores_claimed"] is False
    report = json.loads(Path(result["report_path"]).read_text(encoding="utf-8"))
    assert report["before_summary"]["final_solution_accuracy_percent"] == 0.0
    assert report["after_summary"] is None


def test_cp_bench_submission_gate_writes_manual_review_bundle(tmp_path: Path) -> None:
    submission = tmp_path / "submission.jsonl"
    source_report = tmp_path / "local-eval-report.json"
    submission.write_text(
        '{"id":"csplib__csplib_001_car_sequencing","model":"print(0)"}\n',
        encoding="utf-8",
    )
    source_report.write_text(
        json.dumps({
            "status": "blocked_missing_dependencies",
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    result = write_cp_bench_submission_gate(
        submission,
        tmp_path / "submission-gate",
        source_report_path=source_report,
    )

    assert result["status"] == "written"
    assert result["external_submission_status"] == "not_submitted"
    assert result["official_scores_claimed"] is False
    assert result["manual_submission_required"] is True

    output = tmp_path / "submission-gate"
    assert (output / "submission.jsonl").exists()
    assert (output / "submission-report.md").exists()
    assert (output / "manual-checklist.md").exists()
    assert (output / "artifact-manifest.json").exists()
    assert (output / "SHA256SUMS").exists()
    checklist = (output / "manual-checklist.md").read_text(encoding="utf-8")
    manifest = json.loads((output / "artifact-manifest.json").read_text(encoding="utf-8"))
    assert "official_scores_claimed: `false`" in checklist
    assert "submission.jsonl" in (output / "SHA256SUMS").read_text(encoding="utf-8")
    assert manifest["official_scores_claimed"] is False
