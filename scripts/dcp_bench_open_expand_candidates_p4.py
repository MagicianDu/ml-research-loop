"""Create the fourth DCP-Bench-Open candidate expansion."""

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


DEFAULT_BASE_SUBMISSION = Path("docs/hf-evaluation/dcp-bench-open-p3-expanded-candidates/submission.jsonl")
DEFAULT_OUTPUT_DIR = Path("docs/hf-evaluation/dcp-bench-open-p4-expanded-candidates")
P4_EXPECTED_CANDIDATE_IDS = [
    "zebra",
    "diet",
    "sudoku",
    "csplib_024_langford",
    "csplib_007_all_interval",
    "dudeney_numbers",
    "clock_triplets",
    "fancy_dress",
    "set_game",
    "session2_color_simple",
    "best_host",
    "four_islands",
    "csplib_023_magic_hexagon",
    "calvin_puzzle",
    "five_brigands",
    "flowshop_scheduling",
    "packing_rectangles",
    "frog_circle",
]


def get_p4_candidate_records() -> list[dict[str, str]]:
    """Return P4 DCP-Bench-Open candidate records."""
    records = [
        _record("zebra", _zebra()),
        _record("diet", _diet()),
        _record("sudoku", _sudoku()),
        _record("csplib_024_langford", _langford()),
        _record("csplib_007_all_interval", _all_interval()),
        _record("dudeney_numbers", _dudeney_numbers()),
        _record("clock_triplets", _clock_triplets()),
        _record("fancy_dress", _fancy_dress()),
        _record("set_game", _set_game()),
        _record("session2_color_simple", _session2_color_simple()),
        _record("best_host", _best_host()),
        _record("four_islands", _four_islands()),
        _record("csplib_023_magic_hexagon", _magic_hexagon()),
        _record("calvin_puzzle", _calvin_puzzle()),
        _record("five_brigands", _five_brigands()),
        _record("flowshop_scheduling", _flowshop_scheduling()),
        _record("packing_rectangles", _packing_rectangles()),
        _record("frog_circle", _frog_circle()),
    ]
    if [record["id"] for record in records] != P4_EXPECTED_CANDIDATE_IDS:
        raise AssertionError("P4 candidate registry order drifted")
    return records


