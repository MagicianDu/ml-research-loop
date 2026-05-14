---
name: ml-research-loop-operator
description: Use when installing, validating, troubleshooting, or operating the ML Research Loop MCP service and its skill package
---

# ML Research Loop Operator

## Purpose

Use this skill for setup, release validation, and artifact operations. It is the operational companion to the planner, reproduction, and optimizer skills.

## MCP Registration

- Codex uses the `examples/mcp/codex-config.toml` template.
- Claude Code uses `examples/mcp/claude-code.mcp.json`.
- Claude Desktop uses `examples/mcp/claude-desktop-config.json`.
- Always validate with `get_service_manifest` after registration.

## Acceptance Commands

Run client acceptance:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 scripts/mcp_client_acceptance.py --python "$(which python3)"
```

Run the full release gate:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON="$(which python3)" python3 scripts/release_check.py --json
```

Expected success includes compatible `contract_version`, no missing required tools, ruff clean, pytest passing, MCP smoke, real-data demo, real-code patch demo, and reproduction demo.

## Sandbox And Artifacts

- Use `ML_RESEARCH_LOOP_ALLOWED_ROOTS` for runtime directories outside the checkout.
- Inspect artifacts with `list_runtime_artifacts`.
- Preserve useful outputs with `archive_runtime_artifacts`.
- Use `clean_runtime_artifacts` only with explicit confirmation.

## Benchmark Proof Operations

- Use `get_benchmark_harness_probe` to inspect official MLE-bench and PaperBench prerequisites without running evaluations.
- Use `plan_benchmark_proof_run` to decide whether an official/debug proof run is blocked or ready.
- Use `write_benchmark_proof_setup_bundle` to prepare external setup files without installing dependencies or writing secrets.
- Use `write_benchmark_proof_publication_bundle` after an external run to validate command/config/log/report artifacts and claim boundaries.
- Use `write_benchmark_proof_archive` to copy complete proof artifacts into a hashed archive for Codex/Claude review.
- Add external proof artifact roots to `ML_RESEARCH_LOOP_ALLOWED_ROOTS` before using MCP write tools outside the project checkout.

## Official MLE-bench Agent Loop

- Run official MLE-bench data preparation outside this tool first; the bridge expects an existing competition directory containing `prepared/public/sample_submission.csv`.
- Use `prepare_official_mle_bench_workspace` to create the client-editable workspace under an allowed runtime root.
- Let Codex/Claude patch only the returned `allowed_patch_files` unless you intentionally expand the allowlist.
- Prefer `run_official_mle_bench_patch_round` when Codex/Claude has generated a bounded diff; it applies the patch with rollback, runs the solver round, and returns `loop_decision`.
- Use `write_official_mle_bench_patch_round_proof_bundle` after useful patch rounds to preserve diff/report/log/snapshot evidence in a publication-guarded hashed archive.
- Use `run_official_mle_bench_round` when the workspace already contains the desired solver/submission and no patch needs to be applied.
- Use `grade_official_mle_bench_submission` only for grading a pre-existing submission, then archive useful reports with the proof publication/archive tools.
- Do not report the local `grade-sample` score as a leaderboard result; preserve `official_scores_claimed=false`.

## fastText Full-Reproduction Patch Loop

- Use `run_fasttext_binary_baseline` first to produce a trusted AG News
  baseline report from a local fastText binary.
- Use `run_fasttext_patch_round` only when Codex/Claude has proposed a bounded
  allowlisted training-argument change.
- Inspect `fasttext-runtime-probe.json`, `patch-proposal.json`,
  `patch-diff.patch`, train/test logs, `improvement-report.json`, and
  `client-handoff.json`.
- Use `write_fasttext_patch_round_proof_bundle` after a useful patch round to
  write `human-review-report.json`, `proof-manifest.json`,
  `artifact-index.json`, `SHA256SUMS`, and `proof-summary.md`.
- Use `run_fasttext_multi_proposal_loop` when Codex/Claude has several
  allowlisted proposals to evaluate. Confirm `multi-round-report.json` records
  failed proposals and `rollback_summary` before using it as stronger evidence.
- Use `write_fasttext_release_proof_bundle` after P4/P5 evidence exists to
  write `release-proof-bundle.tar.gz`, `release-proof-bundle.sha256`,
  `release-review-checklist.md`, and `release-proof-manifest.json` for download
  and independent review.
- Report the round as local reproduction-improvement evidence only. Preserve
  `official_scores_claimed=false`.

## PaperBench Codex-Assisted Review

- Use `prepare_paperbench_codex_review_bundle` with an existing PaperBench
  `run_dir`, the matching `paper_dir`, and an allowed `output_dir` to create a
  review packet and Codex prompt without calling an API.
- Ask Codex/Claude to review only packet evidence against the rubric, then pass
  that JSON to `write_paperbench_codex_review_report`.
- Report this as Codex-assisted rubric review, not as an official PaperBench
  score, real-judge result, or leaderboard result. Preserve
  `official_scores_claimed=false`.

## Troubleshooting

- Missing tools: rerun MCP registration and `mcp_client_acceptance.py`.
- Permission or path errors: check runtime root, workspace, and allowed roots.
- Long runs: reduce `max_experiments` and `experiment_duration`.
- Contract mismatch: stop automated loops and read migration hints.
