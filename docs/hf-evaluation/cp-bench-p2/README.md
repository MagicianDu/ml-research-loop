# CP-Bench Local Evaluator Artifact

status: `blocked_missing_dependencies`
official_scores_claimed: `false`
external_submission_status: `not_submitted`
manual_submission_required: `true`
framework: `CPMpy`
dataset_version: `verified`

## Claim Boundary

CP-Bench local evaluator artifact only; not a Hugging Face submission, leaderboard score, or official external result.

## Dependency Gate

本次 smoke 已进入真实 evaluator dependency gate，但未运行 evaluator 评分。缺少依赖：

- `datasets`
- `cpmpy`
- `minizinc`
- `ortools`

因此该目录是 `blocked_missing_dependencies` proof，不是 CP-Bench 评分结果。

## Artifact Roles

- `submission.jsonl`: evaluated local submission fixture.
- `summary.txt`: public CP-Bench evaluator summary when available.
- `cp-bench-local-eval-report.json`: normalized guarded report.
- `runtime-profile.json`: command, dependency, timeout, and exit profile.
- `stdout.txt` / `stderr.txt`: evaluator process streams when available.
- `artifact-manifest.json`: SHA-256 artifact index.
