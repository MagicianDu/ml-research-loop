# Official MLE-bench Patch Proof Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn each official MLE-bench patch round into a durable proof bundle with patch diff, round reports, logs, limitations, publication guard, and hashed archive output.

**Architecture:** Keep the patch loop MCP-first: Codex/Claude proposes code, the MCP service executes and grades locally, then a separate proof step packages the exact artifacts for audit. The proof step consumes a persisted `patch-round-report.json`, writes a manifest plus artifact root, and reuses the existing publication/archive guards so local `grade-sample` feedback is never promoted to a leaderboard claim.

**Tech Stack:** Python stdlib, existing `lib.benchmarks.proof_publication`, existing `lib.benchmarks.proof_archive`, pytest, ruff, release_check.

---

### Task 1: Persist Patch-Round Artifacts

**Files:**
- Modify: `lib/mcp_service.py`
- Test: `tests/unit/test_mcp_service.py`

- [x] **Step 1: Write failing tests**

Add assertions to `test_run_official_mle_bench_patch_round_tool_applies_patch_then_grades`:

```python
patch_round_report = Path(payload["patch_round_report_path"])
patch_diff = Path(payload["patch_diff_path"])
assert patch_round_report.is_file()
assert patch_diff.is_file()
written_report = json.loads(patch_round_report.read_text(encoding="utf-8"))
assert written_report["patch_execution"]["status"] == "applied"
assert written_report["round"]["status"] == "graded"
assert patch_diff.read_text(encoding="utf-8") == patch + "\n"
```

- [x] **Step 2: Verify RED**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest \
  tests/unit/test_mcp_service.py::test_run_official_mle_bench_patch_round_tool_applies_patch_then_grades \
  -q
```

Expected: fail because `patch_round_report_path` and `patch_diff_path` are missing.

- [x] **Step 3: Implement artifact writing**

In `run_official_mle_bench_patch_round_tool`, after building the payload and before returning it, write:

```text
<output_dir>/<round_id>/patch-round-report.json
<output_dir>/<round_id>/patch.diff
```

Store their absolute paths on the payload as `patch_round_report_path` and `patch_diff_path`. The report must contain the same payload returned to MCP clients, including `official_scores_claimed=false`.

- [x] **Step 4: Verify GREEN**

Run the same targeted pytest command. Expected: pass.

### Task 2: Build Patch-Round Proof Bundle

**Files:**
- Create: `lib/benchmarks/mle_patch_proof.py`
- Modify: `lib/benchmarks/__init__.py`
- Modify: `lib/benchmarks/proof_publication.py`
- Modify: `lib/benchmarks/proof_archive.py`
- Test: `tests/unit/test_official_mle_patch_proof.py`
- Test: `tests/unit/test_benchmark_proof_archive.py`
- Test: `tests/unit/test_benchmark_proof_publication.py`

- [x] **Step 1: Write failing tests**

Create tests for `write_official_mle_patch_round_proof_bundle` using a synthetic persisted patch-round report. Assert it writes:

```text
manifest.json
artifacts/commands.txt
artifacts/config.json
artifacts/environment.json
artifacts/logs/combined.log
artifacts/reports/patch-round-report.json
artifacts/patches/patch.diff
artifacts/LIMITATIONS.md
archive/proof-archive.json
archive/artifact-index.json
archive/publication/proof-publication.json
```

Also assert:

```python
payload["status"] == "written"
payload["official_scores_claimed"] is False
payload["archive"]["bundle"]["status"] == "archivable"
assert "patch_diff" in {entry["role"] for entry in archive_index["artifacts"]}
```

Add proof archive/publication tests showing extra manifest artifacts such as `patch_diff` and `solver_snapshot` are path-confined and included in the archive index.

- [x] **Step 2: Verify RED**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest \
  tests/unit/test_official_mle_patch_proof.py \
  tests/unit/test_benchmark_proof_archive.py::test_proof_archive_bundle_indexes_extra_artifacts \
  tests/unit/test_benchmark_proof_publication.py::test_proof_publication_bundle_blocks_extra_artifacts_outside_root \
  -q
```

Expected: fail because the new helper and extra-artifact indexing do not exist.

- [x] **Step 3: Implement proof helper and extra-artifact indexing**

