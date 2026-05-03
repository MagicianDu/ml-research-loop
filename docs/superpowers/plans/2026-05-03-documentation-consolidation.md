# Documentation Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate the current ML Research Loop state into a project-level Chinese overview and a follow-up development roadmap before starting the MCP + Skills implementation phase.

**Architecture:** Keep runtime code unchanged. Add documentation as first-class release artifacts and protect the documentation surface with unit tests so README links, project positioning, and roadmap priorities do not drift silently.

**Tech Stack:** Markdown docs, pytest, existing release gate.

---

### Task 1: Add Documentation Acceptance Tests

**Files:**
- Modify: `tests/unit/test_mcp_delivery_docs.py`

- [x] **Step 1: Write failing tests**

Add tests that require `docs/project-overview-cn.md`, `docs/development-roadmap-cn.md`, README links, and P7-P10 roadmap coverage.

- [x] **Step 2: Verify tests fail**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_mcp_delivery_docs.py -q
```

Expected: fail because `docs/project-overview-cn.md` and `docs/development-roadmap-cn.md` do not exist yet.

### Task 2: Add Project Overview And Roadmap

**Files:**
- Create: `docs/project-overview-cn.md`
- Create: `docs/development-roadmap-cn.md`
- Modify: `README.md`
- Modify: `docs/productization-todos.md`

- [x] **Step 1: Add project overview**

Document the current ml-intern x autoresearch fusion, MCP + Skills product shape, AIDE/PaperBench architecture-pattern boundary, current product status, release gate, and document map.

- [x] **Step 2: Add development roadmap**

Document P7 MCP + Skills product layer, P8 real research retrieval quality, P9 automatic experiment intelligence, and P10 release/distribution.

- [x] **Step 3: Update links and TODOs**

Link the new docs from README and add P7-P10 to `docs/productization-todos.md`.

### Task 3: Verify And Commit

**Files:**
- Verify all modified files.

- [x] **Step 1: Run focused documentation tests**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_mcp_delivery_docs.py -q
```

Observed: `6 passed`.

- [x] **Step 2: Run full release gate**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON="$(which python3)" python3 scripts/release_check.py --json
```

Observed: `status: passed`; `pytest` reported `192 passed`.

- [x] **Step 3: Review diff and commit**

```bash
git diff -- README.md docs/project-overview-cn.md docs/development-roadmap-cn.md docs/productization-todos.md docs/superpowers/plans/2026-05-03-documentation-consolidation.md tests/unit/test_mcp_delivery_docs.py
git add README.md docs/project-overview-cn.md docs/development-roadmap-cn.md docs/productization-todos.md docs/superpowers/plans/2026-05-03-documentation-consolidation.md tests/unit/test_mcp_delivery_docs.py
git commit -m "Document project state and development roadmap"
```
