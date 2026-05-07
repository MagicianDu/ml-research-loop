#!/usr/bin/env python3
"""Run a deterministic official MLE-bench agent-loop bridge smoke test."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lib.benchmarks import (
    materialize_official_mle_agent_workspace,
    run_official_mle_solver_round,
)


COMPETITION_ID = "spooky-author-identification"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run official MLE-bench bridge smoke")
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_root = args.runtime_root.expanduser().resolve()
    prepared_competition_dir = _write_prepared_fixture(runtime_root)
    fake_mlebench = _write_fake_mlebench(runtime_root)
    workspace_payload = materialize_official_mle_agent_workspace(
        competition_id=COMPETITION_ID,
        prepared_competition_dir=prepared_competition_dir,
        runtime_root=runtime_root,
        workspace_name="spooky-debug",
    )
    round_payload = run_official_mle_solver_round(
        competition_id=COMPETITION_ID,
        workspace=Path(workspace_payload["workspace"]),
        data_dir=runtime_root / "mlebench-data",
        output_dir=runtime_root / "benchmark-rounds",
        mlebench_executable=fake_mlebench,
        python_executable=args.python,
        round_id="round-001",
        timeout_seconds=30,
    )
    status = (
        "passed"
        if round_payload.get("status") == "graded"
        and round_payload.get("grade", {}).get("report", {}).get("valid_submission") is True
        and round_payload.get("official_scores_claimed") is False
        else "failed"
    )
    payload = {
        "status": status,
        "official_scores_claimed": False,
        "competition_id": COMPETITION_ID,
        "runtime_root": str(runtime_root),
        "workspace": workspace_payload,
        "round": round_payload,
    }
    _print(payload, args.json)
    return 0 if status == "passed" else 1


def _write_prepared_fixture(runtime_root: Path) -> Path:
    competition_dir = runtime_root / "mlebench-data" / COMPETITION_ID
    public = competition_dir / "prepared" / "public"
    public.mkdir(parents=True, exist_ok=True)
    (public / "train.csv").write_text("id,text,author\n1,hello,EAP\n", encoding="utf-8")
    (public / "test.csv").write_text("id,text\n2,world\n", encoding="utf-8")
    (public / "sample_submission.csv").write_text(
        "id,EAP,HPL,MWS\n2,0.33,0.33,0.34\n",
        encoding="utf-8",
    )
    (public / "description.md").write_text("# Spooky Author Identification\n", encoding="utf-8")
    return competition_dir


def _write_fake_mlebench(runtime_root: Path) -> Path:
    executable = runtime_root / "fake-bin" / "mlebench"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text(
        "\n".join([
            "#!/usr/bin/env python3",
            "import json",
            "print('Competition report:')",
            "print(json.dumps({",
            f"    'competition_id': {COMPETITION_ID!r},",
            "    'score': 1.08468,",
            "    'submission_exists': True,",
            "    'valid_submission': True,",
            "    'any_medal': False,",
            "    'above_median': False,",
            "}))",
        ]),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def _print(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
