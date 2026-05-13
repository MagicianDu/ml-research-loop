#!/usr/bin/env python3
"""Write a full-paper reproduction target spec."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.full_reproduction import (  # noqa: E402
    FullReproductionCandidate,
    evaluate_full_reproduction_candidate,
    write_full_reproduction_target,
)


FASTTEXT_CANDIDATE = FullReproductionCandidate(
    paper_id="arxiv:1607.01759",
    title="Bag of Tricks for Efficient Text Classification",
    paper_url="https://arxiv.org/abs/1607.01759",
    code_url="https://github.com/facebookresearch/fastText",
    task="supervised text classification",
    primary_metric="accuracy",
    dataset_track="AG News or equivalent public text classification dataset",
    baseline_command="fasttext supervised -input train.txt -output model",
    evaluation_command="fasttext test model.bin test.txt",
    resource_profile="cpu_standard_hardware",
    expected_runtime_minutes=30,
    target_claim="fastText-style supervised classifier reproduces a core text classification track",
    improvement_objective="improve local held-out accuracy over the reproduced baseline",
    blockers=[],
    official_scores_claimed=False,
)


MIXUP_CANDIDATE = FullReproductionCandidate(
    paper_id="arxiv:1710.09412",
    title="mixup: Beyond Empirical Risk Minimization",
    paper_url="https://arxiv.org/abs/1710.09412",
    code_url="https://github.com/facebookresearch/mixup-cifar10",
    task="CIFAR-10 image classification",
    primary_metric="top1_accuracy",
    dataset_track="CIFAR-10",
    baseline_command="python train.py --lr=0.1 --seed=20170922 --decay=1e-4",
    evaluation_command="python train.py test checkpoint",
    resource_profile="gpu_legacy_python_stack",
    expected_runtime_minutes=240,
    target_claim="mixup improves image classification generalization",
    improvement_objective="improve local validation accuracy over reproduced baseline",
    blockers=["requires_gpu", "requires_legacy_python36_stack"],
    official_scores_claimed=False,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write a full reproduction target spec")
    parser.add_argument("--paper-id", default=FASTTEXT_CANDIDATE.paper_id)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        candidate = _candidate_for_paper_id(args.paper_id)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    spec = evaluate_full_reproduction_candidate(candidate)
    written = write_full_reproduction_target(spec, args.output_dir)
    payload = {
        "status": "completed",
        "decision": spec.decision,
        "paper_id": spec.paper_id,
        "target_json": str(written["target_json"]),
        "target_markdown": str(written["target_markdown"]),
        "official_scores_claimed": False,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _candidate_for_paper_id(paper_id: str) -> FullReproductionCandidate:
    if paper_id == FASTTEXT_CANDIDATE.paper_id:
        return FASTTEXT_CANDIDATE
    if paper_id == MIXUP_CANDIDATE.paper_id:
        return MIXUP_CANDIDATE
    raise ValueError(f"unsupported full reproduction paper id: {paper_id}")


if __name__ == "__main__":
    raise SystemExit(main())
