from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts.dcp_bench_open_expand_candidates import (
    FORBIDDEN_CANDIDATE_CODE_MARKERS,
    build_expanded_submission,
    get_extra_candidate_records,
)


def test_extra_candidate_records_do_not_use_reference_artifacts() -> None:
    records = get_extra_candidate_records()

    assert len(records) >= 10
    assert len({record["id"] for record in records}) == len(records)
    for record in records:
        assert set(record) == {"id", "model"}
        for marker in FORBIDDEN_CANDIDATE_CODE_MARKERS:
            assert marker not in record["model"]


def test_extra_candidate_records_repair_guards_and_skip_ambiguous_broken_weights() -> None:
    records = {record["id"]: record for record in get_extra_candidate_records()}

    assert "broken_weights" not in records
    assert '{"killer": 0}' not in records["who_killed_agatha"]["model"]
    assert '{"killer":0}' not in records["who_killed_agatha"]["model"]
    result = _run_model(records["session1_guards_and_apples"]["model"])

    assert result == {"apples": [94, 46, 22, 10, 4, 1]}


def test_build_expanded_submission_preserves_base_and_writes_audit(tmp_path: Path) -> None:
    base_submission = tmp_path / "base.jsonl"
    base_submission.write_text(
        json.dumps({"id": "fibonacci_even", "model": "print('base wins')"}) + "\n"
        + json.dumps({"id": "existing_problem", "model": "print('keep me')"}) + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "expanded"
    result = build_expanded_submission(
        base_submission_path=base_submission,
        output_dir=output_dir,
        source_label="unit-test-base",
    )

    submission_records = [
        json.loads(line)
        for line in (output_dir / "submission.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    ids = [record["id"] for record in submission_records]
    audit = json.loads((output_dir / "source-audit.json").read_text(encoding="utf-8"))

    assert ids.count("fibonacci_even") == 1
    assert ids[:2] == ["fibonacci_even", "existing_problem"]
    assert result["base_candidate_count"] == 2
    assert result["added_candidate_count"] == len(get_extra_candidate_records()) - 1
    assert result["official_scores_claimed"] is False
    assert result["external_submission_status"] == "not_submitted"
    assert audit["source_policy"] == "description_and_instance_only_no_dcp_reference"
    assert audit["dcp_reference_model_used_for_generation"] is False
    assert audit["dcp_example_solution_used_for_generation"] is False
    assert (output_dir / "artifact-manifest.json").exists()
    assert (output_dir / "SHA256SUMS").exists()


def _run_model(model_code: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "candidate.py"
        path.write_text(model_code, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
    return json.loads(result.stdout)
