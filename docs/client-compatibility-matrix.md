# Client Compatibility Matrix

This matrix records the MCP clients targeted by the current preview contract.

| Client | Status | Config Helper | Primary Config | Acceptance |
|---|---|---|---|---|
| Codex | Supported preview | `ml-loop init-mcp-config --client codex` | `~/.codex/config.toml` | `scripts/mcp_client_acceptance.py` |
| Claude Code | Supported preview | `ml-loop init-mcp-config --client claude-code` | `claude mcp add-json` | `scripts/mcp_client_acceptance.py` |
| Claude Desktop | Supported preview | `ml-loop init-mcp-config --client claude-desktop` | `claude_desktop_config.json` | manual restart plus `get_service_manifest` |

## Contract Pin

- `contract_version`: `2026-04-30.preview.v1`
- Required manifest field: `tool_contracts`
- Required compatibility field: `compatibility_check.status == compatible`
- Required migration field: `migration_required`

Automated clients must stop before execution if the manifest reports an
unknown `contract_version`, missing required tools, missing tool contracts, or
`migration_required=true`.

## Client Notes

### Codex

Use:

```bash
ml-loop init-mcp-config --client codex
```

Copy or merge the generated `[mcp_servers.mlResearchLoop]` block into
`~/.codex/config.toml`, then restart Codex.

### Claude Code

Use:

```bash
ml-loop init-mcp-config --client claude-code --output /tmp/ml-research-loop.mcp.json
claude mcp add-json ml-research-loop "$(cat /tmp/ml-research-loop.mcp.json)"
```

### Claude Desktop

Use:

```bash
ml-loop init-mcp-config --client claude-desktop
```

Merge the `mcpServers.ml-research-loop` entry into `claude_desktop_config.json`,
then restart Claude Desktop.

## Minimum Validation

Each client integration should be validated by:

```bash
python3 scripts/mcp_client_acceptance.py --python "$(which python3)"
python3 scripts/mcp_golden_path.py --max-experiments 1 --experiment-duration 30
```
