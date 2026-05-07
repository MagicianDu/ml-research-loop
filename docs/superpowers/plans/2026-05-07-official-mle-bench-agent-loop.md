# Official MLE-bench Agent Loop Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Codex/Claude use ML Research Loop to create a safe agent-editable workspace from official MLE-bench prepared data, then run a generated solver/submission through the official local scorer.

**Architecture:** Add a dependency-light bridge module under `lib/benchmarks` that reads an already prepared official MLE-bench competition directory and writes a bounded agent workspace under a runtime root. The bridge never downloads Kaggle data and never claims leaderboard scores; it only copies public files, writes planner instructions/contracts, runs local `solve.py`, and invokes `mlebench grade-sample` for local scorer feedback. Expose this through CLI and MCP so the client model can patch `solve.py` or `submission.csv`, then call one round tool that returns solve logs, grade output, and a round report.

**Tech Stack:** Python stdlib, existing MCP path sandbox, existing CLI/MCP patterns, pytest, official `mlebench` CLI supplied by the operator.

---

### Task 1: Pure Official Workspace Bridge

**Files:**
- Create: `lib/benchmarks/official_mle_bridge.py`
- Modify: `lib/benchmarks/__init__.py`
- Test: `tests/unit/test_official_mle_bridge.py`

- [ ] **Step 1: Write failing tests for workspace materialization**

Create tests that build a fake prepared competition:

```python
def test_materialize_official_mle_workspace_copies_public_files_and_writes_contract(tmp_path):
    prepared = tmp_path / "data" / "spooky-author-identification" / "prepared"
    public = prepared / "public"
    private = prepared / "private"
    public.mkdir(parents=True)
    private.mkdir(parents=True)
    (public / "train.csv").write_text("id,text,author\n1,hello,EAP\n", encoding="utf-8")
    (public / "test.csv").write_text("id,text\n2,world\n", encoding="utf-8")
    (public / "sample_submission.csv").write_text("id,EAP,HPL,MWS\n2,0.33,0.33,0.34\n", encoding="utf-8")
    (public / "description.md").write_text("# Task\n", encoding="utf-8")
    (private / "test.csv").write_text("id,author\n2,EAP\n", encoding="utf-8")

    payload = materialize_official_mle_agent_workspace(
        competition_id="spooky-author-identification",
        prepared_competition_dir=prepared.parent,
        runtime_root=tmp_path / "runtime",
        workspace_name="spooky-debug",
    )

    assert payload["status"] == "ready_for_agent"
    assert payload["official_mle_bench"] is True
    assert payload["official_scores_claimed"] is False
    assert payload["workspace_files"]["public"]["sample_submission.csv"]["role"] == "sample_submission"
    assert (Path(payload["workspace"]) / "solve.py").is_file()
    assert (Path(payload["workspace"]) / "submission.csv").read_text(encoding="utf-8").startswith("id,EAP,HPL,MWS")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest tests/unit/test_official_mle_bridge.py -q
```

Expected: import failure for `lib.benchmarks.official_mle_bridge`.

- [ ] **Step 3: Implement minimal bridge**

Implement:

```python
def materialize_official_mle_agent_workspace(
    *,
    competition_id: str,
    prepared_competition_dir: Path,
    runtime_root: Path,
    workspace_name: str | None = None,
) -> dict[str, Any]:
    ...
```

It must:
- require `prepared/public/sample_submission.csv`;
- copy public prepared files into `workspace/input`;
- copy sample submission to `workspace/submission.csv`;
- write `workspace/solve.py` that copies sample submission by default;
- write `workspace/agent_instructions.md`;
- write `workspace/benchmark_contract.json`;
- return paths, allowed files, test command, and claim policy.

- [ ] **Step 4: Run unit tests to verify green**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest tests/unit/test_official_mle_bridge.py -q
```

Expected: all tests pass.

### Task 2: Official Grade-Sample Runner

**Files:**
- Modify: `lib/benchmarks/official_mle_bridge.py`
- Test: `tests/unit/test_official_mle_bridge.py`

- [ ] **Step 1: Write failing tests for grade runner**

Add tests using a fake `mlebench` executable that prints the official-style report:

```python
def test_grade_official_mle_submission_parses_report_and_writes_artifacts(tmp_path):
    mlebench = tmp_path / "mlebench"
    mlebench.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "print('Competition report:')\n"
        "print(json.dumps({'competition_id':'spooky-author-identification','score':1.23,'valid_submission':True}))\n",
        encoding="utf-8",
    )
    mlebench.chmod(0o755)

    payload = grade_official_mle_submission(
        competition_id="spooky-author-identification",
        submission_path=tmp_path / "submission.csv",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "reports",
        mlebench_executable=mlebench,
        timeout_seconds=10,
    )

    assert payload["status"] == "graded"
    assert payload["report"]["score"] == 1.23
    assert payload["official_scores_claimed"] is False
    assert Path(payload["report_path"]).is_file()
    assert Path(payload["log_path"]).is_file()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest tests/unit/test_official_mle_bridge.py -q
