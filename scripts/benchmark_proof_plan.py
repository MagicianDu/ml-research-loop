#!/usr/bin/env python3
"""Build a read-only public proof-run plan for benchmark adapters."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib.benchmarks import build_official_harness_probe, build_public_proof_plan


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a public proof-run plan")
    parser.add_argument("--mle-bench-repo", type=Path)
    parser.add_argument("--paperbench-repo", type=Path)
    parser.add_argument("--paperbench-data-dir", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    probe = build_official_harness_probe(
        mle_bench_repo=args.mle_bench_repo,
        paperbench_repo=args.paperbench_repo,
        paperbench_data_dir=args.paperbench_data_dir,
    )
    payload = build_public_proof_plan(probe)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
