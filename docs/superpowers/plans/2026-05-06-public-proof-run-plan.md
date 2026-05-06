# Public Proof Run Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only benchmark proof-run planner that bridges official harness probes to safe Codex/Claude next actions.

**Architecture:** Keep the official harness probe as the source of truth and add a small pure function in `lib/benchmarks/proof_plan.py` that derives status, environment recommendation, missing prerequisites, safe commands, blocked commands, and artifact requirements. Expose the same payload through a standalone script, `ml-loop benchmark proof-plan`, MCP manifest, and release gate docs.

**Tech Stack:** Python 3.10+/3.13, pytest, ruff, argparse, JSON CLI output.

---

### Task 1: Proof Plan Core

**Files:**
- Create: `lib/benchmarks/proof_plan.py`
- Modify: `lib/benchmarks/__init__.py`
- Test: `tests/unit/test_benchmark_proof_plan.py`

- [ ] **Step 1: Write failing unit tests**

Create `tests/unit/test_benchmark_proof_plan.py` with tests for blocked and ready probe payloads:

```python
from __future__ import annotations

from lib.benchmarks import build_public_proof_plan


def test_public_proof_plan_blocks_when_probe_needs_setup() -> None:
    probe = {
        "status": "needs_setup",
        "read_only": True,
        "official_scores_claimed": False,
        "harnesses": [
            {
                "name": "mle_bench",
                "status": "needs_setup",
                "required_checks": [
                    {"id": "command:git-lfs", "status": "missing"},
                    {"id": "credentials:kaggle", "status": "missing"},
                ],
                "blocked_commands": ["mlebench prepare"],
            }
        ],
    }

    payload = build_public_proof_plan(probe)

    assert payload["status"] == "blocked"
    assert payload["read_only"] is True
    assert payload["official_scores_claimed"] is False
    assert payload["recommended_environment"] == "external_evaluation_environment"
    assert "mle_bench:command:git-lfs" in payload["missing_prerequisites"]
    assert "mle_bench:credentials:kaggle" in payload["missing_prerequisites"]
    assert "python scripts/benchmark_harness_probe.py --json" in payload["safe_next_commands"]
    assert "mlebench prepare" in payload["blocked_commands"]
    assert payload["harness_probe"] is probe


def test_public_proof_plan_is_ready_when_probe_is_ready() -> None:
    probe = {
        "status": "ready",
        "read_only": True,
        "official_scores_claimed": False,
        "harnesses": [
            {
                "name": "paperbench",
                "status": "ready",
                "required_checks": [
                    {"id": "command:uv", "status": "available"},
                    {"id": "official_data", "status": "available"},
                ],
                "blocked_commands": ["paperbench direct-submission grading"],
            }
        ],
    }

    payload = build_public_proof_plan(probe)

    assert payload["status"] == "ready_for_debug_run"
    assert payload["recommended_environment"] == "local_worktree"
    assert payload["missing_prerequisites"] == []
    assert any("official debug" in command for command in payload["safe_next_commands"])
    assert "official_scores_claimed=false" in payload["artifact_requirements"]
```

- [ ] **Step 2: Run tests and verify missing import failure**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_benchmark_proof_plan.py -q
```

Expected: fail because `build_public_proof_plan` is not implemented.

- [ ] **Step 3: Implement core function**

Create `lib/benchmarks/proof_plan.py` with:

```python
from __future__ import annotations

from typing import Any


def build_public_proof_plan(harness_probe: dict[str, Any]) -> dict[str, Any]:
    missing = _missing_prerequisites(harness_probe)
    ready = harness_probe.get("status") == "ready" and not missing
    return {
        "status": "ready_for_debug_run" if ready else "blocked",
        "read_only": True,
        "official_scores_claimed": False,
        "recommended_environment": "local_worktree" if ready else "external_evaluation_environment",
        "missing_prerequisites": missing,
        "safe_next_commands": _safe_next_commands(ready),
        "blocked_commands": _blocked_commands(harness_probe, ready),
        "artifact_requirements": _artifact_requirements(),
        "harness_probe": harness_probe,
    }
