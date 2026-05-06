# Release Checklist

Use this checklist before calling a branch deliverable or merging it into `main`.

## Preconditions

- Worktree is clean except for the release changes under review.
- Python can import this project with `PYTHONPATH=.:.venv/lib/python3.13/site-packages`.
- `ML_RESEARCH_LOOP_PYTHON` points at a working Python executable.
- Execution runtime roots outside the project checkout are listed in `ML_RESEARCH_LOOP_ALLOWED_ROOTS`.
- `GITHUB_TOKEN` is optional and only needed for GitHub code search.

## One-Command Check

Run the make-independent verifier:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/release_check.py
```

This command runs:

```bash
ruff check lib/ scripts/ ml_intern/ codex_plugin/ tests/
python3 -m pytest tests/ -q
python3 scripts/mcp_server.py
python3 scripts/mcp_client_acceptance.py --python "$(which python3)"
python3 scripts/mcp_golden_path.py --max-experiments 1 --experiment-duration 30
python3 scripts/mcp_multi_round_demo.py --rounds 2 --max-experiments 1 --experiment-duration 30
python3 scripts/mcp_auto_next_demo.py --max-experiments 1 --experiment-duration 30
python3 scripts/mcp_client_patch_demo.py --max-experiments 1 --experiment-duration 30
python3 scripts/mcp_provider_quality_benchmark.py
python3 scripts/mcp_real_task_code_benchmark.py --max-experiments 1 --experiment-duration 30
python3 scripts/benchmark_adapter_smoke.py --json
python3 scripts/mcp_real_data_demo.py --max-experiments 1 --experiment-duration 30
python3 scripts/mcp_reproduction_demo.py --max-experiments 1 --experiment-duration 30 --json
```

The final JSON summary must report `status: passed`.

## CI Gate

`.github/workflows/ci.yml` runs the fast PR gate on GitHub Actions:

- `ruff check lib/ scripts/ ml_intern/ codex_plugin/ tests/`
- `python -m pytest tests/ -q`
- `python scripts/mcp_client_acceptance.py --python "$(which python)"`

Run the full local release check before product-facing delivery because the CI gate
does not execute the longer golden-path, multi-round, provider-quality, or
real-data/code demos.

## Release Documentation Gate

- Confirm `docs/release-notes.md` documents the current `contract_version`,
  migration notes, known limitations, beta release gate, and stable release gate.
- Confirm `docs/client-compatibility-matrix.md` lists Codex, Claude Code, and
  Claude Desktop with config helpers and acceptance commands.
- Confirm `examples/mcp/README.md` documents fresh checkout install,
  `ml-loop init-mcp-config`, `scripts/mcp_client_acceptance.py`, and
  `scripts/mcp_golden_path.py`.
- Confirm `README.md` links to all three release/distribution documents.

## Open Source Release Gate

- Confirm `LICENSE`, `NOTICE`, `CONTRIBUTING.md`, `SECURITY.md`,
  `CODE_OF_CONDUCT.md`, and `CITATION.cff` are present.
- Confirm `.github/workflows/ci.yml` runs ruff, pytest, and MCP client acceptance
  on Python 3.10 and 3.13.
- Confirm `.github/ISSUE_TEMPLATE/bug_report.yml`,
  `.github/ISSUE_TEMPLATE/feature_request.yml`, and
  `.github/PULL_REQUEST_TEMPLATE.md` are present.
- Confirm public docs, examples, and task configs do not contain machine-local
  paths or token-shaped placeholders.
- Confirm `pyproject.toml` includes `skills/`, `docs/`, `examples/`, `LICENSE`,
  `NOTICE`, and `CITATION.cff` in distribution metadata.
- Before tagging a public release, validate from a clean checkout.
- For preview release tags, run:

```bash
python3 scripts/fresh_checkout_check.py \
  --repo-url https://github.com/MagicianDu/ml-research-loop.git \
  --ref main
```

- After tagging, rerun the same command with `--ref v0.1.0-preview`.

## Skill Package Check

- Confirm `skills/ml-research-loop-planner/SKILL.md`,
  `skills/ml-research-loop-reproduction/SKILL.md`,
  `skills/ml-research-loop-experiment-optimizer/SKILL.md`, and
  `skills/ml-research-loop-operator/SKILL.md` exist.
- Confirm `docs/skills-setup-cn.md` documents Codex and Claude installation.
- Confirm `get_service_manifest` returns `recommended_skills`, `skill_contracts`,
  and `skill_package.install_command == ml-loop init-skills`.
- Confirm `ml-loop init-skills --client codex --dry-run` and
  `ml-loop init-skills --client claude --dry-run` report the expected target root.
- Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_skill_packages.py -q
```

