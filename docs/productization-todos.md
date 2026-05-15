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

- [x] Add execution resource limits and run metadata.
  - Acceptance: every execution payload reports wall time, timeout policy, Python executable, sandbox roots, and artifact retention paths.
  - Files: `lib/mcp_service.py`, `docs/mcp-client-setup.md`, `docs/release-checklist.md`, `tests/unit/test_mcp_service.py`.
- [x] Add compatibility and migration checks.
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

## P7: MCP + Skills Product Layer

- [x] Add Codex/Claude skills for the main research loop.
  - Acceptance: `ml-research-loop-planner` tells client agents to call `get_service_manifest` first, then select research, experiment, reproduction, or artifact workflows.
  - Acceptance: the skill documents planner/executor boundaries, evidence gates, patch safety, stop conditions, and when human confirmation is required.
  - Files: `skills/`, `docs/mcp-client-setup.md`, `docs/project-overview-cn.md`, `tests/unit/test_mcp_delivery_docs.py`.
- [x] Add focused reproduction and experiment optimization skills.
  - Acceptance: `ml-research-loop-reproduction` covers paper evidence, reproduction specs, rubric readiness, and grade reports.
  - Acceptance: `ml-research-loop-experiment-optimizer` covers review interpretation, experiment tree state, patch proposal, rollback, and loop decision.
  - Files: `skills/`, `docs/development-roadmap-cn.md`, `tests/unit/test_mcp_delivery_docs.py`.
- [x] Add operator skill and installation docs.
  - Acceptance: `ml-research-loop-operator` covers MCP registration, `mcp_client_acceptance.py`, `scripts/release_check.py --json`, artifact lifecycle, and troubleshooting.
  - Files: `skills/`, `README.md`, `docs/mcp-client-setup.md`, `docs/release-checklist.md`.

## P8: Real Research Retrieval Quality

- [x] Improve provider cache, evidence scoring, and citation trace.
  - Acceptance: research outputs distinguish cache hits, provider failures, weak evidence, and strong paper/dataset/code evidence.
  - Files: `lib/fusion_service.py`, `lib/research_components.py`, `tests/unit/test_mcp_fusion_tools.py`, `scripts/mcp_provider_quality_benchmark.py`.
- [x] Add stable retrieval benchmark queries.
  - Acceptance: paper-heavy, dataset-heavy, and code-heavy benchmark cases produce comparable quality reports across runs.
  - Files: `examples/`, `scripts/mcp_provider_quality_benchmark.py`, `tests/integration/test_mcp_provider_quality_benchmark.py`.

## P9: Automatic Experiment Intelligence

- [x] Strengthen experiment tree policy and loop decisions.
  - Acceptance: failed, improved, and reproduction-blocked nodes produce different next actions and stop reasons.
  - Files: `lib/experiment_tree.py`, `lib/fusion_service.py`, `tests/unit/test_experiment_tree.py`, `tests/unit/test_mcp_fusion_tools.py`.
- [x] Strengthen real code patch execution loop.
  - Acceptance: multi-file bounded diffs report syntax/test preflight, rollback, post-run review, and metric-aware decisions.
  - Files: `lib/mcp_service.py`, `scripts/mcp_real_task_code_benchmark.py`, `tests/unit/test_mcp_service.py`, `tests/integration/test_mcp_real_task_code_benchmark.py`.

## P10: Release And Distribution

- [x] Add formal beta/stable release process.
  - Acceptance: release notes, contract migration notes, client compatibility matrix, and CI release gate are documented.
  - Files: `docs/release-checklist.md`, `docs/mcp-client-setup.md`, `README.md`.
- [x] Improve install and onboarding path.
  - Acceptance: a fresh checkout can install, register MCP, run client acceptance, and complete one bounded demo from the docs.
  - Files: `pyproject.toml`, `scripts/cli.py`, `docs/mcp-client-setup.md`, `examples/mcp/`.

## P11: Skill Contract And Installation Binding

- [x] Expose skill contracts through the MCP manifest.
  - Acceptance: `get_service_manifest` returns `skill_package`, `recommended_skills`, and `skill_contracts` pinned to the current `contract_version`.
  - Files: `lib/mcp_service.py`, `tests/unit/test_mcp_service.py`.
- [x] Add CLI-assisted skill installation.
  - Acceptance: `ml-loop init-skills --client codex|claude` installs the repository skill package, supports `--target-root`, refuses overwrites by default, and supports `--dry-run`.
  - Files: `scripts/cli.py`, `tests/unit/test_cli.py`.
- [x] Document MCP/Skills binding and install verification.
  - Acceptance: setup docs, release notes, examples, and release checklist mention `ml-loop init-skills`, `recommended_skills`, and `skill_contracts`.
  - Files: `docs/skills-setup-cn.md`, `docs/mcp-client-setup.md`, `docs/release-notes.md`, `docs/release-checklist.md`, `examples/mcp/README.md`.

## P12: Open Source Readiness

