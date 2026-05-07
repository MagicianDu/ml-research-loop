from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_benchmark_harness_probe_script_is_read_only_and_never_crashes() -> None:
    env = {
        **os.environ,
        "PYTHONPATH": (
            f"{PROJECT_ROOT}{os.pathsep}"
            f"{PROJECT_ROOT / '.venv' / 'lib' / 'python3.13' / 'site-packages'}"
        ),
    }

    proc = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "benchmark_harness_probe.py"),
            "--json",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )

    assert proc.returncode == 0, proc.stdout
    payload = json.loads(proc.stdout.splitlines()[-1])
    assert payload["read_only"] is True
    assert payload["official_scores_claimed"] is False
    assert payload["status"] in {"ready", "needs_setup"}
    assert [harness["name"] for harness in payload["harnesses"]] == [
        "mle_bench",
        "paperbench",
    ]
