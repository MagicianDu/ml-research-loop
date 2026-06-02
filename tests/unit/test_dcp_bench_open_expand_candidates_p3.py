from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts.dcp_bench_open_expand_candidates import FORBIDDEN_CANDIDATE_CODE_MARKERS
from scripts.dcp_bench_open_expand_candidates_p3 import (
    P3_EXPECTED_CANDIDATE_IDS,
    build_p3_expanded_submission,
    get_p3_candidate_records,
)


def test_p3_candidate_records_do_not_use_reference_artifacts() -> None:
    records = get_p3_candidate_records()

    assert len(records) >= 18
    assert {record["id"] for record in records} == set(P3_EXPECTED_CANDIDATE_IDS)
    for record in records:
        assert set(record) == {"id", "model"}
        for marker in FORBIDDEN_CANDIDATE_CODE_MARKERS:
            assert marker not in record["model"]


def test_p3_candidate_models_solve_representative_public_instances() -> None:
    records = {record["id"]: record for record in get_p3_candidate_records()}

    dinner = _run_model(records["dinner"]["model"])
    assert dinner == {"grandparents": 1, "parents": 5, "children": 14}

    magic = _run_model(records["csplib_019_magic_squares_and_sequences"]["model"])["x"]
    assert len(magic) == 12
    assert [magic.count(idx) for idx in range(12)] == magic

    account = _run_model(records["just_forgotten"]["model"])["x"]
    assert sorted(account) == list(range(10))
    guesses = [
        [9, 4, 6, 2, 1, 5, 7, 8, 3, 0],
        [8, 6, 0, 4, 3, 9, 1, 2, 5, 7],
        [1, 6, 4, 0, 2, 9, 7, 8, 5, 3],
        [6, 8, 2, 4, 3, 1, 9, 0, 7, 5],
    ]
    assert [sum(a == b for a, b in zip(account, guess)) for guess in guesses] == [4, 4, 4, 4]

    futoshiki = _run_model(records["futoshiki"]["model"])["grid"]
    assert _is_latin_square_1_to_5(futoshiki)
    assert futoshiki[0][2] == 3
    assert futoshiki[0][3] == 2
    assert _futoshiki_inequalities_hold(futoshiki)

    de_bruijn = _run_model(records["de_bruijn_sequence"]["model"])["de_bruijn"]
    assert len(de_bruijn) == 16
    assert set(de_bruijn) <= {0, 1}
    assert len(_cyclic_windows(de_bruijn, 4)) == 16

    warehouse = _run_model(records["csplib_034_warehouse_location"]["model"])
    assert warehouse["total_cost"] == _warehouse_cost(warehouse)
    assert _warehouse_assignment_is_feasible(warehouse)

    aircraft = _run_model(records["aircraft_landing"]["model"])
    assert aircraft["landing_times"] == [1, 3, 7]
    assert aircraft["total_penalty"] == 50

    jobshop = _run_model(records["jobshop"]["model"])
    assert jobshop["makespan"] == 11


def test_build_p3_expanded_submission_preserves_base_and_writes_audit(tmp_path: Path) -> None:
    base_submission = tmp_path / "base.jsonl"
    base_submission.write_text(
        json.dumps({"id": "dinner", "model": "print('base wins')"}) + "\n"
        + json.dumps({"id": "existing_problem", "model": "print('keep me')"}) + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "p3"
    result = build_p3_expanded_submission(
        base_submission_path=base_submission,
        output_dir=output_dir,
        source_label="unit-test-p2",
    )
    submission_records = [
        json.loads(line)
        for line in (output_dir / "submission.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    ids = [record["id"] for record in submission_records]
    audit = json.loads((output_dir / "source-audit.json").read_text(encoding="utf-8"))

    assert ids[:2] == ["dinner", "existing_problem"]
    assert ids.count("dinner") == 1
    assert result["base_candidate_count"] == 2
    assert result["added_candidate_count"] == len(P3_EXPECTED_CANDIDATE_IDS) - 1
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


def _is_latin_square_1_to_5(grid: list[list[int]]) -> bool:
    target = [1, 2, 3, 4, 5]
    return all(sorted(row) == target for row in grid) and all(
        sorted(grid[row][col] for row in range(5)) == target for col in range(5)
    )


def _futoshiki_inequalities_hold(grid: list[list[int]]) -> bool:
    inequalities = [
        [1, 2, 1, 1],
        [1, 4, 1, 5],
        [2, 3, 1, 3],
        [3, 3, 2, 3],
        [3, 4, 2, 4],
        [2, 5, 3, 5],
        [3, 2, 4, 2],
        [4, 4, 4, 3],
        [5, 2, 5, 1],
        [5, 4, 5, 3],
        [5, 5, 4, 5],
    ]
    return all(grid[r1 - 1][c1 - 1] < grid[r2 - 1][c2 - 1] for r1, c1, r2, c2 in inequalities)


def _cyclic_windows(values: list[int], size: int) -> set[tuple[int, ...]]:
    return {
        tuple(values[(start + offset) % len(values)] for offset in range(size))
        for start in range(len(values))
    }


def _warehouse_cost(payload: dict[str, object]) -> int:
    building_cost = 30
    cost_matrix = [
        [20, 24, 11, 25, 30],
        [28, 27, 82, 83, 74],
        [74, 97, 71, 96, 70],
        [2, 55, 73, 69, 61],
        [46, 96, 59, 83, 4],
        [42, 22, 29, 67, 59],
        [1, 5, 73, 59, 56],
        [10, 73, 13, 43, 96],
        [93, 35, 63, 85, 46],
        [47, 65, 55, 71, 95],
    ]
    open_warehouses = payload["open_warehouses"]
    supplier_assignment = payload["supplier_assignment"]
    return sum(open_warehouses) * building_cost + sum(
        cost_matrix[store][warehouse] for store, warehouse in enumerate(supplier_assignment)
    )


def _warehouse_assignment_is_feasible(payload: dict[str, object]) -> bool:
    capacity = [1, 4, 2, 1, 3]
    open_warehouses = payload["open_warehouses"]
    supplier_assignment = payload["supplier_assignment"]
    if len(supplier_assignment) != 10:
        return False
    counts = [supplier_assignment.count(warehouse) for warehouse in range(5)]
    return all(
        bool(open_warehouses[warehouse]) == (counts[warehouse] > 0)
        and counts[warehouse] <= capacity[warehouse]
        for warehouse in range(5)
    )
