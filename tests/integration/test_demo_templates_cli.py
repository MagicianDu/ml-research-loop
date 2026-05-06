from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_demo_template_cli_runs_byte_lm_smoke(tmp_path: Path) -> None:
    env = {
        **os.environ,
        "PYTHONPATH": (
            f"{PROJECT_ROOT}{os.pathsep}"
            f"{PROJECT_ROOT / '.venv' / 'lib' / 'python3.13' / 'site-packages'}"
        ),
        "ML_RESEARCH_LOOP_PYTHON": sys.executable,
    }

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.cli",
            "demo",
            "run",
            "--template",
            "byte-lm-smoke",
            "--runtime-root",
            str(tmp_path / "demo-runtime"),
            "--max-experiments",
            "1",
            "--experiment-duration",
            "30",
            "--json",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=120,
    )

    assert proc.returncode == 0, proc.stdout
    payload = json.loads(proc.stdout.splitlines()[-1])

    assert payload["status"] == "completed"
    assert payload["template"]["name"] == "byte-lm-smoke"
    assert payload["task_id"] == "demo-byte-lm-smoke"
    assert payload["best_metric"]["name"] == "val_bpb"
    assert payload["best_metric"]["value"] > 0
    assert Path(payload["result_file"]).exists()
    assert Path(payload["task_file"]).exists()
