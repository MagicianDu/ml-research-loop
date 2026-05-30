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
- after: `3.17`
- delta: `3.17`

## Model Outcomes

- `csplib__csplib_001_car_sequencing`: final_passed: `true`, executed: `true`, consistency: `true`
- `csplib__csplib_005_autocorrelation`: final_passed: `false`, executed: `true`, consistency: `false`
- `csplib__csplib_008_vessel_loading`: final_passed: `true`, executed: `true`, consistency: `true`

## Artifact Roles

- `candidate-submission.jsonl`: client-generated candidate submission.
- `candidate-local-eval/`: local evaluator proof bundle for the candidate.
- `cp-bench-candidate-round-report.json`: normalized before/after report.
- `artifact-manifest.json`: SHA-256 artifact index.
