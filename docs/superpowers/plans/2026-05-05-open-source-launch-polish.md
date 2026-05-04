# Open Source Launch Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare the repository for its first public GitHub push by making the landing path clear, runnable, and differentiated.

**Architecture:** This is a documentation and release-safety pass. It does not expand the MCP contract; it sharpens the README, onboarding examples, launch positioning, and regression checks around public placeholders.

**Tech Stack:** Markdown documentation, pytest regression checks, existing MCP release gate.

---

### Task 1: Public Landing Page

**Files:**
- Modify: `README.md`

- [x] **Step 1: Rewrite the first screen**

  Make the top of `README.md` explain the product in external-user language:
  `MCP-native ML research loop for Codex and Claude`, the `ml-intern` and
  `autoresearch` fusion, and the preview status.

- [x] **Step 2: Add the shortest runnable path**

  Use the real repository URL for `MagicianDu/ml-research-loop`.

- [x] **Step 3: Add client onboarding commands**

  Keep the commands:
  `ml-loop init-mcp-config --client codex`,
  `ml-loop init-mcp-config --client claude-code`,
  `ml-loop init-skills --client codex`, and
  `ml-loop init-skills --client claude`.

### Task 2: Public Onboarding Examples

**Files:**
- Modify: `examples/mcp/README.md`
- Modify: `examples/mcp/codex-config.toml`

- [x] **Step 1: Replace stale clone placeholders**

  Replace stale sample clone URLs with the public repository URL.

- [x] **Step 2: Avoid token-shaped sample values**

  Keep the GitHub token guidance as a comment, but do not include
  token-shaped sample values in public examples.

### Task 3: Differentiation Document

**Files:**
- Create: `docs/open-source-positioning-cn.md`
- Modify: `docs/project-overview-cn.md`

- [x] **Step 1: Document why this project is different**

  Explain the MCP + Skills shape, ml-intern/autoresearch fusion, AIDE/PaperBench
  pattern adoption, and what remains preview.

- [x] **Step 2: Link it from the project overview**

  Add the new document to the docs map.

### Task 4: Regression Checks

**Files:**
- Modify: `tests/unit/test_open_source_readiness.py`

- [x] **Step 1: Add public placeholder assertions**

  Prevent stale sample clone URLs and token-shaped sample values from
  reappearing in public files.

- [x] **Step 2: Run focused and full gates**

  Run:
  `python3 -m pytest tests/unit/test_open_source_readiness.py -q`

  Then run:
  `PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON="$(which python3)" python3 scripts/release_check.py --json`
