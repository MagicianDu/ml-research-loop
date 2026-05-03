# Automatic Experiment Intelligence P9

**Goal:** Make the MCP loop more useful for Codex/Claude planners by turning
experiment-tree state, reproduction readiness, and guarded code-patch execution
into explicit next-step decisions.

**Scope**

- Strengthen `ExperimentTree.recommended_next_action` so failures, fresh
  improvements, stale/non-improving runs, and empty runs are distinguishable.
- Add a fused `experiment_state.loop_policy` that can stop the loop when
  reproduction requirements are missing or unsafe, before running more trials.
- Let planner actions surface reproduction blockers as first-class client-edit
  work.
- Extend `apply_client_code_patch` so multi-file bounded diffs can include a
  post-patch review and a metric-aware `loop_decision`.
- Update the real-task code benchmark to exercise a multi-file patch and return
  the post-patch review through the patch tool.

**Acceptance**

- Failed, improved, non-improving, and reproduction-blocked states produce
  different action categories and stop reasons.
- `run_next_experiment_from_review` / client patch loop decisions include a
  machine-readable reason category.
- `apply_client_code_patch` reports multi-file `changed_files`, syntax/test
  preflight, rollback state, optional `post_patch_review`, and `loop_decision`.
- Focused unit tests, affected integration tests, and the release gate pass.

**Tasks**

- [x] Add failing experiment-tree policy tests.
- [x] Add failing fusion loop-policy tests for reproduction blockers.
- [x] Add failing MCP service tests for metric-aware loop decisions and
      multi-file post-patch review.
- [x] Implement experiment-tree action categories.
- [x] Implement fused loop policy and planner action routing.
- [x] Extend direct code patch schema and response.
- [x] Update real-task code benchmark and product docs.
- [x] Run focused tests, release gate, review diff, stage, and commit.
