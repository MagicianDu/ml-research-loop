# MCP Client Setup

This project exposes the ml-intern x autoresearch fusion workflow as a stdio MCP server.
The intended client chain is:

`research_task -> read_paper -> propose_hypotheses -> run_hypothesis_experiment -> review_research_results -> run_hypothesis_experiment`

## Local Smoke Test

From the project root:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_golden_path.py --max-experiments 1 --experiment-duration 30
```

The last line is JSON. A successful run reports `status: completed`, a `result_file`,
and a `review` payload whose experiments include the validating `hypothesis_id`.

Use `--live-research` to let `research_task` query live arXiv/Hugging Face sources.
The default path is offline and deterministic so a new checkout can verify the MCP
tool chain without depending on network availability.

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

Result reading:

- `review_research_results` returns both `research_review` and `experiment_state`.
  Use `experiment_state` as the Codex/Claude planner handoff after every run.
- `read_paper` accepts an arXiv ID or URL and returns one normalized `source`, section-aware `evidence_snippets`, extracted `findings`, and a first-pass hypothesis for validation.
- `research_task` / `propose_hypotheses` now return `findings` alongside `sources` and `hypotheses`.
- `research_task` also returns `query_plan` and `source_rankings`; rankings include `rank`, `source_type`, `title`, `url`, `relevance_score`, and `evidence`.
- `propose_hypotheses` uses relevance scores when choosing the strongest source/finding for the first hypothesis.
- `review_research_results` returns the original result plus `research_review`, including `decision`, `hypothesis_outcomes`, `next_actions`, `experiment_strategy`, `recommended_search_space`, and `next_task_patch`.
- `run_hypothesis_experiment` accepts either `task_patch` from `review_research_results` or a bare `recommended_search_space`; it writes the patched task config before launching autoresearch. A review-generated `task_patch` may also narrow `budget.max_experiments` and inject stop conditions into `program_md_overrides.hints`.

Client-side planning loop:

1. Call `review_research_results`.
2. Inspect `experiment_state.best_result`, `recent_experiments`, `failure_summary`, `current_code.search_region`, and `next_round`.
3. Let the client model decide whether to continue, revise `task_patch`, edit code in a filesystem-capable client, or stop.
4. Call `run_hypothesis_experiment` again with the selected `task_patch`, or call `run_ai_autoresearch` for explicit server-side autonomous mode.

## References

- OpenAI Codex MCP/config reference: https://developers.openai.com/codex/config-reference
- OpenAI Docs MCP quickstart: https://developers.openai.com/learn/docs-mcp
- Claude Code MCP configuration: https://code.claude.com/docs/en/mcp
- Claude Agent SDK MCP configuration: https://code.claude.com/docs/en/agent-sdk/mcp
