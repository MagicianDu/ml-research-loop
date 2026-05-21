"""Write a Smol AI WorldCup prompt leakage audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib.benchmarks import write_smol_worldcup_prompt_leakage_audit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit Smol AI WorldCup local model prompts for evaluation-only leakage."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--prompt-profile",
        default="default",
        choices=[
            "default",
            "p3-routing-v1",
            "p3-dev-v2",
            "p3-semantic-v1",
            "p3-semantic-v2",
        ],
    )
    parser.add_argument(
        "--evaluation-split",
        default="all",
        choices=["all", "dev", "canary"],
    )
    parser.add_argument("--canary-fraction", type=float, default=0.2)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = write_smol_worldcup_prompt_leakage_audit(
        args.output_dir,
        timeout_seconds=args.timeout_seconds,
        page_size=args.page_size,
        limit=args.limit,
        prompt_profile=args.prompt_profile,
        evaluation_split=args.evaluation_split,
        canary_fraction=args.canary_fraction,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["status"] == "written" else 1


if __name__ == "__main__":
    raise SystemExit(main())
