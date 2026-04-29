# Next Experiment Plan Design

## Goal

Make the autoresearch side more useful to Codex/Claude by turning `code_change_plan` from a target hint into a concrete, machine-readable next-experiment plan.

## Scope

This is an additive planner-handoff increment. It does not change how experiments are executed, does not add implicit server-side LLM calls, and does not edit `train.py` automatically.

## Behavior

- `experiment_state.code_change_plan` keeps existing fields for compatibility.
- For tunable runs, it adds `next_experiment_plan`.
- The plan includes:
  - `mode`: the experiment strategy mode, such as `local_refinement` or `revise_search_space`.
  - `metric`: name, direction, and current best value when available.
  - `target_param`: the SEARCH REGION variable selected for the next one-parameter edit.
  - `current_value`: the current value from `train.py`.
  - `candidate_values`: bounded values from `recommended_search_space.parameter_hints`.
  - `best_params`: the current best parameter set.
  - `stop_conditions`: copied from `experiment_strategy`.
  - `edit_policy`: the fixed safe-edit constraints.
  - `rationale`: short deterministic explanation for the client model.
- If a dataset path must be fixed, code inspected, or failures debugged first, `next_experiment_plan` is omitted and existing action gating still applies.

## Testing

- A clean completed run with a best result and recommended search space exposes `next_experiment_plan`.
- Existing dataset-fix, failure-debug, planner action, and release gates continue to pass.
