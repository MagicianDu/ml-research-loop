# MCP Benchmark Proof Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose benchmark proof-run probe, planning, setup, publication, and archive capabilities as direct MCP tools.

**Architecture:** Add thin MCP tool handlers in `lib/mcp_service.py` that reuse the existing benchmark library modules. Keep the CLI and release-gate paths unchanged, and update manifest contracts, docs, and skills so MCP clients know the proof workflow.

**Tech Stack:** Python 3.10+/3.13, JSON-RPC MCP stdio, pytest, ruff.

---

### Task 1: MCP Tool Contracts

**Files:**
- Modify: `tests/unit/test_mcp_service.py`
- Modify: `tests/integration/test_mcp_server_stdio.py`
- Modify: `lib/mcp_service.py`

- [x] **Step 1: Write failing tools/list tests**

Require `tools/list` to expose:

- `get_benchmark_harness_probe`
- `plan_benchmark_proof_run`
- `write_benchmark_proof_setup_bundle`
- `write_benchmark_proof_publication_bundle`
- `write_benchmark_proof_archive`

- [x] **Step 2: Verify failure**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest tests/unit/test_mcp_service.py::test_tools_list_exposes_research_loop_tools tests/integration/test_mcp_server_stdio.py::test_mcp_server_handles_line_delimited_stdio_requests -q
```

Expected: missing tool names.

- [x] **Step 3: Implement tool definitions and contract descriptions**

Add schemas and required-tool contract entries. Do not implement handlers yet.

- [x] **Step 4: Verify tools/list tests pass**

Run the same command. Expected: pass.

### Task 2: MCP Tool Handlers

**Files:**
- Modify: `tests/unit/test_mcp_service.py`
- Modify: `lib/mcp_service.py`

- [x] **Step 1: Write failing tools/call tests**

Cover:

- `get_benchmark_harness_probe` returns `read_only=true`;
- `plan_benchmark_proof_run` returns `official_scores_claimed=false`;
- `write_benchmark_proof_publication_bundle` writes `proof-publication.json`;
- `write_benchmark_proof_archive` writes `proof-archive.json` and copied artifacts.

- [x] **Step 2: Verify failure**

Run focused MCP service tests. Expected: unknown tool or missing handler failures.

- [x] **Step 3: Implement handlers**

Add handler functions that parse string paths, read manifest JSON, call existing library builders/writers, and return JSON-serializable payloads.

- [x] **Step 4: Verify focused tests pass**

Run focused MCP service tests again.

### Task 3: Manifest, Skills, Docs

**Files:**
- Modify: `lib/mcp_service.py`
- Modify: `skills/ml-research-loop-operator/SKILL.md`
- Modify: `skills/ml-research-loop-planner/SKILL.md`
- Modify: `docs/release-checklist.md`
- Modify: `README.md`
- Modify: `docs/benchmark-adapter-roadmap-cn.md`

- [x] **Step 1: Write or extend contract assertions**

Require benchmark proof tools in `required_tools`, `tool_contracts`, and recommended workflow metadata.

- [x] **Step 2: Implement manifest/docs/skills**

Add an MCP-first benchmark proof workflow and skill guidance.

- [x] **Step 3: Verify contract tests pass**

Run focused MCP service and skill/package tests.

### Task 4: Final Verification

- [x] **Step 1: Run ruff**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m ruff check lib/ scripts/ tests/
```

- [x] **Step 2: Run full tests**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=/opt/homebrew/Caskroom/miniforge/base/bin/python3 /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest tests/ -q
```

- [x] **Step 3: Run release gate**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=/opt/homebrew/Caskroom/miniforge/base/bin/python3 /opt/homebrew/Caskroom/miniforge/base/bin/python3 scripts/release_check.py --python /opt/homebrew/Caskroom/miniforge/base/bin/python3 --json
```

- [x] **Step 4: Review, commit, push**

Use `git diff --check`, review changed code/docs, commit, and push.
