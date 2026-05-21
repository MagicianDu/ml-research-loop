"""Write Smol AI WorldCup live verification artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib.benchmarks import write_smol_worldcup_live_verification


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify the live Smol AI WorldCup public target and write P0 artifacts."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument(
        "--no-raw",
        action="store_true",
        help="Skip writing raw HTTP responses.",
    )
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = write_smol_worldcup_live_verification(
        args.output_dir,
        timeout_seconds=args.timeout_seconds,
        include_raw=not args.no_raw,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["status"] == "written" else 1


if __name__ == "__main__":
    raise SystemExit(main())
