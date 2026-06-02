from __future__ import annotations

import json
from pathlib import Path

from scripts.dcp_bench_open_migration_gate import (
    build_migration_gate,
    normalize_dcp_problem_id,
    parse_dcp_eval_summary,
)


def test_normalize_dcp_problem_id_removes_cp_bench_source_prefix() -> None:
    assert normalize_dcp_problem_id("csplib__csplib_001_car_sequencing") == (
        "csplib_001_car_sequencing"
    )
    assert normalize_dcp_problem_id("hakan_examples__abbots_puzzle") == "abbots_puzzle"
    assert normalize_dcp_problem_id("already_dcp") == "already_dcp"


def test_parse_dcp_eval_summary_extracts_metrics_and_failures(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.txt"
    temp_path = "/" + "var" + "/" + "folders" + "/raw/path.py"
    summary_path.write_text(
        "\n".join(
            [
                "--- Model: ok_problem ---",
                "    0. Found ground-truth model for 'ok_problem' in dataset.",
                "    1. Running submitted model...",
                "      - SUCCESS: Model executed successfully.",
                "      - SUCCESS: Got solution: {'x': [1]}",
                "    2. Performing solution check on ground-truth model...",
                "      - CONSISTENCY: PASSED",
                "      - OBJECTIVE CHECK: PASSED fully",
                "--- Model: bad_problem ---",
                "    0. Found ground-truth model for 'bad_problem' in dataset.",
                "    1. Running submitted model...",
                "      - SUCCESS: Model executed successfully.",
                "    2. Performing solution check on ground-truth model...",
                f"      - CONSISTENCY: FAILED, stdout: {temp_path}",
                "stderr: ",
                "==============================",
                "Overall Evaluation Statistics:",
                "  Total Submitted Models that also exist in the dataset: 2",
                "  Models That Ran Successfully (out of submitted models): 2/2",
                "  Submission coverage perc: 20.73%",
                "  Error perc: 0.00%",
                "  Consistency perc: 10.00%",
                "  Final Solution Accuracy perc: 10.00%",
                "  Final Solution Accuracy perc (considering only submitted models): 50.00%",
                "------------------------------",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    parsed = parse_dcp_eval_summary(summary_path)

    assert parsed["total_submitted_models"] == 2
    assert parsed["models_ran_successfully"] == 2
    assert parsed["submission_coverage_percent"] == 20.73
    assert parsed["final_solution_accuracy_percent"] == 10.0
    assert parsed["submitted_solution_accuracy_percent"] == 50.0
    assert parsed["passed_model_ids"] == ["ok_problem"]
    assert parsed["failed_model_ids"] == ["bad_problem"]
    assert parsed["sanitized_summary"].count("<temporary_evaluator_script>") == 1
    assert not any(line.endswith(" ") for line in parsed["sanitized_summary"].splitlines())


def test_build_migration_gate_writes_no_reference_artifacts(tmp_path: Path) -> None:
    cp_submission_path = tmp_path / "cp-submission.jsonl"
    cp_submission_path.write_text(
        json.dumps(
            {
                "id": "csplib__csplib_001_car_sequencing",
                "model": "from cpmpy import *\nimport json\nprint(json.dumps({'sequence': [0, 1]}))",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    dcp_dataset_path = tmp_path / "dcp-bench-open.jsonl"
    dcp_dataset_path.write_text(
        json.dumps(
            {
                "id": "csplib_001_car_sequencing",
                "model": "GROUND_TRUTH_MODEL",
                "example_instance": "data = 1",
                "example_solution": {"sequence": [1, 0]},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    summary_path = tmp_path / "summary.txt"
    summary_path.write_text(
        "\n".join(
            [
                "--- Model: csplib_001_car_sequencing ---",
                "      - CONSISTENCY: PASSED",
                "      - OBJECTIVE CHECK: PASSED fully",
                "Overall Evaluation Statistics:",
                "  Total Submitted Models that also exist in the dataset: 1",
                "  Models That Ran Successfully (out of submitted models): 1/1",
                "  Submission coverage perc: 100.00%",
                "  Error perc: 0.00%",
                "  Consistency perc: 100.00%",
                "  Final Solution Accuracy perc: 100.00%",
                "  Final Solution Accuracy perc (considering only submitted models): 100.00%",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "gate"
    result = build_migration_gate(
        cp_submission_path=cp_submission_path,
        dcp_dataset_path=dcp_dataset_path,
        dcp_summary_path=summary_path,
        output_dir=output_dir,
        dcp_release="v0.1.0",
        dcp_commit="5bef2ce",
        candidate_source_label="unit-test expanded candidates",
    )

    assert result["status"] == "written"
    assert result["candidate_source_label"] == "unit-test expanded candidates"
    assert result["official_scores_claimed"] is False
    assert result["external_submission_status"] == "not_submitted"
    assert result["dcp_model_exact_match_count"] == 0
    assert result["dcp_example_solution_literal_match_count"] == 0
    assert (output_dir / "submission.jsonl").read_text(encoding="utf-8").startswith(
        '{"id": "csplib_001_car_sequencing"'
    )
    assert (output_dir / "evaluation-summary.txt").exists()
    assert (output_dir / "source-audit.json").exists()
    assert (output_dir / "artifact-manifest.json").exists()
    assert (output_dir / "SHA256SUMS").exists()
    source_audit = json.loads((output_dir / "source-audit.json").read_text(encoding="utf-8"))
    assert source_audit["candidate_model_source"] == "unit-test expanded candidates"
    readme = (output_dir / "README.md").read_text(encoding="utf-8")
    assert "unit-test expanded candidates" in readme
