#!/usr/bin/env python3
"""Run a deterministic autonomous research loop demo."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib.autonomous_loop import decide_next_autonomous_action  # noqa: E402
from lib.research_case import (  # noqa: E402
    EvidenceRef,
    ResearchCase,
    ResearchClaim,
    ResearchMilestone,
    summarize_research_case,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic autonomous research demo")
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    return parser.parse_args()


def build_demo_case(runtime_root: Path) -> ResearchCase:
    artifact_path = runtime_root / "artifacts" / "local-proof.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "metric_name": "demo_accuracy",
                "metric_value": 0.72,
                "official_scores_claimed": False,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return ResearchCase(
        case_id="autonomous-demo-case",
        objective="Demonstrate a bounded autonomous research loop without network access.",
        claims=[
            ResearchClaim(
                claim_id="claim-local-proof",
                text="The demo produced a local proof artifact for loop-control validation.",
                status="supported_local",
                evidence_refs=[
                    EvidenceRef(
                        source_id="local-demo",
                        artifact_path=str(artifact_path),
                        quote="official_scores_claimed=false",
                        strength="runtime_artifact",
                    )
                ],
            )
        ],
        milestones=[
            ResearchMilestone(
                milestone_id="milestone-demo-experiment",
                kind="experiment",
                status="passed",
                artifact_path=str(artifact_path),
                metric_name="demo_accuracy",
                metric_value=0.72,
            )
        ],
        forbidden_claims=["official leaderboard score"],
        official_scores_claimed=False,
    )


def run_demo(runtime_root: Path) -> dict[str, object]:
    runtime_root.mkdir(parents=True, exist_ok=True)
    case = build_demo_case(runtime_root)
    case_summary = summarize_research_case(case)
    latest_review = {
        "loop_decision": {
            "decision": "stop",
            "reason_category": "sufficient_local_proof_for_demo",
        }
    }
    loop_decision = decide_next_autonomous_action(
        case_summary=case_summary,
        budget={"completed_rounds": 1, "max_rounds": 3},
        latest_review=latest_review,
    )
    report = {
        "status": "completed",
        "case_summary": case_summary,
        "latest_review": latest_review,
        "loop_decision": loop_decision,
        "official_scores_claimed": False,
    }
    report_file = runtime_root / "autonomous-research-report.json"
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "completed",
        "report_file": str(report_file),
        "loop_decision": loop_decision,
        "official_scores_claimed": False,
    }


def main() -> int:
    args = parse_args()
    payload = run_demo(args.runtime_root.expanduser().resolve())
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
