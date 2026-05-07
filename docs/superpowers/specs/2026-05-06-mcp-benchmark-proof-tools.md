# MCP Benchmark Proof Tools Spec

## Goal

Expose the benchmark proof-run lifecycle as first-class MCP tools so Codex/Claude can operate it without shelling out to the CLI.

## Problem

The project can already run benchmark proof lifecycle commands through CLI and release checks:

- official harness probe;
- proof-run plan;
- setup bundle;
- publication bundle;
- hashed proof archive.

But MCP clients only see those outputs indirectly through `get_service_manifest`. This weakens the product shape: a Codex/Claude client connected only through MCP cannot directly prepare, validate, publish, or archive proof artifacts.

## Scope

Add MCP tools for the existing safe benchmark proof primitives:

- `get_benchmark_harness_probe`
- `plan_benchmark_proof_run`
- `write_benchmark_proof_setup_bundle`
- `write_benchmark_proof_publication_bundle`
- `write_benchmark_proof_archive`

These tools must reuse the existing benchmark library code and must not execute official benchmark runs, install dependencies, download data, run grading, or read secrets.

## Acceptance

- `tools/list` includes all benchmark proof tools with schemas.
- `tools/call` can call the read-only probe/plan tools.
- `tools/call` can write setup/publication/archive bundles to caller-provided output dirs.
- `get_service_manifest().required_tools` and `tool_contracts` include the tools.
- `mcp_client_acceptance.py` stays compatible.
- Release checklist and repo-local skills document the MCP-first benchmark proof workflow.
