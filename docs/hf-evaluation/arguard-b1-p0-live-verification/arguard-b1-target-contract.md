# ArGuard B1 Live Verification

schema_version: `2026-06-29.arguard-b1-live-verification.v1`
official_scores_claimed: `false`
target_id: `arguard-b1-binary-classification`
verification_status: `verified_with_asset_blockers`

## Claim Boundary

ArGuard B1 target contract only; no Codabench submission, leaderboard score, ranking, or official external result is claimed.

## Target Contract

- platform: `Codabench`
- primary_metric: `macro-F1`
- submission_format: `tsv`
- required_header: `id, label, run_id`
- labels: `safe, unsafe`

## Asset Status

- data_and_scorer: `not_confirmed_released_in_public_readme`

## Hard Blockers

- `released_train_dev_scorer_not_confirmed`

## Checks

- codabench_competition: `reachable` https://www.codabench.org/competitions/16652/
- repository_readme: `reachable` https://raw.githubusercontent.com/araieval/ArGuard-2026-tasks/main/README.md
- task_readme: `reachable` https://raw.githubusercontent.com/araieval/ArGuard-2026-tasks/main/taskB/README.md
