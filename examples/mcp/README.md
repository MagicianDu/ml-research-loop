# MCP Config Examples

This directory contains placeholder config templates plus the recommended fresh
checkout onboarding path.

## Fresh Checkout

```bash
git clone https://github.com/your-username/ml-research-loop.git
cd ml-research-loop
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Generate Client Config

Codex:

```bash
ml-loop init-mcp-config --client codex
```

Claude Code:

```bash
ml-loop init-mcp-config --client claude-code --output /tmp/ml-research-loop.mcp.json
claude mcp add-json ml-research-loop "$(cat /tmp/ml-research-loop.mcp.json)"
```

Claude Desktop:

```bash
ml-loop init-mcp-config --client claude-desktop --output /tmp/claude-desktop-ml-research-loop.json
```

The generated config points at the local `scripts/mcp_server.py`, sets
`PYTHONPATH`, and pins `ML_RESEARCH_LOOP_PYTHON`.

## Acceptance

Run the client contract check:

```bash
python3 scripts/mcp_client_acceptance.py --python "$(which python3)"
```

Run the bounded golden-path demo:

```bash
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_golden_path.py --max-experiments 1 --experiment-duration 30
```

For the full local release gate:

```bash
ml-loop check --json
```
