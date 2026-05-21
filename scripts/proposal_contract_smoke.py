#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.proposal_contract import (
    build_proposal_context,
    build_proposal_reflection,
    validate_client_proposal,
)


DEFAULT_FIXTURE_DIR = ROOT / "examples" / "proposal-contract"


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        summary = run_smoke(
            fixture_dir=args.fixture_dir,
            output_dir=args.output_dir,
            force=args.force,
        )
    except FileExistsError as exc:
        print(f"artifact already exists: {exc}; rerun with --force to overwrite", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - keeps CLI failures readable.
        print(f"proposal contract smoke failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        print(f"summary_file: {summary['summary_file']}")
        print(f"accepted_validation_status: {summary['accepted_validation_status']}")
        print(f"rejected_validation_status: {summary['rejected_validation_status']}")
        print(f"reflection_status: {summary['reflection_status']}")
        print(f"recommended_next_action: {summary['recommended_next_action']}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a local proposal contract context -> validate -> reflect smoke demo.",
    )
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser


def run_smoke(*, fixture_dir: Path, output_dir: Path, force: bool = False) -> dict[str, Any]:
    fixture_dir = fixture_dir.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    accepted_proposal = _read_json(fixture_dir / "accepted-proposal.json")
    rejected_proposal = _read_json(fixture_dir / "rejected-proposal.json")
    evaluation = _read_json(fixture_dir / "evaluation-payload.json")

    allowed_change_surfaces = ["prompt_profile", "routing", "decoding"]
    context = build_proposal_context(
        objective=(
            "Build bounded client-side proposal candidates for local prompt/profile "
            "iteration without running experiments or claiming official scores."
        ),
        output_dir=output_dir,
        baseline_report=fixture_dir / "baseline-report.json",
        current_report=fixture_dir / "current-report.json",
        dev_report=fixture_dir / "dev-report.json",
        canary_report=fixture_dir / "canary-report.json",
        failure_samples=fixture_dir / "failure-samples.json",
        resource_constraints={
            "max_local_rounds": 5,
            "llm_calls_allowed": False,
            "experiment_execution_allowed": False,
            "official_score_claims_allowed": False,
        },
        allowed_change_surfaces=allowed_change_surfaces,
        max_proposals=2,
        overwrite=force,
    )
    accepted_validation = validate_client_proposal(
        accepted_proposal,
        allowed_change_surfaces=allowed_change_surfaces,
    )
    rejected_validation = validate_client_proposal(
        rejected_proposal,
        allowed_change_surfaces=allowed_change_surfaces,
    )
    reflection = build_proposal_reflection(
        proposal=accepted_proposal,
        evaluation=evaluation,
        output_dir=output_dir,
        overwrite=force,
    )

    summary_path = output_dir / "proposal-contract-smoke-summary.json"
    accepted_proposal_output = output_dir / "accepted-proposal.json"
    rejected_proposal_output = output_dir / "rejected-proposal.json"
    accepted_validation_path = output_dir / "accepted-validation.json"
    rejected_validation_path = output_dir / "rejected-validation.json"
    _assert_can_write(summary_path, overwrite=force)
    _write_json(accepted_proposal_output, accepted_proposal, overwrite=force)
    _write_json(rejected_proposal_output, rejected_proposal, overwrite=force)
    _write_json(accepted_validation_path, accepted_validation, overwrite=force)
    _write_json(rejected_validation_path, rejected_validation, overwrite=force)
    summary = {
        "status": "completed",
        "fixture_dir": str(fixture_dir),
        "output_dir": str(output_dir),
        "context_file": context["context_file"],
        "prompt_file": context["prompt_file"],
        "accepted_proposal_file": str(fixture_dir / "accepted-proposal.json"),
        "rejected_proposal_file": str(fixture_dir / "rejected-proposal.json"),
        "accepted_proposal_output_file": str(accepted_proposal_output),
        "rejected_proposal_output_file": str(rejected_proposal_output),
        "accepted_validation_status": accepted_validation["status"],
        "accepted_failure_labels": accepted_validation["failure_labels"],
        "accepted_validation_file": str(accepted_validation_path),
        "rejected_validation_status": rejected_validation["status"],
        "rejected_failure_labels": rejected_validation["failure_labels"],
        "rejected_validation_file": str(rejected_validation_path),
        "reflection_file": reflection["reflection_file"],
        "reflection_status": reflection["status"],
        "recommended_next_action": reflection["recommended_next_action"],
        "claim_boundary": (
            "local proposal contract smoke only; not an official score claim; "
            "dev evidence requires canary or holdout support"
        ),
        "official_scores_claimed": False,
        "executes_llm": False,
        "executes_experiment": False,
        "summary_file": str(summary_path),
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any, *, overwrite: bool) -> None:
    _assert_can_write(path, overwrite=overwrite)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _assert_can_write(path: Path, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(str(path))


if __name__ == "__main__":
    raise SystemExit(main())
