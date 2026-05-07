# PaperBench Codex Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a keyless PaperBench review loop where ML Research Loop prepares PaperBench artifacts for Codex review and stores Codex-assisted rubric judgments without claiming official PaperBench scores.

**Architecture:** Add a focused benchmark module that copies PaperBench paper/run artifacts into a review packet, writes a Codex-facing prompt, and writes back a structured Codex review report. CLI and MCP tools wrap the same module and force `judge_type=codex_assisted`, `official_scores_claimed=false`, and `paperbench_score=null`.

**Tech Stack:** Python stdlib, existing `scripts/cli.py`, `lib/mcp_service.py`, pytest.

---

### Task 1: Core Bundle Builder

**Files:**
- Create: `lib/benchmarks/paperbench_codex_review.py`
- Modify: `lib/benchmarks/__init__.py`
- Test: `tests/unit/test_paperbench_codex_review.py`

- [x] **Step 1: Write failing bundle test**

Create a fixture with `paper.md`, `rubric.json`, `grade.json`, `metadata.json`, `agent.log`, `run.log`, and one submission directory. Assert `write_paperbench_codex_review_bundle(run_dir, paper_dir, output_dir)` writes `codex-review-bundle.json`, `codex-review-prompt.md`, copied packet files, and returns `official_scores_claimed=false`, `judge_type=codex_assisted`, `paperbench_score=None`.

- [x] **Step 2: Run failing test**

Run: `pytest tests/unit/test_paperbench_codex_review.py::test_write_paperbench_codex_review_bundle_copies_artifacts_and_blocks_official_claims -q`

Expected: fail because `lib.benchmarks.paperbench_codex_review` does not exist.

- [x] **Step 3: Implement minimal bundle writer**

Implement path-safe local copying, latest submission detection, bundle JSON, review schema, and prompt rendering. Do not call any API.

- [x] **Step 4: Verify bundle test passes**

Run: `pytest tests/unit/test_paperbench_codex_review.py::test_write_paperbench_codex_review_bundle_copies_artifacts_and_blocks_official_claims -q`

Expected: pass.

### Task 2: Codex Review Report Writer

**Files:**
- Modify: `lib/benchmarks/paperbench_codex_review.py`
- Test: `tests/unit/test_paperbench_codex_review.py`

- [x] **Step 1: Write failing report tests**

Add tests that call `write_paperbench_codex_review_report(bundle_path, review_payload, output_dir)` and assert it writes `codex-review-report.json/md`, keeps `official_scores_claimed=false` even if the review payload tries to claim otherwise, preserves `evidence_refs`, `missing_evidence`, `confidence`, and records blocked claims.

- [x] **Step 2: Run failing tests**

Run: `pytest tests/unit/test_paperbench_codex_review.py -q`

Expected: report tests fail because the function is missing.

- [x] **Step 3: Implement report writer**

Normalize review payload fields into `codex_review`, compute `status`, write JSON and Markdown, and keep official PaperBench score unset.

- [x] **Step 4: Verify report tests pass**

Run: `pytest tests/unit/test_paperbench_codex_review.py -q`

Expected: pass.

### Task 3: CLI and MCP Exposure

**Files:**
- Modify: `scripts/cli.py`
- Modify: `lib/mcp_service.py`
- Test: `tests/unit/test_cli.py`
- Test: `tests/unit/test_mcp_service.py`

- [x] **Step 1: Write failing CLI/MCP tests**

Add parser coverage for `benchmark paperbench-codex-review-bundle` and `benchmark paperbench-codex-review-report`. Add MCP tool list and call tests for `prepare_paperbench_codex_review_bundle` and `write_paperbench_codex_review_report`.

- [x] **Step 2: Run failing tests**

Run: `pytest tests/unit/test_cli.py::test_parser_has_run_status_result_subcommands tests/unit/test_mcp_service.py::test_tools_list_exposes_research_loop_tools -q`

Expected: fail because the new commands/tools do not exist.

- [x] **Step 3: Implement CLI/MCP wiring**

Import the new module, add argparse commands, add tool definitions, handlers, manifest contracts, required tools, and path security checks for all filesystem inputs/outputs.

- [x] **Step 4: Verify CLI/MCP tests pass**

Run: `pytest tests/unit/test_cli.py tests/unit/test_mcp_service.py -q`

Expected: pass.

### Task 4: Docs and Verification

**Files:**
- Modify: `docs/benchmark-adapter-roadmap-cn.md`
- Modify: `docs/evidence/benchmark-results-index-cn.md`
- Optional Modify: `docs/superpowers/plans/2026-05-07-hard-benchmark-results.md`

- [x] **Step 1: Document honest claim boundary**

Add the public phrase: "Codex-assisted rubric review is not an official PaperBench score." Link the new CLI/MCP tool names.

- [x] **Step 2: Run focused and release tests**

Run:

```bash
pytest tests/unit/test_paperbench_codex_review.py tests/unit/test_cli.py tests/unit/test_mcp_service.py -q
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 scripts/release_check.py --json
git diff --check
```

Expected: all pass.
