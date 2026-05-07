# Proof Publication Guard Spec

## Goal

Add a publication guard for future official or official-debug benchmark proof
runs. It validates an artifact manifest, decides which public claims are allowed,
and writes a redacted publication bundle that separates official benchmark
scores from local fixture or setup-only evidence.

## Scope

In scope:

- Consume a JSON artifact manifest and an artifact root.
- Check required publication artifacts: command lines, resolved config,
  environment manifest, raw logs, raw reports, and limitations note.
- Preserve `official_scores_claimed=false` unless the manifest explicitly
  declares an official score and provides official-score evidence.
- Return `status=publishable_with_limitations` when all required artifacts are
  present but no official score is claimed.
- Return `status=blocked` when required artifacts are missing or score claims
  lack evidence.
- Write `proof-publication.json` and `proof-publication.md`.
- Expose through script, CLI, MCP manifest, release check, and docs.

Out of scope:

- Running official MLE-bench or PaperBench.
- Parsing official leaderboard formats.
- Uploading artifacts to GitHub Releases or other hosting.
- Treating deterministic local fixtures as official benchmark results.

## Manifest Contract

The input manifest must be JSON and may contain:

- `benchmark_name`: `mle_bench` or `paperbench`
- `run_mode`: `official_debug`, `official_small`, `official_full`, or
  `local_fixture`
- `official_scores_claimed`: boolean
- `score_evidence_path`: optional path relative to artifact root
- `limitations`: list of limitations
- `artifacts`: object mapping:
  - `command_lines`
  - `resolved_config`
  - `environment_manifest`
  - `raw_logs`
  - `raw_reports`
  - `limitations_note`

## Output Contract

The output bundle includes:

- `status`
- `read_only=true`
- `official_scores_claimed`
- `claim_policy`
- `missing_artifacts`
- `allowed_public_claims`
- `blocked_public_claims`
- `artifact_manifest`
- `write_targets`

## Acceptance

- `python3 scripts/benchmark_proof_publication.py --manifest <file> --artifact-root <dir> --output-dir <dir> --json` exits 0 and writes JSON/Markdown.
- `ml-loop benchmark publication-bundle --manifest <file> --artifact-root <dir> --output-dir <dir> --json` is wired.
- `get_service_manifest()` includes `benchmark_proof_publication`.
- `scripts/release_check.py --json` includes `benchmark-proof-publication` using a generated sample manifest.
