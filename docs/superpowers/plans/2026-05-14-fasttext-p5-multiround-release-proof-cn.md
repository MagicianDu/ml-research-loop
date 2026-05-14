# FastText P5 Multiround Release Proof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Extend the fastText reproduction track from one reviewed patch proof into a multi-round proposal loop with failure/rollback evidence and a downloadable, reviewable release proof package.

**Architecture:** Keep the server as bounded executor. P5 adds one multi-round runner that consumes a list of client proposals, executes each proposal in an isolated subdirectory, records validation/execution failures as structured failed rounds, and keeps a best-so-far rollback state. P5 also adds a release proof packager that consumes a P4 proof manifest plus optional multi-round report, writes a review checklist, verifies hashes, and emits a `.tar.gz` download artifact with its SHA-256.

**Tech Stack:** Python stdlib (`json`, `tarfile`, `hashlib`, `shutil`), existing `lib/full_reproduction_harness.py`, `scripts/full_reproduction_run.py`, MCP stdio service, pytest, ruff.

---

### Task 1: Multi-round Proposal Loop

**Files:**
- Modify: `lib/full_reproduction_harness.py`
- Test: `tests/integration/test_full_reproduction_harness.py`

- [x] **Step 1: Write failing multi-round test**

Add `test_run_fasttext_multi_proposal_loop_records_failure_and_rollback` that:

```python
baseline = run_fasttext_binary_baseline(...)
result = run_fasttext_multi_proposal_loop(
    FullReproductionRunConfig(...),
    train_csv=train_csv,
    test_csv=test_csv,
    fasttext_binary=fake_binary,
    baseline_report=Path(baseline["baseline_report"]),
    proposals=[
        {"proposal_id": "good-bigram", "train_args": {"wordNgrams": 2}},
        {"proposal_id": "bad-arg", "train_args": {"bucket": 100}},
    ],
)
```

Assert:

```python
assert result["status"] == "completed_with_failures"
assert result["best_metric"] == 0.875
assert result["failure_count"] == 1
assert result["rollback_summary"]["rollback_events"] == 1
assert (output_dir / "multi-round-report.json").exists()
assert (output_dir / "rounds" / "round-001-good-bigram" / "improvement-report.json").exists()
```

- [x] **Step 2: Run RED**

Run:

```bash
python3 -m pytest tests/integration/test_full_reproduction_harness.py::test_run_fasttext_multi_proposal_loop_records_failure_and_rollback -q
```

Expected: fail because `run_fasttext_multi_proposal_loop` is not defined.

- [x] **Step 3: Implement minimal multi-round runner**

Add `run_fasttext_multi_proposal_loop(...)` that:

- validates non-empty proposal list;
- reads the baseline `P@1`;
- runs each proposal under `rounds/round-XXX-<proposal-id>`;
- catches `ValueError`, `FileNotFoundError`, and `RuntimeError` as failed rounds;
- records `rollback_action=keep_best_so_far`;
- writes `multi-round-report.json` and `client-handoff.json`;
- returns `official_scores_claimed=false`.

- [x] **Step 4: Run GREEN**

Run the targeted test and then:

```bash
python3 -m pytest tests/integration/test_full_reproduction_harness.py -q
```

### Task 2: Release Proof Download/Review Bundle

**Files:**
- Modify: `lib/full_reproduction_harness.py`
- Test: `tests/integration/test_full_reproduction_harness.py`

- [x] **Step 1: Write failing release-bundle test**

Add `test_write_fasttext_release_proof_bundle_creates_download_and_review_files` that creates a P4 proof bundle and a P5 multi-round report, then calls:

```python
result = write_fasttext_release_proof_bundle(
    proof_manifest=proof_dir / "proof-manifest.json",
    output_dir=release_dir,
    multi_round_report=multi_dir / "multi-round-report.json",
)
```

Assert:

```python
assert result["status"] == "completed"
assert result["stage"] == "p5_fasttext_release_proof_bundle"
assert result["download_bundle"].endswith(".tar.gz")
assert result["bundle_sha256"]
assert (release_dir / "release-review-checklist.md").exists()
assert (release_dir / "release-proof-manifest.json").exists()
assert (release_dir / "release-proof-bundle.tar.gz").exists()
```

- [x] **Step 2: Run RED**

Run the new test and confirm it fails because `write_fasttext_release_proof_bundle` is not defined.

- [x] **Step 3: Implement release packager**

Add `write_fasttext_release_proof_bundle(...)` that:

- verifies P4 proof manifest exists and has `official_scores_claimed=false`;
- optionally verifies P5 multi-round report exists and has `official_scores_claimed=false`;
- copies the P4 proof bundle directory into `output_dir/review-package/p4-proof`;
- copies the multi-round report into `output_dir/review-package/p5-multi-round`;
- writes `release-proof-manifest.json`, `release-review-checklist.md`, and `release-proof-bundle.tar.gz`;
- writes `release-proof-bundle.sha256`;
- keeps public claim boundaries explicit.

### Task 3: CLI, MCP, Skills, Release Gate

**Files:**
- Modify: `scripts/full_reproduction_run.py`
- Modify: `scripts/release_check.py`
- Modify: `lib/mcp_service.py`
- Modify: `tests/unit/test_mcp_service.py`
- Modify: `tests/unit/test_release_check.py`
- Modify: `skills/ml-research-loop-*.md`
- Modify: `tests/unit/test_skill_packages.py`

- [x] **Step 1: Add CLI tests**

Add CLI coverage for:

```bash
--run-fasttext-multi-proposal-loop --fasttext-proposals <proposals.json>
--write-fasttext-release-proof-bundle --proof-manifest <proof-manifest.json> --multi-round-report <multi-round-report.json>
```

- [x] **Step 2: Implement CLI and release gate**

Add release commands:

- `full-reproduction-fasttext-multi-proposal-loop`
- `full-reproduction-fasttext-release-proof-bundle`

- [x] **Step 3: Implement MCP tools**

Expose:

- `run_fasttext_multi_proposal_loop`
- `write_fasttext_release_proof_bundle`

Both tools must path-check inputs/outputs and preserve `official_scores_claimed=false`.

- [x] **Step 4: Update skills**

Document that P5 is the preferred path after P4 when the operator wants stronger public evidence: run several proposals, include at least one failed or rejected proposal, preserve rollback summary, then package release proof for download/review.

### Task 4: Docs, Real P5 Run, Verification, Commit

**Files:**
- Create: `docs/evidence/fasttext-ag-news-p5-release-proof-20260514-cn.md`
- Modify: `README.md`
- Modify: `docs/evidence/benchmark-results-index-cn.md`
- Modify: `docs/evidence/autonomous-product-proof-matrix-cn.md`
- Modify: `docs/evidence/public-claims-map.json`
- Modify: `docs/reproduction-pilot/full-reproduction-fasttext-target-cn.md`
- Modify: `docs/release-checklist.md`

- [x] **Step 1: Run real P5 artifacts**

Create `.demo_runs/p5-fasttext-real/proposals.json` with one successful proposal and one invalid proposal. Run:

```bash
.venv/bin/python scripts/full_reproduction_run.py \
  --target-spec docs/reproduction-pilot/full-reproduction-target.json \
  --output-dir .demo_runs/p5-fasttext-real/multi-round \
  --run-fasttext-multi-proposal-loop \
  --ag-news-train-csv .demo_runs/p2ppp-ag-news-current/train.csv \
  --ag-news-test-csv .demo_runs/p2ppp-ag-news-current/test.csv \
  --fasttext-binary .external/fastText/fasttext \
  --baseline-report .demo_runs/p2ppp-fasttext-real-baseline/fasttext-baseline-report.json \
  --fasttext-proposals .demo_runs/p5-fasttext-real/proposals.json \
  --max-train-seconds 900 \
  --json
```

Then package:

```bash
.venv/bin/python scripts/full_reproduction_run.py \
  --target-spec docs/reproduction-pilot/full-reproduction-target.json \
  --output-dir .demo_runs/p5-fasttext-real/release-proof \
  --write-fasttext-release-proof-bundle \
  --proof-manifest .demo_runs/p4-fasttext-real-proof/proof-manifest.json \
  --multi-round-report .demo_runs/p5-fasttext-real/multi-round/multi-round-report.json \
  --json
```

- [x] **Step 2: Update docs**

Document P5 metrics, failure count, rollback event count, release package path, tarball SHA-256, and claim boundary. Public docs must not include machine-specific absolute paths.

- [x] **Step 3: Verify**

Run:

```bash
.venv/bin/ruff check lib/ scripts/ ml_intern/ codex_plugin/ tests/
python3 -m pytest tests/integration/test_full_reproduction_harness.py tests/unit/test_mcp_service.py tests/unit/test_release_check.py tests/unit/test_skill_packages.py -q
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON="$(which python3)" python3 scripts/release_check.py --json
git diff --check
```

- [x] **Step 4: Review and commit**

Review for overclaims, path leaks, large tracked artifacts, missing negative tests, and release gate coverage. Commit and push after verification.
