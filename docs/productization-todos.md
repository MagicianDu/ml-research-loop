# Productization TODOs

This file tracks the gap from preview MCP service to product-grade release.

## P0: Product Safety And Real-Task Readiness

- [x] Enforce execution path sandboxing for MCP tools that run code.
  - Acceptance: `run_fresh_demo`, `run_autoresearch`, `run_ai_autoresearch`, `run_hypothesis_experiment`, and `run_next_experiment_from_review` reject `runtime_root`, `workspace`, or `task_config` paths outside configured allowed roots.
  - Acceptance: `get_service_manifest` reports the sandbox policy and required environment variables.
  - Acceptance: full `scripts/release_check.py --json` still passes with default project-local demo roots.
- [ ] Add subprocess lifecycle hardening.
  - Acceptance: child experiment processes are killed on timeout, and process cleanup is covered by tests.
  - Acceptance: user-facing errors distinguish startup failure, timeout, non-zero exit, and missing metric.
- [ ] Add a real-task acceptance fixture.
  - Acceptance: one small external-style task config and dataset run through MCP without synthetic fallback.
  - Acceptance: review output includes dataset profile, code-change plan, logs path, and next experiment patch.

## P1: Research Quality And Automatic Patch Loop

- [ ] Improve real provider retrieval quality.
  - Acceptance: provider-specific retries/backoff, stronger dedupe, and provider coverage thresholds are visible in `research_task`.
- [ ] Add evidence citation quality scoring.
  - Acceptance: sources without summary/url/provider are downgraded; paper evidence snippets are tied to findings.
- [ ] Add code patch planning and execution guardrails.
  - Acceptance: generated patch plans include diff preview, preflight validation, apply step, rollback path, and post-run review.
- [ ] Improve auto-next loop intelligence.
  - Acceptance: `run_next_experiment_from_review` can optionally run final review and return stop/continue decision in one call.

## P2: Packaging, Onboarding, And Product Polish

- [ ] Add install/check commands for Codex and Claude users.
  - Acceptance: one command validates Python, dependencies, MCP stdio, manifest contract, and demo readiness.
- [ ] Add product examples.
  - Acceptance: examples include synthetic, local real-data, paper-guided, and failed-run debugging flows.
- [ ] Add artifact lifecycle management.
  - Acceptance: users can list, archive, and clean demo/runtime artifacts safely.
- [ ] Add product-facing docs.
  - Acceptance: docs include limitations, security model, supported clients, troubleshooting, and version compatibility.
