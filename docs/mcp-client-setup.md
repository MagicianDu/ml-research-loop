# MCP Client Setup

This project exposes the ml-intern x autoresearch fusion workflow as a stdio MCP server.
The intended client chain is:

`research_task -> read_paper -> propose_hypotheses -> run_hypothesis_experiment -> review_research_results -> run_next_experiment_from_review`

## Proposal Prompt Contract 工作流

本节描述 preview/new workflow。相关 CLI/MCP 工具在本分支提供，但客户端不能把
这里的流程视为已 release 或 stable 的公共契约；每次会话仍必须先调用
`get_service_manifest`，确认工具实际存在、契约版本已知、兼容性通过后再执行。

面向 Codex/Claude 的最短路径是：

1. 调用 `build_proposal_context` 生成 artifact bundle，输入应来自当前
   baseline report、dev/canary report、previous proposal history、rollback
   summary、memory cards 和资源约束。
2. Codex/Claude 只基于该 bundle 生成 proposal JSON。proposal 必须包含
   hypothesis、evidence_used、change_surface、change_spec、expected_effect、
   validation_plan、risk_assessment、next_if_success、next_if_failure 和
   claim_boundary。
3. 调用 `validate_client_proposal_contract` 做 schema、action space、
   `single_primary_variable=true`、禁止 official score claim 等校验。
4. 校验通过后，再选择现有执行工具，例如 `run_client_patch_experiment`、
   `apply_client_code_patch` 或 `run_fasttext_multi_proposal_loop`。客户端
   不应绕过 MCP guardrails 直接把 proposal 当作已验证结论。
5. 执行后调用 `write_proposal_reflection`，把 dev/canary/holdout delta、
   failure labels、rollback 结论、副作用和下一步建议写成 evidence。

约束口径：

- Codex/Claude 是 planner，不是 evaluator；成功只能来自 MCP/evaluator
  产物和 gate。
- 每个 proposal 只允许一个 primary variable；如果需要多变量探索，应拆成
  多个 proposal 或 proposal family。
- dev split 的局部提升只表示候选方向，不能被描述为稳定提升；promotion 至少
  需要 canary/holdout 或计划中明确的外部 gate。
- 失败 proposal、无效 proposal、preflight error、metric regression 和
  rollback reason 都要保留为审计证据，不能从报告中抹掉。
- `build_proposal_context` 和 `write_proposal_reflection` 默认不覆盖同名
  artifacts；如需重跑，应换新的 `output_dir` 或在明确知道后果时启用 overwrite/force。
- 默认 `official_scores_claimed=false`。本地 diagnostic、proof bundle 或
  Codex/Claude review 都不能自动升级为 official leaderboard/release claim。

For the fastText full-reproduction track, the client-driven proof chain is:

`run_fasttext_patch_round -> write_fasttext_patch_round_proof_bundle -> run_fasttext_multi_proposal_loop -> write_fasttext_release_proof_bundle`

In that chain Codex/Claude proposes bounded hyperparameter changes; the MCP
service executes, records failed proposals and rollback state, and packages
review artifacts. It still keeps `official_scores_claimed=false`.

For research memory, the advisory chain is:

`retrieve_research_memory -> suggest_from_memory -> audit_memory_trace -> guarded MCP execution -> record_research_memory`

memory suggestions are advisory. They provide provenance-backed historical
context only; Codex/Claude must still inspect current evidence, choose the next
action, and execute through guarded MCP tools.

中文产品说明见 `docs/product-overview-cn.md`。
MCP + Skills 使用说明见 `docs/skills-setup-cn.md`。
产品目标架构见 `docs/product/target-architecture-cn.md`。客户端接入时应保持该边界：Codex/Claude 做 planner，Skills 固化工作流，MCP 执行，Runtime Artifacts 保存事实证据，Research Memory Layer 只返回带 provenance 的历史上下文和建议。

## Local Smoke Test

