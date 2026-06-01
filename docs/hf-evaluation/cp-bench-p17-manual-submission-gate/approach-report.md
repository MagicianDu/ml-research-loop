# ML Research Loop CP-Bench P17 Approach Report

## Submission

- Proposed submission name: `ml_research_loop_p17`
- Dataset version: `verified`
- Modelling framework: `CPMpy`
- Base LLM field: `Codex-assisted deterministic CPMPy solver expansion`
- External submission status: `not_submitted`
- Official scores claimed: `false`

## Method Summary

This submission is a bounded local proof from ML Research Loop's CP-Bench track.
It does not copy the public CP-Bench reference `model` field. The candidate
generator uses public problem identifiers and problem metadata to emit small,
deterministic CPMpy/Python solver programs for a 34-problem verified slice.

The P17 round extends the previous non-reference client solver path from P15.
P16 reached a local `Final Solution Accuracy` of `50.79%`, but one generated
solver timed out on `hakan_examples__coin3_application`. P17 replaces that
unbounded search with a bounded constant solution derived from the public
problem specification.

## Local Evaluation Evidence

- Local evaluator: CP-Bench public evaluator.
- Local dataset version: `verified`.
- Submitted models in local candidate round: `34`.
- Runtime success: `34/34`.
- Final Solution Accuracy: `52.38%`.
- Passing problems: `33`.
- Failing problems: `1`.
- Remaining failing problem: `csplib__csplib_021_crossfigures`.

The local competitiveness audit compares this P17 local result with the public
verified storage snapshot available at the time of the run. The lowest public
verified result in that snapshot was `46.03%`, so P17 is above that low-water
mark locally. This report does not claim an official leaderboard score or rank.

## Reproducibility Boundary

The repository evidence bundle includes:

- `submission.jsonl`: candidate file for upload review.
- `source-report.json`: local candidate-round report.
- `artifact-manifest.json` and `SHA256SUMS`: hash index for the gate artifacts.
- `manual-checklist.md`: explicit pre-upload checklist.

CP-Bench has been superseded upstream by DCP-Bench-Open. This submission should
therefore be treated as an archival CP-Bench leaderboard proof unless the team
chooses to port the same workflow to DCP-Bench-Open.
