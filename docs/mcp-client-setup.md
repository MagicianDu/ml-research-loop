# MCP Client Setup

This project exposes the ml-intern x autoresearch fusion workflow as a stdio MCP server.
The intended client chain is:

`research_task -> propose_hypotheses -> run_hypothesis_experiment -> review_research_results`

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

## References

- OpenAI Codex MCP/config reference: https://developers.openai.com/codex/config-reference
- OpenAI Docs MCP quickstart: https://developers.openai.com/learn/docs-mcp
- Claude Code MCP configuration: https://code.claude.com/docs/en/mcp
- Claude Agent SDK MCP configuration: https://code.claude.com/docs/en/agent-sdk/mcp
