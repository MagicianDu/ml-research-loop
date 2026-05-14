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
    run_fasttext_binary_baseline,
    run_fasttext_full_data_alignment,
    run_fasttext_multi_proposal_loop,
    run_fasttext_patch_round,
    run_fasttext_style_baseline,
    write_fasttext_release_proof_bundle,
    write_fasttext_patch_round_proof_bundle,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full-reproduction harness steps")
    parser.add_argument("--target-spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--prepare-data", action="store_true")
    parser.add_argument("--run-baseline", action="store_true")
    parser.add_argument("--align-baseline", action="store_true")
    parser.add_argument("--align-full-data", action="store_true")
    parser.add_argument("--run-fasttext-baseline", action="store_true")
    parser.add_argument("--run-fasttext-patch-round", action="store_true")
    parser.add_argument("--run-fasttext-multi-proposal-loop", action="store_true")
    parser.add_argument("--write-fasttext-patch-proof-bundle", action="store_true")
    parser.add_argument("--write-fasttext-release-proof-bundle", action="store_true")
    parser.add_argument("--ag-news-train-csv", type=Path)
    parser.add_argument("--ag-news-test-csv", type=Path)
    parser.add_argument("--fasttext-binary", type=Path)
    parser.add_argument("--baseline-report", type=Path)
    parser.add_argument("--fasttext-proposal", type=Path)
    parser.add_argument("--fasttext-proposals", type=Path)
    parser.add_argument("--patch-round-report", type=Path)
    parser.add_argument("--proof-manifest", type=Path)
    parser.add_argument("--multi-round-report", type=Path)
    parser.add_argument("--reviewer", default="local-review")
    parser.add_argument("--review-status", default="approved_with_limitations")
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
            args.run_fasttext_baseline,
            args.run_fasttext_patch_round,
            args.run_fasttext_multi_proposal_loop,
            args.write_fasttext_patch_proof_bundle,
            args.write_fasttext_release_proof_bundle,
        ]
    )
    if selected_modes != 1:
        print(
            "error: choose exactly one of --prepare-data, --run-baseline, "
            "--align-baseline, --align-full-data, --run-fasttext-baseline, "
            "--run-fasttext-patch-round, --run-fasttext-multi-proposal-loop, "
            "--write-fasttext-patch-proof-bundle, or "
            "--write-fasttext-release-proof-bundle",
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
    elif args.align_full_data:
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
    elif args.run_fasttext_baseline:
        if args.ag_news_train_csv is None or args.ag_news_test_csv is None:
            print(
                "error: --run-fasttext-baseline requires --ag-news-train-csv and --ag-news-test-csv",
                file=sys.stderr,
            )
            return 2
        if args.fasttext_binary is None:
            print(
                "error: --run-fasttext-baseline requires --fasttext-binary",
                file=sys.stderr,
            )
            return 2
        payload = run_fasttext_binary_baseline(
            FullReproductionRunConfig(
                target_spec_path=args.target_spec,
                output_dir=args.output_dir,
                max_train_seconds=args.max_train_seconds,
            ),
            train_csv=args.ag_news_train_csv,
            test_csv=args.ag_news_test_csv,
            fasttext_binary=args.fasttext_binary,
        )
    elif args.run_fasttext_patch_round:
        if args.ag_news_train_csv is None or args.ag_news_test_csv is None:
            print(
                "error: --run-fasttext-patch-round requires --ag-news-train-csv and --ag-news-test-csv",
                file=sys.stderr,
            )
            return 2
        if args.fasttext_binary is None:
            print(
                "error: --run-fasttext-patch-round requires --fasttext-binary",
                file=sys.stderr,
            )
            return 2
        if args.baseline_report is None:
            print(
                "error: --run-fasttext-patch-round requires --baseline-report",
                file=sys.stderr,
            )
            return 2
        if args.fasttext_proposal is None:
            print(
                "error: --run-fasttext-patch-round requires --fasttext-proposal",
                file=sys.stderr,
            )
            return 2
        proposal = json.loads(args.fasttext_proposal.read_text(encoding="utf-8"))
        payload = run_fasttext_patch_round(
            FullReproductionRunConfig(
                target_spec_path=args.target_spec,
                output_dir=args.output_dir,
                max_train_seconds=args.max_train_seconds,
            ),
            train_csv=args.ag_news_train_csv,
            test_csv=args.ag_news_test_csv,
            fasttext_binary=args.fasttext_binary,
            baseline_report=args.baseline_report,
            proposal=proposal,
        )
    elif args.run_fasttext_multi_proposal_loop:
        if args.ag_news_train_csv is None or args.ag_news_test_csv is None:
            print(
                "error: --run-fasttext-multi-proposal-loop requires "
                "--ag-news-train-csv and --ag-news-test-csv",
                file=sys.stderr,
            )
            return 2
        if args.fasttext_binary is None:
            print(
                "error: --run-fasttext-multi-proposal-loop requires --fasttext-binary",
                file=sys.stderr,
            )
            return 2
        if args.baseline_report is None:
            print(
                "error: --run-fasttext-multi-proposal-loop requires --baseline-report",
                file=sys.stderr,
            )
            return 2
        if args.fasttext_proposals is None:
            print(
                "error: --run-fasttext-multi-proposal-loop requires --fasttext-proposals",
                file=sys.stderr,
            )
            return 2
        proposals = _load_fasttext_proposals(args.fasttext_proposals)
        payload = run_fasttext_multi_proposal_loop(
            FullReproductionRunConfig(
                target_spec_path=args.target_spec,
                output_dir=args.output_dir,
                max_train_seconds=args.max_train_seconds,
            ),
            train_csv=args.ag_news_train_csv,
            test_csv=args.ag_news_test_csv,
            fasttext_binary=args.fasttext_binary,
            baseline_report=args.baseline_report,
            proposals=proposals,
        )
    elif args.write_fasttext_patch_proof_bundle:
        if args.patch_round_report is None:
            print(
                "error: --write-fasttext-patch-proof-bundle requires --patch-round-report",
                file=sys.stderr,
            )
            return 2
        payload = write_fasttext_patch_round_proof_bundle(
            patch_round_report=args.patch_round_report,
            output_dir=args.output_dir,
            reviewer=args.reviewer,
            review_status=args.review_status,
        )
    else:
        if args.proof_manifest is None:
            print(
                "error: --write-fasttext-release-proof-bundle requires --proof-manifest",
                file=sys.stderr,
            )
            return 2
        payload = write_fasttext_release_proof_bundle(
            proof_manifest=args.proof_manifest,
            output_dir=args.output_dir,
            multi_round_report=args.multi_round_report,
            reviewer=args.reviewer,
        )

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _load_fasttext_proposals(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    proposals = payload.get("proposals") if isinstance(payload, dict) else payload
    if not isinstance(proposals, list) or not proposals:
        raise ValueError("--fasttext-proposals must contain a non-empty list")
    if not all(isinstance(proposal, dict) for proposal in proposals):
        raise ValueError("--fasttext-proposals entries must be objects")
    return proposals


if __name__ == "__main__":
    raise SystemExit(main())