```

Export it from `lib/benchmarks/__init__.py`.

- [ ] **Step 4: Run unit tests**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_benchmark_proof_plan.py -q
```

Expected: 2 passed.

### Task 2: Script and CLI

**Files:**
- Create: `scripts/benchmark_proof_plan.py`
- Modify: `scripts/cli.py`
- Test: `tests/integration/test_benchmark_proof_plan.py`, `tests/unit/test_cli.py`

- [ ] **Step 1: Write failing script and CLI tests**

Add an integration test that runs `scripts/benchmark_proof_plan.py --json` and
asserts `read_only=true`, `official_scores_claimed=false`, and status in
`blocked|ready_for_debug_run`.

Add a CLI parser and command test for:

```bash
ml-loop benchmark proof-plan --json
```

- [ ] **Step 2: Verify failures**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/integration/test_benchmark_proof_plan.py tests/unit/test_cli.py::test_parser_has_run_status_result_subcommands tests/unit/test_cli.py::test_benchmark_proof_plan_command_prints_plan -q
```

Expected: fail because script, parser command, or CLI handler is missing.

- [ ] **Step 3: Implement script and CLI handler**

`scripts/benchmark_proof_plan.py` should build the official harness probe, then
wrap it with `build_public_proof_plan()`. `scripts/cli.py` should add
`benchmark proof-plan` with the same repo/data args as `benchmark probe`.

- [ ] **Step 4: Run focused tests**

Run the same focused test command. Expected: all selected tests pass.

### Task 3: Manifest, Release Gate, and Docs

**Files:**
- Modify: `lib/mcp_service.py`
- Modify: `scripts/release_check.py`
- Modify: `tests/unit/test_mcp_service.py`
- Modify: `tests/unit/test_release_check.py`
- Modify: `docs/benchmark-adapter-roadmap-cn.md`
- Modify: `docs/productization-todos.md`
- Modify: `docs/release-checklist.md`
- Modify: `examples/README.md`
- Modify: `README.md`
- Modify: `docs/open-source-positioning-cn.md`

- [ ] **Step 1: Write failing contract tests**

Update tests to require:

- `get_service_manifest()["benchmark_proof_plan"]`
- `planning_signals` includes `benchmark_proof_plan`
- `acceptance_commands` includes `benchmark_proof_plan.py`
- release command labels include `benchmark-proof-plan`
- release checklist docs mention `ml-loop benchmark proof-plan --json`

- [ ] **Step 2: Verify failures**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_mcp_service.py tests/unit/test_release_check.py -q
```

Expected: fail until manifest, release gate, and docs are updated.

- [ ] **Step 3: Implement manifest, release gate, and docs**

Wire `build_public_proof_plan(build_official_harness_probe())` into the
manifest, add `scripts/benchmark_proof_plan.py --json` to release commands,
and update docs to describe the proof-run plan as a pre-score decision artifact.

- [ ] **Step 4: Run focused tests**

Run the same focused command. Expected: tests pass.

### Task 4: Final Verification

**Files:**
- All changed files

- [ ] **Step 1: Run ruff**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m ruff check lib/ scripts/ tests/
```

- [ ] **Step 2: Run full tests**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=/opt/homebrew/Caskroom/miniforge/base/bin/python3 /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest tests/ -q
```

- [ ] **Step 3: Run proof-plan CLI**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages ml-loop benchmark proof-plan --json
```

- [ ] **Step 4: Run release gate**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=/opt/homebrew/Caskroom/miniforge/base/bin/python3 /opt/homebrew/Caskroom/miniforge/base/bin/python3 scripts/release_check.py --python /opt/homebrew/Caskroom/miniforge/base/bin/python3 --json
```

Expected: final JSON reports `status=passed`.

- [ ] **Step 5: Review diff and commit**

Use `git diff --check`, review `git diff`, then commit and push to the PR branch.