```

Expected: missing `grade_official_mle_submission`.

- [ ] **Step 3: Implement grade runner**

Implement a runner that executes:

```bash
mlebench grade-sample <submission.csv> <competition_id> --data-dir <data_dir>
```

It must parse the last JSON object from stdout, write `grade-report.json`, write `grade.log`, and preserve `official_scores_claimed=false`.

- [ ] **Step 4: Run unit tests**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest tests/unit/test_official_mle_bridge.py -q
```

Expected: all tests pass.

### Task 3: CLI Surface

**Files:**
- Modify: `scripts/cli.py`
- Create: `scripts/mle_bench_official_workspace.py`
- Test: `tests/unit/test_cli.py`
- Test: `tests/integration/test_official_mle_bridge_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Add parser assertions for:

```bash
ml-loop benchmark mle-workspace --competition-id spooky-author-identification --prepared-competition-dir <dir> --runtime-root <dir> --json
ml-loop benchmark mle-grade --competition-id spooky-author-identification --submission <file> --data-dir <dir> --mlebench <exe> --output-dir <dir> --json
```

- [ ] **Step 2: Run targeted CLI tests and verify failure**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest tests/unit/test_cli.py tests/integration/test_official_mle_bridge_cli.py -q
```

- [ ] **Step 3: Wire CLI commands**

Add `benchmark mle-workspace` and `benchmark mle-grade` branches that call the bridge functions and print JSON.

- [ ] **Step 4: Run targeted CLI tests**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest tests/unit/test_cli.py tests/integration/test_official_mle_bridge_cli.py -q
```

### Task 4: MCP Tool Surface

**Files:**
- Modify: `lib/mcp_service.py`
- Modify: `tests/unit/test_mcp_service.py`
- Modify: `tests/integration/test_mcp_server_stdio.py`

- [ ] **Step 1: Write failing MCP tests**

Assert that `tools/list` includes:
- `prepare_official_mle_bench_workspace`
- `grade_official_mle_bench_submission`

Assert direct tool calls return:
- workspace status `ready_for_agent`;
- grade status `graded`;
- execution metadata;
- `official_scores_claimed=false`.

- [ ] **Step 2: Run targeted MCP tests and verify failure**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest tests/unit/test_mcp_service.py tests/integration/test_mcp_server_stdio.py -q
```

- [ ] **Step 3: Implement MCP schema and handlers**

Add tool definitions, required tool contracts, service manifest planning signals, recommended workflow, and handler functions. Enforce existing allowed-root policy for all paths.

- [ ] **Step 4: Run targeted MCP tests**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest tests/unit/test_mcp_service.py tests/integration/test_mcp_server_stdio.py -q
```

### Task 5: Docs and Release Gate

**Files:**
- Modify: `docs/benchmark-adapter-roadmap-cn.md`
- Modify: `docs/release-checklist.md`
- Modify: `skills/ml-research-loop-planner/SKILL.md`
- Modify: `skills/ml-research-loop-operator/SKILL.md`
- Modify: `scripts/release_check.py`

- [ ] **Step 1: Add bridge acceptance command**

Add a deterministic fake-harness acceptance command to `release_check.py` so the feature is checked without Kaggle/network.

- [ ] **Step 2: Update Chinese docs and skills**

Document the workflow:
1. prepare official data externally;
2. create workspace through MCP;
3. patch `solve.py` or `submission.csv`;
4. call `run_official_mle_bench_round` / `ml-loop benchmark mle-round`;
5. inspect solve/grade artifacts;
6. archive artifacts with proof tools.

### Task 6: Solver Round Closure

**Files:**
- Modify: `lib/benchmarks/official_mle_bridge.py`
- Modify: `scripts/cli.py`
- Modify: `lib/mcp_service.py`
- Modify: `scripts/mle_bench_official_bridge_demo.py`
- Modify: related tests/docs/skills

- [x] Add `run_official_mle_solver_round` to execute `solve.py`, check `submission.csv`, call `grade_official_mle_submission`, and write `round-report.json`.
- [x] Add `ml-loop benchmark mle-round` for CLI users.
- [x] Add MCP tool `run_official_mle_bench_round` for Codex/Claude clients.
- [x] Update the deterministic release demo to exercise the round path.
- [x] Preserve `official_scores_claimed=false` throughout all round artifacts.

- [ ] **Step 3: Run release gate**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=/opt/homebrew/Caskroom/miniforge/base/bin/python3 /opt/homebrew/Caskroom/miniforge/base/bin/python3 scripts/release_check.py --python /opt/homebrew/Caskroom/miniforge/base/bin/python3 --json
```

Expected: status `passed`.

---

## Self-Review

- Spec coverage: The plan covers the next product gap: real official MLE-bench prepared data can now enter the client-planned optimization loop. It intentionally does not claim full benchmark leaderboard performance.
- Placeholder scan: No TODO/TBD placeholders remain in implementation steps.
- Type consistency: Public function names, CLI commands, and MCP tool names are consistent across tasks.
