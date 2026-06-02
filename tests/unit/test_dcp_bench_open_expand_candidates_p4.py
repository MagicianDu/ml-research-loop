from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts.dcp_bench_open_expand_candidates import FORBIDDEN_CANDIDATE_CODE_MARKERS
from scripts.dcp_bench_open_expand_candidates_p4 import (
    P4_EXPECTED_CANDIDATE_IDS,
    build_p4_expanded_submission,
    get_p4_candidate_records,
)


def test_p4_candidate_records_do_not_use_reference_artifacts() -> None:
    records = get_p4_candidate_records()

    assert len(records) == 18
    assert {record["id"] for record in records} == set(P4_EXPECTED_CANDIDATE_IDS)
    for record in records:
        assert set(record) == {"id", "model"}
        for marker in FORBIDDEN_CANDIDATE_CODE_MARKERS:
            assert marker not in record["model"]


def test_p4_candidate_models_solve_public_instances() -> None:
    records = {record["id"]: record for record in get_p4_candidate_records()}

    zebra = _run_model(records["zebra"]["model"])
    assert _zebra_solution_is_valid(zebra)

    assert _run_model(records["diet"]["model"]) == {"cost": 90}
    assert _sudoku_solution_is_valid(_run_model(records["sudoku"]["model"])["grid"])

    langford = _run_model(records["csplib_024_langford"]["model"])["sol"]
    assert _langford_solution_is_valid(langford, 12)

    all_interval = _run_model(records["csplib_007_all_interval"]["model"])
    assert sorted(all_interval["x"]) == list(range(12))
    assert sorted(all_interval["diffs"]) == list(range(1, 12))
    assert all_interval["diffs"] == [
        abs(all_interval["x"][idx + 1] - all_interval["x"][idx]) for idx in range(11)
    ]

    dudeney = _run_model(records["dudeney_numbers"]["model"])["number"]
    assert dudeney > 1
    root = round(dudeney ** (1 / 3))
    assert root**3 == dudeney
    assert sum(int(digit) for digit in str(dudeney)) == root

    clock = _run_model(records["clock_triplets"]["model"])["x"]
    assert sorted(clock) == list(range(1, 13))
    assert all(clock[idx] + clock[(idx + 1) % 12] + clock[(idx + 2) % 12] <= 21 for idx in range(12))

    assert _run_model(records["fancy_dress"]["model"]) == {"t": 1, "h": 0, "r": 1, "s": 0, "n": 0}

    winning_cards = _run_model(records["set_game"]["model"])["winning_cards"]
    assert _set_cards_form_set(winning_cards)

    colors = _run_model(records["session2_color_simple"]["model"])["colors"]
    assert _country_coloring_is_valid(colors)

    seating = _run_model(records["best_host"]["model"])["x"]
    assert _best_host_conflicts(seating) == 0

    islands = _run_model(records["four_islands"]["model"])
    assert _four_islands_solution_is_valid(islands)

    magic = _run_model(records["csplib_023_magic_hexagon"]["model"])["LD"]
    assert _magic_hexagon_solution_is_valid(magic)

    calvin = _run_model(records["calvin_puzzle"]["model"])["x"]
    assert _calvin_solution_is_valid(calvin)

    brigands = _run_model(records["five_brigands"]["model"])
    assert _five_brigands_solution_is_valid(brigands)

    assert _run_model(records["flowshop_scheduling"]["model"]) == {"makespan": 24}

    packing = _run_model(records["packing_rectangles"]["model"])
    assert _packing_solution_is_valid(packing)

    frog = _run_model(records["frog_circle"]["model"])["x"]
    assert _frog_circle_solution_is_valid(frog)


