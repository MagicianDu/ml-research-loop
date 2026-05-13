---
name: ml-research-loop-reproduction
description: Use when reproducing a paper, checking reproduction readiness, creating rubric-based evaluations, or grading ML Research Loop artifacts
---

# ML Research Loop Reproduction

## Purpose

Use this skill for PaperBench-style lightweight reproduction inside ML Research Loop. The goal is to move from paper evidence to local required files, runnable commands, and a deterministic `grade_report`.

## Flow

1. Gather evidence with `read_paper` for a known paper or `research_task` for a broader objective.
2. Convert the target into a local `reproduction_spec` with workspace-relative `required_files`, a bounded command, and a rubric.
3. Run or reuse an experiment with `run_hypothesis_experiment`.
4. Review with `review_research_results`.
5. Inspect `experiment_state.reproduction.readiness`, `missing_files`, `invalid_required_files`, and `grade_report`.
6. For PaperBench run artifacts, use `prepare_paperbench_codex_review_bundle`
   to gather `paper.md`, `rubric.json`, run logs, grading metadata, and
   submission metadata into a Codex review packet.
7. After Codex/Claude reviews the packet against the rubric, persist the
   non-official audit with `write_paperbench_codex_review_report`.
8. For the fastText AG News full-reproduction track, first establish a trusted
   baseline with `run_fasttext_binary_baseline`, then let Codex/Claude propose a
   bounded training-argument change and execute it with `run_fasttext_patch_round`.
9. After a useful fastText patch round, call
   `write_fasttext_patch_round_proof_bundle` to produce
   `human-review-report.json`, `proof-manifest.json`, `artifact-index.json`, and
   hashed artifact evidence before treating the result as public proof.

## Required Checks

- `required_files` must be workspace-relative. Absolute paths and `..` escapes are invalid.
- Treat `invalid_required_files` as a hard blocker until the spec is fixed.
- Treat missing files as a reproduction readiness failure, not as a model-quality failure.
- A usable rubric has leaf tasks with clear requirements and weights.
- A `grade_report.score` is only meaningful after readiness is `ready` or the report explains why not.
- `write_paperbench_codex_review_report` records Codex-assisted rubric
  judgment only. It is not an official PaperBench score and should retain
  `official_scores_claimed=false`.
- `run_fasttext_patch_round` must consume an existing baseline report and an
  allowlisted proposal. Treat `improvement-report.json` and
  `client-handoff.json` as local reproducibility artifacts, not as full-paper or
  leaderboard proof.
- `write_fasttext_patch_round_proof_bundle` must keep
  `official_scores_claimed=false`; `proof-manifest.json` only proves the local
  patch round artifacts were reviewed and hashed.

## Demo

Use `scripts/mcp_reproduction_demo.py --max-experiments 1 --experiment-duration 30 --json` for the deterministic local smoke test. It does not require Docker, GPU, network, or LLM credentials.

## Output

Report paper/source evidence, reproduction readiness status, missing or invalid files, rubric coverage, `grade_report.score`, fastText baseline/patch metrics when present, and result artifact paths.
