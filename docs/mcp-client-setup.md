# MCP Client Setup

This project exposes the ml-intern x autoresearch fusion workflow as a stdio MCP server.
The intended client chain is:

`research_task -> read_paper -> propose_hypotheses -> run_hypothesis_experiment -> review_research_results -> run_hypothesis_experiment`

## Local Smoke Test

From the project root:

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

To verify the loop on an actual local byte dataset instead of synthetic fallback:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_real_data_demo.py --max-experiments 1 --experiment-duration 30
```

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
- each selected tool has matching `input_schema_version` and `output_schema_version`

Because this is still a preview service, breaking response changes are allowed only
with a `contract_version` change. Automated planner loops should stop and ask for
operator review when the returned contract version is unknown.

## Codex

OpenAI's Codex configuration supports stdio MCP servers through
`~/.codex/config.toml`. Copy `examples/mcp/codex-config.toml` into that file or
merge the `[mcp_servers.mlResearchLoop]` section into your existing config.

Replace:

- `/ABS/PATH/TO/ml-research-loop` with this checkout path.
- `/ABS/PATH/TO/python3` with the Python executable used for this environment.
- `GITHUB_TOKEN` only if you want `research_task` to include GitHub code search.

Verify from Codex with its MCP listing command or by asking it to call
`research_task` for a small objective.

## Claude Code

Claude Code supports project-scoped MCP servers in `.mcp.json` and also supports
adding JSON config from the CLI. Copy `examples/mcp/claude-code.mcp.json` to
`.mcp.json`, replace the placeholder paths, then restart Claude Code or run:

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
  "experiment_duration": 30
}
```

Use this payload with `run_next_experiment_from_review` when the previous
`review_research_results` returned a valid
`code_change_plan.next_experiment_plan.proposed_task_patch`. The tool re-runs
the review, selects `proposed_task_patch` first, falls back to
`next_round.task_patch`, and then calls `run_hypothesis_experiment`.

Result reading:

- `get_service_manifest` returns the versioned product contract, `contract_version`, `schema_versions`, `tool_contracts`, required tools, planner/executor boundary, and recommended workflows. Use it first when connecting a new Codex/Claude client.
- `review_research_results` returns both `research_review` and `experiment_state`.
  Use `experiment_state` as the Codex/Claude planner handoff after every run.
- `experiment_state.research_evidence_gate` tells the client whether the current research context is evidence-backed or should be refreshed before trusting the next hypothesis.
- `experiment_state.dataset_profile` summarizes the task dataset path, existence, size, inferred vocab/sequence length, and data risks.
- `experiment_state.code_change_plan` gives the client model a conservative next SEARCH REGION target, reason, and edit constraints.
- `experiment_state.code_change_plan.next_experiment_plan` gives the selected metric, target parameter, candidate values, best params, stop conditions, and edit policy for the next one-parameter validation.
- `experiment_state.planner_actions` is an ordered action list. Prefer the first action unless the user gives a stronger instruction; actions may call `research_task`, `get_experiment_logs`, or `run_hypothesis_experiment`, or require a client-side edit.
- `get_experiment_logs` returns recent per-experiment log tails. Use it when
  `experiment_state.failure_summary.failed_count > 0` or a run has no target metric.
- `read_paper` accepts an arXiv ID or URL and returns one normalized `source`, section-aware `evidence_snippets`, extracted `findings`, and a first-pass hypothesis for validation.
- `research_task` / `propose_hypotheses` now return `findings` alongside `sources` and `hypotheses`.
- `research_task` accepts optional `cache_dir`; when provided, paper/dataset/GitHub searches are cached as JSON and the response includes `cache` hit/miss metadata.
- `research_task` accepts optional `query_fanout` (default `true`). When a primary query returns too few sources, it tries `query_plan` variants before returning.
- `research_task` returns `evidence_quality`, and each source includes `metadata.evidence_quality` for judging whether a context is evidence-backed.
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
5. Call `run_ai_autoresearch` only for explicit server-side autonomous mode.

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