From the project root:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
python3 scripts/mcp_client_acceptance.py --python "$(which python3)"
```

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_golden_path.py --max-experiments 1 --experiment-duration 30
```

To verify the client-planner loop across two rounds:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_multi_round_demo.py --rounds 2 --max-experiments 1 --experiment-duration 30
```

To verify the automatic review-to-next-run shortcut:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_auto_next_demo.py --max-experiments 1 --experiment-duration 30
```

To verify the loop on an actual local byte dataset instead of synthetic fallback:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_real_data_demo.py --max-experiments 1 --experiment-duration 30
```

To verify the lightweight reproduction/rubric path without Docker, GPU, network,
or LLM credentials:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_reproduction_demo.py --max-experiments 1 --experiment-duration 30 --json
```

To verify the dependency-free local research memory baseline:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
python3 scripts/memory_smoke.py --output-dir .demo_runs/memory-smoke --json
```

For custom `reproduction_spec` payloads, `required_files` must be
workspace-relative paths. Absolute paths and `..` escapes are reported as
`invalid_required_files`.

One-command product readiness check:

```bash
ml-loop check --json
```

Use `ml-loop check --skip-demos --json` for a faster MCP/client contract check
that skips the demo runs.

The last line is JSON. A successful run reports `status: completed`, a `result_file`,
and a `review` payload whose experiments include the validating `hypothesis_id`.

Use `--live-research` to let `research_task` query live arXiv/Hugging Face sources.
The default path is offline and deterministic so a new checkout can verify the MCP
tool chain without depending on network availability.

## Contract Pinning

Call `get_service_manifest` first in every new Codex/Claude client session.
The current preview public contract is `contract_version: 2026-04-30.preview.v1`.
Clients should check:

- `schema_versions.service_manifest == 2026-04-30.preview.v1`
- `compatibility.status == preview`
- `tool_contracts` contains every entry listed in `required_tools`
- `recommended_skills` and `skill_contracts` match the installed skill package
- each selected tool has matching `input_schema_version` and `output_schema_version`
- `execution_sandbox.status == enforced`
- `planning_signals` includes `execution_metadata`
- if `research_memory.status == preview`, memory tools are present in
  `required_tools` and suggestions report `executes_tool=false`

Because this is still a preview service, breaking response changes are allowed only
with a `contract_version` change. Automated planner loops should stop and ask for
operator review when the returned contract version is unknown.

`scripts/mcp_client_acceptance.py` also returns `compatibility_check`. Automated
clients should require `compatibility_check.status == compatible`; if it reports
`migration_required=true`, inspect `migration_hints` before running a planning loop.

## Execution Sandbox

MCP tools that execute code enforce path allowlisting. By default, executable
artifacts must live under the project checkout or the server-configured
`ML_RESEARCH_LOOP_ROOT`. To allow another runtime directory, set:

```bash
ML_RESEARCH_LOOP_ALLOWED_ROOTS="/ABS/PATH/TO/runtime"
```

Multiple roots can be separated with the platform path separator. When both
`runtime_root` and `workspace` are provided, `workspace` must stay inside
`runtime_root`.

## Execution Metadata

Execution-class tools return `execution_metadata` with wall time, Python
executable, timeout policy, sandbox roots, and artifact retention paths. Clients
should use it to audit which interpreter ran, whether a timeout was enforced, and
where tasks/results/workdirs/snapshots/archive entries are retained.

## Research Memory

The preview exposes five project-owned memory tools:

- `record_research_memory`: append a public `ResearchMemoryCard` or extract
  cards from fastText release proof artifacts.
- `retrieve_research_memory`: search by query, paper id, dataset, metric, patch
  type, or failure category.
- `suggest_from_memory`: return advisory next-step candidates with provenance,
  confidence, known failures, and `executes_tool=false`.
- `promote_memory_card`: append a promoted copy of a reviewed card without
  mutating old JSONL lines.
- `audit_memory_trace`: show which cards, artifact hashes, and claim
  boundaries support a suggestion.

Graphiti and cognee are optional adapters. A fresh checkout uses the local
JSONL baseline and does not require external memory services.

To enable external memory indexing, install the optional extras and opt in per
call:

```bash
pip install -e ".[memory]"

