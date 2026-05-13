#!/usr/bin/env python3
"""Run the full-reproduction P1 baseline harness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.full_reproduction_harness import (  # noqa: E402
    FullReproductionRunConfig,
    prepare_fasttext_mini_dataset,
    run_fasttext_baseline_alignment,
    run_fasttext_full_data_alignment,
    run_fasttext_style_baseline,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full-reproduction harness steps")
    parser.add_argument("--target-spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--prepare-data", action="store_true")
    parser.add_argument("--run-baseline", action="store_true")
    parser.add_argument("--align-baseline", action="store_true")
    parser.add_argument("--align-full-data", action="store_true")
    parser.add_argument("--ag-news-train-csv", type=Path)
    parser.add_argument("--ag-news-test-csv", type=Path)
    parser.add_argument("--fasttext-binary", type=Path)
    parser.add_argument("--repeat-count", type=int, default=3)
    parser.add_argument("--max-train-seconds", type=int, default=300)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_modes = sum(
        bool(mode)
        for mode in [
            args.prepare_data,
            args.run_baseline,
            args.align_baseline,
            args.align_full_data,
        ]
    )
    if selected_modes != 1:
        print(
            "error: choose exactly one of --prepare-data, --run-baseline, "
            "--align-baseline, or --align-full-data",
            file=sys.stderr,
        )
        return 2

    if args.prepare_data:
        artifacts = prepare_fasttext_mini_dataset(
            target_spec_path=args.target_spec,
            output_dir=args.output_dir,
        )
        payload = {
            "status": "completed",
            "artifacts": {key: str(path) for key, path in artifacts.items()},
            "official_scores_claimed": False,
        }
    elif args.run_baseline:
        payload = run_fasttext_style_baseline(
            FullReproductionRunConfig(
                target_spec_path=args.target_spec,
                output_dir=args.output_dir,
                max_train_seconds=args.max_train_seconds,
            )
        )
    elif args.align_baseline:
        payload = run_fasttext_baseline_alignment(
            FullReproductionRunConfig(
                target_spec_path=args.target_spec,
                output_dir=args.output_dir,
                max_train_seconds=args.max_train_seconds,
            ),
            repeat_count=args.repeat_count,
        )
    else:
        if args.ag_news_train_csv is None or args.ag_news_test_csv is None:
            print(
                "error: --align-full-data requires --ag-news-train-csv and --ag-news-test-csv",
                file=sys.stderr,
            )
            return 2
        payload = run_fasttext_full_data_alignment(
            FullReproductionRunConfig(
                target_spec_path=args.target_spec,
                output_dir=args.output_dir,
                max_train_seconds=args.max_train_seconds,
            ),
            train_csv=args.ag_news_train_csv,
            test_csv=args.ag_news_test_csv,
            fasttext_binary=args.fasttext_binary,
            repeat_count=args.repeat_count,
        )

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
