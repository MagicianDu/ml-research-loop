# PaperBench Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic PaperBench-shaped adapter and demo that exercises research reproduction stages through ML Research Loop artifacts.

**Architecture:** Add a small dependency-free `lib/benchmarks/paperbench.py` module that materializes a local paper/rubric fixture, runs a reproduction demo, writes submission/reproduction/grading artifacts, and emits a stage-aware benchmark report. Expose it through `scripts/paperbench_adapter_demo.py` first; do not alter MCP contracts yet.

**Tech Stack:** Python standard library, existing `scripts.mcp_reproduction_demo` patterns, existing reproduction/grade report structures, pytest, ruff.

---

### Task 1: PaperBench Fixture And Mapping

**Files:**
- Create: `lib/benchmarks/__init__.py`
- Create: `lib/benchmarks/paperbench.py`
- Test: `tests/unit/test_paperbench_adapter.py`

- [x] Write tests for fixture materialization, `reproduction_spec` mapping, and rubric leaf grading.
- [x] Run: `PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_paperbench_adapter.py -q`
      Expected: fails because `lib.benchmarks.paperbench` does not exist.
- [x] Implement:
      - `PaperBenchFixture`
      - `materialize_paperbench_fixture(runtime_root, paper_id="mlrl-debug-paper")`
      - `build_reproduction_spec(fixture, submission_dir)`
      - `build_paperbench_report(...)`
- [x] Re-run the unit test until it passes.

### Task 2: Demo Runner

**Files:**
- Create: `scripts/paperbench_adapter_demo.py`
- Test: `tests/integration/test_paperbench_adapter_demo.py`

- [x] Write an integration test that calls the script with `--runtime-root <tmp> --json`.
- [x] Run the test and verify it fails because the script does not exist.
- [x] Implement the script:
      - materialize the PaperBench fixture
      - create a submission directory
      - reuse the local reproduction demo flow or equivalent deterministic reproduction run
      - write `reproduction-report.json`
      - write `grade-report.json`
      - write `paperbench-report.json`
      - print final JSON
- [x] Re-run the integration test until it passes.

### Task 3: Docs And Gate

**Files:**
- Modify: `examples/README.md`
- Modify: `docs/development-roadmap-cn.md`
- Test: existing docs tests if they cover these docs.

- [x] Document that this is a PaperBench compatibility spike, not an official leaderboard score.
- [x] Run:
      `PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m ruff check lib/ scripts/ tests/`
- [x] Run:
      `PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=/opt/homebrew/Caskroom/miniforge/base/bin/python3 /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest tests/ -q`
- [x] Commit on `codex/paperbench-spike`.
