# Proof Run Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a proof-run archive intake that copies complete external benchmark artifacts into a hashed, reproducible evidence archive.

**Architecture:** Add `lib/benchmarks/proof_archive.py` as a pure archive planner plus writer. The writer reuses the publication guard, copies only artifacts confined to `artifact_root`, writes hash indexes, and is exposed through a script, `ml-loop benchmark archive-proof`, MCP manifest, release gate, and docs.

**Tech Stack:** Python 3.10+/3.13, pytest, ruff, argparse, JSON, SHA-256, shutil.

---

### Task 1: Core Archive Planner

**Files:**
- Create: `lib/benchmarks/proof_archive.py`
- Modify: `lib/benchmarks/__init__.py`
- Test: `tests/unit/test_benchmark_proof_archive.py`

- [x] **Step 1: Write failing unit tests**

Cover:

- complete manifest returns `status=archivable`, `artifact_count=6`, and SHA-256 entries;
- outside-root paths are blocked and not treated as archiveable;
- writer copies artifacts, writes `proof-archive.json`, `artifact-index.json`, and nested publication guard files.

- [x] **Step 2: Verify failure**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest tests/unit/test_benchmark_proof_archive.py -q
```

Expected: import failure because `build_proof_archive_bundle` does not exist.

- [x] **Step 3: Implement core**

Implement:

- `build_proof_archive_bundle(artifact_manifest, artifact_root)`;
- `write_proof_archive_bundle(bundle, artifact_root, output_dir)`;
- SHA-256, size, role, source path, and archive path indexing;
- path confinement under `artifact_root`.

- [x] **Step 4: Verify unit tests pass**

Run the same command. Expected: pass.

### Task 2: Script and CLI

**Files:**
- Create: `scripts/benchmark_proof_archive.py`
- Modify: `scripts/cli.py`
- Test: `tests/integration/test_benchmark_proof_archive.py`, `tests/unit/test_cli.py`

- [x] **Step 1: Write failing tests**

Integration test writes a small artifact root/manifest, runs the script, and asserts archive files and copied artifacts exist. CLI unit test verifies `benchmark archive-proof` calls the builder/writer.

- [x] **Step 2: Verify failure**

Run focused tests and confirm missing script/CLI failures.

- [x] **Step 3: Implement script and CLI**

The script reads JSON manifest, builds the archive bundle, writes output, and prints writer paths.

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

- `benchmark_proof_archive` in manifest;
- `benchmark_proof_archive` in planning signals;
- `benchmark_proof_archive.py` in acceptance commands;
- `benchmark-proof-archive` release command label;
- docs mention `ml-loop benchmark archive-proof`.

- [x] **Step 2: Verify failure**

Run contract tests and confirm failures.

- [x] **Step 3: Implement manifest/release/docs**

Use the existing release-check sample proof artifacts to run both publication and archive checks.

- [x] **Step 4: Verify focused tests pass**

Run focused contract tests.

### Task 4: Final Verification

- [x] **Step 1: Run ruff**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m ruff check lib/ scripts/ tests/
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
