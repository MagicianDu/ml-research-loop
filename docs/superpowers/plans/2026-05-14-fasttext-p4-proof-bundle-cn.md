# FastText P4 Proof Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the P3 fastText AG News patch round into a human-reviewed, hash-indexed proof bundle that can support honest public claims.

**Architecture:** Keep P3 as the execution loop and add a P4 packaging layer. The packaging layer consumes an existing `improvement-report.json`, verifies all required artifacts, copies them into a bounded proof directory, writes `human-review-report.json`, `proof-manifest.json`, `artifact-index.json`, `SHA256SUMS`, and a Chinese/English proof summary, while preserving `official_scores_claimed=false`. The MCP service remains an executor; Codex/Claude still performs planning and review decisions.

**Tech Stack:** Python stdlib, existing `lib/full_reproduction_harness.py`, `scripts/full_reproduction_run.py`, MCP stdio service, pytest, ruff.

---

### Task 1: Core Proof Bundle Writer

**Files:**
- Modify: `lib/full_reproduction_harness.py`
- Test: `tests/integration/test_full_reproduction_harness.py`

- [ ] **Step 1: Write the failing proof-bundle test**

Add `test_write_fasttext_patch_round_proof_bundle_hashes_required_artifacts`:

```python
def test_write_fasttext_patch_round_proof_bundle_hashes_required_artifacts(tmp_path: Path) -> None:
    train_csv, test_csv = _write_ag_news_fixture_csvs(tmp_path)
    fake_binary = _write_fake_fasttext_binary(tmp_path)
    baseline_dir = tmp_path / "baseline"
    patch_dir = tmp_path / "patch-round"
    proof_dir = tmp_path / "proof"
    baseline = run_fasttext_binary_baseline(...)
    run_fasttext_patch_round(..., baseline_report=Path(baseline["baseline_report"]), ...)

    result = write_fasttext_patch_round_proof_bundle(
        patch_round_report=patch_dir / "improvement-report.json",
        output_dir=proof_dir,
        reviewer="p4-test-reviewer",
    )

    assert result["status"] == "completed"
    assert result["stage"] == "p4_fasttext_patch_proof_bundle"
    assert result["official_scores_claimed"] is False
    assert (proof_dir / "proof-manifest.json").exists()
    assert (proof_dir / "human-review-report.json").exists()
    assert (proof_dir / "artifact-index.json").exists()
    assert (proof_dir / "SHA256SUMS").exists()
    manifest = json.loads((proof_dir / "proof-manifest.json").read_text())
    assert manifest["review_status"] == "approved_with_limitations"
    assert manifest["artifact_sha256"]["improvement_report"]
    assert manifest["artifact_sha256"]["patch_diff"]
    assert manifest["metric_summary"]["delta"] == 0.125
```

- [ ] **Step 2: Run RED**

Run:

```bash
python3 -m pytest tests/integration/test_full_reproduction_harness.py::test_write_fasttext_patch_round_proof_bundle_hashes_required_artifacts -q
```

Expected: fail because `write_fasttext_patch_round_proof_bundle` is not defined.

- [ ] **Step 3: Implement minimal core**

Add `write_fasttext_patch_round_proof_bundle(...)` that:

- reads `improvement-report.json`;
- verifies stage `p3_fasttext_patch_round`;
- resolves required artifacts from the patch round directory and baseline report path;
- blocks if any required artifact is missing;
- copies artifacts into `output_dir/artifacts`;
- writes SHA-256 hashes and byte sizes;
- writes `human-review-report.json` with `review_status=approved_with_limitations`;
- writes `proof-manifest.json`, `artifact-index.json`, `SHA256SUMS`, and `proof-summary.md`;
- keeps `official_scores_claimed=false`.

- [ ] **Step 4: Add missing-artifact negative test**

Add `test_write_fasttext_patch_round_proof_bundle_blocks_missing_artifact` by deleting `patch-diff.patch` before calling the writer.

Expected result:

```python
assert result["status"] == "blocked"
assert "patch_diff" in result["missing_artifacts"]
assert not (proof_dir / "proof-manifest.json").exists()
```

### Task 2: CLI and Release Gate

**Files:**
- Modify: `scripts/full_reproduction_run.py`
- Modify: `scripts/release_check.py`
- Modify: `tests/integration/test_full_reproduction_harness.py`
- Modify: `tests/unit/test_release_check.py`

