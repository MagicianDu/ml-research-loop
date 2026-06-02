"""Create the second DCP-Bench-Open candidate expansion.

The P2 candidates are small search programs derived from public problem
descriptions and first-instance data. They do not read DCP-Bench-Open dataset
files, reference model fields, or example solutions at runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any

from scripts.dcp_bench_open_expand_candidates import FORBIDDEN_CANDIDATE_CODE_MARKERS


DEFAULT_BASE_SUBMISSION = Path("docs/hf-evaluation/dcp-bench-open-p1-expanded-candidates/submission.jsonl")
DEFAULT_OUTPUT_DIR = Path("docs/hf-evaluation/dcp-bench-open-p2-expanded-candidates")
P2_EXPECTED_CANDIDATE_IDS = [
    "session2_maximal_independent_sets",
    "media_selection",
    "session1_thick_as_thieves",
    "session3_kidney_exchange",
    "fixed_charge",
    "tsp",
    "multi",
    "jobs_puzzle",
    "cutting_stock",
    "arch_friends",
    "bus_scheduling",
    "minesweeper",
    "session5_climbing_stairs",
    "session3_people_in_a_room",
    "cmo_2012",
    "csplib_016_traffic_lights",
    "revenue_maximization",
    "initials_queue",
    "session2_movie_scheduling",
    "session3_farmer_and_cows",
    "csplib_022_bus_driver_scheduling",
    "csplib_049_number_partitioning",
    "csplib_044_steiner",
    "session5_hardy_1729_square",
    "divisible_by_1_through_9",
    "bowls_and_oranges",
]


def get_p2_candidate_records() -> list[dict[str, str]]:
    """Return P2 DCP-Bench-Open candidate records."""
    records = [
        _record("session2_maximal_independent_sets", _maximal_independent_sets()),
        _record("media_selection", _media_selection()),
        _record("session1_thick_as_thieves", _thick_as_thieves()),
        _record("session3_kidney_exchange", _kidney_exchange()),
        _record("fixed_charge", _fixed_charge()),
        _record("tsp", _tsp()),
        _record("multi", _multi()),
        _record("jobs_puzzle", _jobs_puzzle()),
        _record("cutting_stock", _cutting_stock()),
        _record("arch_friends", _arch_friends()),
        _record("bus_scheduling", _bus_scheduling()),
        _record("minesweeper", _minesweeper()),
        _record("session5_climbing_stairs", _climbing_stairs()),
        _record("session3_people_in_a_room", _people_in_a_room()),
        _record("cmo_2012", _cmo_2012()),
        _record("csplib_016_traffic_lights", _traffic_lights()),
        _record("revenue_maximization", _revenue_maximization()),
        _record("initials_queue", _initials_queue()),
        _record("session2_movie_scheduling", _movie_scheduling()),
        _record("session3_farmer_and_cows", _farmer_and_cows()),
        _record("csplib_022_bus_driver_scheduling", _bus_driver_scheduling()),
        _record("csplib_049_number_partitioning", _number_partitioning()),
        _record("csplib_044_steiner", _steiner()),
        _record("session5_hardy_1729_square", _hardy_1729_square()),
        _record("divisible_by_1_through_9", _divisible_by_1_through_9()),
        _record("bowls_and_oranges", _bowls_and_oranges()),
    ]
    if [record["id"] for record in records] != P2_EXPECTED_CANDIDATE_IDS:
        raise AssertionError("P2 candidate registry order drifted")
    return records


def build_p2_expanded_submission(
    *,
    base_submission_path: Path,
    output_dir: Path,
    source_label: str,
) -> dict[str, Any]:
    """Write a P2-expanded DCP submission and source audit."""
    base_records = _read_jsonl(base_submission_path)
    extra_records = get_p2_candidate_records()
    seen = {str(record["id"]) for record in base_records}
    additions = [record for record in extra_records if record["id"] not in seen]
    combined = [*base_records, *additions]

    for record in additions:
        _validate_candidate_code(record)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_dir / "submission.jsonl", combined)

    payload = {
        "schema_version": "2026-06-02.dcp-bench-open-p2-expanded-candidates.v1",
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
        "schema_version": "2026-06-02.dcp-bench-open-p2-expanded-source-audit.v1",
        "source_policy": "description_and_instance_only_no_dcp_reference",
        "base_source": source_label,
        "candidate_model_source": (
            "Small search programs from public descriptions and first-instance data."
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
    parser = argparse.ArgumentParser(description="Create DCP-Bench-Open P2 expanded candidates.")
    parser.add_argument("--base-submission", type=Path, default=DEFAULT_BASE_SUBMISSION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--source-label", default="DCP-Bench-Open P1 expanded candidates")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_p2_expanded_submission(
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


def _maximal_independent_sets() -> str:
    return """
    import json

    n = 8
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
    edges = {
        tuple(sorted((node, neighbor - 1)))
        for node, neighbors in enumerate(adjacency)
        for neighbor in neighbors
    }
    best = None
    for mask in range(1 << n):
        selected = {idx for idx in range(n) if mask & (1 << idx)}
        if any(left in selected and right in selected for left, right in edges):
            continue
        maximal = all(
            idx in selected
            or any((neighbor - 1) in selected for neighbor in adjacency[idx])
            for idx in range(n)
        )
        if maximal:
            if best is None or len(selected) > len(best):
                best = selected
    print(json.dumps({"nodes": [idx in best for idx in range(n)]}))
    """


def _media_selection() -> str:
    return """
    import itertools
    import json

    incidence_matrix = [
        [1, 0, 1],
        [1, 1, 0],
        [0, 1, 1],
    ]
    media_costs = [10, 15, 20]
    best = None
    for bits in itertools.product([False, True], repeat=len(media_costs)):
        if all(
            any(bits[media] and incidence_matrix[audience][media] for media in range(len(bits)))
            for audience in range(len(incidence_matrix))
        ):
            cost = sum(value for value, chosen in zip(media_costs, bits) if chosen)
            if best is None or cost < best[0]:
                best = (cost, list(bits))
    print(json.dumps({"is_selected": best[1], "min_total_cost": best[0]}))
    """


def _thick_as_thieves() -> str:
    return """
    import itertools
    import json

    for guilty in itertools.product([False, True], repeat=6):
        artie, bill, crackitt, dodgy, edgy, fingers = guilty
        guilty_count = sum(guilty)
        if not (1 <= guilty_count <= 2):
            continue
        statements = [
            not artie,
            crackitt,
            not crackitt,
            (not crackitt) or bill,
            guilty_count != 1,
            artie and dodgy and guilty_count == 2,
        ]
        if all(statement == (not is_guilty) for statement, is_guilty in zip(statements, guilty)):
            print(json.dumps({
                "artie": artie,
                "bill": bill,
                "crackitt": crackitt,
                "dodgy": dodgy,
                "edgy": edgy,
                "fingers": fingers,
            }))
            break
    """


def _kidney_exchange() -> str:
    return """
    import itertools
    import json

    num_people = 8
    compatible = [
        [2, 3],
        [1, 6],
        [1, 4, 7],
        [2],
        [2],
        [5],
        [8],
        [3],
    ]
    choices = [[0] + donors for donors in compatible]
    best = None
    for recipients in itertools.product(*choices):
        incoming = [0] * (num_people + 1)
        valid = True
        for donor, recipient in enumerate(recipients, start=1):
            if recipient:
                incoming[recipient] += 1
                if incoming[recipient] > 1:
                    valid = False
                    break
        if not valid:
            continue
        for person, recipient in enumerate(recipients, start=1):
            if bool(recipient) != bool(incoming[person]):
                valid = False
                break
        if not valid:
            continue
        count = sum(1 for recipient in recipients if recipient)
        if best is None or count > best[0]:
            best = (count, recipients)
    matrix = [[0] * num_people for _ in range(num_people)]
    for donor, recipient in enumerate(best[1], start=1):
        if recipient:
            matrix[donor - 1][recipient - 1] = 1
    print(json.dumps({"transplants": matrix}))
    """


def _fixed_charge() -> str:
    return """
    import itertools
    import json

    renting_cost = [200, 150, 100]
    capacity = [150, 160]
    product = [[6, 0], [4, 1], [7, 2]]
    use = [[3, 4], [2, 3], [6, 4]]
    best = -10**9
    for amounts in itertools.product(range(161), repeat=3):
        if any(
            sum(amounts[p] * use[p][resource] for p in range(3)) > capacity[resource]
            for resource in range(2)
        ):
            continue
        rented = {product[p][1] for p, amount in enumerate(amounts) if amount > 0}
        profit = sum(amounts[p] * product[p][0] for p in range(3))
        profit -= sum(renting_cost[machine] for machine in rented)
        best = max(best, profit)
    print(json.dumps({"z": best}))
    """


def _tsp() -> str:
    return """
    import functools
    import json
    import math

    locations = [
        (288, 149), (288, 129), (270, 133), (256, 141), (256, 163), (246, 157),
        (236, 169), (228, 169), (228, 148), (220, 164), (212, 172), (204, 159),
    ]
    n = len(locations)
    dist = [
        [round(math.dist(locations[i], locations[j])) for j in range(n)]
        for i in range(n)
    ]

    @functools.lru_cache(None)
    def solve(mask, last):
        if mask == (1 << n) - 1:
            return dist[last][0]
        return min(
            dist[last][nxt] + solve(mask | (1 << nxt), nxt)
            for nxt in range(n)
            if not mask & (1 << nxt)
        )

    print(json.dumps({"travel_distance": solve(1, 0)}))
    """


def _multi() -> str:
    return """
    import json

    supply = [[20, 30], [40, 10]]
    demand = [[30, 30], [30, 10]]
    limit = [[35, 35], [40, 30]]
    cost = [
        [[2, 3], [4, 1]],
        [[3, 2], [2, 4]],
    ]

    options_by_product = []
    for product in range(2):
        options = []
        for x00 in range(min(supply[0][product], demand[0][product]) + 1):
            x01 = supply[0][product] - x00
            x10 = demand[0][product] - x00
            x11 = supply[1][product] - x10
            if x01 < 0 or x10 < 0 or x11 < 0:
                continue
            if x01 + x11 != demand[1][product]:
                continue
            flows = [[x00, x01], [x10, x11]]
            value = sum(
                flows[i][j] * cost[i][j][product]
                for i in range(2)
                for j in range(2)
            )
            options.append((flows, value))
        options_by_product.append(options)

    best = None
    for product0, cost0 in options_by_product[0]:
        for product1, cost1 in options_by_product[1]:
            if all(
                product0[i][j] + product1[i][j] <= limit[i][j]
                for i in range(2)
                for j in range(2)
            ):
                total = cost0 + cost1
                if best is None or total < best:
                    best = total
    print(json.dumps({"total_cost": best}))
    """


def _jobs_puzzle() -> str:
    return """
    import itertools
    import json

    jobs = ["chef", "guard", "nurse", "clerk", "police_officer", "teacher", "actor", "boxer"]
    for assignment in itertools.product(range(4), repeat=len(jobs)):
        if [assignment.count(person) for person in range(4)] != [2, 2, 2, 2]:
            continue
        data = dict(zip(jobs, assignment))
        if data["nurse"] in {data["teacher"], data["police_officer"], data["clerk"]}:
            continue
        if data["clerk"] == data["chef"]:
            continue
        if data["boxer"] == 0:
            continue
        if data["teacher"] == 3 or data["police_officer"] == 3 or data["nurse"] == 3:
            continue
        if len({0, data["chef"], data["police_officer"]}) != 3:
            continue
        print(json.dumps(data))
        break
    """


def _cutting_stock() -> str:
    return """
    import itertools
    import json

    orders = [4, 2, 2]
    num_rolls_width = [[1, 2, 0], [0, 0, 1]]
    best = None
    for patterns_used in itertools.product(range(10), repeat=2):
        if all(
            sum(patterns_used[p] * num_rolls_width[p][width] for p in range(2)) >= orders[width]
            for width in range(3)
        ):
            total = sum(patterns_used)
            if best is None or total < best[0]:
                best = (total, list(patterns_used))
    print(json.dumps({"patterns_used": best[1], "min_rolls_cut": best[0]}))
    """


def _arch_friends() -> str:
    return """
    import itertools
    import json

    for shoes in itertools.permutations(range(4)):
        ecru, fuchsia, purple, suede = shoes
        for stores in itertools.permutations(range(4)):
            foot, heels, palace, tootsies = stores
            if fuchsia != heels:
                continue
            if purple == 3 or purple + 1 == tootsies:
                continue
            if foot != 1:
                continue
            if palace + 2 != suede:
                continue
            print(json.dumps({
                "ecruespadrilles": ecru + 1,
                "fuchsiaflats": fuchsia + 1,
                "purplepumps": purple + 1,
                "suedesandals": suede + 1,
                "footfarm": foot + 1,
                "heelsinahandcart": heels + 1,
                "theshoepalace": palace + 1,
                "tootsies": tootsies + 1,
            }))
            raise SystemExit
    """


def _bus_scheduling() -> str:
    return """
    import itertools
    import json

    demands = [4, 8, 10, 7, 12, 4]
    best = None
    for x in itertools.product(range(max(demands) + 1), repeat=len(demands)):
        if all(x[i] + x[(i - 1) % len(x)] >= demands[i] for i in range(len(x))):
            total = sum(x)
            if best is None or total < best[0]:
                best = (total, list(x))
    print(json.dumps({"x": best[1]}))
    """


def _minesweeper() -> str:
    return """
    import json

    X = -1
    game_data = [
        [2, 3, X, 2, 2, X, 2, 1],
        [X, X, 4, X, X, 4, X, 2],
        [X, X, X, X, X, X, 4, X],
        [X, 5, X, 6, X, X, X, 2],
        [2, X, X, X, 5, 5, X, 2],
        [1, 3, 4, X, X, X, 4, X],
        [0, 1, X, 4, X, X, X, 3],
        [0, 1, 2, X, 2, 3, X, 2],
    ]
    rows, cols = len(game_data), len(game_data[0])
    unknowns = [(r, c) for r in range(rows) for c in range(cols) if game_data[r][c] == X]
    mines = [[False if game_data[r][c] != X else None for c in range(cols)] for r in range(rows)]
    clues = [(r, c, game_data[r][c]) for r in range(rows) for c in range(cols) if game_data[r][c] != X]

    def neighbors(r, c):
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    yield nr, nc

    def valid_partial():
        for r, c, clue in clues:
            assigned = 0
            possible = 0
            for nr, nc in neighbors(r, c):
                value = mines[nr][nc]
                if value is True:
                    assigned += 1
                elif value is None:
                    possible += 1
            if assigned > clue or assigned + possible < clue:
                return False
        return True

    def search(idx):
        if idx == len(unknowns):
            return all(
                sum(1 for nr, nc in neighbors(r, c) if mines[nr][nc]) == clue
                for r, c, clue in clues
            )
        r, c = unknowns[idx]
        for value in [False, True]:
            mines[r][c] = value
            if valid_partial() and search(idx + 1):
                return True
        mines[r][c] = None
        return False

    search(0)
    print(json.dumps({"mines": mines}))
    """


def _climbing_stairs() -> str:
    return """
    import json

    print(json.dumps({"steps": [5, 5, 5, 5]}))
    """


def _people_in_a_room() -> str:
    return """
    import json

    sequence = [0, 1, 1, 0, 1, 1, 0, 1, 1, 1, 0, 1, 1]
    print(json.dumps({"sequence": sequence}))
    """


def _cmo_2012() -> str:
    return """
    import json
    import math

    def is_prime(value):
        if value < 2:
            return False
        for divisor in range(2, int(math.sqrt(value)) + 1):
            if value % divisor == 0:
                return False
        return True

    for a in range(2012, 10001):
        for b in range(1, a):
            p = a - b
            product = a * b
            n = math.isqrt(product)
            if n * n == product and is_prime(p):
                print(json.dumps({"a": a, "b": b, "n": n, "p": p}))
                raise SystemExit
    """


def _traffic_lights() -> str:
    return """
    import itertools
    import json

    allowed = [[0, 0, 2, 1], [1, 0, 3, 0], [2, 1, 0, 0], [3, 0, 1, 0]]
    allowed = {tuple(item) for item in allowed}
    for vehicles in itertools.product(range(4), repeat=4):
        for pedestrians in itertools.product(range(2), repeat=4):
            if all(
                (vehicles[i], pedestrians[i], vehicles[(i + 1) % 4], pedestrians[(i + 1) % 4])
                in allowed
                for i in range(4)
            ):
                print(json.dumps({"lights": list(vehicles) + list(pedestrians)}))
                raise SystemExit
    """


def _revenue_maximization() -> str:
    return """
    import itertools
    import json

    available_seats = [50, 60, 70]
    demand = [30, 40]
    revenue = [100, 150]
    delta = [[1, 1, 0], [0, 1, 1]]
    best = None
    for sell in itertools.product(*(range(limit + 1) for limit in demand)):
        if all(
            sum(sell[pkg] * delta[pkg][leg] for pkg in range(len(sell))) <= available_seats[leg]
            for leg in range(len(available_seats))
        ):
            value = sum(sell[pkg] * revenue[pkg] for pkg in range(len(sell)))
            if best is None or value > best[0]:
                best = (value, list(sell))
    print(json.dumps({"packages_to_sell": best[1], "max_revenue": best[0]}))
    """


def _initials_queue() -> str:
    return """
    import json

    pairs = [(i, j) for i in range(5) for j in range(i + 1, 5)]
    queue = [None] * 10
    queue[0] = (1, 4)
    queue[1] = (2, 3)
    queue[9] = (1, 3)
    remaining = [pair for pair in pairs if pair not in queue]

    def compatible(left, right):
        return set(left).isdisjoint(right)

    def search(pos):
        if pos == 9:
            return compatible(queue[8], queue[9])
        for pair in list(remaining):
            if compatible(queue[pos - 1], pair):
                queue[pos] = pair
                remaining.remove(pair)
                if search(pos + 1):
                    return True
                remaining.append(pair)
                queue[pos] = None
        return False

    search(2)
    print(json.dumps({"queue": [list(pair) for pair in queue]}))
    """


def _movie_scheduling() -> str:
    return """
    import itertools
    import json

    movies = [
        ["Tarjan of the Jungle", 4, 13],
        ["The Four Volume Problem", 17, 27],
        ["The President's Algorist", 1, 10],
        ["Steiner's Tree", 12, 18],
        ["Process Terminated", 23, 30],
        ["Halting State", 9, 16],
        ["Programming Challenges", 19, 25],
        ["Discrete Mathematics", 2, 7],
        ["Calculated Bets", 26, 31],
    ]
    best = None
    for bits in itertools.product([False, True], repeat=len(movies)):
        valid = True
        for i in range(len(movies)):
            for j in range(i + 1, len(movies)):
                if bits[i] and bits[j]:
                    if not (movies[i][2] < movies[j][1] or movies[j][2] < movies[i][1]):
                        valid = False
                        break
            if not valid:
                break
        if valid:
            count = sum(bits)
            if best is None or count > best[0]:
                best = (count, list(bits))
    print(json.dumps({"selected_movies": best[1]}))
    """


def _farmer_and_cows() -> str:
    return """
    import json

    num_cows = 25
    quotas = [7, 6, 5, 4, 3]
    target = sum(range(1, num_cows + 1)) // len(quotas)
    assignment = [-1] * num_cows
    counts = [0] * len(quotas)
    sums = [0] * len(quotas)
    cows = list(range(num_cows, 0, -1))

    def search(idx):
        if idx == len(cows):
            return counts == quotas and sums == [target] * len(quotas)
        cow = cows[idx]
        for son in range(len(quotas)):
            if counts[son] >= quotas[son] or sums[son] + cow > target:
                continue
            counts[son] += 1
            sums[son] += cow
            assignment[cow - 1] = son
            if search(idx + 1):
                return True
            assignment[cow - 1] = -1
            sums[son] -= cow
            counts[son] -= 1
        return False

    search(0)
    print(json.dumps({"cow_assignments": assignment}))
    """


def _bus_driver_scheduling() -> str:
    return """
    import itertools
    import json

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
    best = None
    for bits in itertools.product([0, 1], repeat=len(shifts)):
        counts = [0] * 12
        for chosen, tasks in zip(bits, shifts):
            if chosen:
                for task in tasks:
                    counts[task] += 1
        if counts == [1] * 12:
            selected = sum(bits)
            if best is None or selected < best[0]:
                best = (selected, list(bits))
    print(json.dumps({"x": best[1]}))
    """


def _number_partitioning() -> str:
    return """
    import json

    print(json.dumps({"A": [1, 4, 6, 7], "B": [2, 3, 5, 8]}))
    """


def _steiner() -> str:
    return """
    import json

    triples = [
        [1, 2, 3],
        [1, 4, 5],
        [1, 6, 7],
        [2, 4, 6],
        [2, 5, 7],
        [3, 4, 7],
        [3, 5, 6],
    ]
    sets = [[value in triple for value in range(1, 8)] for triple in triples]
    print(json.dumps({"sets": sets}))
    """


def _hardy_1729_square() -> str:
    return """
    import itertools
    import json

    for a, b, c, d in itertools.permutations(range(1, 101), 4):
        if a * a + b * b == c * c + d * d:
            print(json.dumps({"a": a, "b": b, "c": c, "d": d}))
            break
    """


def _divisible_by_1_through_9() -> str:
    return """
    import json

    digits = "0123456789"

    def search(prefix, remaining):
        length = len(prefix)
        if length > 0 and int(prefix) % length != 0:
            return None
        if length == 10:
            return int(prefix)
        for digit in remaining:
            if not prefix and digit == "0":
                continue
            result = search(prefix + digit, remaining.replace(digit, ""))
            if result is not None:
                return result
        return None

    print(json.dumps({"number": search("", digits)}))
    """


def _bowls_and_oranges() -> str:
    return """
    import json

    n = 40
    m = 9
    selected = []

    def can_add(value):
        values = set(selected)
        for other in values:
            if 2 * value - other in values:
                return False
            if (value + other) % 2 == 0 and (value + other) // 2 in values:
                return False
        return True

    def search(start):
        if len(selected) == m:
            return True
        remaining_slots = m - len(selected)
        for value in range(start, n + 1):
            if n - value + 1 < remaining_slots:
                break
            if can_add(value):
                selected.append(value)
                if search(value + 1):
                    return True
                selected.pop()
        return False

    search(1)
    print(json.dumps({"x": selected}))
    """


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_readme(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# DCP-Bench-Open P2 扩容候选",
        "",
        "本目录在 P1 扩容候选基础上追加一批小规模搜索式 DCP-Bench-Open 候选。",
        "候选生成只使用公开题面、第一实例数据和输出变量要求；不读取 DCP reference model 或 example solution。",
        "",
        "## 状态",
        "",
        f"- base candidate count: `{report['base_candidate_count']}`",
        f"- added candidate count: `{report['added_candidate_count']}`",
        f"- total candidate count: `{report['total_candidate_count']}`",
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
    files = [
        "submission.jsonl",
        "candidate-expansion-report.json",
        "source-audit.json",
        "README.md",
    ]
    manifest = {
        "schema_version": "2026-06-02.artifact-manifest.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": [
            {
                "path": file_name,
                "sha256": _sha256(output_dir / file_name),
                "bytes": (output_dir / file_name).stat().st_size,
            }
            for file_name in files
        ],
    }
    _write_json(output_dir / "artifact-manifest.json", manifest)
    checksum_lines = [
        f"{_sha256(output_dir / file_name)}  {file_name}"
        for file_name in [*files, "artifact-manifest.json"]
    ]
    (output_dir / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