## Manual Spot Checks

- Confirm `get_service_manifest` returns:
  - `contract_version == 2026-04-30.preview.v1`
  - `schema_versions.service_manifest == 2026-04-30.preview.v1`
  - `tool_contracts` entries for every `required_tools` item
  - `compatibility.status == preview`
  - `execution_sandbox.status == enforced`
  - `planning_signals` includes `execution_metadata`
  - `execution_metadata_contract.required_fields` contains `wall_time_seconds`
  - `recommended_skills` lists the four repository skills
  - `skill_contracts` entries pin `contract_version == 2026-04-30.preview.v1`
  - `skill_package.install_command == ml-loop init-skills`
  - `benchmark_adapters.status == compatibility_ready`
  - `benchmark_adapters.official_scores_claimed == false`
  - `benchmark_adapters.adapters[*].official == false`
  - `upstream_patterns.aide.direct_dependency == false`
  - `upstream_patterns.paperbench.direct_dependency == false`
  - `upstream_patterns.*.integration_mode == architecture_pattern`
- Confirm MCP tools include:
  - `get_service_manifest`
  - `read_paper`
  - `research_task`
  - `propose_hypotheses`
  - `run_hypothesis_experiment`
  - `run_ai_autoresearch`
  - `review_research_results`
  - `run_client_patch_experiment`
  - `apply_client_code_patch`
  - `run_next_experiment_from_review`
  - `get_experiment_logs`
- Confirm `scripts/mcp_client_acceptance.py` reports:
  - `compatibility_check.status == compatible`
  - `compatibility_check.migration_required == false`
  - `compatibility_check.migration_hints == []`
- Confirm the golden-path result contains:
  - `research_context.sources`
  - `review.research_review.next_task_patch.budget`
  - `review.experiment_state.planner_handoff`
  - `review.experiment_state.current_code.search_region`
  - `review.experiment_state.research_evidence_gate`
  - `review.experiment_state.dataset_profile`
  - `review.experiment_state.experiment_tree`
  - `review.experiment_state.failure_diagnostics`
  - `review.experiment_state.metric_stop_policy`
  - `review.experiment_state.reproduction.readiness`
  - `review.experiment_state.code_change_plan`
  - `review.experiment_state.code_change_plan.next_experiment_plan`
  - `review.experiment_state.code_change_plan.next_experiment_plan.proposed_task_patch`
  - `review.experiment_state.code_change_plan.next_experiment_plan.dry_run_validation`
  - `review.experiment_state.code_change_plan.next_experiment_plan.diff_preview`
  - `review.experiment_state.code_change_plan.next_experiment_plan.execution_guardrails`
  - `review.experiment_state.planner_actions`
  - `research_context.retrieval_diagnostics`
  - `hypotheses`
  - `experiments[*].hypothesis_id`
  - `review.research_review.experiment_strategy`
  - `review.research_review.recommended_search_space`
  - `review.research_review.next_task_patch`
- Confirm `research_task` query fanout behavior contains:
  - `query_plan[*].query`
  - `cache.<source>.cache_scope`
  - `cache.<source>.freshness_seconds`
  - `sources[*].metadata.source_id`
  - `sources[*].metadata.query_variant`
  - `sources[*].metadata.query_reason`
  - `sources[*].metadata.evidence_quality.source_class`
  - `evidence_quality.source_class_counts`
  - `evidence_citations[*].source_trace[*].source_id`
  - `evidence_citations[*].source_trace[*].snippet_ids`
  - `source_rankings[*].provider`
  - `source_rankings[*].evidence_quality_score`
  - `provider_coverage.providers.<provider>.source_count`
  - `provider_coverage.unknown_provider_source_count`
  - `retrieval_diagnostics.summary.provider_count`
  - `deduplication_report.input_source_count`
  - `deduplication_report.duplicate_source_count`
  - `cache_summary.backend_count`
  - `provider_quality_matrix.providers`
  - `cache.<source>.variants` when cached multi-query retrieval is used