- [ ] **Step 1: Write the failing CLI test**

Add `test_full_reproduction_run_cli_writes_fasttext_patch_proof_bundle` for:

```bash
python scripts/full_reproduction_run.py \
  --target-spec docs/reproduction-pilot/full-reproduction-target.json \
  --output-dir <tmp>/proof \
  --write-fasttext-patch-proof-bundle \
  --patch-round-report <tmp>/patch-round/improvement-report.json \
  --reviewer p4-cli-reviewer \
  --json
```

Expected: fail because the CLI mode does not exist.

- [ ] **Step 2: Implement CLI mode**

Add:

- `--write-fasttext-patch-proof-bundle`
- `--patch-round-report`
- `--reviewer`
- `--review-status`

Validate required arguments and call `write_fasttext_patch_round_proof_bundle`.

- [ ] **Step 3: Extend release gate**

Add release command `full-reproduction-fasttext-patch-proof-bundle` after `full-reproduction-fasttext-patch-round`, pointing to the release fixture patch-round report.

Update release-check unit tests to assert:

```python
assert "full-reproduction-fasttext-patch-proof-bundle" in labels
assert "--write-fasttext-patch-proof-bundle" in doc
```

### Task 3: MCP and Skills Contract

**Files:**
- Modify: `lib/mcp_service.py`
- Modify: `tests/unit/test_mcp_service.py`
- Modify: `skills/ml-research-loop-planner/SKILL.md`
- Modify: `skills/ml-research-loop-reproduction/SKILL.md`
- Modify: `skills/ml-research-loop-experiment-optimizer/SKILL.md`
- Modify: `skills/ml-research-loop-operator/SKILL.md`
- Modify: `tests/unit/test_skill_packages.py`

- [ ] **Step 1: Write failing MCP tests**

Assert `tools/list`, `get_service_manifest`, and direct tool execution expose and run `write_fasttext_patch_round_proof_bundle`.

Direct tool payload:

```json
{
  "patch_round_report": "/ABS/PATH/improvement-report.json",
  "output_dir": "/ABS/PATH/proof",
  "reviewer": "mcp-p4-reviewer"
}
```

- [ ] **Step 2: Implement MCP handler**

Add a path-checked `write_fasttext_patch_round_proof_bundle_tool` and add the tool to `REQUIRED_TOOLS`, `TOOL_CONTRACT_DESCRIPTIONS`, skill contracts, service manifest planning signals, and handler map.

- [ ] **Step 3: Update skills**

Document that P4 follows a useful P3 patch round and creates a human-reviewed proof bundle. Skills must continue to block official score and unattended-research claims.

### Task 4: Docs, Real Bundle, Verification, Commit

**Files:**
- Modify: `README.md`
- Modify: `docs/evidence/benchmark-results-index-cn.md`
- Modify: `docs/evidence/autonomous-product-proof-matrix-cn.md`
- Modify: `docs/reproduction-pilot/full-reproduction-fasttext-target-cn.md`
- Modify: `docs/evidence/fasttext-ag-news-p3-patch-round-20260513-cn.md`
- Modify: `docs/release-checklist.md`

- [ ] **Step 1: Generate real P4 bundle from existing P3 artifacts**

Run:

```bash
.venv/bin/python scripts/full_reproduction_run.py \
  --target-spec docs/reproduction-pilot/full-reproduction-target.json \
  --output-dir .demo_runs/p4-fasttext-real-proof \
  --write-fasttext-patch-proof-bundle \
  --patch-round-report .demo_runs/p3-fasttext-real-patch/improvement-report.json \
  --reviewer codex-local-review \
  --json
```

- [ ] **Step 2: Update Chinese docs**

Record proof bundle path, manifest, artifact count, hash index, review status, and claim boundary. Do not include machine-specific absolute paths in public docs.

- [ ] **Step 3: Verify**

Run:

```bash
.venv/bin/ruff check lib/ scripts/ ml_intern/ codex_plugin/ tests/
python3 -m pytest tests/integration/test_full_reproduction_harness.py tests/unit/test_mcp_service.py tests/unit/test_release_check.py tests/unit/test_skill_packages.py -q
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON="$(which python3)" python3 scripts/release_check.py --json
git diff --check
```

- [ ] **Step 4: Review and commit**

Review for overclaims, large artifacts, path leaks, missing negative tests, and release gate coverage. Commit and push only after verification passes.
