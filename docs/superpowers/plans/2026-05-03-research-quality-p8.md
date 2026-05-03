# Research Quality P8 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen real research retrieval quality by making cache provenance, evidence classes, citation trace, and provider benchmark coverage explicit.

**Architecture:** Keep MCP tool names and response compatibility stable. Add optional metadata fields to existing research payloads, expand deterministic fixture benchmarks, and protect the new behavior with focused tests before implementation.

**Tech Stack:** Python stdlib, pytest, existing MCP stdio service, deterministic fixture providers.

---

### Task 1: Cache And Citation Quality Signals

**Files:**
- Modify: `ml_intern/research_tools.py`
- Modify: `lib/fusion_service.py`
- Create: `tests/unit/test_research_quality_p8.py`

- [x] **Step 1: Write failing tests**

Add tests that require:

- `cached_search()` metadata to include `cache_schema_version`, `source_count`, `freshness_seconds`, and `cache_scope`.
- `research_task` source metadata to include `source_id` and `evidence_quality.source_class`.
- aggregate `evidence_quality.source_class_counts`.
- `evidence_citations[*].source_trace` to include `source_id`, provider, query variant, query reason, and snippet ids.

- [x] **Step 2: Verify tests fail**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_research_quality_p8.py -q
```

Expected: fail because these P8 fields are not present yet.

Observed: failed on missing `cache_schema_version`, `source_id`, `source_class`, and `code-heavy`.

- [x] **Step 3: Implement metadata additions**

Add metadata fields without removing existing fields. Preserve old cache keys and response shape.

### Task 2: Stable Provider Benchmark Pack

**Files:**
- Modify: `scripts/mcp_provider_quality_benchmark.py`
- Modify: `tests/integration/test_mcp_provider_quality_benchmark.py`

- [x] **Step 1: Write failing benchmark expectations**

Update the benchmark test to require `paper-heavy`, `dataset-heavy`, and `code-heavy` benchmark entries, each with cache hit, provider count, evidence citations, source rankings, and rate-limit recovery.

- [x] **Step 2: Implement code-heavy fixture**

Add a GitHub-code fixture provider and extend rate-limit simulation to `github_code`.

### Task 3: Docs, Verification, Commit

**Files:**
- Modify: `docs/mcp-client-setup.md`
- Modify: `docs/release-checklist.md`
- Modify: `docs/productization-todos.md`
- Modify: `docs/development-roadmap-cn.md`

- [x] **Step 1: Document P8 fields**

Document cache provenance, source classes, citation trace, and three benchmark query classes.

- [x] **Step 2: Run focused tests**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_research_quality_p8.py tests/integration/test_mcp_provider_quality_benchmark.py -q
```

Observed: `4 passed`; affected research/manifest suite later reported `81 passed`; doc/release docs suite reported `17 passed`.

- [x] **Step 3: Run full release gate**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON="$(which python3)" python3 scripts/release_check.py --json
```

Observed: `status: passed`; `pytest` reported `201 passed`.

- [x] **Step 4: Review and commit**

```bash
git diff --check
git diff --stat
git add ml_intern/research_tools.py lib/fusion_service.py scripts/mcp_provider_quality_benchmark.py tests/unit/test_research_quality_p8.py tests/integration/test_mcp_provider_quality_benchmark.py docs/mcp-client-setup.md docs/release-checklist.md docs/productization-todos.md docs/development-roadmap-cn.md docs/superpowers/plans/2026-05-03-research-quality-p8.md
git commit -m "Improve research evidence quality signals"
```