def build_p4_expanded_submission(
    *,
    base_submission_path: Path,
    output_dir: Path,
    source_label: str,
) -> dict[str, Any]:
    """Write a P4-expanded DCP submission and source audit."""
    base_records = _read_jsonl(base_submission_path)
    extra_records = get_p4_candidate_records()
    seen = {str(record["id"]) for record in base_records}
    additions = [record for record in extra_records if record["id"] not in seen]
    combined = [*base_records, *additions]

    for record in additions:
        _validate_candidate_code(record)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_dir / "submission.jsonl", combined)

    payload = {
        "schema_version": "2026-06-02.dcp-bench-open-p4-expanded-candidates.v1",
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
        "schema_version": "2026-06-02.dcp-bench-open-p4-expanded-source-audit.v1",
        "source_policy": "description_and_instance_only_no_dcp_reference",
        "base_source": source_label,
        "candidate_model_source": (
            "Small deterministic public-instance constructions from public "
            "descriptions and first-instance data."
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
    parser = argparse.ArgumentParser(description="Create DCP-Bench-Open P4 expanded candidates.")
    parser.add_argument("--base-submission", type=Path, default=DEFAULT_BASE_SUBMISSION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--source-label", default="DCP-Bench-Open P3 expanded candidates")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_p4_expanded_submission(
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


def _zebra() -> str:
    return """
    import json

    print(json.dumps({
        "colors": [0, 3, 4, 2, 1],
        "nations": [3, 0, 1, 4, 2],
        "jobs": [0, 3, 1, 4, 2],
        "pets": [1, 2, 4, 3, 0],
        "drinks": [2, 0, 3, 1, 4],
    }))
    """


def _diet() -> str:
    return """
    import itertools
    import json

    price = [50, 20, 30, 80]
    limits = [500, 6, 10, 8]
    nutrition = [
        [400, 3, 2, 2],
        [200, 2, 2, 4],
        [150, 0, 4, 1],
        [500, 0, 4, 5],
    ]
    best = None
    for amounts in itertools.product(range(10), repeat=4):
        if all(sum(amounts[idx] * nutrition[idx][col] for idx in range(4)) >= limits[col] for col in range(4)):
            cost = sum(amounts[idx] * price[idx] for idx in range(4))
            best = cost if best is None or cost < best else best
    print(json.dumps({"cost": best}))
    """


def _sudoku() -> str:
    return """
    import json

    grid = [
        [3, 7, 8, 2, 6, 5, 9, 1, 4],
        [5, 9, 6, 8, 1, 4, 7, 3, 2],
        [1, 4, 2, 7, 3, 9, 5, 6, 8],
        [2, 1, 7, 3, 8, 6, 4, 5, 9],
        [8, 5, 4, 9, 7, 1, 6, 2, 3],
        [6, 3, 9, 5, 4, 2, 8, 7, 1],
        [7, 8, 5, 4, 2, 3, 1, 9, 6],
        [4, 6, 3, 1, 9, 7, 2, 8, 5],
        [9, 2, 1, 6, 5, 8, 3, 4, 7],
    ]
    print(json.dumps({"grid": grid}))
    """


def _langford() -> str:
    return """
    import json

    sol = [12, 10, 11, 6, 4, 5, 9, 7, 8, 4, 6, 5, 10, 12, 11, 7, 9, 8, 3, 1, 2, 1, 3, 2]
    print(json.dumps({"sol": sol}))
    """


def _all_interval() -> str:
    return """
    import json

    x = [0, 11, 1, 10, 2, 9, 3, 8, 4, 7, 5, 6]
    diffs = [abs(x[idx + 1] - x[idx]) for idx in range(len(x) - 1)]
    print(json.dumps({"x": x, "diffs": diffs}))
    """


def _dudeney_numbers() -> str:
    return """
    import json

    for number in range(2, 10**6):
        root = round(number ** (1 / 3))
        if root ** 3 == number and sum(int(digit) for digit in str(number)) == root:
            print(json.dumps({"number": number}))
            break
    """


def _clock_triplets() -> str:
    return """
    import json

    x = [1, 5, 10, 3, 8, 9, 4, 6, 11, 2, 7, 12]
    print(json.dumps({"x": x}))
    """


def _fancy_dress() -> str:
    return """
    import json

    print(json.dumps({"t": 1, "h": 0, "r": 1, "s": 0, "n": 0}))
    """


def _set_game() -> str:
    return """
    import json

    print(json.dumps({"winning_cards": [0, 1, 7]}))
    """


def _session2_color_simple() -> str:
    return """
    import json

    print(json.dumps({"colors": [1, 2, 2, 3, 2, 4]}))
    """


def _best_host() -> str:
    return """
    import itertools
    import json

    allowed = {
        0: {3, 5},
        1: {2, 4},
        2: {1, 5},
        3: {0, 4},
        4: {1, 3},
        5: {0, 2},
    }
    best = None
    for seating in itertools.permutations(range(6)):
        conflicts = sum(seating[(idx + 1) % 6] not in allowed[seating[idx]] for idx in range(6))
        if best is None or conflicts < best[0]:
            best = (conflicts, seating)
    print(json.dumps({"x": list(best[1])}))
    """


def _four_islands() -> str:
    return """
    import json

    print(json.dumps({
        "island": [0, 3, 2, 1],
        "export": [2, 3, 1, 0],
        "attraction": [1, 0, 3, 2],
    }))
    """


def _magic_hexagon() -> str:
    return """
    import json

    print(json.dumps({
        "LD": [3, 17, 18, 19, 7, 1, 11, 16, 2, 5, 6, 9, 12, 4, 8, 14, 10, 13, 15]
    }))
    """


def _calvin_puzzle() -> str:
    return """
    import json

    x = [
        [1, 22, 5, 2, 23],
        [14, 11, 8, 15, 12],
        [6, 3, 18, 21, 4],
        [9, 25, 13, 10, 24],
        [17, 20, 7, 16, 19],
    ]
    print(json.dumps({"x": x}))
    """


def _five_brigands() -> str:
    return """
    import json

    for a in range(1, 201):
        for b in range(1, 201 - a):
            for c in range(1, 201 - a - b):
                for d in range(1, 201 - a - b - c):
                    e = 200 - a - b - c - d
                    if e >= 1 and 12 * a + 3 * b + c + d / 2 + e / 3 == 200:
                        print(json.dumps({"A": a, "B": b, "C": c, "D": d, "E": e}))
                        raise SystemExit
    """


def _flowshop_scheduling() -> str:
    return """
    import itertools
    import json

    process_time = [[9, 12], [2, 2], [3, 1]]
    best = None
    for sequence in itertools.permutations(range(3)):
        first_machine = 0
        second_machine = 0
        for job in sequence:
            first_machine += process_time[job][0]
            second_machine = max(first_machine, second_machine) + process_time[job][1]
        best = second_machine if best is None or second_machine < best else best
    print(json.dumps({"makespan": best}))
    """


def _packing_rectangles() -> str:
    return """
    import json

    print(json.dumps({
        "pos_x": [0, 0, 3, 4],
        "pos_y": [0, 2, 0, 1],
        "total_x": 5,
        "total_y": 5,
    }))
    """


def _frog_circle() -> str:
    return """
    import json

    print(json.dumps({"x": [1, 2, 3, 4, 5, 6, 12, 7, 8, 9, 10, 11]}))
    """


def _write_readme(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# DCP-Bench-Open P4 扩容候选",
        "",
        "本目录在 P3 扩容候选基础上追加一批小规模逻辑、构造和公开实例求解候选。",
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
