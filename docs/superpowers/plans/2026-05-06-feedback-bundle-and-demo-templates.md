# Feedback Bundle And Demo Templates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the preview easier to test by adding a redacted feedback bundle and stable demo task templates.

**Architecture:** Keep the implementation dependency-free. Add focused library modules for collecting diagnostics and materializing demo templates, then expose them through the existing `ml-loop` CLI.

**Tech Stack:** Python standard library, existing MCP/autoresearch modules, pytest, ruff.

---

### Task 1: P0 Feedback Bundle

**Files:**
- Create: `lib/feedback_bundle.py`
- Modify: `scripts/cli.py`
- Modify: `docs/preview-feedback-cn.md`
- Modify: `README.md`
- Test: `tests/unit/test_feedback_bundle.py`
- Test: `tests/unit/test_cli.py`

- [ ] Write tests for redaction, bundle writing, and CLI output.
- [ ] Run `python -m pytest tests/unit/test_feedback_bundle.py tests/unit/test_cli.py -q` and verify the new tests fail because the module and command do not exist.
- [ ] Implement `lib.feedback_bundle` with structured JSON, markdown rendering, log tails, artifact paths, environment metadata, and token/path redaction.
- [ ] Add `ml-loop feedback-bundle`.
- [ ] Document the command in README and the preview feedback guide.
- [ ] Re-run the focused tests.

### Task 2: P1 Demo Templates

**Files:**
- Create: `lib/demo_templates.py`
- Modify: `scripts/cli.py`
- Modify: `examples/README.md`
- Modify: `docs/launch-demo-cn.md`
- Test: `tests/unit/test_demo_templates.py`
- Test: `tests/integration/test_demo_templates_cli.py`

- [ ] Write tests for listing templates, materializing a real local byte-LM template, and running the CLI demo.
- [ ] Run `python -m pytest tests/unit/test_demo_templates.py tests/integration/test_demo_templates_cli.py -q` and verify the new tests fail because the module and command do not exist.
- [ ] Implement deterministic demo templates that write local data and task configs under the selected runtime root.
- [ ] Add `ml-loop demo list`, `ml-loop demo init`, and `ml-loop demo run`.
- [ ] Document the templates and expected output fields.
- [ ] Re-run the focused tests.

### Task 3: Final Verification

**Files:**
- Modify any failing tests or docs discovered by the gate.

- [ ] Run `python -m pytest tests/unit/test_feedback_bundle.py tests/unit/test_demo_templates.py tests/unit/test_cli.py -q`.
- [ ] Run `python -m pytest tests/integration/test_demo_templates_cli.py -q`.
- [ ] Run `python scripts/release_check.py --json`.
- [ ] Review the diff manually for path/token leakage, command ergonomics, and compatibility with fresh checkouts.
- [ ] Commit the completed P0/P1 work.
