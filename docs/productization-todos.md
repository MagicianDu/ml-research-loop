# Productization TODOs

This file tracks the gap from preview MCP service to product-grade release.

## P0: Product Safety And Real-Task Readiness

- [x] Enforce execution path sandboxing for MCP tools that run code.
  - Acceptance: `run_fresh_demo`, `run_autoresearch`, `run_ai_autoresearch`, `run_hypothesis_experiment`, and `run_next_experiment_from_review` reject `runtime_root`, `workspace`, or `task_config` paths outside configured allowed roots.
  - Acceptance: `get_service_manifest` reports the sandbox policy and required environment variables.
  - Acceptance: full `scripts/release_check.py --json` still passes with default project-local demo roots.
- [x] Add subprocess lifecycle hardening.
  - Acceptance: child experiment processes are killed on timeout, and process cleanup is covered by tests.
  - Acceptance: user-facing errors distinguish startup failure, timeout, non-zero exit, and missing metric.
  - Files: `scripts/autoresearch_run.py`, `lib/mcp_service.py`, `tests/unit/test_autoresearch_run.py`, `tests/unit/test_mcp_service.py`.
  - Order: first harden `run_training`, then wrap MCP subprocess execution with typed tool errors.
- [x] Add a real-task acceptance fixture.
  - Acceptance: one small external-style task config and dataset run through MCP without synthetic fallback.
  - Acceptance: review output includes dataset profile, code-change plan, logs path, and next experiment patch.
  - Files: `scripts/mcp_real_data_demo.py`, `tests/integration/test_mcp_real_data_demo.py`, `examples/tasks/`.
  - Order: promote the current real-data demo into a reusable fixture, then assert planner handoff fields.

## P1: Research Quality And Automatic Patch Loop

- [x] Improve real provider retrieval quality.
  - Acceptance: provider-specific retries/backoff, stronger dedupe, and provider coverage thresholds are visible in `research_task`.
  - Files: `ml_intern/research_tools.py`, `lib/fusion_service.py`, `tests/unit/test_research_tools.py`, `tests/unit/test_mcp_fusion_tools.py`.
- [x] Add evidence citation quality scoring.
  - Acceptance: sources without summary/url/provider are downgraded; paper evidence snippets are tied to findings.
  - Files: `lib/fusion_service.py`, `tests/unit/test_mcp_fusion_tools.py`.
- [x] Add code patch planning and execution guardrails.
  - Acceptance: generated patch plans include diff preview, preflight validation, apply step, rollback path, and post-run review.
  - Files: `lib/research_components.py`, `lib/fusion_service.py`, `lib/mcp_service.py`, `tests/unit/test_research_components.py`, `tests/unit/test_mcp_fusion_tools.py`.
- [x] Improve auto-next loop intelligence.
  - Acceptance: `run_next_experiment_from_review` can optionally run final review and return stop/continue decision in one call.
  - Files: `lib/mcp_service.py`, `scripts/mcp_auto_next_demo.py`, `tests/unit/test_mcp_service.py`, `tests/integration/test_mcp_multi_round_demo.py`.

## P2: Packaging, Onboarding, And Product Polish

- [x] Add install/check commands for Codex and Claude users.
  - Acceptance: one command validates Python, dependencies, MCP stdio, manifest contract, and demo readiness.
  - Files: `scripts/cli.py`, `pyproject.toml`, `scripts/mcp_client_acceptance.py`, `docs/mcp-client-setup.md`.
- [x] Add product examples.
  - Acceptance: examples include synthetic, local real-data, paper-guided, and failed-run debugging flows.
  - Files: `examples/`, `docs/mcp-client-setup.md`, `README.md`.
- [x] Add artifact lifecycle management.
  - Acceptance: users can list, archive, and clean demo/runtime artifacts safely.
  - Files: `lib/mcp_service.py`, `scripts/cli.py`, `tests/unit/test_mcp_service.py`, `tests/unit/test_cli.py`.
- [x] Add product-facing docs.
  - Acceptance: docs include limitations, security model, supported clients, troubleshooting, and version compatibility.
  - Files: `README.md`, `docs/mcp-client-setup.md`, `docs/release-checklist.md`.

## P3: Client-Planner Optimization Loop

