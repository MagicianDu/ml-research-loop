# Release Notes

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

## Migration Notes

Clients must call `get_service_manifest` before automated planning. If
`compatibility_check.migration_required` or `migration_required` is true, stop
the loop and inspect `migration_hints` before invoking execution tools.

Preview compatibility rules:

- Additive optional fields may appear without changing `contract_version`.
- Removing tools, renaming tools, changing required inputs, or changing existing output meanings requires a new `contract_version`.
- Stable clients should pin both `contract_version` and the required tool list.

## Beta Release Gate

The beta release gate is:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/release_check.py --json
```

The gate must return `status: passed` and cover ruff, pytest, MCP stdio smoke,
client acceptance, golden path, multi-round, auto-next, client patch, provider
quality, real task/code patch, real data, and reproduction demos.

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

The stable release gate includes every beta gate plus:

- No known breaking changes under the current `contract_version`.
- A compatibility matrix entry for each supported client.
- Documented migration notes for every contract change since the previous tag.
- A fresh checkout install test using `pip install -e ".[dev]"`.
- A client acceptance run using the installed console scripts.

## Known Limitations

- Product status remains preview until a release tag is cut and validated on a clean checkout.
- Live paper, dataset, and GitHub retrieval can be rate-limited; offline demos remain the deterministic acceptance path.
- `run_ai_autoresearch` is opt-in and requires configured server-side provider credentials unless `llm_provider=mock`.
- AIDE and PaperBench are architecture patterns, not runtime dependencies.
