"""Run the Smol AI WorldCup local-compatible baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib.benchmarks import write_smol_worldcup_baseline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a deterministic local Smol AI WorldCup baseline and write P1 artifacts."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--strategy", default="local-abstain-baseline")
    parser.add_argument(
        "--evaluation-split",
        default="all",
        choices=["all", "dev", "canary"],
    )
    parser.add_argument("--canary-fraction", type=float, default=0.2)
    parser.add_argument("--model-size-billion", type=float, default=0.001)
    parser.add_argument("--estimated-ram-gb", type=float, default=0.01)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = write_smol_worldcup_baseline(
        args.output_dir,
        timeout_seconds=args.timeout_seconds,
        page_size=args.page_size,
        strategy=args.strategy,
        limit=args.limit,
        evaluation_split=args.evaluation_split,
        canary_fraction=args.canary_fraction,
        model_size_billion=args.model_size_billion,
        estimated_ram_gb=args.estimated_ram_gb,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["status"] == "written" else 1


if __name__ == "__main__":
    raise SystemExit(main())
