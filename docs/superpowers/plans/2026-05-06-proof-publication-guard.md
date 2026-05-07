# Proof Publication Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only proof publication guard that validates future official/debug benchmark artifact bundles and prevents overstated public claims.

**Architecture:** Add `lib/benchmarks/proof_publication.py` as a pure validator plus writer/markdown renderer. Wire it through a standalone script, `ml-loop benchmark publication-bundle`, MCP manifest, release check, and public docs.

**Tech Stack:** Python 3.10+/3.13, pytest, ruff, argparse, JSON/Markdown output.

---

### Task 1: Core Publication Guard

**Files:**
- Create: `lib/benchmarks/proof_publication.py`
- Modify: `lib/benchmarks/__init__.py`
- Test: `tests/unit/test_benchmark_proof_publication.py`

- [x] **Step 1: Write failing unit tests**

Cover:

- publishable artifact manifest with `official_scores_claimed=false`
- blocked manifest with missing artifacts
- blocked manifest where `official_scores_claimed=true` but score evidence is missing
- writer emits JSON and Markdown

- [x] **Step 2: Verify failure**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_benchmark_proof_publication.py -q
```

Expected: import failure because the builder does not exist.

- [x] **Step 3: Implement core**

Implement:

- `build_proof_publication_bundle(manifest, artifact_root)`
- `render_proof_publication_markdown(bundle)`
- `write_proof_publication_bundle(bundle, output_dir)`

- [x] **Step 4: Verify unit tests pass**

Run the same command. Expected: pass.

### Task 2: Script and CLI

**Files:**
- Create: `scripts/benchmark_proof_publication.py`
- Modify: `scripts/cli.py`
- Test: `tests/integration/test_benchmark_proof_publication.py`, `tests/unit/test_cli.py`

- [x] **Step 1: Write failing tests**

Integration test writes a small artifact root/manifest, runs the script, and
asserts output files exist. CLI unit test verifies `benchmark publication-bundle`
calls the builder/writer.

- [x] **Step 2: Verify failure**

Run focused tests and confirm missing script/CLI failures.

- [x] **Step 3: Implement script and CLI**

The script reads JSON manifest, builds the bundle, writes output, and prints
writer paths.

- [x] **Step 4: Verify focused tests pass**

Run focused tests again.

### Task 3: Manifest, Release Gate, Docs

**Files:**
- Modify: `lib/mcp_service.py`
- Modify: `scripts/release_check.py`
- Modify: `tests/unit/test_mcp_service.py`
- Modify: `tests/unit/test_release_check.py`
- Modify: `README.md`
- Modify: `docs/benchmark-adapter-roadmap-cn.md`
- Modify: `docs/productization-todos.md`
- Modify: `docs/release-checklist.md`
- Modify: `examples/README.md`

- [x] **Step 1: Write failing contract tests**

Require:

- `benchmark_proof_publication` in manifest
- `benchmark_proof_publication` in planning signals
- `benchmark_proof_publication.py` in acceptance commands
- `benchmark-proof-publication` release command label
- docs mention `ml-loop benchmark publication-bundle`

- [x] **Step 2: Verify failure**

Run contract tests and confirm failures.

- [x] **Step 3: Implement manifest/release/docs**

Add release check sample artifact root and manifest under `.demo_runs`.

- [x] **Step 4: Verify focused tests pass**

Run focused contract tests.

### Task 4: Final Verification

- [x] **Step 1: Run ruff**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m ruff check lib/ scripts/ tests/
```

- [x] **Step 2: Run full tests**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=/opt/homebrew/Caskroom/miniforge/base/bin/python3 /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest tests/ -q
```

- [x] **Step 3: Run release gate**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=/opt/homebrew/Caskroom/miniforge/base/bin/python3 /opt/homebrew/Caskroom/miniforge/base/bin/python3 scripts/release_check.py --python /opt/homebrew/Caskroom/miniforge/base/bin/python3 --json
```

- [x] **Step 4: Review, commit, push**

Use `git diff --check`, review changed code/docs, commit, and push.
