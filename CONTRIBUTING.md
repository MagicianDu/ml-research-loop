# Contributing

Thanks for helping improve ML Research Loop. This project is currently a
preview MCP product, so compatibility and repeatable local verification matter
more than broad refactors.

## Development Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Before Opening A Pull Request

Run the fast checks:

```bash
ruff check lib/ scripts/ ml_intern/ codex_plugin/ tests/
python -m pytest tests/ -q
python scripts/mcp_client_acceptance.py --python "$(which python)"
```

For product-facing changes, run the full local release gate:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/release_check.py --json
```

## Compatibility Rules

- Call `get_service_manifest` first when changing MCP client behavior.
- Keep preview changes additive unless you intentionally bump
  `contract_version`.
- Update tests and docs for any new public field, tool, skill, or artifact path.
- Do not add implicit server-side LLM calls to the default execution path.
- Do not bypass path sandboxing for runtime roots, workspaces, or task configs.

## Pull Request Checklist

- Explain the user-visible behavior change.
- Link related issues or design notes when relevant.
- Include focused tests for the changed behavior.
- Confirm whether the full release gate was run.