ml-loop memory record-fasttext-release \
  --store .memory/research-memory.jsonl \
  --release-manifest <release-proof-manifest.json> \
  --multi-round-report <multi-round-report.json> \
  --review-checklist <release-review-checklist.md> \
  --sync-adapters \
  --adapter graphiti \
  --adapter cognee

ml-loop memory retrieve \
  --store .memory/research-memory.jsonl \
  --query "fastText AG News P@1" \
  --include-adapters \
  --adapter graphiti \
  --adapter cognee
```

Graphiti requires `ML_RESEARCH_LOOP_GRAPHITI_URI`,
`ML_RESEARCH_LOOP_GRAPHITI_USER`, and `ML_RESEARCH_LOOP_GRAPHITI_PASSWORD`.
cognee uses `ML_RESEARCH_LOOP_COGNEE_DATASET` when provided and otherwise uses
`ml_research_loop_memory`. Adapter results are advisory context; they do not
execute experiments or prove reproduction quality.

本地 Neo4j、Graphiti/cognee optional extras、LM Studio/OpenAI-compatible
配置和 live smoke 口径见 `docs/memory-live-infra-setup-cn.md`。

## Skills Layer

Install the repository skill package after MCP registration so Codex/Claude can
reuse the intended planning workflows instead of rediscovering tool order each
session. See `docs/skills-setup-cn.md`.

Recommended install commands:

```bash
ml-loop init-skills --client codex
ml-loop init-skills --client claude
```

Use `--target-root` for project-local or non-default skill roots, and `--force`
only when intentionally replacing an existing skill package.

The four skills are:

- `ml-research-loop-planner`
- `ml-research-loop-reproduction`
- `ml-research-loop-experiment-optimizer`
- `ml-research-loop-operator`

## Codex

OpenAI's Codex configuration supports stdio MCP servers through
`~/.codex/config.toml`. Copy `examples/mcp/codex-config.toml` into that file or
merge the `[mcp_servers.mlResearchLoop]` section into your existing config.
For a concrete config using the current checkout paths, run:

```bash
ml-loop init-mcp-config --client codex
```

Replace:

- `/ABS/PATH/TO/ml-research-loop` with this checkout path.
- `/ABS/PATH/TO/python3` with the Python executable used for this environment.
- `GITHUB_TOKEN` only if you want `research_task` to include GitHub code search.
- `ML_RESEARCH_LOOP_ALLOWED_ROOTS` if execution tools should use runtime roots
  outside the project checkout.

Verify from Codex with its MCP listing command or by asking it to call
`research_task` for a small objective.

## Claude Code

Claude Code supports project-scoped MCP servers in `.mcp.json` and also supports
adding JSON config from the CLI. Copy `examples/mcp/claude-code.mcp.json` to
`.mcp.json`, replace the placeholder paths, then restart Claude Code or run:

```bash
ml-loop init-mcp-config --client claude-code --output /tmp/ml-research-loop.mcp.json
claude mcp add-json ml-research-loop "$(cat /tmp/ml-research-loop.mcp.json)"
```

Static placeholder template:

```bash
claude mcp add-json ml-research-loop "$(cat examples/mcp/claude-code.mcp.json)"
claude mcp get ml-research-loop
```

When using the Claude Agent SDK, allow the tools with:

```text
mcp__ml-research-loop__*
```

## Claude Desktop

Claude Desktop uses a separate `claude_desktop_config.json` from Claude Code.
Copy the `ml-research-loop` entry from `examples/mcp/claude-desktop-config.json`
into your Desktop config and restart the app.
To generate a concrete entry:

```bash
ml-loop init-mcp-config --client claude-desktop --output /tmp/claude-desktop-ml-research-loop.json
```

## Tool Inputs

Minimal research call:

```json
{
  "objective": "reduce val_bpb on TinyStories",
  "query": "tiny stories transformer",
  "paper_limit": 1,
  "dataset_limit": 1
}
```

Read a specific paper after search:

```json
{
  "identifier": "2108.12409",
  "objective": "reduce val_bpb on TinyStories with longer context"
}
```

Minimal hypothesis run:

```json
{
  "task_config": "/ABS/PATH/TO/runtime/tasks/my-task.json",
  "runtime_root": "/ABS/PATH/TO/runtime",
  "research_context": {
    "sources": []
  },
  "hypotheses": [
    {
      "hypothesis_id": "hyp-001",
      "title": "Validate one research-backed change"
    }
  ],
  "max_experiments": 1,
  "experiment_duration": 30
}
```

Optional server-side LLM autoresearch run:

```json
{
  "task_config": "/ABS/PATH/TO/runtime/tasks/my-task.json",
  "runtime_root": "/ABS/PATH/TO/runtime",
  "llm_provider": "mock",
  "mock_response": {
    "change_type": "hyperparam",
    "target": "DEPTH",
    "current_value": "4",
    "proposed_value": "6",
    "reason": "Try a small capacity increase inside the current budget.",
    "confidence": 0.8
  },
  "max_experiments": 1,
  "experiment_duration": 30
}
```

Use `mock` for deterministic client acceptance tests. Use `minimax` or `openai`
only when the server process has the matching API key in its environment
(`MINIMAX_API_KEY` or `OPENAI_API_KEY`). `llm_model` is optional and passes a
model name through to the selected provider.

Follow-up run from a review:

```json
{
  "task_config": "/ABS/PATH/TO/runtime/tasks/my-task.json",
  "runtime_root": "/ABS/PATH/TO/runtime",
  "task_patch": {
    "hyperparameter_space": {
      "lr": {"type": "q_log_uniform", "min": 0.0005, "max": 0.002, "q": 0.0001}
    },
    "sampling_constraints": {
      "avoid_params": [{"lr": 0.01}]
    },
    "program_md_overrides": {
      "hints": ["Continue locally around the current best experiment."]
    }
  },
  "max_experiments": 1,
  "experiment_duration": 30
}
```

Automatic follow-up from a completed review:

```json
{
  "task_id": "my-task",
  "runtime_root": "/ABS/PATH/TO/runtime",
  "workspace": "/ABS/PATH/TO/runtime/workdir/my-task",
  "experiment_duration": 30,
  "include_final_review": true
}
```

Use this payload with `run_next_experiment_from_review` when the previous
`review_research_results` returned a valid
`code_change_plan.next_experiment_plan.proposed_task_patch`. The tool re-runs
the review, selects `proposed_task_patch` first, falls back to
`next_round.task_patch`, and then calls `run_hypothesis_experiment`. With
`include_final_review=true`, the response also includes `final_review` and
`loop_decision` so the client can stop or continue without making a second tool
call.

Client-generated single-parameter patch:

```json
{
  "task_config": "/ABS/PATH/TO/runtime/tasks/my-task.json",
  "runtime_root": "/ABS/PATH/TO/runtime",
  "workspace": "/ABS/PATH/TO/runtime/workdir/my-task",
  "change_proposal": {
    "change_type": "hyperparam",
    "target": "DEPTH",
    "current_value": "1",
    "proposed_value": "2",
    "reason": "best accepted runs suggest a slightly deeper model",
    "confidence": 0.74
  },
  "max_experiments": 1,
  "experiment_duration": 30,
  "include_final_review": true
}
```

Use this payload with `run_client_patch_experiment` when the client model wants
to make its own one-parameter change after reading
`experiment_state.current_code.search_region`. The tool validates that
`change_proposal.target` still exists and `change_proposal.current_value` still
matches `train.py`; stale or out-of-region proposals are rejected before any
run starts. The execution mode is `task_patch_only`: MCP does not mutate
`train.py` directly, but narrows the next run to a single-value
`hyperparameter_space` and returns `patch_execution`, `run`, optional
`initial_review`, `final_review`, and `loop_decision`.

Client-generated workspace code patch:

```json
{
  "runtime_root": "/ABS/PATH/TO/runtime",
  "workspace": "/ABS/PATH/TO/runtime/workdir/my-task",
  "patch": "--- a/train.py\n+++ b/train.py\n@@ -12,1 +12,1 @@\n-DEPTH = 1\n+DEPTH = 2\n",
  "allowed_files": ["train.py"],
  "run_syntax_check": true,
  "test_command": ["/ABS/PATH/TO/python3", "-m", "py_compile", "train.py"],
  "test_timeout_seconds": 60
}
```

Use this payload with `apply_client_code_patch` only when Codex/Claude needs to
mutate workspace code directly rather than running a task patch. The tool only
accepts workspace-relative unified diffs, rejects path escapes, preflights hunk
context, syntax-checks changed Python files, optionally runs `test_command` from
the workspace, and rolls back on syntax or test failure. For direct experiment
loops, pass `task_id`, `include_post_patch_review=true`, and the previous
`initial_review` so the tool can return `post_patch_review` and a metric-aware
`loop_decision`.

Client-generated fastText reproduction patch round:

```json
{
  "target_spec": "/ABS/PATH/TO/ml-research-loop/docs/reproduction-pilot/full-reproduction-target.json",
  "output_dir": "/ABS/PATH/TO/ml-research-loop/.demo_runs/p3-fasttext-real-patch",
  "ag_news_train_csv": "/ABS/PATH/TO/ml-research-loop/.demo_runs/p2ppp-ag-news-current/train.csv",
  "ag_news_test_csv": "/ABS/PATH/TO/ml-research-loop/.demo_runs/p2ppp-ag-news-current/test.csv",
  "fasttext_binary": "/ABS/PATH/TO/ml-research-loop/.external/fastText/fasttext",
  "baseline_report": "/ABS/PATH/TO/ml-research-loop/.demo_runs/p2ppp-fasttext-real-baseline/fasttext-baseline-report.json",
  "proposal": {
    "proposal_id": "p3-fasttext-wordngrams-2",
    "reason": "add bigram features while keeping fixed seed and single-thread execution",
    "train_args": {
      "-wordNgrams": 2
    }
  },
  "max_train_seconds": 900
}
```

Use this payload with `run_fasttext_patch_round` after a trusted
`run_fasttext_binary_baseline` report exists. The client model chooses one
allowlisted fastText training-argument proposal; MCP converts AG News CSV,
runs training/test, writes `patch-diff.patch`, `improvement-report.json`, logs,
and `client-handoff.json`, then returns baseline metric, patch metric, delta,
and `loop_decision`. Keep `official_scores_claimed=false`.

FastText patch proof bundle:

```json
{
  "patch_round_report": "/ABS/PATH/TO/ml-research-loop/.demo_runs/p3-fasttext-real-patch/improvement-report.json",
  "output_dir": "/ABS/PATH/TO/ml-research-loop/.demo_runs/p4-fasttext-real-proof",
  "reviewer": "codex-local-review",
  "review_status": "approved_with_limitations"
}
```

Use this payload with `write_fasttext_patch_round_proof_bundle` after a useful
`run_fasttext_patch_round`. It writes `human-review-report.json`,
`proof-manifest.json`, `artifact-index.json`, `SHA256SUMS`, `proof-summary.md`,
and copied artifacts under `artifacts/`. The bundle is a local publication
guard and still keeps `official_scores_claimed=false`.

Artifact lifecycle commands:

```bash
ml-loop artifacts list --runtime-root /ABS/PATH/TO/runtime
ml-loop artifacts archive --runtime-root /ABS/PATH/TO/runtime --task-id my-task
ml-loop artifacts clean --runtime-root /ABS/PATH/TO/runtime --task-id my-task --confirm
```

Result reading:

- `get_service_manifest` returns the versioned product contract, `contract_version`, `schema_versions`, `tool_contracts`, required tools, planner/executor boundary, and recommended workflows. Use it first when connecting a new Codex/Claude client.
- `review_research_results` returns both `research_review` and `experiment_state`.
  Use `experiment_state` as the Codex/Claude planner handoff after every run.
- `experiment_state.research_evidence_gate` tells the client whether the current research context is evidence-backed or should be refreshed before trusting the next hypothesis.
- `experiment_state.dataset_profile` summarizes the task dataset path, existence, size, inferred vocab/sequence length, and data risks.
- `experiment_state.loop_policy` fuses experiment-tree state and reproduction readiness into `decision`, `reason_category`, `recommended_next_action`, and `stop_reason`.
- `experiment_state.code_change_plan` gives the client model a conservative next SEARCH REGION target, reason, and edit constraints.
- `experiment_state.code_change_plan.next_experiment_plan` gives the selected metric, target parameter, candidate values, best params, stop conditions, edit policy, `diff_preview`, and `execution_guardrails` for the next one-parameter validation.
- `run_client_patch_experiment` is the guarded client-planner patch path. Use it when Codex/Claude generates a single-parameter `change_proposal`; inspect `patch_execution.mode == "task_patch_only"`, `patch_execution.diff_preview`, and `patch_execution.execution_guardrails` before trusting the run.
- `apply_client_code_patch` is the guarded direct code-edit path. Use it only for explicit unified diffs; inspect `patch_execution.preflight`, `syntax_check`, `test_check`, `rollback`, optional `post_patch_review`, and optional `loop_decision` before continuing.
- `run_fasttext_patch_round` is the full-reproduction track's guarded
  hyperparameter patch executor. Use it only against an archived trusted
  baseline report; inspect `improvement_report`, `patch_diff`,
  `client_handoff`, and `official_scores_claimed=false`.
- `write_fasttext_patch_round_proof_bundle` is the P4 publication guard for a
  completed fastText patch round. Use it before presenting patch evidence as a
  public proof artifact.
- `experiment_state.planner_actions` is an ordered action list. Prefer the first action unless the user gives a stronger instruction; actions may call `research_task`, `get_experiment_logs`, or `run_hypothesis_experiment`, or require a client-side edit.
- `get_experiment_logs` returns recent per-experiment log tails. Use it when
  `experiment_state.failure_summary.failed_count > 0` or a run has no target metric.
- `read_paper` accepts an arXiv ID or URL and returns one normalized `source`, section-aware `evidence_snippets`, extracted `findings`, and a first-pass hypothesis for validation.
- `research_task` / `propose_hypotheses` now return `findings` alongside `sources` and `hypotheses`.
- `research_task` accepts optional `cache_dir`; when provided, paper/dataset/GitHub searches are cached as JSON and the response includes `cache` hit/miss metadata, `cache_schema_version`, `cache_scope`, `source_count`, `source_types`, and `freshness_seconds`.
- `research_task` accepts optional `query_fanout` (default `true`). When a primary query returns too few sources, it tries `query_plan` variants before returning.
- `research_task` returns `evidence_quality`, `evidence_citations`, and each source includes `metadata.source_id` plus `metadata.evidence_quality` for judging whether a context is evidence-backed.
- `metadata.evidence_quality.source_class` distinguishes `paper_fulltext_ready`, `paper_abstract`, `dataset_card`, `code_reference`, provider-attributed sources, and weak unattributed evidence; aggregate counts appear in `evidence_quality.source_class_counts`.
- `evidence_citations[*].source_trace` ties each finding to `source_id`, provider, URL, query variant, query reason, and snippet ids so planners can audit citation provenance.
- `research_task` returns `provider_coverage` and `provider_coverage_gate`; use them to see provider counts, source types, evidence quality by provider, known-provider ratio, and sources still missing provider metadata.
- `research_task` returns `retrieval_diagnostics`; inspect it when `status == "research_context_partial"` to see backend statuses, attempted query variants, warning text, cache usage, and `recommended_recovery`.
- When an attempted query includes `error.category == "rate_limited"`, treat the
  research context as incomplete. Follow `recommended_recovery` in order; for
  `wait_for_rate_limit_reset`, wait or retry later before asking the planner to
  make evidence-backed code or hyperparameter changes.
- Real provider sources include `metadata.provider`, and `source_rankings`
  include provider and evidence quality score so planners can prefer stronger
  arXiv, Hugging Face, or GitHub evidence.
- Each returned source includes `metadata.query_variant` and `metadata.query_reason`, so client planners can distinguish primary-query evidence from keyword-expansion evidence.
- `research_task` also returns `query_plan` and `source_rankings`; rankings include `rank`, `source_type`, `title`, `url`, `relevance_score`, and `evidence`.
- `propose_hypotheses` uses relevance scores when choosing the strongest source/finding for the first hypothesis.
- `review_research_results` returns the original result plus `research_review`, including `decision`, `hypothesis_outcomes`, `next_actions`, `experiment_strategy`, `recommended_search_space`, and `next_task_patch`.
- `run_hypothesis_experiment` accepts either `task_patch` from `review_research_results` or a bare `recommended_search_space`; it writes the patched task config before launching autoresearch. A review-generated `task_patch` may also narrow `budget.max_experiments` and inject stop conditions into `program_md_overrides.hints`.
- `run_next_experiment_from_review` is the shortest automatic loop entry: it
  reads the completed task review, chooses
  `next_experiment_plan.proposed_task_patch` when present, and launches the next
  `run_hypothesis_experiment`.

Client-side planning loop:

1. Call `review_research_results`.
2. Inspect `experiment_state.planner_actions` first, then inspect `best_result`, `recent_experiments`, `failure_summary`, `research_evidence_gate`, `dataset_profile`, `current_code.search_region`, `code_change_plan.next_experiment_plan`, and `next_round`.
3. Execute or adapt the first planner action: refresh research when evidence is partial, inspect logs when failures exist, fix dataset paths before tuning, or continue with `run_hypothesis_experiment`.
4. Use `run_next_experiment_from_review` when the proposed patch is acceptable
   and no client-side code edit is needed.
5. Use `run_client_patch_experiment` when the client model intentionally changes
   one SEARCH REGION parameter itself; include `current_value` to protect
   against stale state.
6. Use `apply_client_code_patch` only when a true workspace code diff is needed;
   include `allowed_files`, a small `test_command`, `task_id`,
   `include_post_patch_review=true`, and `initial_review` when possible.
7. Use `run_fasttext_patch_round` only for the fastText AG News reproduction
   track after a trusted baseline report exists and the proposal is allowlisted.
8. Use `write_fasttext_patch_round_proof_bundle` after a useful fastText patch
   round to preserve hash-indexed artifacts and human-review boundaries.
9. Call `run_ai_autoresearch` only for explicit server-side autonomous mode.

When the first planner action asks for research refresh, pass its suggested `args`
through unchanged. In particular, keep `query_fanout=true` unless the user explicitly
needs single-query reproducibility.
If `research_evidence_gate.retrieval_recovery` is present, use it to explain why
research refresh is preferred before treating generated hypotheses as evidence-backed.

## References

- OpenAI Codex MCP/config reference: https://developers.openai.com/codex/config-reference
- OpenAI Docs MCP quickstart: https://developers.openai.com/learn/docs-mcp
- Claude Code MCP configuration: https://code.claude.com/docs/en/mcp
- Claude Agent SDK MCP configuration: https://code.claude.com/docs/en/agent-sdk/mcp
