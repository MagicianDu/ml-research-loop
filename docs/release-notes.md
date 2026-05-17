# Release Notes

## v0.1.0-preview

Release date: 2026-05-05.

Audience: early adopters who want to try the MCP + Skills preview locally with
Codex, Claude Code, or Claude Desktop.

Fresh checkout validation:

```bash
python3 scripts/fresh_checkout_check.py \
  --repo-url https://github.com/MagicianDu/ml-research-loop.git \
  --ref v0.1.0-preview
```

This validates clone, editable install, MCP client acceptance, Codex config
rendering, skills dry-run, and a bounded golden-path demo from a clean checkout.

## 0.1.0 Preview

Status: preview MCP product.

Public contract:

- `contract_version`: `2026-04-30.preview.v1`
- `schema_versions.service_manifest`: `2026-04-30.preview.v1`
- Supported clients: Codex, Claude Code, Claude Desktop
- Default architecture: Codex/Claude client planner plus local MCP executor

Highlights:

- ml-intern style research planning through `research_task`, `read_paper`, and `propose_hypotheses`.
- autoresearch style fixed-budget validation through `run_hypothesis_experiment`.
- Hybrid loop handoff through `review_research_results`, `experiment_state`, `planner_actions`, `experiment_tree`, `loop_policy`, and `code_change_plan`.
- Guarded client patch paths through `run_client_patch_experiment`, `apply_client_code_patch`, rollback, `post_patch_review`, and `loop_decision`.
- Lightweight PaperBench-style `reproduction_spec`, readiness checks, and `grade_report`.
- Repository-local skills under `skills/` for planner, reproduction, experiment optimizer, and operator workflows.
- Manifest-level `recommended_skills` and `skill_contracts` so clients can bind
  installed skills to the current MCP `contract_version`.
- `ml-loop init-skills` for Codex/Claude skill installation with dry-run and
  overwrite protection.
- Open-source readiness files including `LICENSE`, `NOTICE`, `CONTRIBUTING.md`,
  `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CITATION.cff`, GitHub issue templates,
  PR template, and CI workflow.
- Distribution metadata includes repository product assets needed for MCP and
  skills onboarding.
- Fresh checkout verifier for public release validation.
- Public launch materials covering demo transcript, architecture, and
  open-source positioning.
- Provider quality payloads now include `deduplication_report`,
  `cache_summary`, and `provider_quality_matrix` for client-side evidence
  checks.
- Experiment review payloads now include `failure_diagnostics` and
  `metric_stop_policy`; the real task/code benchmark also emits a compact
  `benchmark_summary`.

## Migration Notes

Clients must call `get_service_manifest` before automated planning. If
`compatibility_check.migration_required` or `migration_required` is true, stop
the loop and inspect `migration_hints` before invoking execution tools.

Preview compatibility rules:

- Additive optional fields may appear without changing `contract_version`.
- Removing tools, renaming tools, changing required inputs, or changing existing output meanings requires a new `contract_version`.
- Stable clients should pin both `contract_version` and the required tool list.

## Beta Release Gate

Current state: beta gate defined, not yet tagged as beta.

The beta release gate is:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/release_check.py --json
```

The gate must return `status: passed` and cover ruff, pytest, MCP stdio smoke,
client acceptance, golden path, multi-round, auto-next, client patch, provider
quality, real task/code patch, real data, and reproduction demos.

Minimum beta evidence:

- Release gate passes through `scripts/release_check.py --json`.
- Clean checkout install passes through `scripts/fresh_checkout_check.py`.
- MCP client acceptance passes through `scripts/mcp_client_acceptance.py`.
- Skills install dry-run passes for Codex and Claude targets.
- Bounded demo passes through `scripts/mcp_golden_path.py`.
- Autonomous research demo passes through `scripts/autonomous_research_demo.py`.
- Proof matrix has at least three capability entries.
- Institution pilot guide is complete enough for install, privacy/resource
  boundaries, feedback capture, and sign-off.
- Known limitations are explicit and remain visible in public release notes.
- Cognee is optional and does not block beta. It remains an opt-in memory
  adapter live-smoke path, separate from the dependency-free beta release gate.

Before tagging beta:

- Update this file with the release date and commit.
- Run `ml-loop check --json`.
- Run `ml-loop init-mcp-config` for the target client and verify the generated config.
- Run `ml-loop init-skills --client codex --dry-run` and
  `ml-loop init-skills --client claude --dry-run`.
- Confirm `docs/client-compatibility-matrix.md` matches the tested client versions.
- Confirm `examples/mcp/README.md` fresh-checkout onboarding still works.
- Confirm `SECURITY.md`, `NOTICE`, and `CITATION.cff` are current.
- Confirm a clean checkout can run the fast CI gate and MCP client acceptance.

## Stable Release Gate

Current state: stable gate defined, not met. Do not describe the current project
as stable until all stable blockers are closed and verified from a release
artifact.

Check readiness without cloning or installing:

```bash
python3 scripts/fresh_checkout_check.py --stable-readiness
```

Expected current shape is `status: beta_ready`, `beta_blockers: []`,
`release_boundary.beta.status: ready`, `release_boundary.stable.status:
blocked`, and `release_artifacts.status: verified` after the wheel/sdist and
hash verification are produced. A stable tag still requires an empty
`stable_blockers` list.

The stable release gate includes every beta gate plus:

- Frozen contract versions for service manifest, tool contracts, skills, and
  benchmark proof/archive payloads. Stable must not reuse a `preview.v*`
  contract string.
- Compatibility matrix coverage for Codex, Claude Code, and Claude Desktop,
  including config helper, acceptance command, validated status, and operator
  notes.
- At least three external pilot feedback items with installation, execution,
  limitation, and support observations.
- At least two real task proof archives with `proof-archive.json`,
  `artifact-index.json`, `publication/proof-publication.json`, and artifact
  files whose SHA-256 hashes match the archive index. Stable readiness only
  reads committed or release evidence roots such as
  `docs/evidence/proof-archives/`, `release/evidence/`, and `dist/evidence/`;
  ignored runtime directories such as `.demo_runs/` do not count.
- At least one official or official-debug benchmark proof with complete command,
  config, log, local scorer or judge provenance, and `official_scores_claimed`
  boundary.
- All public claims mapped through `docs/evidence/public-claims-map.json` to
  proof matrix entries and concrete evidence paths. Public claims that do not
  have proof matrix evidence must stay out of release notes, README, marketing,
  and pilot materials.
- Downloadable release artifact with hash verification, such as `dist/*.whl`
  and `dist/*.tar.gz` plus `dist/SHA256SUMS` or `.sha256` sidecars. Missing
  artifacts must be reported as missing; do not claim or invent a release
  artifact before `python3 -m build` creates it and SHA-256 verification
  matches the final bytes.

## Known Limitations

- Product status remains preview until a release tag is cut and validated on a clean checkout.
- Live paper, dataset, and GitHub retrieval can be rate-limited; offline demos remain the deterministic acceptance path.
- `run_ai_autoresearch` is opt-in and requires configured server-side provider credentials unless `llm_provider=mock`.
- AIDE and PaperBench are architecture patterns, not runtime dependencies.
- Cognee remains an optional memory adapter. It does not affect beta readiness;
  stable still depends on official/debug proof and stable release artifact hash
  verification, not on Cognee live-smoke success.
- Stable is not claimed: frozen contracts, real external pilot feedback, and
  official/debug benchmark proof are still required. Real-task proof archives
  and downloadable artifact hash verification are now present in this checkout.
