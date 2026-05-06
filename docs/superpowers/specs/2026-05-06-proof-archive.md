# Proof Run Archive Spec

## Goal

Make external official/debug benchmark proof-run artifacts importable into ML Research Loop as a reproducible evidence archive.

## Problem

The project can already:

- probe official benchmark harness readiness;
- write setup instructions for an external evaluation environment;
- validate a future publication bundle and block unsupported score claims.

The missing step is artifact intake. After an external MLE-bench or PaperBench debug/small run completes, Codex/Claude needs a deterministic command that copies the proof-run artifacts into a stable archive, records hashes and sizes, and exposes the archive status through CLI, MCP manifest, release checks, and docs.

## Scope

Build a local archive writer. It must not run official evaluations, install dependencies, download data, grade submissions, or read/write secrets.

Inputs:

- artifact manifest JSON;
- artifact root containing command lines, resolved config, environment manifest, raw logs, raw reports, and limitations note;
- output directory.

Outputs:

- `proof-archive.json`;
- `artifact-index.json`;
- copied artifacts under `artifacts/`;
- nested publication guard files under `publication/`.

## Safety

- Artifact paths must resolve inside `artifact_root`.
- Missing or invalid artifacts block archival.
- The archive must keep `official_scores_claimed=false` unless explicit score evidence is provided in the manifest.
- Archive metadata may include hashes, sizes, roles, and relative paths, but must not expose secret values beyond what the user placed in artifacts.

## Acceptance

- `python3 scripts/benchmark_proof_archive.py --manifest <file> --artifact-root <dir> --output-dir <dir> --json` exits 0 and writes the archive for complete artifacts.
- `ml-loop benchmark archive-proof --manifest <file> --artifact-root <dir> --output-dir <dir> --json` is wired.
- `get_service_manifest()` includes `benchmark_proof_archive`.
- `scripts/release_check.py --json` includes `benchmark-proof-archive`.
- Unit tests cover hashing, copying, path confinement, CLI wiring, MCP manifest, release command, and docs.
