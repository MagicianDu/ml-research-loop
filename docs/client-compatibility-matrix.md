# Client Compatibility Matrix

This matrix records the MCP clients targeted by the current preview contract and
the evidence required before beta or stable release. Current status remains
preview; stable is not claimed.

| Client | Current Status | Beta Acceptance | Stable Requirement | Config Helper | Primary Config |
|---|---|---|---|---|---|
| Codex | Supported preview | `scripts/mcp_client_acceptance.py`; `ml-loop init-skills --client codex --dry-run`; bounded demo | Frozen contract pin, external pilot feedback, and release artifact hash verified for Codex | `ml-loop init-mcp-config --client codex` | `~/.codex/config.toml` |
| Claude Code | Supported preview | `scripts/mcp_client_acceptance.py`; `ml-loop init-skills --client claude --dry-run`; bounded demo | Frozen contract pin, external pilot feedback, and release artifact hash verified for Claude Code | `ml-loop init-mcp-config --client claude-code` | `claude mcp add-json` |
| Claude Desktop | Supported preview | generated config plus manual restart and `get_service_manifest`; bounded demo through the same local MCP server | Frozen contract pin, external pilot feedback, and release artifact hash verified for Claude Desktop | `ml-loop init-mcp-config --client claude-desktop` | `claude_desktop_config.json` |

## Contract Pin

- `contract_version`: `2026-07-10.preview.v1`
- Required manifest field: `tool_contracts`
- Required compatibility field: `compatibility_check.status == compatible`
- Required migration field: `migration_required`

Automated clients must stop before execution if the manifest reports an
unknown `contract_version`, missing required tools, missing tool contracts, or
`migration_required=true`.

## Release Gate Coverage

Beta coverage requires each supported client to have:

- Config helper documented.
- MCP client acceptance path documented.
- Skills install dry-run documented where the client supports repository skills.
- Bounded demo path documented.
- Known limitations visible in release notes.

Stable coverage requires beta coverage plus:

- Frozen, non-preview contract versions.
- At least three external pilot feedback items across supported clients.
- At least two real task proof archives and at least one official or
  official-debug benchmark proof under committed/release evidence roots, with
  artifact files present and SHA-256 hashes verified.
- All public claims mapped through `docs/evidence/public-claims-map.json` to
  proof matrix entries.
- Downloadable release artifact with SHA-256 verification.

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