- Confirm partial research contexts contain:
  - `retrieval_diagnostics.backends.<source>.status`
  - `retrieval_diagnostics.backends.<source>.attempted_queries`
  - `retrieval_diagnostics.backends.<source>.attempted_queries[*].error.category == rate_limited` when a provider returns HTTP 429
  - `retrieval_diagnostics.recommended_recovery`
- Confirm the multi-round result contains:
  - `round_count == 2`
  - `rounds[1].input_task_patch == rounds[0].review.experiment_state.next_round.task_patch`
  - `rounds[1].patched_task.hyperparameter_space`
- Confirm execution-class tool payloads include:
  - `execution_metadata.wall_time_seconds`
  - `execution_metadata.timeout_policy`
  - `execution_metadata.python_executable`
  - `execution_metadata.sandbox_roots`
  - `execution_metadata.artifact_retention`
- Confirm `run_next_experiment_from_review` can consume a completed review and
  execute `next_experiment_plan.proposed_task_patch` without manually copying
  `task_patch`.
- Confirm `run_next_experiment_from_review` can return `final_review` and
  `loop_decision.reason_category` when `include_final_review=true`.
- Confirm `run_client_patch_experiment` rejects stale `change_proposal.current_value`
  and returns `patch_execution.mode == task_patch_only` for valid proposals.
- Confirm `apply_client_code_patch` rejects path escapes, preflights hunks,
  returns `patch_execution.mode == workspace_unified_diff`, syntax-checks
  changed Python files, rolls back on syntax failure, and can return
  `post_patch_review` plus metric-aware `loop_decision`.
- Confirm `scripts/mcp_client_patch_demo.py` reports
  `client_patch.patch_execution.mode == task_patch_only`,
  completed `initial_review` / `final_review`, and a `loop_decision`.
- Confirm `scripts/mcp_provider_quality_benchmark.py` reports paper-heavy,
  dataset-heavy, and code-heavy provider counts, cache hits, rate-limit
  diagnostics, deduplication reports, cache summaries, provider quality
  matrices, evidence citations, source rankings, and recovery hints.
- Confirm `scripts/mcp_real_task_code_benchmark.py` reports a real local data
  source, bounded runtime, `code_change_plan.next_experiment_plan` patch
  planning, `experiment_tree` best-node state, successful multi-file
  `apply_client_code_patch`, post-patch review, and `benchmark_summary`
  with failure diagnostics and metric stop policy.
- Confirm `scripts/benchmark_adapter_smoke.py` reports `status == passed`,
  MLE-bench-shaped `official_mle_bench == false`, PaperBench-shaped
  `official_paperbench == false`, and benchmark report artifact paths.
- Confirm `scripts/mcp_reproduction_demo.py` reports
  `reproduction.readiness.status == ready`, a `grade_report.score`, and
  `grade_report.num_leaf_nodes == 2` without Docker, GPU, network, or LLM
  credentials.
- Confirm reproduction `required_files` are workspace-relative and unsafe
  absolute or parent-traversal paths return `invalid_required_files`.
- Confirm `scripts/mcp_auto_next_demo.py` reports
  `auto_next.selected_patch_source == proposed_task_patch` and a completed
  final review.
- Confirm the real-data result contains:
  - `data_source == real_file`
  - `review.experiments[0].metrics.val_bpb`
  - `review.experiment_state.dataset_profile.exists == true`
- Confirm `docs/mcp-client-setup.md` and `examples/mcp/` have placeholder paths,
  not machine-local absolute paths.
- Confirm `ml-loop init-mcp-config --client codex` prints a concrete Codex
  config for the current checkout.
- Confirm `ml-loop init-mcp-config --client claude-code --output /tmp/ml-research-loop.mcp.json`
  writes parseable JSON.
- Confirm `ml-loop check --json` runs the product readiness gate.
- Confirm `ml-loop benchmark readiness --json` reports the available
  benchmark adapter flows.
- Confirm `ml-loop benchmark smoke --runtime-root /tmp/mlrl-benchmark --json`
  runs both compatibility demos.
- Confirm `ml-loop artifacts list|archive|clean` can manage a throwaway runtime
  root and that `clean` requires explicit confirmation.

## Known Local Caveat

On this machine, `/usr/bin/make` currently exits with Xcode license error 69 before
executing Makefile targets. Use `python3 scripts/release_check.py` as the release
gate until the macOS Xcode license is accepted outside this project.
