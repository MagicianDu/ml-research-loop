# Release Distribution P10 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current preview MCP product into a beta-ready distribution path with explicit release notes, compatibility guidance, and fresh-checkout onboarding.

**Architecture:** Keep `lib/mcp_service.py` and the public MCP tool contract stable. Add release-facing docs and a small `ml-loop init-mcp-config` CLI helper that renders Codex/Claude MCP config snippets from the local checkout path and Python executable.

**Tech Stack:** Python stdlib CLI, pytest documentation checks, existing MCP demo and release gate scripts.

---

## Files

- Modify `scripts/cli.py`: add `init-mcp-config` and config rendering helpers.
- Modify `tests/unit/test_cli.py`: TDD coverage for the new subcommand and rendered config.
- Create `docs/release-notes.md`: beta/stable release process, migration notes, known limitations.
- Create `docs/client-compatibility-matrix.md`: Codex, Claude Code, Claude Desktop support matrix.
- Create `examples/mcp/README.md`: shortest fresh-checkout registration and smoke-test path.
- Modify `README.md`, `docs/mcp-client-setup.md`, `docs/release-checklist.md`, `docs/productization-todos.md`, `tests/unit/test_mcp_delivery_docs.py`, and `tests/unit/test_release_check.py` to wire the docs into the release gate.

## Tasks

- [x] **Step 1: Add failing CLI tests**

  Add tests proving `ml-loop init-mcp-config` parses, prints Codex TOML, and writes Claude JSON with absolute paths.

- [x] **Step 2: Add failing release docs tests**

  Require release notes, compatibility matrix, and MCP examples README to mention contract version, migration notes, beta/stable gates, `ml-loop init-mcp-config`, client acceptance, and golden-path demo.

- [x] **Step 3: Verify red**

  Run:

  ```bash
  PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_cli.py tests/unit/test_mcp_delivery_docs.py tests/unit/test_release_check.py -q
  ```

  Expected: fail because the new CLI subcommand and new docs do not exist yet.

- [x] **Step 4: Implement CLI config rendering**

  Add `init-mcp-config` with `--client`, `--project-root`, `--python`, `--server-name`, `--output`, and `--force`.

- [x] **Step 5: Add release and onboarding docs**

  Document beta/stable release process, contract migration policy, client compatibility, and fresh checkout setup.

- [x] **Step 6: Verify green**

  Run the focused tests, then run:

  ```bash
  PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON="$(which python3)" python3 scripts/release_check.py --json
  ```

- [x] **Step 7: Review, stage, and commit**

  Run `git diff --check`, inspect the diff, stage all P10 files, and commit.
