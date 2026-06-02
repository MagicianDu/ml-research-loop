from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts.dcp_bench_open_expand_candidates import FORBIDDEN_CANDIDATE_CODE_MARKERS
from scripts.dcp_bench_open_expand_candidates_p2 import (
    P2_EXPECTED_CANDIDATE_IDS,
    build_p2_expanded_submission,
    get_p2_candidate_records,
)


def test_p2_candidate_records_do_not_use_reference_artifacts() -> None:
    records = get_p2_candidate_records()

    assert len(records) >= 20
    assert {record["id"] for record in records} == set(P2_EXPECTED_CANDIDATE_IDS)
    for record in records:
        assert set(record) == {"id", "model"}
        for marker in FORBIDDEN_CANDIDATE_CODE_MARKERS:
            assert marker not in record["model"]


def test_p2_candidate_models_solve_representative_public_instances() -> None:
    records = {record["id"]: record for record in get_p2_candidate_records()}

    independent = _run_model(records["session2_maximal_independent_sets"]["model"])["nodes"]
    assert _is_maximal_independent_set(independent)
    assert sum(independent) == 4

    media = _run_model(records["media_selection"]["model"])
    assert media == {"is_selected": [True, True, False], "min_total_cost": 25}

    arch = _run_model(records["arch_friends"]["model"])
    assert set(arch.values()) == {1, 2, 3, 4}
    assert arch["fuchsiaflats"] == arch["heelsinahandcart"]
    assert arch["purplepumps"] < 4
    assert arch["purplepumps"] + 1 != arch["tootsies"]
    assert arch["footfarm"] == 2
    assert arch["theshoepalace"] + 2 == arch["suedesandals"]

    bus_driver = _run_model(records["csplib_022_bus_driver_scheduling"]["model"])["x"]
    assert _covers_each_work_piece_once(bus_driver)

    number = _run_model(records["divisible_by_1_through_9"]["model"])["number"]
    assert sorted(str(number)) == list("0123456789")
    assert all(int(str(number)[:idx]) % idx == 0 for idx in range(1, 11))

    bowls = _run_model(records["bowls_and_oranges"]["model"])["x"]
    assert len(bowls) == 9
    assert len(set(bowls)) == 9
    assert all(1 <= bowl <= 40 for bowl in bowls)
    assert _has_no_three_term_arithmetic_progression(bowls)

    cows = _run_model(records["session3_farmer_and_cows"]["model"])["cow_assignments"]
    assert len(cows) == 25
    assert [cows.count(son) for son in range(5)] == [7, 6, 5, 4, 3]
    assert {sum(idx + 1 for idx, son in enumerate(cows) if son == group) for group in range(5)} == {65}


def test_build_p2_expanded_submission_preserves_base_and_writes_audit(tmp_path: Path) -> None:
    base_submission = tmp_path / "base.jsonl"
    base_submission.write_text(
        json.dumps({"id": "media_selection", "model": "print('base wins')"}) + "\n"
        + json.dumps({"id": "existing_problem", "model": "print('keep me')"}) + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "p2"
    result = build_p2_expanded_submission(
        base_submission_path=base_submission,
        output_dir=output_dir,
        source_label="unit-test-p1",
    )
    submission_records = [
        json.loads(line)
        for line in (output_dir / "submission.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    ids = [record["id"] for record in submission_records]
    audit = json.loads((output_dir / "source-audit.json").read_text(encoding="utf-8"))

    assert ids[:2] == ["media_selection", "existing_problem"]
    assert ids.count("media_selection") == 1
    assert result["base_candidate_count"] == 2
    assert result["added_candidate_count"] == len(P2_EXPECTED_CANDIDATE_IDS) - 1
    assert result["official_scores_claimed"] is False
    assert result["external_submission_status"] == "not_submitted"
    assert audit["source_policy"] == "description_and_instance_only_no_dcp_reference"
    assert audit["runtime_dataset_file_access"] is False
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


def _is_maximal_independent_set(nodes: list[bool]) -> bool:
    adjacency = [
        [2, 3, 7],
        [1, 4, 8],
        [1, 4, 5],
        [2, 3, 6],
        [3, 6, 7],
        [4, 5, 8],
        [1, 5, 8],
        [2, 6, 7],
    ]
    selected = {idx + 1 for idx, value in enumerate(nodes) if value}
    for node, neighbors in enumerate(adjacency, start=1):
        if node in selected and selected.intersection(neighbors):
            return False
    for node in range(1, len(nodes) + 1):
        if node not in selected and not selected.intersection(adjacency[node - 1]):
            return False
    return True


def _covers_each_work_piece_once(selected_shifts: list[int]) -> bool:
    shifts = [
        [0, 1, 2],
        [0, 1, 2, 3],
        [2, 3, 4, 5],
        [4, 5],
        [6, 7],
        [6, 7, 8],
        [8, 9],
        [8, 9, 10],
        [10, 11],
        [0, 4, 8],
        [0, 5, 10],
        [1, 6, 11],
        [2, 7, 9],
        [3, 6, 8],
    ]
    counts = [0] * 12
    for is_selected, tasks in zip(selected_shifts, shifts):
        if is_selected:
            for task in tasks:
                counts[task] += 1
    return counts == [1] * 12


def _has_no_three_term_arithmetic_progression(values: list[int]) -> bool:
    selected = set(values)
    return not any(
        left < middle < right and left + right == 2 * middle
        for left in selected
        for middle in selected
        for right in selected
    )
