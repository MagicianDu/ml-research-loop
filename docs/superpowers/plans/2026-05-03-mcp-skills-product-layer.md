# MCP Skills Product Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a repository-local skill package that teaches Codex/Claude how to use the ML Research Loop MCP service for research planning, reproduction, experiment optimization, and operations.

**Architecture:** Keep MCP runtime code unchanged. Add one `SKILL.md` per workflow under `skills/`, document installation for Codex and Claude, and protect the package with pytest-based documentation checks.

**Tech Stack:** Markdown skills, pytest, existing release gate.

---

### Task 1: Add Skill Package Tests

**Files:**
- Create: `tests/unit/test_skill_packages.py`

- [x] **Step 1: Write failing tests**

Require four skill directories, valid `SKILL.md` frontmatter, workflow-specific tool coverage, linked installation docs, and P7 TODO completion.

- [x] **Step 2: Verify tests fail**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_skill_packages.py -q
```

Observed: six failures because `skills/` and `docs/skills-setup-cn.md` did not exist yet.

### Task 2: Add Skills And Installation Docs

**Files:**
- Create: `skills/ml-research-loop-planner/SKILL.md`
- Create: `skills/ml-research-loop-reproduction/SKILL.md`
- Create: `skills/ml-research-loop-experiment-optimizer/SKILL.md`
- Create: `skills/ml-research-loop-operator/SKILL.md`
- Create: `docs/skills-setup-cn.md`
- Modify: `README.md`
- Modify: `docs/mcp-client-setup.md`
- Modify: `docs/project-overview-cn.md`
- Modify: `docs/productization-todos.md`
- Modify: `docs/release-checklist.md`

- [x] **Step 1: Add skill files**

Create concise `SKILL.md` files with required frontmatter and workflow instructions.

- [x] **Step 2: Add installation docs**

Document Codex and Claude skill copy paths, MCP-first usage order, and safety boundaries.

- [x] **Step 3: Wire docs and TODOs**

Link skills setup from README, MCP setup, and project overview; mark P7 items complete after verification.

### Task 3: Verify And Commit

**Files:**
- Verify all modified files.

- [x] **Step 1: Run focused skill tests**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_skill_packages.py -q
```

Observed: `6 passed`.

- [x] **Step 2: Run documentation tests**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_mcp_delivery_docs.py tests/unit/test_skill_packages.py -q
```

Observed: `12 passed`.

- [x] **Step 3: Run full release gate**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON="$(which python3)" python3 scripts/release_check.py --json
```

Observed: `status: passed`; `pytest` reported `198 passed`.

- [x] **Step 4: Review diff and commit**

```bash
git diff --check
git diff --stat
git add README.md docs/mcp-client-setup.md docs/project-overview-cn.md docs/productization-todos.md docs/release-checklist.md docs/skills-setup-cn.md docs/superpowers/plans/2026-05-03-mcp-skills-product-layer.md skills tests/unit/test_skill_packages.py
git commit -m "Add MCP skill package"
```
