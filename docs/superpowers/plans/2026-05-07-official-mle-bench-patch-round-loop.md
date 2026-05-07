# Official MLE-bench Patch Round Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an MCP-first patch/grade round that lets Codex/Claude propose a bounded `solve.py` diff and have ML Research Loop apply it, run official local MLE-bench grading, and return auditable loop feedback.

**Architecture:** Keep the hybrid client-planner/server-executor boundary. The client model generates a unified diff from the latest round artifact; the MCP service atomically applies the patch using existing guarded patch logic, runs `run_official_mle_bench_round`, and returns patch execution, grade artifact paths, and a score-aware loop decision. The service still does not generate code with a server-side LLM and still preserves `official_scores_claimed=false`.

**Tech Stack:** Python stdlib, existing MCP service patch helpers, `lib.benchmarks.official_mle_bridge`, pytest, release_check.

---

### Task 1: MCP Patch Round Contract

**Files:**
- Modify: `lib/mcp_service.py`
- Test: `tests/unit/test_mcp_service.py`
- Test: `tests/integration/test_mcp_server_stdio.py`

- [x] **Step 1: Write failing tests**

Add a unit test that creates an MLE workspace with `solve.py`, sends a unified diff through a new `run_official_mle_bench_patch_round_tool`, and asserts:

```python
payload = mcp_service.run_official_mle_bench_patch_round_tool({
    "competition_id": "spooky-author-identification",
    "workspace": str(workspace),
    "data_dir": str(data_dir),
    "mlebench": str(mlebench),
    "output_dir": str(tmp_path / "rounds"),
    "patch": patch,
    "python": sys.executable,
    "round_id": "round-002",
    "timeout_seconds": 10,
})

assert payload["status"] == "graded"
assert payload["patch_execution"]["status"] == "applied"
assert payload["round"]["status"] == "graded"
assert payload["loop_decision"]["recommended_next_action"] in {"continue", "stop"}
assert payload["official_scores_claimed"] is False
```

Also assert `tools/list`, `required_tools`, `tool_contracts`, and `planning_signals` include `run_official_mle_bench_patch_round` and `official_mle_patch_round`.

- [x] **Step 2: Verify RED**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest \
  tests/unit/test_mcp_service.py::test_tools_list_exposes_research_loop_tools \
  tests/unit/test_mcp_service.py::test_get_service_manifest_returns_client_contract \
  tests/unit/test_mcp_service.py::test_run_official_mle_bench_patch_round_tool_applies_patch_then_grades \
  tests/integration/test_mcp_server_stdio.py \
  -q
```

Expected: failure because `run_official_mle_bench_patch_round_tool` and the tool contract do not exist.

- [x] **Step 3: Implement minimal MCP tool**

Add `run_official_mle_bench_patch_round_tool(arguments)` that:

1. validates `workspace`, `data_dir`, `mlebench`, and `output_dir` against `ML_RESEARCH_LOOP_ALLOWED_ROOTS`;
2. calls `apply_client_code_patch_tool` with `allowed_files=["solve.py", "submission.csv"]` unless the caller passes a narrower list;
3. if patch application fails, returns the existing MCP error payload unchanged through the normal MCP error path;
4. calls `run_official_mle_bench_round_tool` with the same competition/workspace/scorer fields;
5. returns:

```python
{
    "status": round_payload["status"],
    "official_mle_bench": True,
    "official_scores_claimed": False,
    "round_id": round_id,
    "patch_execution": patch_payload["patch_execution"],
    "round": round_payload,
    "loop_decision": _official_mle_patch_loop_decision(round_payload),
    "execution_metadata": ...,
}
```

The loop decision should use `round.grade.report.valid_submission`, `round.grade.report.score`, and `round.status` only. It must not claim leaderboard standing.

- [x] **Step 4: Verify GREEN**

Run the same targeted pytest command. Expected: all selected tests pass.

### Task 2: CLI Patch Round Smoke

**Files:**
- Modify: `scripts/cli.py`
- Test: `tests/unit/test_cli.py`
- Test: `tests/integration/test_official_mle_bridge_cli.py`

- [x] **Step 1: Write failing CLI tests**

Add parser and integration coverage for:

```bash
ml-loop benchmark mle-patch-round \
  --competition-id spooky-author-identification \
  --workspace <workspace> \
  --data-dir <mlebench-data> \
  --mlebench <mlebench> \
  --output-dir <rounds> \
  --patch-file <patch.diff> \
  --python <python> \
  --round-id round-002 \
  --json
```

Expected payload fields: `status`, `patch_execution`, `round`, `loop_decision`, and `official_scores_claimed=false`.

- [x] **Step 2: Verify RED**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest \
  tests/unit/test_cli.py::test_parser_has_run_status_result_subcommands \
  tests/unit/test_cli.py::test_benchmark_mle_patch_round_command_applies_patch_then_runs_round \
  tests/integration/test_official_mle_bridge_cli.py \
  -q
```

Expected: parser rejects `mle-patch-round`.

- [x] **Step 3: Implement CLI command**

Wire `benchmark mle-patch-round` to the same service helper or a small public benchmark helper. The CLI should read `--patch-file`, call the patch round implementation, print JSON, and exit 0 only when `status == "graded"`.

- [x] **Step 4: Verify GREEN**

Run the same targeted CLI command. Expected: all selected tests pass.

### Task 3: Demo, Docs, and Release Gate

**Files:**
- Modify: `scripts/mle_bench_official_bridge_demo.py`
- Modify: `scripts/release_check.py`
- Modify: `docs/benchmark-adapter-roadmap-cn.md`
- Modify: `docs/release-checklist.md`
- Modify: `skills/ml-research-loop-planner/SKILL.md`
- Modify: `skills/ml-research-loop-operator/SKILL.md`
- Test: `tests/unit/test_release_check.py`
- Test: `tests/unit/test_skill_packages.py`

- [x] **Step 1: Extend deterministic demo**

Update the demo to run:

1. workspace creation;
2. baseline `run_official_mle_solver_round`;
3. one patch round that changes `solve.py` in a harmless deterministic way;
4. JSON output with `baseline_round`, `patch_round`, and `official_scores_claimed=false`.

- [x] **Step 2: Update release_check**

Keep the existing `mle-bench-official-bridge` label but make the script validate both baseline and patch round paths. Update release checklist assertions to mention `mle-patch-round` and `run_official_mle_bench_patch_round`.

- [x] **Step 3: Update skills**

Planner skill should tell Codex/Claude to prefer:

```text
read latest round-report.json -> generate bounded diff -> run_official_mle_bench_patch_round -> inspect loop_decision
```

Operator skill should mention that patch rounds preserve rollback and `official_scores_claimed=false`.

- [x] **Step 4: Run full validation**

Run:

```bash
.venv/bin/ruff check lib/ scripts/ ml_intern/ codex_plugin/ tests/
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest tests/ -q
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=/opt/homebrew/Caskroom/miniforge/base/bin/python3 /opt/homebrew/Caskroom/miniforge/base/bin/python3 scripts/release_check.py --python /opt/homebrew/Caskroom/miniforge/base/bin/python3 --json
```

Expected: ruff passes, pytest passes, release_check returns `status=passed`.

---

## Self-Review

- Spec coverage: P0 covers the next gap after `mle-round`: client-generated patch, guarded apply, score feedback, and loop decision in one MCP/CLI round.
- Placeholder scan: No TBD/TODO placeholders remain.
- Type consistency: Public names are `run_official_mle_bench_patch_round` for MCP and `mle-patch-round` for CLI; round payload remains nested under `round`.
