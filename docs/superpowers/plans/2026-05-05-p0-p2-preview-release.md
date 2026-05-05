# P0-P2 Preview Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the public repository from an open code drop to a validated preview release with stronger launch materials and incremental research/experiment intelligence.

**Architecture:** Keep the MCP contract preview-compatible and additive. P0 validates and publishes the current product, P1 improves external comprehension and demo readiness, and P2 adds deterministic quality signals that Codex/Claude can consume without introducing new runtime dependencies.

**Tech Stack:** Python 3.10/3.13, MCP stdio service, pytest, GitHub CLI, GitHub Actions, Markdown docs.

---

### Task 1: P0 Preview Release Pack

**Files:**
- Create: `scripts/fresh_checkout_check.py`
- Create: `docs/fresh-checkout-validation-cn.md`
- Modify: `docs/release-notes.md`
- Modify: `docs/release-checklist.md`

- [x] **Step 1: Add a fresh checkout verifier**

  Create `scripts/fresh_checkout_check.py` that clones a repository into a temp
  directory, creates a venv, installs `.[dev]`, runs MCP client acceptance,
  renders a Codex config, dry-runs skill install, and runs a bounded golden path.

- [x] **Step 2: Document the fresh checkout validation path**

  Create `docs/fresh-checkout-validation-cn.md` with the exact command and the
  acceptance fields to inspect.

- [x] **Step 3: Update release notes and checklist**

  Add `v0.1.0-preview` release guidance, fresh checkout validation, and public
  GitHub release expectations.

### Task 2: P1 Launch Materials

**Files:**
- Create: `docs/demo-transcript-cn.md`
- Create: `docs/launch-demo-cn.md`
- Modify: `README.md`
- Modify: `docs/project-overview-cn.md`

- [x] **Step 1: Add a demo transcript**

  Document a client-facing workflow from manifest to research context, hypothesis,
  experiment, review, and next action. Use generic paths only.

- [x] **Step 2: Add a launch demo runbook**

  Provide a 5-minute demo path and a Mermaid architecture diagram that explains
  Codex/Claude + Skills + MCP + runtime artifacts.

- [x] **Step 3: Link launch materials from README and project overview**

  Keep the README first screen short, but make the demo and architecture easy to
  find.

### Task 3: P2 Research Provider Quality Signals

**Files:**
- Modify: `lib/fusion_service.py`
- Modify: `tests/unit/test_research_quality_p8.py`

- [x] **Step 1: Add deterministic deduplication and cache summaries**

  Return `deduplication_report`, `cache_summary`, and `provider_quality_matrix`
  from `research_task`.

- [x] **Step 2: Test duplicate handling and cache summary shape**

  Add unit coverage that duplicate provider records are counted and cache hits
  are summarized for planner consumption.

### Task 4: P2 Automatic Experiment Intelligence Signals

**Files:**
- Modify: `lib/fusion_service.py`
- Modify: `scripts/mcp_real_task_code_benchmark.py`
- Modify: `tests/integration/test_mcp_real_task_code_benchmark.py`
- Create: `docs/real-paper-reproduction-demo-cn.md`

- [x] **Step 1: Add failure diagnostics and metric stop policy**

  Add `failure_diagnostics` and `metric_stop_policy` to `experiment_state` so
  clients can distinguish startup, timeout, missing metric, metric regression,
  and healthy continuation.

- [x] **Step 2: Surface benchmark intelligence**

  Extend the real task/code benchmark output with a compact benchmark summary
  covering data source, patch mode, loop decision, failure diagnostics, and stop
  policy.

- [x] **Step 3: Document a real-paper reproduction mini task**

  Add a product-facing doc that explains how to run a small paper-grounded
  reproduction using `read_paper`, `run_hypothesis_experiment`, and
  `mcp_reproduction_demo.py`.

### Task 5: Verification, Commit, Push, Release

**Files:**
- No code files beyond tasks above.

- [x] **Step 1: Run focused tests**

  Run provider quality, real task/code benchmark, open-source readiness, and CLI
  tests.

- [x] **Step 2: Run full release gate**

  Run `PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON="$(which python3)" python3 scripts/release_check.py --json`.

- [ ] **Step 3: Run fresh checkout validation**

  Run `python3 scripts/fresh_checkout_check.py --repo-url https://github.com/MagicianDu/ml-research-loop.git --ref main --skip-full-release-check`.

- [ ] **Step 4: Push and validate GitHub CI**

  Push to `main` and wait for the Python 3.10/3.13 GitHub Actions matrix.

- [ ] **Step 5: Tag and publish release**

  Create `v0.1.0-preview` after CI passes, publish a GitHub release, and verify
  the release URL.
