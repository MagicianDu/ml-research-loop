# PaperBench Adapter Spec

## Goal

Build a first PaperBench-facing research reproduction adapter that proves ML Research Loop can represent and execute the three PaperBench stages at small scale:

1. agent rollout creates a submission codebase;
2. reproduction executes the submitted codebase;
3. grading evaluates the executed submission against a rubric.

This spike is not an official PaperBench leaderboard submission. It is the compatibility layer for research reproduction evidence.

## External Contract

Reference behavior from official PaperBench docs:

- PaperBench evaluates agents on replicating 20 ICML 2024 Spotlight and Oral papers.
- Each sample includes a research paper and rubric.
- PaperBench has three stages: Agent Rollout, Reproduction, and Grading.
- PaperBench supports a debug split and dummy scaffold for infrastructure testing.
- Existing submissions can be graded through a direct-submission path.

Primary references:

- https://github.com/openai/frontier-evals/tree/main/project/paperbench
- https://github.com/openai/frontier-evals/blob/main/project/paperbench/README.md

## Scope

### In

- A dependency-free adapter module under `lib/benchmarks/`.
- A deterministic local PaperBench-shaped fixture:
  - `paper_id`
  - paper metadata
  - paper summary text
  - rubric tree
  - required file list
- Output artifacts:
  - submission directory
  - reproduction report
  - grade report
  - ML Research Loop task file/result file references
  - benchmark report JSON
- CLI/demo script to run the local fixture end-to-end.
- Tests for schema mapping, rubric grading, and demo execution.

### Out

- No full PaperBench data hydration.
- No GPU reproduction.
- No OpenAI judge invocation.
- No official PaperBench score claim.

## Product Requirements

1. A user can run one command and see a PaperBench-shaped reproduction lifecycle.
2. The result must mark `official_paperbench=false`.
3. The output must preserve stage-level status:
   - `agent_rollout.status`
   - `reproduction.status`
   - `grading.status`
4. The adapter must reuse existing `reproduction_spec`, `grade_report`, and runtime artifacts instead of inventing an unrelated schema.
5. The report must be useful to Codex/Claude as a research reproduction handoff:
   - paper metadata
   - rubric leaves
   - missing/valid required files
   - result/log paths
   - next actions

## Acceptance

- `python scripts/paperbench_adapter_demo.py --runtime-root <tmp> --json` exits 0.
- The JSON payload includes `status=passed`, `official_paperbench=false`, `paper_id`, `submission_dir`, `reproduction_report_path`, `grade_report_path`, and `benchmark_report_path`.
- `grade_report.score` is present and greater than 0 for the deterministic fixture.
- The report contains stage-level statuses and rubric leaf results.
- New tests pass under Python 3.13.
- Existing full test suite remains green.
