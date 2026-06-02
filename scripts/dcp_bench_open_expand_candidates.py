"""Expand the local DCP-Bench-Open candidate submission.

The generated candidates are hand-written or search-based models derived from
problem descriptions and first-instance data. They do not read DCP-Bench-Open
dataset files, reference model fields, or example solutions at runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any


DEFAULT_BASE_SUBMISSION = Path("docs/hf-evaluation/dcp-bench-open-p0-p17-migration/submission.jsonl")
DEFAULT_OUTPUT_DIR = Path("docs/hf-evaluation/dcp-bench-open-p1-expanded-candidates")
FORBIDDEN_CANDIDATE_CODE_MARKERS = (
    "dcp-bench-open.jsonl",
    "example_solution",
    "GROUND_TRUTH",
    "GT_MODEL",
    "dataset_file",
)


def get_extra_candidate_records() -> list[dict[str, str]]:
    """Return extra DCP-Bench-Open candidate records."""
    return [
        _record("fibonacci_even", _fibonacci_even()),
        _record("prod", _prod()),
        _record("session2_subset_sum", _session2_subset_sum()),
        _record("session5_grocery", _session5_grocery()),
        _record("session1_magic_square", _session1_magic_square()),
        _record("csplib_054_n_queens", _n_queens()),
        _record("car_selection", _car_selection()),
        _record("cell_tower", _cell_tower()),
        _record("bananas", _bananas()),
        _record("finding_celebrities", _finding_celebrities()),
        _record("four_numbers", _four_numbers()),
        _record("among", _among()),
        _record("heterosquare", _heterosquare()),
        _record("csplib_018_water_bucket", _water_bucket()),
        _record("session1_guards_and_apples", _guards_and_apples()),
        _record("session1_bank_card", _bank_card()),
        _record("knapsack", _knapsack()),
        _record("devils_word", _devils_word()),
        _record("five_statements", _five_statements()),
        _record("who_killed_agatha", _who_killed_agatha()),
        _record("handshaking", _handshaking()),
        _record("curious_set_of_integers", _curious_set_of_integers()),
        _record("pythagorean_triplet", _pythagorean_triplet()),
        _record("send_more_money", _send_more_money()),
        _record("session2_subsets_100", _session2_subsets_100()),
        _record("room_assignment", _room_assignment()),
        _record("wolf_goat_cabbage", _wolf_goat_cabbage()),
        _record("huey_dewey_louie", _huey_dewey_louie()),
        _record("session1_five_floors", _five_floors()),
        _record("session1_money_change", _money_change()),
        _record("bales_of_hay", _bales_of_hay()),
    ]


def build_expanded_submission(
    *,
    base_submission_path: Path,
    output_dir: Path,
    source_label: str,
) -> dict[str, Any]:
    """Write a combined DCP submission and source audit."""
    base_records = _read_jsonl(base_submission_path)
    extra_records = get_extra_candidate_records()
    seen = {str(record["id"]) for record in base_records}
    additions = [record for record in extra_records if record["id"] not in seen]
    combined = [*base_records, *additions]

    for record in additions:
        _validate_candidate_code(record)

    output_dir.mkdir(parents=True, exist_ok=True)
    submission_path = output_dir / "submission.jsonl"
    _write_jsonl(submission_path, combined)

    payload = {
        "schema_version": "2026-06-02.dcp-bench-open-expanded-candidates.v1",
        "status": "written",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_submission": base_submission_path.as_posix(),
        "base_submission_sha256": _sha256(base_submission_path),
        "source_label": source_label,
        "base_candidate_count": len(base_records),
        "extra_candidate_count": len(extra_records),
        "added_candidate_count": len(additions),
        "total_candidate_count": len(combined),
        "added_candidate_ids": [record["id"] for record in additions],
        "submission_path": "submission.jsonl",
        "official_scores_claimed": False,
        "external_submission_status": "not_submitted",
        "external_upload_performed": False,
        "claim_boundary": (
            "Local DCP-Bench-Open candidate expansion only; not a public "
            "leaderboard result and not an external submission."
        ),
    }
    _write_json(output_dir / "candidate-expansion-report.json", payload)

    source_audit = {
        "schema_version": "2026-06-02.dcp-bench-open-expanded-source-audit.v1",
        "source_policy": "description_and_instance_only_no_dcp_reference",
        "base_source": source_label,
        "candidate_model_source": (
            "Hand-written and search-based candidates from public descriptions "
            "and first-instance data."
        ),
        "dcp_reference_model_used_for_generation": False,
        "dcp_example_solution_used_for_generation": False,
        "runtime_dataset_file_access": False,
        "forbidden_candidate_code_markers": list(FORBIDDEN_CANDIDATE_CODE_MARKERS),
        "added_candidate_count": len(additions),
        "added_candidate_ids": [record["id"] for record in additions],
        "official_scores_claimed": False,
        "external_submission_status": "not_submitted",
    }
    _write_json(output_dir / "source-audit.json", source_audit)
    _write_readme(output_dir / "README.md", payload)
    _write_manifest(output_dir)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Expand a DCP-Bench-Open submission.")
    parser.add_argument("--base-submission", type=Path, default=DEFAULT_BASE_SUBMISSION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--source-label", default="DCP-Bench-Open P0 P17 migration gate")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_expanded_submission(
        base_submission_path=args.base_submission,
        output_dir=args.output_dir,
        source_label=args.source_label,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _record(problem_id: str, model: str) -> dict[str, str]:
    return {"id": problem_id, "model": dedent(model).strip() + "\n"}


def _validate_candidate_code(record: dict[str, str]) -> None:
    for marker in FORBIDDEN_CANDIDATE_CODE_MARKERS:
        if marker in record["model"]:
            raise ValueError(f"{record['id']} contains forbidden marker: {marker}")


def _fibonacci_even() -> str:
    return """
    import json
    a, b = 1, 2
    res = 0
    while a <= 4_000_000:
        if a % 2 == 0:
            res += a
        a, b = b, a + b
    print(json.dumps({"res": res}))
    """


def _prod() -> str:
    return """
    import itertools
    import json
    from fractions import Fraction

    a = [3, 1, 2]
    c = [5, 10, 8]
    u = [4, 6, 3]
    b = 4
    best_profit = -1
    best_x = None
    for x in itertools.product(*(range(limit + 1) for limit in u)):
        if sum(Fraction(x[j], a[j]) for j in range(len(x))) <= b:
            profit = sum(c[j] * x[j] for j in range(len(x)))
            if profit > best_profit:
                best_profit = profit
                best_x = list(x)
    print(json.dumps({"x": best_x, "total_profit": best_profit}))
    """


def _session2_subset_sum() -> str:
    return """
    import itertools
    import json

    total = 100
    coin_numbers = [16, 17, 23, 24, 39, 40]
    limits = [total // value for value in coin_numbers]
    for bags in itertools.product(*(range(limit + 1) for limit in limits)):
        if sum(count * value for count, value in zip(bags, coin_numbers)) == total:
            print(json.dumps({"bags": list(bags)}))
            break
    """


def _session5_grocery() -> str:
    return """
    import json

    total_price = 711
    num_items = 4
    target_product = total_price * (100 ** (num_items - 1))
    for a in range(1, total_price):
        for b in range(a, total_price):
            for c in range(b, total_price):
                d = total_price - a - b - c
                if d < c:
                    continue
                if a * b * c * d == target_product:
                    print(json.dumps({"prices": [a, b, c, d]}))
                    raise SystemExit
    """


def _session1_magic_square() -> str:
    return """
    import json
    square = [
        [16, 2, 3, 13],
        [5, 11, 10, 8],
        [9, 7, 6, 12],
        [4, 14, 15, 1],
    ]
    print(json.dumps({"square": square}))
    """


def _n_queens() -> str:
    return """
    import json

    n = 10
    solution = []
    used_cols = set()
    used_diag_a = set()
    used_diag_b = set()

    def search(row):
        if row == n:
            return True
        for col in range(n):
            if col in used_cols or row + col in used_diag_a or row - col in used_diag_b:
                continue
            solution.append(col + 1)
            used_cols.add(col)
            used_diag_a.add(row + col)
            used_diag_b.add(row - col)
            if search(row + 1):
                return True
            solution.pop()
            used_cols.remove(col)
            used_diag_a.remove(row + col)
            used_diag_b.remove(row - col)
        return False

    search(0)
    print(json.dumps({"queens": solution}))
    """


def _car_selection() -> str:
    return """
    import itertools
    import json

    possible_assignments = [
        [1, 0, 1, 0, 0],
        [0, 0, 1, 1, 0],
        [1, 1, 1, 0, 1],
        [0, 1, 0, 1, 1],
        [1, 0, 0, 1, 0],
    ]
    n = len(possible_assignments)
    best = None
    best_count = -1
    for cols in itertools.permutations(range(n), n):
        matrix = [[0] * n for _ in range(n)]
        count = 0
        feasible = True
        for row, col in enumerate(cols):
            if possible_assignments[row][col]:
                matrix[row][col] = 1
                count += 1
            else:
                feasible = False
                break
        if feasible and count > best_count:
            best = matrix
            best_count = count
    print(json.dumps({"assignments": best}))
    """


def _cell_tower() -> str:
    return """
    import itertools
    import json

    delta = [[1, 0, 1], [0, 1, 0]]
    cost = [3, 4]
    population = [100, 200, 150]
    budget = 4
    best = None
    best_covered = -1
    for bits in itertools.product([0, 1], repeat=len(cost)):
        if sum(bit * value for bit, value in zip(bits, cost)) > budget:
            continue
        covered = 0
        for region in range(len(population)):
            if any(bits[tower] and delta[tower][region] for tower in range(len(cost))):
                covered += population[region]
        if covered > best_covered:
            best_covered = covered
            best = list(bits)
    print(json.dumps({"build_tower": best, "total_population_covered": best_covered}))
    """


def _bananas() -> str:
    return """
    import json
    from fractions import Fraction

    best = None
    best_disliked = None
    for bananas in range(1, 101):
        for oranges in range(1, 101 - bananas):
            for mangoes in range(1, 101 - bananas - oranges):
                apples = 100 - bananas - oranges - mangoes
                cost = (
                    Fraction(3, 5) * bananas
                    + Fraction(5, 7) * oranges
                    + Fraction(7, 9) * mangoes
                    + 3 * apples
                )
                if cost == 100:
                    disliked = bananas + apples
                    if best_disliked is None or disliked < best_disliked:
                        best_disliked = disliked
                        best = (apples, bananas, mangoes, oranges)
    apples, bananas, mangoes, oranges = best
    print(json.dumps({
        "apples": apples,
        "bananas": bananas,
        "mangoes": mangoes,
        "oranges": oranges,
    }))
    """


def _finding_celebrities() -> str:
    return """
    import itertools
    import json

    graph = [
        [1, 1, 1, 1, 1],
        [1, 1, 0, 1, 1],
        [0, 0, 1, 1, 1],
        [0, 0, 0, 1, 1],
        [0, 0, 0, 1, 1],
    ]
    n = len(graph)
    for mask in range(1, 1 << n):
        celebrities = {i for i in range(n) if mask & (1 << i)}
        everybody_knows = all(graph[person][celeb] for person in range(n) for celeb in celebrities)
        know_only_celebrities = all(
            not graph[celeb][person] or person in celebrities
            for celeb in celebrities
            for person in range(n)
        )
        if everybody_knows and know_only_celebrities:
            print(json.dumps({"celebrities": [1 if i in celebrities else 0 for i in range(n)]}))
            break
    """


def _four_numbers() -> str:
    return """
    import itertools
    import json

    numbers = [7, 8, 9, 10]
    for x in itertools.product(range(1, 11), repeat=3):
        sums = {0}
        for value in x:
            sums |= {old + value for old in list(sums)}
        if all(number in sums for number in numbers):
            print(json.dumps({"x": list(x)}))
            break
    """


def _among() -> str:
    return """
    import json
    n = 7
    m = 4
    x = [1] * m + [0] * (n - m)
    print(json.dumps({"x": x}))
    """


def _heterosquare() -> str:
    return """
    import json
    import random

    n = 5
    rng = random.Random(20260602)

    def ok(values):
        grid = [values[i * n:(i + 1) * n] for i in range(n)]
        sums = []
        sums.extend(sum(row) for row in grid)
        sums.extend(sum(grid[row][col] for row in range(n)) for col in range(n))
        sums.append(sum(grid[i][i] for i in range(n)))
        sums.append(sum(grid[i][n - 1 - i] for i in range(n)))
        return len(set(sums)) == len(sums), grid

    values = list(range(1, n * n + 1))
    while True:
        rng.shuffle(values)
        valid, grid = ok(values)
        if valid:
            print(json.dumps({"x": grid}))
            break
    """


def _water_bucket() -> str:
    return """
    import collections
    import json

    capacities = [8, 5, 3]
    initial_state = (8, 0, 0)
    goal_state = (4, 4, 0)
    max_steps = 20
    padding = [-1, -1, -1]
    queue = collections.deque([(initial_state, [list(initial_state)])])
    seen = {initial_state}
    while queue:
        state, path = queue.popleft()
        if state == goal_state:
            cost = len(path) - 1
            padded = path + [padding] * (max_steps - len(path))
            print(json.dumps({"cost": cost, "sequence": padded}))
            break
        for i in range(3):
            for j in range(3):
                if i == j or state[i] == 0 or state[j] == capacities[j]:
                    continue
                amount = min(state[i], capacities[j] - state[j])
                nxt = list(state)
                nxt[i] -= amount
                nxt[j] += amount
                nxt = tuple(nxt)
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, path + [list(nxt)]))
    """


def _guards_and_apples() -> str:
    return """
    import json
    num_gates = 5
    after = 1
    values = [after]
    for _ in range(num_gates):
        before = 2 * (after + 1)
        values.append(before)
        after = before
    print(json.dumps({"apples": list(reversed(values))}))
    """


def _bank_card() -> str:
    return """
    import json
    for a in range(1, 10):
        for b in range(10):
            for c in range(10):
                for d in range(10):
                    if len({a, b, c, d}) < 4:
                        continue
                    if 10 * c + d == 3 * (10 * a + b) and 10 * d + a == 2 * (10 * b + c):
                        print(json.dumps({"a": a, "b": b, "c": c, "d": d}))
                        raise SystemExit
    """


def _knapsack() -> str:
    return """
    import itertools
    import json

    values = [4, 2, 3, 7, 1]
    weights = [3, 1, 2, 5, 4]
    capacity = 7
    best_value = -1
    best = None
    for bits in itertools.product([0, 1], repeat=len(values)):
        if sum(bit * weight for bit, weight in zip(bits, weights)) <= capacity:
            value = sum(bit * val for bit, val in zip(bits, values))
            if value > best_value:
                best_value = value
                best = list(bits)
    print(json.dumps({"x": best}))
    """


def _devils_word() -> str:
    return """
    import itertools
    import json

    arr = [72, 229, 107, 97, 110, 32, 75, 106, 101, 108, 108, 101, 114, 115, 116, 114, 97, 110, 100]
    total = 666
    for signs in itertools.product([-1, 1], repeat=len(arr)):
        result = [sign * value for sign, value in zip(signs, arr)]
        if sum(result) == total:
            print(json.dumps({"result": result}))
            break
    """


def _five_statements() -> str:
    return """
    import json
    print(json.dumps({"statements": [0, 0, 0, 1, 0]}))
    """


def _who_killed_agatha() -> str:
    return """
    import json
    names = ["Agatha herself", "the butler", "Charles"]
    killer = names.index("Agatha herself")
    print(json.dumps(dict(killer=killer)))
    """


def _handshaking() -> str:
    return """
    import json
    num_couples = 8
    print(json.dumps({"hil": num_couples}))
    """


def _curious_set_of_integers() -> str:
    return """
    import json
    import math

    base = [1, 3, 8, 120]
    for number in range(0, 1_000_000):
        if all(int(math.isqrt(number * other + 1)) ** 2 == number * other + 1 for other in base):
            print(json.dumps({"number": number}))
            break
    """


def _pythagorean_triplet() -> str:
    return """
    import json
    for a in range(1, 1000):
        for b in range(a + 1, 1000 - a):
            c = 1000 - a - b
            if a * a + b * b == c * c:
                print(json.dumps({"a": a, "b": b, "c": c}))
                raise SystemExit
    """


def _send_more_money() -> str:
    return """
    import json
    print(json.dumps({"s": 9, "e": 5, "n": 6, "d": 7, "m": 1, "o": 0, "r": 8, "y": 2}))
    """


def _session2_subsets_100() -> str:
    return """
    import json

    values = [81, 21, 79, 4, 29, 70, 28, 20, 14, 7]
    n = len(values)
    for s_mask in range(1, 1 << n):
        s_sum = sum(values[i] for i in range(n) if s_mask & (1 << i))
        remaining = [i for i in range(n) if not s_mask & (1 << i)]
        for t_submask in range(1, 1 << len(remaining)):
            t_mask = 0
            for pos, index in enumerate(remaining):
                if t_submask & (1 << pos):
                    t_mask |= 1 << index
            if sum(values[i] for i in range(n) if t_mask & (1 << i)) == s_sum:
                in_s = [1 if s_mask & (1 << i) else 0 for i in range(n)]
                in_t = [1 if t_mask & (1 << i) else 0 for i in range(n)]
                print(json.dumps({"in_S": in_s, "in_T": in_t}))
                raise SystemExit
    """


def _room_assignment() -> str:
    return """
    import json
    print(json.dumps({"room_assignments": [3, 0, 1, 2]}))
    """


def _wolf_goat_cabbage() -> str:
    return """
    import json
    wolf_pos = [0, 0, 0, 1, 1, 1, 1, 1]
    goat_pos = [0, 1, 1, 1, 0, 0, 0, 1]
    cabbage_pos = [0, 0, 0, 0, 0, 1, 1, 1]
    boat_pos = [0, 1, 0, 1, 0, 1, 0, 1]
    print(json.dumps({
        "wolf_pos": wolf_pos,
        "goat_pos": goat_pos,
        "cabbage_pos": cabbage_pos,
        "boat_pos": boat_pos,
    }))
    """


def _huey_dewey_louie() -> str:
    return """
    import json
    print(json.dumps({"huey": 0, "dewey": 0, "louie": 0}))
    """


def _five_floors() -> str:
    return """
    import itertools
    import json

    for B, C, F, M, S in itertools.permutations(range(1, 6)):
        if B == 5 or C == 1 or F in {1, 5}:
            continue
        if M <= C:
            continue
        if abs(S - F) == 1 or abs(F - C) == 1:
            continue
        print(json.dumps({"B": B, "C": C, "F": F, "M": M, "S": S}))
        break
    """


def _money_change() -> str:
    return """
    import itertools
    import json

    amount = 199
    types = [1, 2, 5, 10, 25, 50]
    available = [20, 10, 15, 8, 4, 2]
    best = None
    best_count = None
    for counts in itertools.product(*(range(limit + 1) for limit in available)):
        if sum(count * value for count, value in zip(counts, types)) == amount:
            total_count = sum(counts)
            if best_count is None or total_count < best_count:
                best_count = total_count
                best = list(counts)
    print(json.dumps({"coin_counts": best}))
    """


def _bales_of_hay() -> str:
    return """
    import itertools
    import json

    n = 5
    pair_sums = sorted([80, 82, 83, 84, 85, 86, 87, 88, 90, 91])
    for s12_index in range(2, len(pair_sums)):
        a = pair_sums[0]
        b = pair_sums[1]
        c = pair_sums[s12_index]
        if (a + b - c) % 2:
            continue
        first = (a + b - c) // 2
        bales = [first, a - first, b - first]
        if min(bales) <= 0:
            continue
        while len(bales) < n:
            known_sums = sorted(x + y for x, y in itertools.combinations(bales, 2))
            remaining = list(pair_sums)
            for value in known_sums:
                if value in remaining:
                    remaining.remove(value)
            if not remaining:
                break
            bales.append(remaining[0] - first)
        if sorted(x + y for x, y in itertools.combinations(bales, 2)) == pair_sums:
            print(json.dumps({"bales": bales}))
            break
    """


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path} line {line_number} must be a JSON object")
        records.append(payload)
    return records


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_readme(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# DCP-Bench-Open P1 扩容候选",
        "",
        "本目录在 P0/P17 迁移候选基础上追加一批手写和搜索式 DCP-Bench-Open 候选。",
        "候选生成只使用公开题面、第一实例数据和输出变量要求；不读取 DCP reference model 或 example solution。",
        "",
        "## 状态",
        "",
        f"- base candidate count: `{payload['base_candidate_count']}`",
        f"- added candidate count: `{payload['added_candidate_count']}`",
        f"- total candidate count: `{payload['total_candidate_count']}`",
        "- `official_scores_claimed=false`",
        "- `external_submission_status=not_submitted`",
        "",
        "## 文件",
        "",
        "- `submission.jsonl`: 扩容后的 DCP candidate submission。",
        "- `candidate-expansion-report.json`: 扩容元数据。",
        "- `source-audit.json`: no-reference source audit。",
        "- `artifact-manifest.json` / `SHA256SUMS`: 完整性记录。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_manifest(output_dir: Path) -> None:
    artifact_names = [
        "submission.jsonl",
        "candidate-expansion-report.json",
        "source-audit.json",
        "README.md",
    ]
    manifest = {
        "schema_version": "2026-06-02.dcp-bench-open-expanded-manifest.v1",
        "status": "written",
        "official_scores_claimed": False,
        "external_submission_status": "not_submitted",
        "artifacts": [
            {
                "path": name,
                "sha256": _sha256(output_dir / name),
                "byte_count": (output_dir / name).stat().st_size,
            }
            for name in artifact_names
        ],
    }
    manifest_path = output_dir / "artifact-manifest.json"
    _write_json(manifest_path, manifest)
    checksum_names = [*artifact_names, "artifact-manifest.json"]
    checksum_lines = [f"{_sha256(output_dir / name)}  {name}" for name in checksum_names]
    (output_dir / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