Implement `write_official_mle_patch_round_proof_bundle(patch_round_report: Path, output_dir: Path) -> dict[str, Any]`.

The helper must:
- read the persisted patch-round report;
- copy the patch-round report, underlying round report, patch diff, solve log, grade log, `solve.py`, and `submission.csv` when present;
- write `commands.txt`, `config.json`, `environment.json`, `logs/combined.log`, and `LIMITATIONS.md`;
- write `manifest.json` with required artifact roles plus extra roles `patch_diff`, `round_report`, `solve_log`, `grade_log`, `solver_snapshot`, and `submission_snapshot`;
- call `build_proof_archive_bundle` and `write_proof_archive_bundle`;
- keep `official_scores_claimed=false`.

Update `proof_publication.py` and `proof_archive.py` so extra artifact roles under `artifact_manifest["artifacts"]` are validated for path confinement and included in the archive index without becoming required artifacts.

- [x] **Step 4: Verify GREEN**

Run the same targeted pytest command. Expected: pass.

### Task 3: CLI, MCP, Demo, and Release Gate

**Files:**
- Modify: `scripts/cli.py`
- Modify: `lib/mcp_service.py`
- Modify: `scripts/mle_bench_official_bridge_demo.py`
- Modify: `scripts/release_check.py`
- Modify: `docs/release-checklist.md`
- Modify: `docs/benchmark-adapter-roadmap-cn.md`
- Modify: `skills/ml-research-loop-planner/SKILL.md`
- Modify: `skills/ml-research-loop-operator/SKILL.md`
- Test: `tests/unit/test_cli.py`
- Test: `tests/unit/test_mcp_service.py`
- Test: `tests/integration/test_official_mle_bridge_cli.py`
- Test: `tests/unit/test_release_check.py`
- Test: `tests/unit/test_skill_packages.py`

- [x] **Step 1: Write failing tests**

Add CLI coverage for:

```bash
ml-loop benchmark mle-patch-proof \
  --patch-round-report <rounds/round-002/patch-round-report.json> \
  --output-dir <proof-dir> \
  --json
```

Add MCP coverage for `write_official_mle_bench_patch_round_proof_bundle` with required args `patch_round_report` and `output_dir`.

Extend the official bridge demo assertions so its JSON includes `patch_proof.status == "written"` and an archive bundle status of `archivable`.

- [x] **Step 2: Verify RED**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest \
  tests/unit/test_cli.py::test_parser_has_run_status_result_subcommands \
  tests/unit/test_cli.py::test_benchmark_mle_patch_proof_command_writes_bundle \
  tests/unit/test_mcp_service.py::test_tools_list_exposes_research_loop_tools \
  tests/unit/test_mcp_service.py::test_benchmark_mcp_writes_mle_patch_proof_bundle \
  tests/integration/test_official_mle_bridge_cli.py \
  -q
```

Expected: fail because the CLI and MCP tool are not wired.

- [x] **Step 3: Implement surfaces and docs**

Wire:
- `ml-loop benchmark mle-patch-proof`;
- MCP tool `write_official_mle_bench_patch_round_proof_bundle`;
- `mle_bench_official_bridge_demo.py` proof output;
- release docs and skill guidance that recommend `mle-patch-round -> mle-patch-proof -> archive/publication review`.

- [x] **Step 4: Run full validation**

Run:

```bash
.venv/bin/ruff check lib/ scripts/ ml_intern/ codex_plugin/ tests/
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest tests/ -q
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=/opt/homebrew/Caskroom/miniforge/base/bin/python3 /opt/homebrew/Caskroom/miniforge/base/bin/python3 scripts/release_check.py --python /opt/homebrew/Caskroom/miniforge/base/bin/python3 --json
```

Expected: ruff passes, pytest passes, release_check returns `status=passed`.

---

## Self-Review

- Spec coverage: P1 closes the patch-round audit gap by persisting patch artifacts and packaging them through existing proof publication/archive guards.
- Placeholder scan: No TBD/TODO placeholders remain outside the self-review wording.
- Type consistency: Public names are `write_official_mle_patch_round_proof_bundle`, `write_official_mle_bench_patch_round_proof_bundle`, and `ml-loop benchmark mle-patch-proof`.
