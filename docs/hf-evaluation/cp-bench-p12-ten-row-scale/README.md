# CP-Bench Candidate Round

status: `improved`
decision: `candidate_improved`
official_scores_claimed: `false`
external_submission_status: `not_submitted`
manual_submission_required: `true`
framework: `CPMpy`
dataset_version: `verified`

## Claim Boundary

CP-Bench candidate-round artifact only; it records local evaluator feedback for a client-generated candidate and does not upload to Hugging Face or claim leaderboard scores.

## Metric Comparison

- metric: `final_solution_accuracy_percent`
- before: `0.0`
- after: `15.87`
- delta: `15.87`

## Failure Summary

- total: `10`
- passed: `10`
- failed: `0`

## Model Outcomes

- `csplib__csplib_001_car_sequencing`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `csplib__csplib_005_autocorrelation`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `csplib__csplib_008_vessel_loading`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `csplib__csplib_009_perfect_square_placement`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `csplib__csplib_012_nonogram`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `csplib__csplib_015_schurs_lemma`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `csplib__csplib_021_crossfigures`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `csplib__csplib_053_graceful_graphs`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `csplib__csplib_084_hadamard_matrix`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__abbots_puzzle`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`

## Rollback Evidence

- rollback_required: `false`
- partial_failures_require_followup: `false`

## Artifact Roles

- `candidate-submission.jsonl`: client-generated candidate submission.
- `candidate-local-eval/`: local evaluator proof bundle for the candidate.
- `cp-bench-candidate-round-report.json`: normalized before/after report.
- `rollback-evidence.json`: rollback and follow-up decision record.
- `artifact-manifest.json`: SHA-256 artifact index.
