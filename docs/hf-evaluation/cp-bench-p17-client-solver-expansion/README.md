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
- after: `52.38`
- delta: `52.38`

## Failure Summary

- total: `34`
- passed: `33`
- failed: `1`

## Model Outcomes

- `csplib__csplib_001_car_sequencing`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `csplib__csplib_005_autocorrelation`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `csplib__csplib_008_vessel_loading`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `csplib__csplib_009_perfect_square_placement`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `csplib__csplib_012_nonogram`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `csplib__csplib_015_schurs_lemma`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `csplib__csplib_021_crossfigures`: final_passed: `false`, executed: `true`, consistency: `false`, failure_type: `consistency_or_objective_failed`
- `csplib__csplib_053_graceful_graphs`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `csplib__csplib_084_hadamard_matrix`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__abbots_puzzle`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__added_corners`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__ages_of_the_sons`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__allergy`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__appointment_scheduling`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__archery_puzzle`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__assignment_costs`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__autoref`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__bin_packing`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__cabling`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__candies`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__capital_budget`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__chess_set`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__circling_squares`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__coin3_application`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__coins_grid`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__contracting_costs`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__covering_opl`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__crossword`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__crypta`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__eighteen_hole_golf`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__facility_location`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__fifty_puzzle`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__three_sum`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`
- `hakan_examples__twelve_pack`: final_passed: `true`, executed: `true`, consistency: `true`, failure_type: `none`

## Rollback Evidence

- rollback_required: `false`
- partial_failures_require_followup: `true`

## Leaderboard Competitiveness Audit

- audit: `leaderboard-competitiveness-audit.json`
- local candidate: `52.38`
- current public verified lowest result: `46.03`
- estimated public position if submitted now: `17/18`
- decision: `prepare_manual_submission_gate`

P17 is locally competitive against the current public CP-Bench verified storage
low-water mark, but CP-Bench is archived upstream and no external upload has
been performed. Manual approval and visible external result archival are still
required before claiming any official score or rank.

## Artifact Roles

- `candidate-submission.jsonl`: client-generated candidate submission.
- `candidate-local-eval/`: local evaluator proof bundle for the candidate.
- `cp-bench-candidate-round-report.json`: normalized before/after report.
- `leaderboard-competitiveness-audit.json`: public-result comparison and submit/defer decision.
- `rollback-evidence.json`: rollback and follow-up decision record.
- `artifact-manifest.json`: SHA-256 artifact index.
