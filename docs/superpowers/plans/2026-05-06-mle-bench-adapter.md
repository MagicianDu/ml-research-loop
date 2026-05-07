# MLE-bench Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic MLE-bench-shaped adapter and demo so ML Research Loop can produce benchmark-style ML engineering artifacts.

**Architecture:** Add a small dependency-free `lib/benchmarks/mle_bench.py` module that materializes a fixture competition, runs an existing demo-backed experiment, writes a submission, and emits run-group metadata/report files. Expose it through `scripts/mle_bench_adapter_demo.py` first; do not alter MCP contracts yet.

**Tech Stack:** Python standard library, existing `lib.demo_templates`, pytest, ruff.

---

### Task 1: Adapter Model And Fixture

**Files:**
- Create: `lib/benchmarks/__init__.py`
- Create: `lib/benchmarks/mle_bench.py`
- Test: `tests/unit/test_mle_bench_adapter.py`

- [x] Write tests for fixture materialization and report schema.
- [x] Run: `PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_mle_bench_adapter.py -q`
      Expected: fails because `lib.benchmarks.mle_bench` does not exist.
- [x] Implement:
      - `MLEBenchFixture`
      - `materialize_mle_bench_fixture(runtime_root, competition_id="mlrl-byte-lm")`
      - `build_mle_bench_report(...)`
      - `write_mle_bench_submission(...)`
- [x] Re-run the unit test until it passes.

### Task 2: Demo Runner

**Files:**
- Create: `scripts/mle_bench_adapter_demo.py`
- Test: `tests/integration/test_mle_bench_adapter_demo.py`

- [x] Write an integration test that calls the script with `--runtime-root <tmp> --json`.
- [x] Run the test and verify it fails because the script does not exist.
- [x] Implement the script:
      - materialize the fixture
      - call `run_demo_template(template_name="byte-lm-smoke", ...)`
      - write `submission.csv`
      - write `metadata.json`
      - write `benchmark_report.json`
      - print final JSON
- [x] Re-run the integration test until it passes.

### Task 3: Docs And Gate

**Files:**
- Modify: `examples/README.md`
- Modify: `docs/development-roadmap-cn.md`
- Test: existing docs tests if they cover these docs.

- [x] Document that this is an MLE-bench compatibility spike, not an official score.
- [x] Run:
      `PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m ruff check lib/ scripts/ tests/`
- [x] Run:
      `PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=/opt/homebrew/Caskroom/miniforge/base/bin/python3 /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest tests/ -q`
- [x] Commit on `codex/mle-bench-spike`.