- [x] Add open-source governance files.
  - Acceptance: root-level `LICENSE`, `NOTICE`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, and `CITATION.cff` are present and linked from README.
  - Files: `LICENSE`, `NOTICE`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CITATION.cff`, `README.md`.
- [x] Add GitHub issue, PR, and CI templates.
  - Acceptance: CI runs ruff, pytest, and MCP client acceptance on Python 3.10 and 3.13; issue and PR templates capture reproduction and validation data.
  - Files: `.github/`.
- [x] Clean public release artifacts.
  - Acceptance: public docs, examples, and task configs do not contain machine-specific home-directory paths or token-shaped placeholders.
  - Files: `README.md`, `docs/`, `examples/`, `tasks/`.
- [x] Include product assets in source and wheel distribution metadata.
  - Acceptance: `pyproject.toml` includes `skills/`, `docs/`, `examples/`, `LICENSE`, `NOTICE`, and `CITATION.cff` in distribution configuration.
  - Files: `pyproject.toml`.

## P13: Benchmark Adapter Productization

- [x] Integrate MLE-bench and PaperBench compatibility spikes.
  - Acceptance: both adapter families live under `lib/benchmarks/`, both demo scripts run locally, and both reports preserve explicit non-official benchmark flags.
  - Files: `lib/benchmarks/`, `scripts/mle_bench_adapter_demo.py`, `scripts/paperbench_adapter_demo.py`, `tests/unit/test_mle_bench_adapter.py`, `tests/unit/test_paperbench_adapter.py`, `tests/integration/test_mle_bench_adapter_demo.py`, `tests/integration/test_paperbench_adapter_demo.py`.
- [x] Add a combined benchmark compatibility smoke.
  - Acceptance: one command runs both adapter demos and prints a compact status report with artifact paths.
  - Files: `scripts/benchmark_adapter_smoke.py`, `tests/integration/test_benchmark_adapter_smoke.py`, `docs/benchmark-adapter-roadmap-cn.md`.
- [x] Surface benchmark readiness through CLI or manifest output.
  - Acceptance: Codex/Claude can ask the product what benchmark adapter flows are available before running them.
  - Files: `lib/benchmarks/readiness.py`, `scripts/cli.py`, `lib/mcp_service.py`, `tests/unit/test_benchmark_readiness.py`, `tests/unit/test_cli.py`, `tests/unit/test_mcp_service.py`.

## P14: Official Harness Feasibility

- [x] Add read-only official harness probes for MLE-bench and PaperBench.
  - Acceptance: probes report whether required repos, data, credentials, Docker/environment support, and commands are available without launching long-running evaluations.
  - Files: `lib/benchmarks/harness_probe.py`, `scripts/benchmark_harness_probe.py`, `scripts/cli.py`, `lib/mcp_service.py`, `tests/unit/test_benchmark_harness_probe.py`, `tests/integration/test_benchmark_harness_probe.py`.
- [x] Document required credentials, data, runtime, and cost.
  - Acceptance: docs separate local compatibility demos from official harness requirements.
  - Files: `docs/benchmark-adapter-roadmap-cn.md`, `docs/release-checklist.md`, `examples/README.md`.

## P15: Public Proof Run

- [x] Add a read-only public proof-run plan.
  - Acceptance: Codex/Claude can ask whether an official debug/small benchmark path is blocked or ready, see missing prerequisites, safe next commands, blocked commands, artifact requirements, and `official_scores_claimed=false`.
  - Files: `lib/benchmarks/proof_plan.py`, `scripts/benchmark_proof_plan.py`, `scripts/cli.py`, `lib/mcp_service.py`, `tests/unit/test_benchmark_proof_plan.py`, `tests/integration/test_benchmark_proof_plan.py`.
- [x] Add a read-only official proof-run setup bundle.
  - Acceptance: Codex/Claude can write a setup bundle containing official references, redacted env example, manual setup commands, and artifact requirements without installing dependencies, downloading data, writing secrets, or claiming official scores.
  - Files: `lib/benchmarks/proof_setup.py`, `scripts/benchmark_proof_setup.py`, `scripts/cli.py`, `lib/mcp_service.py`, `tests/unit/test_benchmark_proof_setup.py`, `tests/integration/test_benchmark_proof_setup.py`.
- [x] Add a guarded proof publication bundle.
  - Acceptance: Codex/Claude can validate future proof-run artifacts, write a publication bundle, and block official score claims unless explicit score evidence is present.
  - Files: `lib/benchmarks/proof_publication.py`, `scripts/benchmark_proof_publication.py`, `scripts/cli.py`, `lib/mcp_service.py`, `tests/unit/test_benchmark_proof_publication.py`, `tests/integration/test_benchmark_proof_publication.py`.
- [x] Add a hashed proof-run archive intake.
  - Acceptance: Codex/Claude can import complete external proof-run artifacts into a copied archive, review SHA-256 hashes, and reuse the publication guard before reporting.
  - Files: `lib/benchmarks/proof_archive.py`, `scripts/benchmark_proof_archive.py`, `scripts/cli.py`, `lib/mcp_service.py`, `tests/unit/test_benchmark_proof_archive.py`, `tests/integration/test_benchmark_proof_archive.py`.
- [x] Expose benchmark proof lifecycle as MCP tools.
  - Acceptance: Codex/Claude can call probe, proof plan, setup bundle, publication bundle, and proof archive directly through MCP.
  - Files: `lib/mcp_service.py`, `tests/unit/test_mcp_service.py`, `tests/integration/test_mcp_server_stdio.py`, `skills/ml-research-loop-operator/SKILL.md`, `skills/ml-research-loop-planner/SKILL.md`.
- [ ] Run one official or official-debug benchmark path.
  - Acceptance: artifacts include command lines, configs, logs, reports, and known limitations.
  - Files: `docs/`, `.demo_runs/` or archived release artifacts.
- [ ] Publish artifacts and limitations without overstating scores.
  - Acceptance: public docs distinguish official benchmark results from deterministic local fixtures.
  - Files: `README.md`, `docs/open-source-positioning-cn.md`, `docs/benchmark-adapter-roadmap-cn.md`.

## P16: Research Memory Layer

- [x] Add canonical local memory schema and dependency-free baseline.
  - Acceptance: `ResearchMemoryCard`, `MemoryEvidenceRef`, `MemoryArtifactRef`, `MemorySuggestion`, and `MemoryTrace` are represented in code and documented in `docs/product/target-architecture-cn.md`.
  - Acceptance: existing fastText P3/P4/P5 proof artifacts can be extracted into local JSONL or SQLite memory records without Graphiti/cognee installed.
  - Files: `lib/research_memory.py`, `tests/unit/test_research_memory.py`, `docs/product/research-memory-layer-cn.md`, `docs/product/target-architecture-cn.md`.
- [x] Add Graphiti and cognee optional adapter interfaces（可选 adapter interface spike）.
  - Acceptance: adapter status can report disabled/enabled state and skip safely when Graphiti/cognee dependencies are unavailable.
  - Acceptance: fresh checkout and release gate still pass without optional adapter dependencies.
  - Files: `lib/memory_adapters/`, `tests/unit/test_memory_adapters.py`, `docs/product/research-memory-layer-cn.md`.
- [x] Implement real Graphiti and cognee indexing/retrieval adapter paths.
  - Acceptance: Graphiti adapter can represent paper -> claim -> dataset -> model -> config -> metric -> patch -> failure/rollback -> artifact relations and call `add_episode` / `search` when configured.
  - Acceptance: cognee adapter can call `add` / `cognify` / `search` and return project-owned memory card views when configured.
  - Acceptance: CLI/MCP only access adapters through explicit opt-in flags/arguments.
  - Files: `lib/memory_adapters/`, `scripts/cli.py`, `lib/mcp_service.py`, `tests/unit/test_memory_adapters.py`, `tests/unit/test_cli.py`, `tests/unit/test_mcp_service.py`, `docs/product/research-memory-layer-cn.md`.
- [ ] Run live Graphiti/cognee integration smoke in a configured external environment.
  - Acceptance: Graphiti smoke runs against Neo4j/Graphiti with env vars set and retrieves at least one relation-backed memory result.
  - Acceptance: cognee smoke runs with configured LLM/vector/graph backend and retrieves at least one CHUNKS result from indexed proof artifacts.
  - Files: `tests/integration/`, `docs/release-checklist.md`.
- [x] Expose memory tools through MCP and CLI.
  - Acceptance: `record_research_memory`, `retrieve_research_memory`, `suggest_from_memory`, `promote_memory_card`, and `audit_memory_trace` return provenance-backed payloads and never execute patches or experiments directly.
  - Acceptance: tool contracts appear in `get_service_manifest` only when implemented and covered by tests.
  - Files: `lib/mcp_service.py`, `scripts/cli.py`, `tests/unit/test_mcp_service.py`, `tests/unit/test_cli.py`.
- [x] Bind memory workflows into Skills and planner docs.
  - Acceptance: planner, reproduction, and experiment optimizer skills retrieve memory before proposing new work and record memory after reviewed runs when tools are available.
  - Acceptance: docs state that memory suggestions are advisory and must still go through MCP guardrails, proof archive, and release gate.
  - Files: `skills/`, `docs/client-planner-template.md`, `docs/skills-setup-cn.md`, `tests/unit/test_skill_packages.py`, `tests/unit/test_planner_docs.py`.
- [x] Add memory-guided proposal handoff proof.
  - Acceptance: a dependency-free script retrieves local memory first, writes a client-reviewed proposal payload, preserves memory provenance, and keeps `executes_tool=false`.
  - Files: `scripts/memory_guided_proposal.py`, `tests/unit/test_memory_guided_proposal.py`, `docs/release-checklist.md`, `docs/product/research-memory-layer-cn.md`.
- [ ] Add privacy, export/import, cleanup, and release checks.
  - Acceptance: private papers, private data, and sensitive logs require explicit opt-in and redaction before memory ingestion.
  - Acceptance: release check covers dependency-free local memory; Graphiti/cognee checks are optional integration checks. This release-check portion is implemented; private export/import redaction guardrails are implemented; cleanup/retention policy remains pending.
  - Files: `lib/research_memory.py`, `scripts/release_check.py`, `docs/release-checklist.md`, `SECURITY.md`.
