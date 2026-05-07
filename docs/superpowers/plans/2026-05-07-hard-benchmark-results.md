# Hard Benchmark Results Acceleration Plan

## Goal

Produce promotion-grade, evidence-backed benchmark artifacts without overstating official leaderboard claims.

## Constraints

- Preserve `official_scores_claimed=false` unless a real official leaderboard or official submission path is completed.
- Keep large benchmark data, generated submissions, logs, and archives under ignored runtime directories unless explicitly publishing an artifact bundle.
- Prefer official harness paths over synthetic compatibility fixtures for public claims.
- Use MCP/CLI proof archive output as the publication gate.

## P0: Lock the first hard MLE-bench result

- [x] Install and verify official MLE-bench CLI in an isolated runtime.
- [x] Prepare `spooky-author-identification` data through official MLE-bench + Kaggle path.
- [x] Run baseline sample-submission round.
- [x] Run at least one client-patch round.
- [x] Produce a patch round that beats the competition median threshold.
- [x] Write proof archive and artifact index.
- [x] Add a Chinese evidence note with claims, limits, and local artifact paths.

## P1: Unblock PaperBench debug proof path

- [x] Hydrate the required Git LFS paper data for the debug split.
- [x] Start Docker Desktop and verify the daemon is available.
- [x] Run official PaperBench debug split with dummy solver and dummy judge.
- [x] Capture commands, config, logs, reports, and limitations.
- [x] Write a PaperBench evidence note parallel to the MLE-bench one.
- [x] Add a keyless Codex-assisted review bundle/report path for PaperBench artifacts.
- [x] Keep real judge claims blocked until `OPENAI_API_KEY` or `GRADER_OPENAI_API_KEY` is available.

## P2: Convert hard results into launch material

- [ ] Add a concise public README section: "What has been proven".
- [x] Add a benchmark evidence index that links all reproducible result notes.
- [ ] Add a short Chinese launch/demo script using the MLE-bench result.
- [ ] Add a reviewer checklist for avoiding unsupported leaderboard claims.

## Current Decision

The project now has one credible MLE-bench proof result: local official scorer feedback improved log loss from `1.08468` to `0.37038`, beating the median threshold `0.418785`.

The project also has one PaperBench official debug dummy proof result: the `rice` debug sample completed rollout, reproduction, and grading with dummy judge score `1.0` and zero rollout/reproduction/grading failures. A true PaperBench judge run remains credential-gated.

The keyless fallback is now honest by design: Codex-assisted rubric review can
audit packet evidence and write a report, but it is not an official PaperBench
score and keeps `official_scores_claimed=false`.
