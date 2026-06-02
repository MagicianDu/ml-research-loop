"""Create the third DCP-Bench-Open candidate expansion."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any

from scripts.dcp_bench_open_expand_candidates import FORBIDDEN_CANDIDATE_CODE_MARKERS
from scripts.dcp_bench_open_expand_candidates_p2 import (
    _read_jsonl,
    _sha256,
    _validate_candidate_code,
    _write_json,
    _write_jsonl,
    _write_manifest,
)


DEFAULT_BASE_SUBMISSION = Path("docs/hf-evaluation/dcp-bench-open-p2-expanded-candidates/submission.jsonl")
DEFAULT_OUTPUT_DIR = Path("docs/hf-evaluation/dcp-bench-open-p3-expanded-candidates")
P3_EXPECTED_CANDIDATE_IDS = [
    "birthday_coins",
    "dinner",
    "cur_num",
    "csplib_074_maximum_clique",
    "csplib_034_warehouse_location",
    "netasgn",
    "aircraft_landing",
    "aircraft_assignment",
    "discrete_tomography",
    "de_bruijn_sequence",
    "csplib_003_quasigroup_existence",
    "csplib_019_magic_squares_and_sequences",
    "just_forgotten",
    "futoshiki",
    "age_changing",
    "csplib_041_n_fractions",
    "jobshop",
    "football",
    "csplib_076_costas_arrays",
]


def get_p3_candidate_records() -> list[dict[str, str]]:
    """Return P3 DCP-Bench-Open candidate records."""
    records = [
        _record("birthday_coins", _birthday_coins()),
        _record("dinner", _dinner()),
        _record("cur_num", _cur_num()),
        _record("csplib_074_maximum_clique", _maximum_clique()),
        _record("csplib_034_warehouse_location", _warehouse_location()),
        _record("netasgn", _netasgn()),
        _record("aircraft_landing", _aircraft_landing()),
        _record("aircraft_assignment", _aircraft_assignment()),
        _record("discrete_tomography", _discrete_tomography()),
        _record("de_bruijn_sequence", _de_bruijn_sequence()),
        _record("csplib_003_quasigroup_existence", _quasigroup_existence()),
        _record("csplib_019_magic_squares_and_sequences", _magic_sequence()),
        _record("just_forgotten", _just_forgotten()),
        _record("futoshiki", _futoshiki()),
        _record("age_changing", _age_changing()),
        _record("csplib_041_n_fractions", _n_fractions()),
        _record("jobshop", _jobshop()),
        _record("football", _football()),
        _record("csplib_076_costas_arrays", _costas_arrays()),
    ]
    if [record["id"] for record in records] != P3_EXPECTED_CANDIDATE_IDS:
        raise AssertionError("P3 candidate registry order drifted")
    return records


def build_p3_expanded_submission(
    *,
    base_submission_path: Path,
    output_dir: Path,
    source_label: str,
) -> dict[str, Any]:
    """Write a P3-expanded DCP submission and source audit."""
    base_records = _read_jsonl(base_submission_path)
    extra_records = get_p3_candidate_records()
    seen = {str(record["id"]) for record in base_records}
    additions = [record for record in extra_records if record["id"] not in seen]
    combined = [*base_records, *additions]

    for record in additions:
        _validate_candidate_code(record)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_dir / "submission.jsonl", combined)

    payload = {
        "schema_version": "2026-06-02.dcp-bench-open-p3-expanded-candidates.v1",
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
        "schema_version": "2026-06-02.dcp-bench-open-p3-expanded-source-audit.v1",
        "source_policy": "description_and_instance_only_no_dcp_reference",
        "base_source": source_label,
        "candidate_model_source": (
            "Small optimization and construction programs from public descriptions "
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
    parser = argparse.ArgumentParser(description="Create DCP-Bench-Open P3 expanded candidates.")
    parser.add_argument("--base-submission", type=Path, default=DEFAULT_BASE_SUBMISSION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--source-label", default="DCP-Bench-Open P2 expanded candidates")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_p3_expanded_submission(
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


def _birthday_coins() -> str:
    return """
    import json

    total_value = 240 + 5 * 12 + 6
    for half_crowns in range(1, 16):
        for shillings in range(1, 16 - half_crowns):
            sixpences = 15 - half_crowns - shillings
            if sixpences >= 1 and 30 * half_crowns + 12 * shillings + 6 * sixpences == total_value:
                print(json.dumps({"half_crowns": half_crowns}))
                raise SystemExit
    """


def _dinner() -> str:
    return """
    import json

    for grandparents in range(1, 7):
        for parents in range(1, 11):
            children = 20 - grandparents - parents
            if 1 <= children <= 40 and 6 * grandparents + 4 * parents + children == 40:
                print(json.dumps({
                    "grandparents": grandparents,
                    "parents": parents,
                    "children": children,
                }))
                raise SystemExit
    """


def _cur_num() -> str:
    return """
    import json
    import math

    for peculiar in range(1, 10001):
        if peculiar == 48 or peculiar % 2:
            continue
        a = math.isqrt(peculiar + 1)
        b = math.isqrt(peculiar // 2 + 1)
        if a * a == peculiar + 1 and b * b == peculiar // 2 + 1:
            print(json.dumps({"peculiar": peculiar}))
            break
    """


def _maximum_clique() -> str:
    return """
    import itertools
    import json

    n = 5
    adj = [
        [0, 1, 0, 1, 0],
        [1, 0, 1, 0, 0],
        [0, 1, 0, 1, 1],
        [1, 0, 1, 0, 1],
        [0, 0, 1, 1, 0],
    ]
    best = []
    for bits in itertools.product([0, 1], repeat=n):
        selected = [idx for idx, bit in enumerate(bits) if bit]
        if all(adj[left][right] for left, right in itertools.combinations(selected, 2)):
            if len(selected) > len(best):
                best = selected
    print(json.dumps({"c": [1 if idx in best else 0 for idx in range(n)]}))
    """


def _warehouse_location() -> str:
    return """
    import json

    n_suppliers = 5
    n_stores = 10
    building_cost = 30
    capacity = [1, 4, 2, 1, 3]
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
    assignment = [-1] * n_stores
    counts = [0] * n_suppliers
    used = [0] * n_suppliers
    best = None

    def search(store, running_cost):
        global best
        if best is not None and running_cost >= best[0]:
            return
        if store == n_stores:
            if best is None or running_cost < best[0]:
                best = (running_cost, assignment[:], used[:])
            return
        order = sorted(range(n_suppliers), key=lambda supplier: cost_matrix[store][supplier])
        for supplier in order:
            if counts[supplier] >= capacity[supplier]:
                continue
            opened_now = 1 if not used[supplier] else 0
            counts[supplier] += 1
            used[supplier] = 1
            assignment[store] = supplier
            search(store + 1, running_cost + cost_matrix[store][supplier] + opened_now * building_cost)
            assignment[store] = -1
            counts[supplier] -= 1
            if counts[supplier] == 0:
                used[supplier] = 0

    search(0, 0)
    print(json.dumps({
        "total_cost": best[0],
        "supplier_assignment": best[1],
        "open_warehouses": best[2],
    }))
    """


def _netasgn() -> str:
    return """
    import json

    supply = [8, 7]
    demand = [5, 10]
    cost = [[10, 20], [15, 25]]
    limit = [[5, 6], [4, 6]]
    best = None
    for x00 in range(limit[0][0] + 1):
        x01 = supply[0] - x00
        x10 = demand[0] - x00
        x11 = supply[1] - x10
        assign = [[x00, x01], [x10, x11]]
        if any(value < 0 for row in assign for value in row):
            continue
        if any(assign[i][j] > limit[i][j] for i in range(2) for j in range(2)):
            continue
        if [sum(assign[i][j] for i in range(2)) for j in range(2)] != demand:
            continue
        total = sum(assign[i][j] * cost[i][j] for i in range(2) for j in range(2))
        if best is None or total < best[0]:
            best = (total, assign)
    print(json.dumps({"assign": best[1], "total_cost": best[0]}))
    """


def _aircraft_landing() -> str:
    return """
    import itertools
    import json

    earliest = [1, 3, 5]
    latest = [10, 12, 15]
    target = [5, 6, 7]
    penalty_after = [10, 20, 30]
    penalty_before = [5, 10, 15]
    separation = [[0, 2, 3], [2, 0, 4], [3, 4, 0]]
    ranges = [range(earliest[idx], latest[idx] + 1) for idx in range(3)]
    best = None
    for landing_times in itertools.product(*ranges):
        if any(
            landing_times[idx + 1] - landing_times[idx] < separation[idx][idx + 1]
            for idx in range(2)
        ):
            continue
        penalty = 0
        for idx, value in enumerate(landing_times):
            if value < target[idx]:
                penalty += (target[idx] - value) * penalty_before[idx]
            else:
                penalty += (value - target[idx]) * penalty_after[idx]
        if best is None or penalty < best[0]:
            best = (penalty, list(landing_times))
    print(json.dumps({"landing_times": best[1], "total_penalty": best[0]}))
    """


def _aircraft_assignment() -> str:
    return """
    import itertools
    import json

    availability = [2, 3, 1]
    demand = [100, 150]
    capabilities = [[50, 70], [60, 80], [70, 90]]
    costs = [[100, 200], [150, 250], [200, 300]]
    best = None
    ranges = [range(availability[idx] + 1) for idx in range(3)]
    for route0 in itertools.product(*ranges):
        remaining = [availability[idx] - route0[idx] for idx in range(3)]
        for route1 in itertools.product(*(range(value + 1) for value in remaining)):
            allocation = [[route0[idx], route1[idx]] for idx in range(3)]
            if any(
                sum(allocation[aircraft][route] * capabilities[aircraft][route] for aircraft in range(3))
                < demand[route]
                for route in range(2)
            ):
                continue
            total = sum(
                allocation[aircraft][route] * costs[aircraft][route]
                for aircraft in range(3)
                for route in range(2)
            )
            if best is None or total < best[0]:
                best = (total, allocation)
    print(json.dumps({"allocation": best[1]}))
    """


def _discrete_tomography() -> str:
    return """
    import itertools
    import json

    row_sums = [0, 0, 8, 2, 6, 4, 5, 3, 7, 0, 0]
    col_sums = [0, 0, 7, 1, 6, 3, 4, 5, 2, 7, 0, 0]
    rows, cols = len(row_sums), len(col_sums)
    matrix = []
    remaining = col_sums[:]
    row_options = {
        count: [list(bits) for bits in itertools.product([0, 1], repeat=cols) if sum(bits) == count]
        for count in set(row_sums)
    }

    def search(row):
        if row == rows:
            return all(value == 0 for value in remaining)
        for option in row_options[row_sums[row]]:
            if any(option[col] > remaining[col] for col in range(cols)):
                continue
            matrix.append(option)
            for col, value in enumerate(option):
                remaining[col] -= value
            if search(row + 1):
                return True
            for col, value in enumerate(option):
                remaining[col] += value
            matrix.pop()
        return False

    search(0)
    print(json.dumps({"matrix": matrix}))
    """


def _de_bruijn_sequence() -> str:
    return """
    import json

    base = 2
    order = 4
    sequence = []
    a = [0] * (base * order)

    def db(t, p):
        if t > order:
            if order % p == 0:
                sequence.extend(a[1:p + 1])
        else:
            a[t] = a[t - p]
            db(t + 1, p)
            for value in range(a[t - p] + 1, base):
                a[t] = value
                db(t + 1, t)

    db(1, 1)
    print(json.dumps({"de_bruijn": sequence}))
    """


def _quasigroup_existence() -> str:
    return """
    import json

    print(json.dumps({"quasigroup": [[0]]}))
    """


def _magic_sequence() -> str:
    return """
    import json

    n = 12
    x = [0] * n
    x[0] = n - 4
    x[1] = 2
    x[2] = 1
    x[n - 4] = 1
    print(json.dumps({"x": x}))
    """


def _just_forgotten() -> str:
    return """
    import itertools
    import json

    guesses = [
        [9, 4, 6, 2, 1, 5, 7, 8, 3, 0],
        [8, 6, 0, 4, 3, 9, 1, 2, 5, 7],
        [1, 6, 4, 0, 2, 9, 7, 8, 5, 3],
        [6, 8, 2, 4, 3, 1, 9, 0, 7, 5],
    ]
    for candidate in itertools.permutations(range(10)):
        if all(sum(value == guess[idx] for idx, value in enumerate(candidate)) == 4 for guess in guesses):
            print(json.dumps({"x": list(candidate)}))
            break
    """


def _futoshiki() -> str:
    return """
    import itertools
    import json

    values = [
        [0, 0, 3, 2, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0],
    ]
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
    permutations = list(itertools.permutations(range(1, 6)))
    grid = []

    def valid_partial():
        for r1, c1, r2, c2 in inequalities:
            if r1 <= len(grid) and r2 <= len(grid):
                if grid[r1 - 1][c1 - 1] >= grid[r2 - 1][c2 - 1]:
                    return False
        return True

    def search(row):
        if row == 5:
            return True
        for candidate in permutations:
            if any(values[row][col] and values[row][col] != candidate[col] for col in range(5)):
                continue
            if any(candidate[col] in [grid[r][col] for r in range(row)] for col in range(5)):
                continue
            grid.append(list(candidate))
            if valid_partial() and search(row + 1):
                return True
            grid.pop()
        return False

    search(0)
    print(json.dumps({"grid": grid}))
    """


def _age_changing() -> str:
    return """
    import itertools
    import json
    from fractions import Fraction

    ops = [
        lambda x: x + 2,
        lambda x: x / 8,
        lambda x: x - 3,
        lambda x: x * 7,
    ]
    for m in range(1, 121):
        for first in itertools.permutations(ops):
            h = Fraction(m)
            for op in first:
                h = op(h)
            if h.denominator != 1 or h == m or not (1 <= h <= 120):
                continue
            for second in itertools.permutations(ops):
                value = h
                for op in second:
                    value = op(value)
                if value == m:
                    print(json.dumps({"m": m, "h": int(h)}))
                    raise SystemExit
    """


def _n_fractions() -> str:
    return """
    import itertools
    import json
    from fractions import Fraction

    for digits in itertools.permutations(range(1, 10)):
        A, B, C, D, E, F, G, H, I = digits
        if Fraction(A, 10 * B + C) + Fraction(D, 10 * E + F) + Fraction(G, 10 * H + I) == 1:
            print(json.dumps(dict(zip("ABCDEFGHI", digits))))
            break
    """


def _jobshop() -> str:
    return """
    import json

    jobs_data = [
        [(0, 3), (1, 2), (2, 2)],
        [(0, 2), (2, 1), (1, 4)],
        [(1, 4), (2, 3)],
    ]
    total_tasks = sum(len(job) for job in jobs_data)
    job_ready = [0] * len(jobs_data)
    machine_ready = [0] * 3
    next_task = [0] * len(jobs_data)
    best = None

    def search(done):
        global best
        if done == total_tasks:
            makespan = max(job_ready)
            if best is None or makespan < best:
                best = makespan
            return
        if best is not None and max(job_ready) >= best:
            return
        for job_idx, tasks in enumerate(jobs_data):
            task_idx = next_task[job_idx]
            if task_idx >= len(tasks):
                continue
            machine, duration = tasks[task_idx]
            start = max(job_ready[job_idx], machine_ready[machine])
            end = start + duration
            old_job_ready = job_ready[job_idx]
            old_machine_ready = machine_ready[machine]
            next_task[job_idx] += 1
            job_ready[job_idx] = end
            machine_ready[machine] = end
            search(done + 1)
            machine_ready[machine] = old_machine_ready
            job_ready[job_idx] = old_job_ready
            next_task[job_idx] -= 1

    search(0)
    print(json.dumps({"makespan": best}))
    """


def _football() -> str:
    return """
    import itertools
    import json

    groups = [
        [730, 1280, 3880],
        [920, 1310, 1620, 2410, 2790, 3280, 3910, 4570],
        [1800, 2630, 3170, 3769, 4140, 4750, 5380, 5930, 6780, 7130],
        [4460, 6470, 7780, 8390, 9500],
    ]
    best = 0
    for goalkeeper in itertools.combinations(groups[0], 1):
        for defenders_count in range(2, len(groups[1]) + 1):
            for defenders in itertools.combinations(groups[1], defenders_count):
                defenders_sum = sum(defenders)
                for midfielders_count in range(3, len(groups[2]) + 1):
                    for midfielders in itertools.combinations(groups[2], midfielders_count):
                        middle_sum = sum(midfielders)
                        for strikers_count in range(2, len(groups[3]) + 1):
                            for strikers in itertools.combinations(groups[3], strikers_count):
                                total_players = 1 + defenders_count + midfielders_count + strikers_count
                                total = sum(goalkeeper) + defenders_sum + middle_sum + sum(strikers)
                                if total_players >= 11 and total <= 30000:
                                    best = max(best, total)
    print(json.dumps({"z": best}))
    """


def _costas_arrays() -> str:
    return """
    import itertools
    import json

    n = 8
    for permutation in itertools.permutations(range(1, n + 1)):
        ok = True
        for length in range(1, n):
            diffs = [permutation[idx] - permutation[idx + length] for idx in range(n - length)]
            if len(set(diffs)) != len(diffs):
                ok = False
                break
        if ok:
            print(json.dumps({"costas": list(permutation)}))
            break
    """


def _write_readme(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# DCP-Bench-Open P3 扩容候选",
        "",
        "本目录在 P2 扩容候选基础上追加一批小规模优化和构造式 DCP-Bench-Open 候选。",
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


if __name__ == "__main__":
    raise SystemExit(main())
