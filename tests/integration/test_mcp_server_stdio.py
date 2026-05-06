from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_mcp_server_handles_line_delimited_stdio_requests() -> None:
    env = {
        **os.environ,
        "PYTHONPATH": (
            f"{PROJECT_ROOT}{os.pathsep}"
            f"{PROJECT_ROOT / '.venv' / 'lib' / 'python3.13' / 'site-packages'}"
        ),
    }
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        },
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]

    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "mcp_server.py")],
        input="\n".join(json.dumps(request) for request in requests) + "\n",
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=5,
    )

    assert proc.returncode == 0, proc.stderr
    responses = [json.loads(line) for line in proc.stdout.splitlines()]

    assert responses[0]["result"]["serverInfo"]["name"] == "ml-research-loop"
    assert {tool["name"] for tool in responses[1]["result"]["tools"]} >= {
        "run_fresh_demo",
        "run_autoresearch",
        "get_experiment_status",
        "get_experiment_result",
        "get_benchmark_harness_probe",
        "plan_benchmark_proof_run",
        "write_benchmark_proof_setup_bundle",
        "write_benchmark_proof_publication_bundle",
        "write_benchmark_proof_archive",
    }
