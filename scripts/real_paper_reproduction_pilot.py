#!/usr/bin/env python3
"""Run the real-paper reproduction pilot entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.reproduction_pilot import (  # noqa: E402
    PaperCandidate,
    PilotRunConfig,
    build_research_case_from_selection,
    evaluate_paper_candidate,
    probe_pilot_environment,
    run_bounded_pilot_experiment,
    run_guarded_pilot_iteration,
    write_pilot_evidence_indexes,
    write_pilot_proof_archive,
    write_fixture_dataset,
    write_human_review_report,
    write_public_memflow_slice,
    write_research_case,
)


MEMFLOW_CANDIDATE = PaperCandidate(
    paper_id="arxiv:2605.03312",
    title="MemFlow: Intent-Driven Memory Orchestration for Small Language Model Agents",
    arxiv_url="https://arxiv.org/abs/2605.03312",
    task="bounded memory-routing ablation",
    metric="accuracy",
    dataset_plan="small public or fixture-backed substitute dataset",
    algorithm_plan="minimal intent-router ablation",
    resource_budget_minutes=15,
    target_claim="intent-driven routing improves evidence selection on the bounded task",
    official_scores_claimed=False,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a real-paper reproduction pilot")
    parser.add_argument("--paper-id", default=MEMFLOW_CANDIDATE.paper_id)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--select-only", action="store_true")
    parser.add_argument("--probe-only", action="store_true")
    parser.add_argument("--run-baseline", action="store_true")
    parser.add_argument("--run-iteration", action="store_true")
    parser.add_argument("--write-review-report", action="store_true")
    parser.add_argument("--archive-proof", action="store_true")
    parser.add_argument(
        "--use-fixture-data",
        action="store_true",
        help="Write and use a local substitute dataset for the bounded pilot.",
    )
    parser.add_argument(
        "--use-public-mini-slice",
        action="store_true",
        help="Write and use the curated public MemFlow mini-slice for the bounded pilot.",
    )
    parser.add_argument(
        "--data-path",
        type=Path,
        default=None,
        help="Pilot dataset path; defaults to <output-dir>/data/pilot.jsonl.",
    )
    parser.add_argument("--max-runtime-seconds", type=int, default=900)
    parser.add_argument(
        "--proof-dir",
        type=Path,
        default=Path("proof_runs/real-paper-pilot/memflow"),
        help="Proof archive output directory.",
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=ROOT / "docs" / "evidence",
        help="Evidence index output directory.",
    )
    parser.add_argument("--update-evidence-index", action="store_true")
    parser.add_argument(
        "--reviewer",
        default="local-operator",
        help="Reviewer name recorded in human-review-report.json.",
    )
    parser.add_argument(
        "--review-decision",
        default="approved_with_limitations",
        choices=["approved_with_limitations", "needs_more_evidence", "rejected"],
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_modes = sum(
        1
        for enabled in [
            args.select_only,
            args.probe_only,
            args.run_baseline,
            args.run_iteration,
            args.write_review_report,
            args.archive_proof,
        ]
        if enabled
    )
    if selected_modes != 1:
        print(
            "error: choose exactly one of --select-only, --probe-only, "
            "--run-baseline, --run-iteration, --write-review-report, or --archive-proof",
            file=sys.stderr,
        )
        return 2
    if args.use_fixture_data and args.use_public_mini_slice:
        print(
            "error: choose at most one of --use-fixture-data or --use-public-mini-slice",
            file=sys.stderr,
        )
        return 2

    try:
        candidate = _candidate_for_paper_id(args.paper_id)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = evaluate_paper_candidate(candidate)
    report_path = args.output_dir / "paper-selection-report.json"
    report_path.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if args.select_only:
        payload = report.to_dict()
        _print_payload(payload, args.json)
        return 0

    if report.decision != "accepted_for_pilot":
        payload = {
            "status": "blocked",
            "paper_selection_report": str(report_path),
            "decision": report.decision,
            "reject_reasons": list(report.reject_reasons),
            "official_scores_claimed": False,
        }
        _print_payload(payload, args.json)
        return 1

    case = build_research_case_from_selection(
        report,
        selection_artifact_path=report_path,
    )
    case_path = write_research_case(case, args.output_dir)
    if args.archive_proof:
        proof_result = write_pilot_proof_archive(
            output_dir=args.output_dir,
            proof_dir=args.proof_dir,
            paper_id=report.paper_id,
            claim=report.target_claim,
            commands=_archive_commands(args.output_dir),
        )
        payload = {
            **proof_result,
            "paper_selection_report": str(report_path),
            "research_case": str(case_path),
        }
        if proof_result["status"] == "completed" and args.update_evidence_index:
            indexes = write_pilot_evidence_indexes(
                manifest_path=Path(proof_result["proof_manifest"]),
                evidence_dir=args.evidence_dir,
            )
            payload["evidence_indexes"] = {
                key: str(path) for key, path in indexes.items()
            }
        _print_payload(payload, args.json)
        return 0 if proof_result["status"] == "completed" else 1

    if args.write_review_report:
        try:
            review_path = write_human_review_report(
                output_dir=args.output_dir,
                paper_id=report.paper_id,
                claim=report.target_claim,
                reviewer=args.reviewer,
                decision=args.review_decision,
            )
        except (FileNotFoundError, ValueError) as exc:
            payload = {
                "status": "blocked",
                "paper_selection_report": str(report_path),
                "research_case": str(case_path),
                "blockers": [str(exc)],
                "official_scores_claimed": False,
            }
            _print_payload(payload, args.json)
            return 1
        review_payload = json.loads(review_path.read_text(encoding="utf-8"))
        payload = {
            "status": "completed",
            "review_report": str(review_path),
            "review_status": review_payload["review_status"],
            "paper_selection_report": str(report_path),
            "research_case": str(case_path),
            "official_scores_claimed": False,
        }
        _print_payload(payload, args.json)
        return 0

    data_path = args.data_path or (args.output_dir / "data" / "pilot.jsonl")
    if (args.probe_only or args.run_baseline or args.run_iteration) and args.use_fixture_data:
        write_fixture_dataset(data_path)
    if (args.probe_only or args.run_baseline or args.run_iteration) and args.use_public_mini_slice:
        write_public_memflow_slice(data_path)

    environment_report = probe_pilot_environment(
        PilotRunConfig(
            case_id=case.case_id,
            data_path=data_path,
            output_dir=args.output_dir,
            max_runtime_seconds=args.max_runtime_seconds,
        )
    )
    probe_path = args.output_dir / "environment-probe.json"
    probe_path.write_text(
        json.dumps(environment_report.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if args.probe_only:
        payload = {
            "status": environment_report.status,
            "paper_selection_report": str(report_path),
            "research_case": str(case_path),
            "environment_probe": str(probe_path),
            "blockers": environment_report.blockers,
            "official_scores_claimed": False,
        }
        _print_payload(payload, args.json)
        return 0

    if environment_report.status != "ready":
        payload = {
            "status": "blocked",
            "paper_selection_report": str(report_path),
            "research_case": str(case_path),
            "environment_probe": str(probe_path),
            "blockers": environment_report.blockers,
            "official_scores_claimed": False,
        }
        _print_payload(payload, args.json)
        return 1

    run_config = PilotRunConfig(
        case_id=case.case_id,
        data_path=data_path,
        output_dir=args.output_dir,
        max_runtime_seconds=args.max_runtime_seconds,
    )
    if args.run_iteration:
        iteration_result = run_guarded_pilot_iteration(
            run_config,
            target_claim=report.target_claim,
            metric_name="selection_accuracy",
            substitute_data=args.use_fixture_data,
        )
        payload = {
            **iteration_result,
            "paper_selection_report": str(report_path),
            "research_case": str(case_path),
            "environment_probe": str(probe_path),
        }
        _print_payload(payload, args.json)
        return 0 if iteration_result["status"] == "completed" else 1

    experiment_result = run_bounded_pilot_experiment(
        PilotRunConfig(
            case_id=case.case_id,
            data_path=data_path,
            output_dir=args.output_dir,
            max_runtime_seconds=args.max_runtime_seconds,
        ),
        target_claim=report.target_claim,
        metric_name="selection_accuracy",
        substitute_data=args.use_fixture_data,
    )
    payload = {
        "status": experiment_result.status,
        "paper_selection_report": str(report_path),
        "research_case": str(case_path),
        "environment_probe": str(probe_path),
        "metric_name": experiment_result.metric_name,
        "metric_before": experiment_result.baseline_metric,
        "metric_after": experiment_result.ablation_metric,
        "sample_count": experiment_result.sample_count,
        "substitute_data": experiment_result.substitute_data,
        "artifacts": {
            role: str(path) for role, path in experiment_result.artifacts.items()
        },
        "official_scores_claimed": False,
    }
    _print_payload(payload, args.json)
    return 0


def _print_payload(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))


def _candidate_for_paper_id(paper_id: str) -> PaperCandidate:
    if paper_id == MEMFLOW_CANDIDATE.paper_id:
        return MEMFLOW_CANDIDATE
    raise ValueError(f"unsupported P0 paper id: {paper_id}")


def _archive_commands(output_dir: Path) -> list[str]:
    summary_path = output_dir / "experiment-summary.json"
    data_flag = "--use-fixture-data"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if not summary.get("substitute_data", True):
            data_flag = "--use-public-mini-slice"
    return [
        f"python3 scripts/real_paper_reproduction_pilot.py --run-baseline {data_flag}",
        f"python3 scripts/real_paper_reproduction_pilot.py --run-iteration {data_flag}",
    ]


if __name__ == "__main__":
    raise SystemExit(main())
