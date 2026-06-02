from __future__ import annotations

import json
from pathlib import Path

from scripts.cp_bench_from_dcp_candidates import build_cp_submission_from_dcp


def test_build_cp_submission_from_dcp_maps_direct_and_aplai_aliases(tmp_path: Path) -> None:
    cp_dataset = tmp_path / "cp_verified.jsonl"
    dcp_submission = tmp_path / "dcp_submission.jsonl"
    output_dir = tmp_path / "cp-from-dcp"
    cp_dataset.write_text(
        "\n".join(
            [
                json.dumps({"id": "csplib__csplib_001_car_sequencing"}),
                json.dumps({"id": "aplai_course__2_color_simple"}),
                json.dumps({"id": "cpmpy_examples__resource_constrained_project_scheduling"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    dcp_submission.write_text(
        "\n".join(
            [
                json.dumps({"id": "csplib_001_car_sequencing", "model": "print('direct')"}),
                json.dumps({"id": "session2_color_simple", "model": "print('alias')"}),
                json.dumps({"id": "unrelated", "model": "print('skip')"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = build_cp_submission_from_dcp(
        cp_dataset_path=cp_dataset,
        dcp_submission_path=dcp_submission,
        output_dir=output_dir,
        source_label="unit-test DCP candidates",
    )

    records = [
        json.loads(line)
        for line in (output_dir / "submission.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert payload["status"] == "written"
    assert payload["cp_dataset_count"] == 3
    assert payload["mapped_count"] == 2
    assert payload["missing_count"] == 1
    assert payload["alias_mapped_count"] == 1
    assert payload["mapped_cp_ids"] == [
        "csplib__csplib_001_car_sequencing",
        "aplai_course__2_color_simple",
    ]
    assert payload["missing_cp_ids"] == [
        "cpmpy_examples__resource_constrained_project_scheduling"
    ]
    assert records == [
        {"id": "csplib__csplib_001_car_sequencing", "model": "print('direct')"},
        {"id": "aplai_course__2_color_simple", "model": "print('alias')"},
    ]
    assert payload["official_scores_claimed"] is False
    assert payload["external_submission_status"] == "not_submitted"
    report_text = (output_dir / "candidate-build-report.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in report_text
    assert (output_dir / "source-audit.json").exists()
    assert (output_dir / "README.md").exists()
    assert (output_dir / "artifact-manifest.json").exists()
    assert (output_dir / "SHA256SUMS").exists()


def test_build_cp_submission_from_dcp_records_dcp_pass_fail_overlap(
    tmp_path: Path,
) -> None:
    cp_dataset = tmp_path / "cp_verified.jsonl"
    dcp_submission = tmp_path / "dcp_submission.jsonl"
    dcp_report = tmp_path / "dcp-report.json"
    output_dir = tmp_path / "cp-from-dcp"
    cp_dataset.write_text(
        "\n".join(
            [
                json.dumps({"id": "hakan_examples__coins_grid"}),
                json.dumps({"id": "hakan_examples__zebra"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    dcp_submission.write_text(
        "\n".join(
            [
                json.dumps({"id": "coins_grid", "model": "print('failed')"}),
                json.dumps({"id": "zebra", "model": "print('passed')"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    dcp_report.write_text(
        json.dumps({"failed_model_ids": ["coins_grid"]}) + "\n",
        encoding="utf-8",
    )

    payload = build_cp_submission_from_dcp(
        cp_dataset_path=cp_dataset,
        dcp_submission_path=dcp_submission,
        output_dir=output_dir,
        dcp_eval_report_path=dcp_report,
        source_label="unit-test DCP candidates",
    )

    assert payload["dcp_failed_overlap_count"] == 1
    assert payload["dcp_passed_overlap_count"] == 1
    assert payload["dcp_failed_overlap"] == [
        {"cp_id": "hakan_examples__coins_grid", "dcp_id": "coins_grid"}
    ]
