# Official Harness Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build read-only MLE-bench and PaperBench official harness feasibility probes and expose them through script, CLI, manifest, docs, and release checks.

**Architecture:** Add a pure `lib/benchmarks/harness_probe.py` module that accepts env, command lookup, and optional paths so tests can simulate ready/missing states without touching the host. The CLI/script call the same module; MCP manifest includes the same read-only payload so Codex/Claude can inspect readiness before planning benchmark work.

**Tech Stack:** Python standard library, argparse, pytest, existing CLI and MCP manifest patterns.

---

## File Structure

- Create: `lib/benchmarks/harness_probe.py`
  - Read-only command, repo, data, credential, and environment checks.
- Modify: `lib/benchmarks/__init__.py`
  - Export `build_official_harness_probe`.
- Create: `scripts/benchmark_harness_probe.py`
  - Direct JSON probe entrypoint.
- Modify: `scripts/cli.py`
  - Add `ml-loop benchmark probe`.
- Modify: `lib/mcp_service.py`
  - Add `benchmark_harness_probe` to manifest.
- Modify: `scripts/release_check.py`
  - Add cheap `benchmark-harness-probe` command.
- Test: `tests/unit/test_benchmark_harness_probe.py`
- Test: `tests/integration/test_benchmark_harness_probe.py`
- Modify: `tests/unit/test_cli.py`
- Modify: `tests/unit/test_mcp_service.py`
- Modify: `tests/unit/test_release_check.py`
- Docs: `docs/benchmark-adapter-roadmap-cn.md`, `docs/productization-todos.md`, `docs/release-checklist.md`, `examples/README.md`

### Task 1: Write Failing Probe Tests

- [x] Add a unit test that simulates all MLE-bench and PaperBench prerequisites and expects both harnesses to return `status=ready`.
- [x] Add a unit test that simulates missing commands/repos/credentials and expects top-level `status=needs_setup`.
- [x] Add a script integration test that runs `scripts/benchmark_harness_probe.py --json` and asserts it does not crash on a normal machine.
- [x] Add CLI, manifest, and release-check assertions.

### Task 2: Implement Probe Module And Script

- [x] Implement `build_official_harness_probe(...)`.
- [x] Ensure it never prints secret values.
- [x] Implement `scripts/benchmark_harness_probe.py`.
- [x] Run focused tests and confirm the RED tests turn GREEN.

### Task 3: Expose Through CLI, Manifest, Release Check

- [x] Add `ml-loop benchmark probe --json`.
- [x] Add `benchmark_harness_probe` to `get_service_manifest`.
- [x] Add `benchmark-harness-probe` to release check.
- [x] Update docs and TODO state.

### Task 4: Verification And Commit

- [x] Run `ruff check lib/ scripts/ tests/`.
- [x] Run full `pytest tests/ -q`.
- [x] Run `ml-loop benchmark probe --json`.
- [x] Run `scripts/release_check.py --json`.
- [x] Commit and push to `codex/benchmark-adapter-integration`.
