# P5 Product Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add product-grade execution metadata and explicit MCP contract compatibility checks.

**Architecture:** Keep the existing MCP preview contract and tool names stable. Add a shared execution metadata helper behind current execution tools, and add a structured client compatibility report in `scripts/mcp_client_acceptance.py` without changing normal stdio startup behavior.

**Tech Stack:** Python stdlib, existing MCP stdio JSON-RPC service, pytest, release_check.

---

## File Structure

- Modify `lib/mcp_service.py`: build execution metadata for run tools and expose the metadata contract in the manifest.
- Modify `scripts/mcp_client_acceptance.py`: add explicit contract/schema/tool compatibility checks and migration hints.
- Modify `docs/productization-todos.md`: mark P5 items complete after verification.
- Modify `docs/mcp-client-setup.md` and `docs/release-checklist.md`: document execution metadata and compatibility gates.
- Modify tests:
  - `tests/unit/test_mcp_service.py`
  - `tests/integration/test_mcp_client_acceptance.py`
  - `tests/unit/test_mcp_delivery_docs.py`
  - `tests/unit/test_release_check.py`

## Task 1: Execution Metadata

- [x] Add failing tests that assert execution payloads include `execution_metadata`.
- [x] Implement `_execution_metadata()` and `_artifact_retention_paths()` in `lib/mcp_service.py`.
- [x] Attach metadata to `run_fresh_demo`, `run_autoresearch`, `run_client_patch_experiment`, `apply_client_code_patch`, and `run_next_experiment_from_review`.
- [x] Verify targeted tests.

Expected command:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_mcp_service.py::test_run_autoresearch_reports_execution_metadata \
  tests/unit/test_mcp_service.py::test_apply_client_code_patch_reports_execution_metadata \
  tests/unit/test_mcp_service.py::test_run_client_patch_experiment_reports_execution_metadata \
  tests/unit/test_mcp_service.py::test_run_next_experiment_from_review_reports_execution_metadata -q
```

## Task 2: Compatibility And Migration Gate

- [x] Add failing tests for `compatibility_check` in client acceptance output.
- [x] Implement structured compatibility checks for `contract_version`, schema versions, required tools, and tool contracts.
- [x] Add migration hints for unknown contract versions and missing tool contracts.
- [x] Verify targeted tests.

Expected command:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/integration/test_mcp_client_acceptance.py \
  tests/unit/test_mcp_service.py::test_get_service_manifest_returns_client_contract -q
```

## Task 3: Docs, TODOs, And Release Gate

- [x] Document `execution_metadata` and `compatibility_check`.
- [x] Mark P5 complete in `docs/productization-todos.md`.
- [x] Run whitespace check and full release gate.

Expected command:

```bash
git diff --check
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
  python3 scripts/release_check.py --json
```
