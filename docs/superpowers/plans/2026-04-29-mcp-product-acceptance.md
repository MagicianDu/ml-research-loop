# MCP Product Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the MCP service easier for Codex/Claude clients to self-discover and add a true stdio client acceptance check to the release gate.

**Architecture:** Keep the hybrid planner/executor boundary unchanged. Add one lightweight MCP manifest tool that returns product status, model-boundary rules, recommended workflows, and release commands. Add one external client script that talks to `scripts/mcp_server.py` over line-delimited stdio, verifying the same path real MCP clients use.

**Tech Stack:** Python stdio JSON-RPC MCP service, pytest, ruff, markdown docs.

---

### Task 1: MCP Service Manifest Tool

**Files:**
- Modify: `lib/mcp_service.py`
- Modify: `tests/unit/test_mcp_service.py`
- Modify: `README.md`
- Modify: `docs/mcp-client-setup.md`
- Modify: `docs/release-checklist.md`

- [x] **Step 1: Write failing manifest tests**

Add tests that assert `tools/list` includes `get_service_manifest` and the handler returns:

- `architecture == "hybrid_client_planner_server_executor"`
- `product_status == "preview"`
- `client_model_role` mentions Codex/Claude planner responsibility
- `server_side_llm.tool == "run_ai_autoresearch"`
- `recommended_workflows[0].tools` starts with `research_task`

- [x] **Step 2: Run manifest tests and verify failure**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_mcp_service.py::test_tools_list_exposes_research_loop_tools \
  tests/unit/test_mcp_service.py::test_get_service_manifest_returns_client_contract -q
```

Expected: fail because `get_service_manifest` does not exist.

- [x] **Step 3: Implement manifest tool**

Add the MCP tool definition and handler in `lib/mcp_service.py`. Register it in `TOOL_HANDLERS`.

- [x] **Step 4: Document manifest usage**

Mention `get_service_manifest` in README, MCP client setup, and release checklist.

- [x] **Step 5: Verify Task 1**

Run the manifest tests again and expect pass.

### Task 2: True Stdio Client Acceptance Script

**Files:**
- Create: `scripts/mcp_client_acceptance.py`
- Create: `tests/integration/test_mcp_client_acceptance.py`
- Modify: `scripts/release_check.py`
- Modify: `tests/unit/test_release_check.py`
- Modify: `docs/mcp-client-setup.md`
- Modify: `docs/release-checklist.md`

- [x] **Step 1: Write failing acceptance tests**

Add an integration test that runs:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
python3 scripts/mcp_client_acceptance.py --python "$(which python3)"
```

Assert the final JSON reports:

- `status == "passed"`
- `server_info.name == "ml-research-loop"`
- `manifest.architecture == "hybrid_client_planner_server_executor"`
- `missing_required_tools == []`

Update release-check unit tests to expect label `mcp-client-acceptance`.

- [x] **Step 2: Run acceptance tests and verify failure**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/integration/test_mcp_client_acceptance.py \
  tests/unit/test_release_check.py -q
```

Expected: fail because the script and release label do not exist.

- [x] **Step 3: Implement stdio acceptance script**

Spawn `scripts/mcp_server.py`, send `initialize`, `tools/list`, and `tools/call get_service_manifest`, parse line-delimited JSON responses, and print a compact JSON acceptance report.

- [x] **Step 4: Wire acceptance into release gate and docs**

Add the script to `scripts/release_check.py` and document it in setup/release docs.

- [x] **Step 5: Verify Task 2**

Run targeted tests and expect pass.

### Task 3: Full Verification And Commit

**Files:**
- All files changed above.

- [x] **Step 1: Run full release check**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=$(which python3) python3 scripts/release_check.py --json
```

Expected: `status: passed`.

- [x] **Step 2: Run diff checks**

Run:

```bash
git diff --check
git diff --stat
```

Expected: no whitespace errors and scoped changes only.

- [x] **Step 3: Commit**

Commit message:

```bash
git commit -m "feat: add mcp product acceptance checks"
```
