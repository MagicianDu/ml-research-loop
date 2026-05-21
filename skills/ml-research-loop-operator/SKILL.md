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

Expected success includes compatible `contract_version`, no missing required tools, ruff clean, pytest passing, MCP smoke, research memory smoke, real-data demo, real-code patch demo, and reproduction demo.

## Sandbox And Artifacts

- Use `ML_RESEARCH_LOOP_ALLOWED_ROOTS` for runtime directories outside the checkout.
- Inspect artifacts with `list_runtime_artifacts`.
- Preserve useful outputs with `archive_runtime_artifacts`.
- Use `clean_runtime_artifacts` only with explicit confirmation.

## Research Memory Operations

- Use `record_research_memory` to append reviewed proof, patch, failure, or
  procedure cards to the local store.
- Use `retrieve_research_memory`, `suggest_from_memory`, and
  `audit_memory_trace` before client-planned patch work.
- Use `promote_memory_card` only after human or client-model review decides the
  card is reusable.
- Run `python3 scripts/memory_smoke.py --output-dir .demo_runs/memory-smoke --json`
  to verify the dependency-free baseline. Graphiti/cognee are optional adapter
  checks, not release-gate requirements.

## Benchmark Proof Operations

- Use `get_benchmark_harness_probe` to inspect official MLE-bench and PaperBench prerequisites without running evaluations.
- Use `plan_benchmark_proof_run` to decide whether an official/debug proof run is blocked or ready.
- Use `write_benchmark_proof_setup_bundle` to prepare external setup files without installing dependencies or writing secrets.
- Use `write_benchmark_proof_publication_bundle` after an external run to validate command/config/log/report artifacts and claim boundaries.
- Use `write_benchmark_proof_archive` to copy complete proof artifacts into a hashed archive for Codex/Claude review.
- Add external proof artifact roots to `ML_RESEARCH_LOOP_ALLOWED_ROOTS` before using MCP write tools outside the project checkout.

## Hugging Face External Validation

- Use `get_hf_external_eval_targets` to inspect the current shortlist of public Hugging Face competition, leaderboard, and evaluation targets.
- Use `write_hf_external_eval_plan` to write a local proof plan before any live Hugging Face submission attempt.
- Use `write_smol_worldcup_live_verification` for the Smol AI WorldCup P0 target to write `hf-live-verification.json` and `hf-target-contract.md` before baseline work.
- Use `write_smol_worldcup_prompt_leakage_audit` before local model eval or prompt/routing comparison. A passing audit means generated model prompts do not expose `answer_key`, `grading_rule`, `test_case`, or `correct_answer`; it does not prove hidden-test generalization.
- Use `run_smol_worldcup_local_baseline` for the Smol AI WorldCup P1 local baseline to write `smol-worldcup-baseline-report.json`, `prediction.jsonl`, `score-breakdown.json`, `failure-cases.json`, and `runtime-profile.json`.
- Use `run_smol_worldcup_model_eval` for the Smol AI WorldCup P2 local model eval when LM Studio, DeepSeek, or another OpenAI-compatible endpoint is available. It writes `smol-worldcup-model-eval-report.json`, `prediction.jsonl`, `score-breakdown.json`, `failure-cases.json`, `runtime-profile.json`, `proposal-rounds/`, and `multi-round-report.json`.
- For DeepSeek V4 Flash/Pro diagnostics, pass `model_provider=deepseek`, `model=deepseek-v4-flash` or `deepseek-v4-pro`, and keep the secret in the configured env var such as `DEEPSEEK_API_KEY`. Artifacts may record the env var name and estimated cost, but must never record the API key value.
- For P3 prompt/routing iteration, pass `prompt_profile=p3-routing-v1` for the first bounded routing round. Use `prompt_profile=p3-dev-v2` only for dev-split follow-up on `reasoning`, `confidence_calibration`, and `self_correction`; compare dev metrics and failure cases before a single canary check.
- For future tuning, use `evaluation_split=dev` and keep `evaluation_split=canary` for final checks. Historical round-001/002/003 already used all public rows, so they are not untouched canary evidence.
- For P3 rubric-judge diagnostics, pass `judge_mode=openai-compatible` plus `judge_model` and optionally `judge_base_url`. Treat these results as local rubric diagnostics, not as official Hugging Face scores or pure model-improvement deltas.
- Treat scorer-v2 changes as scoring-adapter audit evidence, not as a new model run. If rescoring existing predictions, preserve original `llm_judge` rubric scores unless a fresh judge call is explicitly rerun.
- Use `run_smol_worldcup_rescore` for formal scorer-v2 audit runs. It writes `smol-worldcup-rescore-report.json`, `prediction.jsonl`, `score-breakdown.json`, `failure-cases.json`, and `confidence-calibration-audit.json`; review the confidence band score and answer correctness track separately.
- Use `write_smol_worldcup_rescore_proof_archive` after an accepted formal rescore to package command lines, resolved config, environment, logs, reports, source predictions, limitations, and hash index before public reporting.
- Use `write_smol_worldcup_submission_probe` before any real Hugging Face submission decision. If the probe reports `blocked_for_local_predictions`, local LM Studio predictions are not submit-ready; choose a Space-supported model ID or fork/PR the Space submission contract.
- Do not continue tuning against canary after a canary run. Move remaining failures into scorer/normalization audit or a new held-out target.
- Treat Smol AI WorldCup as the first small-LLM validation target unless a newer product decision overrides the shortlist.
- Do not upload results, create Spaces, or report leaderboard scores from these tools. They only prepare a local proof plan with `official_scores_claimed=false`.

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
