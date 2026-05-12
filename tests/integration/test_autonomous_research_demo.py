from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_autonomous_research_demo_writes_report(tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "autonomous_research_demo.py"),
            "--runtime-root",
            str(tmp_path),
            "--json",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )
    payload = json.loads(proc.stdout)

    assert payload["status"] == "completed"
    assert payload["official_scores_claimed"] is False
    assert payload["loop_decision"]["official_scores_claimed"] is False
    assert Path(payload["report_file"]).exists()