def test_build_p4_expanded_submission_preserves_base_and_writes_audit(tmp_path: Path) -> None:
    base_submission = tmp_path / "base.jsonl"
    base_submission.write_text(
        json.dumps({"id": "zebra", "model": "print('base wins')"}) + "\n"
        + json.dumps({"id": "existing_problem", "model": "print('keep me')"}) + "\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "p4"
    result = build_p4_expanded_submission(
        base_submission_path=base_submission,
        output_dir=output_dir,
        source_label="unit-test-p3",
    )
    submission_records = [
        json.loads(line)
        for line in (output_dir / "submission.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    ids = [record["id"] for record in submission_records]
    audit = json.loads((output_dir / "source-audit.json").read_text(encoding="utf-8"))

    assert ids[:2] == ["zebra", "existing_problem"]
    assert ids.count("zebra") == 1
    assert result["base_candidate_count"] == 2
    assert result["added_candidate_count"] == len(P4_EXPECTED_CANDIDATE_IDS) - 1
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


def _zebra_solution_is_valid(payload: dict[str, object]) -> bool:
    colors = payload["colors"]
    nations = payload["nations"]
    jobs = payload["jobs"]
    pets = payload["pets"]
    drinks = payload["drinks"]
    if not all(sorted(values) == list(range(5)) for values in (colors, nations, jobs, pets, drinks)):
        return False
    yellow, green, red, white, blue = colors
    italy, spain, japan, england, norway = nations
    cat, zebra, bear, snails, horse = pets
    milk, water, tea, coffee, juice = drinks
    painter, sculptor, diplomat, pianist, doctor = jobs
    return all(
        [
            painter == horse,
            diplomat == coffee,
            milk == white,
            spain == painter,
            england == red,
            snails == sculptor,
            green + 1 == red,
            norway == blue + 1,
            doctor == milk,
            diplomat == japan,
            norway == zebra,
            abs(green - white) == 1,
            abs(horse - diplomat) == 1,
            italy in {red, white, green},
            cat in set(range(5)),
            water in set(range(5)),
            tea in set(range(5)),
            juice in set(range(5)),
            yellow in set(range(5)),
            bear in set(range(5)),
            pianist in set(range(5)),
        ]
    )


def _sudoku_solution_is_valid(grid: list[list[int]]) -> bool:
    givens = [
        [0, 0, 0, 2, 0, 5, 0, 0, 0],
        [0, 9, 0, 0, 0, 0, 7, 3, 0],
        [0, 0, 2, 0, 0, 9, 0, 6, 0],
        [2, 0, 0, 0, 0, 0, 4, 0, 9],
        [0, 0, 0, 0, 7, 0, 0, 0, 0],
        [6, 0, 9, 0, 0, 0, 0, 0, 1],
        [0, 8, 0, 4, 0, 0, 1, 0, 0],
        [0, 6, 3, 0, 0, 0, 0, 8, 0],
        [0, 0, 0, 6, 0, 8, 0, 0, 0],
    ]
    target = list(range(1, 10))
    return (
        all(sorted(row) == target for row in grid)
        and all(sorted(grid[row][col] for row in range(9)) == target for col in range(9))
        and all(
            sorted(grid[row][col] for row in range(box_r, box_r + 3) for col in range(box_c, box_c + 3)) == target
            for box_r in (0, 3, 6)
            for box_c in (0, 3, 6)
        )
        and all(givens[row][col] in {0, grid[row][col]} for row in range(9) for col in range(9))
    )


def _langford_solution_is_valid(values: list[int], k: int) -> bool:
    return len(values) == 2 * k and all(
        values.count(number) == 2
        and values.index(number, values.index(number) + 1) - values.index(number) == number + 1
        for number in range(1, k + 1)
    )


def _set_cards_form_set(indices: list[int]) -> bool:
    cards = [
        [1, 2, 3, 1],
        [2, 3, 1, 2],
        [3, 3, 3, 1],
        [3, 1, 1, 1],
        [1, 3, 3, 1],
        [1, 2, 1, 1],
        [2, 1, 2, 1],
        [3, 1, 2, 3],
        [3, 1, 3, 2],
        [1, 1, 2, 1],
        [1, 3, 2, 1],
        [1, 1, 3, 2],
    ]
    return len(indices) == 3 and all(
        len({cards[index][feature] for index in indices}) in {1, 3} for feature in range(4)
    )


def _country_coloring_is_valid(colors: list[int]) -> bool:
    edges = [[3, 1], [3, 6], [3, 4], [6, 4], [6, 1], [1, 5], [1, 4], [4, 5], [4, 2]]
    return len(colors) == 6 and max(colors) == 4 and all(colors[left - 1] != colors[right - 1] for left, right in edges)


def _best_host_conflicts(seating: list[int]) -> int:
    allowed = {0: {3, 5}, 1: {2, 4}, 2: {1, 5}, 3: {0, 4}, 4: {1, 3}, 5: {0, 2}}
    return sum(seating[(idx + 1) % 6] not in allowed[seating[idx]] for idx in range(6))


def _four_islands_solution_is_valid(payload: dict[str, list[int]]) -> bool:
    island = payload["island"]
    export = payload["export"]
    attraction = payload["attraction"]
    if not all(sorted(values) == list(range(4)) for values in (island, export, attraction)):
        return False
    pwana, quero, rayou, skern = island
    alabaster, bananas, coconuts, durian = export
    hotel, ice, jai_alai, koala = attraction
    south_of = {0: 2, 1: 3}
    west_of = {1: 0, 3: 2}
    east_of = {0: 1, 2: 3}
    bridges = {frozenset(pair) for pair in [(0, 1), (0, 2), (1, 3), (2, 3)]}
    vertical = {frozenset(pair) for pair in [(0, 2), (1, 3)]}
    horizontal = {frozenset(pair) for pair in [(0, 1), (2, 3)]}
    return all(
        [
            south_of.get(pwana) == koala,
            west_of.get(quero) == alabaster,
            east_of.get(durian) == hotel,
            frozenset((skern, jai_alai)) in vertical,
            frozenset((rayou, bananas)) in horizontal,
            frozenset((ice, jai_alai)) not in bridges,
            coconuts in set(range(4)),
        ]
    )


def _magic_hexagon_solution_is_valid(values: list[int]) -> bool:
    if sorted(values) != list(range(1, 20)):
        return False
    a, b, c, d, e, f, g, h, i, j, k, cell_l, m, n, o, p, q, r, s = values
    lines = [
        [a, b, c],
        [d, e, f, g],
        [h, i, j, k, cell_l],
        [m, n, o, p],
        [q, r, s],
        [a, d, h],
        [b, e, i, m],
        [c, f, j, n, q],
        [g, k, o, r],
        [cell_l, p, s],
        [c, g, cell_l],
        [b, f, k, p],
        [a, e, j, o, s],
        [d, i, n, r],
        [h, m, q],
    ]
    return all(sum(line) == 38 for line in lines)


def _calvin_solution_is_valid(grid: list[list[int]]) -> bool:
    flat = [value for row in grid for value in row]
    positions = {value: (row, col) for row, values in enumerate(grid) for col, value in enumerate(values)}
    if sorted(flat) != list(range(1, 26)):
        return False
    for value in range(1, 25):
        row, col = positions[value]
        next_row, next_col = positions[value + 1]
        dr = abs(next_row - row)
        dc = abs(next_col - col)
        if (dr, dc) not in {(3, 0), (0, 3), (2, 2)}:
            return False
    return True


def _five_brigands_solution_is_valid(payload: dict[str, int]) -> bool:
    values = [payload[name] for name in ["A", "B", "C", "D", "E"]]
    return (
        all(value >= 1 for value in values)
        and sum(values) == 200
        and 12 * payload["A"] + 3 * payload["B"] + payload["C"] + payload["D"] / 2 + payload["E"] / 3 == 200
    )


def _packing_solution_is_valid(payload: dict[str, object]) -> bool:
    widths = [3, 4, 2, 1]
    heights = [2, 3, 1, 4]
    pos_x = payload["pos_x"]
    pos_y = payload["pos_y"]
    total_x = payload["total_x"]
    total_y = payload["total_y"]
    rects = [
        (pos_x[idx], pos_y[idx], pos_x[idx] + widths[idx], pos_y[idx] + heights[idx])
        for idx in range(4)
    ]
    return (
        total_x * total_y == 25
        and all(0 <= left < right <= total_x and 0 <= bottom < top <= total_y for left, bottom, right, top in rects)
        and all(
            a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]
            for idx, a in enumerate(rects)
            for b in rects[idx + 1 :]
        )
    )


def _frog_circle_solution_is_valid(values: list[int]) -> bool:
    if sorted(values) != list(range(1, 13)):
        return False
    position = values.index(1)
    seen = []
    for _ in range(12):
        if position in seen:
            return False
        seen.append(position)
        position = (position + values[position]) % len(values)
    return len(seen) == 12
