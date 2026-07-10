from __future__ import annotations

import json
import os
from pathlib import Path
import sys


EVIDENCE_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVIDENCE_DIR.parents[2]
EVIDENCE_REL = EVIDENCE_DIR.relative_to(REPO_ROOT)
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(EVIDENCE_DIR / "runtime_plugins"))

from lib.failure_driven_proposal import run_real_benchmark_readiness_run


def fixture_chat_completion(**kwargs):
    messages = kwargs.get("messages") or []
    text = "\n".join(
        str(message.get("content") or "")
        for message in messages
        if isinstance(message, dict)
    )
    answers = {
        "S1-H1-001": "Brazil",
        "S1-H1-002": "South Africa",
        "S1-I1-003": "France",
        "S1-I1-004": "Argentina",
    }
    answer = "wrong"
    if "fixture optimizer: add an alias-confusion guard" in text:
        for row_id, expected in answers.items():
            if row_id in text:
                answer = expected
                break
    return {
        "content": json.dumps({
            "answer": answer,
            "confidence": 90,
            "is_verified": True,
            "source_note": "deterministic local smoke fixture",
        }),
        "input_tokens_estimate": 8,
        "output_tokens_estimate": 4,
        "latency_seconds": 0.001,
    }


def main() -> int:
    os.chdir(REPO_ROOT)
    payload = run_real_benchmark_readiness_run(
        run_name="real-benchmark-readiness-smoke",
        benchmark_id="smol_worldcup",
        objective=(
            "verify optimizer candidate generation, benchmark eval, gate, and "
            "feedback memory as one readiness loop"
        ),
        rows=EVIDENCE_REL / "inputs" / "rows.json",
        context=EVIDENCE_REL / "inputs" / "slice-repair-context.json",
        round_count=3,
        optimizer_sources=["readiness-optimizer-plugin"],
        operators=["adapt", "combine"],
        optimizer_gate_plugin_manifests=[
            EVIDENCE_REL / "inputs" / "plugin-manifest.json"
        ],
        chat_completion=fixture_chat_completion,
        output_dir=EVIDENCE_REL / "run",
        feedback_store_path=EVIDENCE_REL / "gate-feedback-memory-store.json",
        output_path=EVIDENCE_REL / "real-benchmark-readiness-run.json",
        overwrite=True,
    )
    print(json.dumps({
        "status": payload["status"],
        "schema_version": payload["schema_version"],
        "round_count": payload["round_count"],
        "real_optimizer_candidate_count": payload["real_optimizer_candidate_count"],
        "real_eval_outcome_count": payload["real_eval_outcome_count"],
        "best_path": payload["best_path"],
        "official_scores_claimed": payload["official_scores_claimed"],
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
