# Official Proof Setup Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only official benchmark proof-run setup bundle so Codex/Claude and a human operator can prepare an external evaluation environment safely.

**Architecture:** Add a pure builder in `lib/benchmarks/proof_setup.py` that consumes the existing proof plan and returns setup instructions, redacted environment templates, artifact manifests, and official references. Add a writer and markdown renderer, expose them through `scripts/benchmark_proof_setup.py`, `ml-loop benchmark setup-bundle`, the MCP manifest, and release gate docs.

**Tech Stack:** Python 3.10+/3.13, pytest, ruff, argparse, JSON/Markdown file output.

---

### Task 1: Core Bundle Builder

**Files:**
- Create: `lib/benchmarks/proof_setup.py`
- Modify: `lib/benchmarks/__init__.py`
- Test: `tests/unit/test_benchmark_proof_setup.py`

- [ ] **Step 1: Write failing tests**

Test `build_official_proof_setup_bundle()` with a blocked proof plan and assert:

- `read_only is True`
- `official_scores_claimed is False`
- `status == "blocked"`
- environment template contains variable names with empty values
- serialized payload has no token-shaped values
- MLE-bench and PaperBench setup sections are present

- [ ] **Step 2: Verify failure**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_benchmark_proof_setup.py -q
```

Expected: import failure because the builder does not exist.

- [ ] **Step 3: Implement minimal builder and renderer**

Create `lib/benchmarks/proof_setup.py` with:

- `build_official_proof_setup_bundle(proof_plan)`
- `render_official_proof_setup_markdown(bundle)`
- `write_official_proof_setup_bundle(bundle, output_dir)`

- [ ] **Step 4: Verify tests pass**

Run the same unit test command. Expected: pass.

### Task 2: Script and CLI

**Files:**
- Create: `scripts/benchmark_proof_setup.py`
- Modify: `scripts/cli.py`
- Test: `tests/integration/test_benchmark_proof_setup.py`, `tests/unit/test_cli.py`

- [ ] **Step 1: Write failing tests**

Integration test runs:

```bash
python3 scripts/benchmark_proof_setup.py --output-dir <tmp> --json
```

and verifies the three files exist.

CLI unit test verifies:

```bash
ml-loop benchmark setup-bundle --output-dir <tmp> --json
```

calls the bundle writer.

- [ ] **Step 2: Verify failure**

Run focused tests and confirm missing script/CLI failures.

- [ ] **Step 3: Implement script and CLI**

The script and CLI must call the existing official harness probe, proof plan,
setup bundle builder, and writer. They must not run any official benchmark
command.

- [ ] **Step 4: Verify focused tests pass**

Run focused tests again.

### Task 3: Manifest, Release Gate, and Docs

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

- [ ] **Step 1: Write failing contract tests**

Require:

- `benchmark_proof_setup` in manifest
- `benchmark_proof_setup` in planning signals
- `benchmark_proof_setup.py` in acceptance commands
- `benchmark-proof-setup` release command label
- docs mention `ml-loop benchmark setup-bundle`

- [ ] **Step 2: Verify failure**

Run contract tests and confirm failures.

- [ ] **Step 3: Implement manifest/release/docs**

Add a cheap setup-bundle check using a `.demo_runs/release-check-proof-setup-*`
output directory.

- [ ] **Step 4: Verify focused tests pass**

Run focused contract tests again.

### Task 4: Full Verification and Commit

- [ ] **Step 1: Run ruff**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m ruff check lib/ scripts/ tests/
```

- [ ] **Step 2: Run full tests**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=/opt/homebrew/Caskroom/miniforge/base/bin/python3 /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest tests/ -q
```

- [ ] **Step 3: Run setup script**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 scripts/benchmark_proof_setup.py --output-dir .demo_runs/proof-setup-check --json
```

- [ ] **Step 4: Run full release gate**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=/opt/homebrew/Caskroom/miniforge/base/bin/python3 /opt/homebrew/Caskroom/miniforge/base/bin/python3 scripts/release_check.py --python /opt/homebrew/Caskroom/miniforge/base/bin/python3 --json
```

- [ ] **Step 5: Review diff, commit, and push**

Use `git diff --check`, review code/docs, commit, and push the PR branch.