- [x] Add guarded client-generated patch execution.
  - Acceptance: Codex/Claude can pass a single-parameter `change_proposal` to MCP, which validates the current `train.py` SEARCH REGION and rejects stale or out-of-region proposals before execution.
  - Acceptance: the tool executes through `task_patch_only`, returns `patch_execution`, `run`, optional `initial_review`, `final_review`, and `loop_decision`, and does not directly mutate `train.py`.
  - Files: `lib/mcp_service.py`, `tests/unit/test_mcp_service.py`, `docs/mcp-client-setup.md`, `docs/client-planner-template.md`, `examples/README.md`.
- [x] Add real code patch execution beyond SEARCH REGION hyperparameter narrowing.
  - Acceptance: client-generated code edits are applied in an isolated workspace with syntax/test preflight, rollback, and post-run review.
  - Files: `lib/mcp_service.py`, `tests/unit/test_mcp_service.py`, `scripts/mcp_real_task_code_benchmark.py`, `tests/integration/test_mcp_real_task_code_benchmark.py`.
- [x] Add client patch demo script.
  - Acceptance: one repeatable stdio demo runs `review_research_results`, submits a client `change_proposal`, runs `run_client_patch_experiment`, and prints status, best metric, patch mode, and loop decision.
  - Files: `scripts/mcp_client_patch_demo.py`, `tests/integration/test_mcp_client_patch_demo.py`, `scripts/release_check.py`.

## P4: Real Provider And Real Task Benchmarking

- [x] Add live provider quality benchmark pack.
  - Acceptance: benchmark reports provider counts, cache hits, rate-limit diagnostics, evidence citations, and recovery hints for at least one paper-heavy and one dataset-heavy query.
  - Files: `scripts/mcp_provider_quality_benchmark.py`, `tests/integration/test_mcp_provider_quality_benchmark.py`, `docs/release-checklist.md`.
- [x] Add real task/code benchmark pack.
  - Acceptance: one non-synthetic repository-style task validates dataset profile, patch planning, bounded runtime, and post-run review on a real local dataset fixture.
  - Files: `examples/tasks/`, `scripts/mcp_real_task_code_benchmark.py`, `tests/integration/test_mcp_real_task_code_benchmark.py`.

## P5: Product Hardening

- [ ] Add execution resource limits and run metadata.
  - Acceptance: every execution payload reports wall time, timeout policy, Python executable, sandbox roots, and artifact retention paths.
  - Files: `lib/mcp_service.py`, `scripts/autoresearch_run.py`, `docs/mcp-client-setup.md`.
- [ ] Add compatibility and migration checks.
  - Acceptance: client acceptance fails clearly when `contract_version` or required tool contracts are incompatible.
  - Files: `scripts/mcp_client_acceptance.py`, `docs/release-checklist.md`, `tests/integration/test_mcp_client_acceptance.py`.

## P6: Experiment Tree And Reproduction Intelligence

- [x] Add lightweight AIDE-style experiment tree state.
  - Acceptance: `review_research_results` returns best-node tracking, draft/improve/debug stages, and a next-action recommendation derived from existing experiment history.
  - Files: `lib/experiment_tree.py`, `lib/fusion_service.py`, `tests/unit/test_experiment_tree.py`, `tests/unit/test_mcp_fusion_tools.py`.
- [x] Add lightweight PaperBench-style reproduction specs and rubric grade reports.
  - Acceptance: task configs may optionally include a local reproduction spec and rubric tree; grade reports aggregate weighted leaf scores without requiring Docker, GPU, network, or LLM credentials.
  - Files: `lib/reproduction_protocol.py`, `lib/task_protocol.py`, `tests/unit/test_reproduction_protocol.py`, `tests/unit/test_task_protocol.py`.
- [x] Surface tree and reproduction state through the existing MCP review path.
  - Acceptance: `get_service_manifest` reports AIDE/PaperBench as `architecture_pattern` integrations with `direct_dependency=false`; existing tool inputs remain backward compatible.
  - Files: `lib/mcp_service.py`, `lib/fusion_service.py`, `tests/unit/test_mcp_service.py`, `tests/unit/test_mcp_fusion_tools.py`.
- [x] Add a deterministic reproduction demo to the release gate.
  - Acceptance: the demo runs a bounded local task, reports reproduction readiness and a grade report, and is included in `scripts/release_check.py --json`.
  - Files: `scripts/mcp_reproduction_demo.py`, `tests/integration/test_mcp_reproduction_demo.py`, `scripts/release_check.py`, `docs/mcp-client-setup.md`.
