---
name: ml-research-loop-tournament-driver
description: Use when a scheduled/cron wake asks you to drive an ML Research Loop tournament job unattended from a job.json file
---

# ML Research Loop Tournament Driver

## Purpose

Drive exactly one wake of an unattended tournament job. All countable
decisions (wakeup budgets, Phase A, stop conditions, notification
idempotency) live in the MCP `tournament` tool's `driver_tick` /
`driver_finish` stages — your job is only the two reasoning touchpoints
(direction generation, per-round proposals) plus pushing the final
notification and deregistering the schedule when the run stops.

## Per-wake procedure

1. Call `tournament` stage=`driver_tick` with `job_file=<the job path from
   your task prompt>`. Branch on `action`:
   - `proceed`: go to step 2.
   - `finalize`: if `pending_action.type == "finalize"`, call stage=`step`
     once (writes report.json), then go to step 3.
   - `phase_a_retry`: call stage=`driver_finish`, then exit quietly (no
     notification, no deregistration — the next wake retries Phase A).
   - `preflight_failed` / `stop_budget_exhausted`: go to step 3.
   - `quiescent`: exit immediately; do nothing.
2. Work loop — repeat until the engine stops, you have executed
   `per_wake_budget.max_rounds` rounds (each stage=`step` on a `run_round`
   pending action counts as one), or the wall clock passes
   `per_wake_budget.deadline_at` (check between actions; never abandon an
   action midway):
   - `pending_action.type == "need_direction_proposals"`: propose K
     mutually distinct direction hypotheses, each from a different
     parameter family for this target (fastText families: n-gram window,
     learning rate, epochs, dimension — all within the engine's allowlist),
     each with a concrete `first_proposal`. Submit via
     stage=`submit_directions`.
   - `need_round_proposal`: call stage=`status`, read that arm's
     `hypothesis` and `history` (its accepted chain), and propose the next
     single change WITHIN that hypothesis. Submit via
     stage=`submit_proposal`. If the tool returns an invalid-proposal
     error, read the message and correct — the engine kills the arm after
     3 consecutive invalid proposals regardless.
   - anything else (`run_round`/`stage_end`/`finalize`): call stage=`step`.
3. Call stage=`driver_finish`. If the result's `notification.required` is
   true and `sent` is false: push the notification (payload text comes from
   `notification.payload` — do not rewrite the numbers), then call
   stage=`driver_finish` with `mark_notified=true`, then deregister this
   job's scheduled task. If deregistration fails, exit anyway — the driver
   self-quenches (future wakes are quiescent and the wakeup cap is a hard
   ceiling).
4. Exit. Never loop past the per-wake budget; the schedule will wake you
   again.

## Failure rules

- A structured error from `driver_tick` itself (unreadable job file):
  best-effort push an error notification, deregister the schedule, exit.
- Never edit state files by hand; every mutation goes through the tool.
- Never claim benchmark results in notifications beyond what
  `notification.payload` states (`official_scores_claimed=false` culture).

## Manual acceptance (not CI)

```bash
# one wake, by hand, against the offline synthetic demo job:
ml-loop tournament driver-tick --job examples/tournament-jobs/synthetic-demo.json --json
# ... drive stages per the procedure above ...
ml-loop tournament driver-finish --job examples/tournament-jobs/synthetic-demo.json --json
```

Real unattended run: create a Claude Code scheduled task whose prompt is
"Use the ml-research-loop-tournament-driver skill to drive
<absolute path to job.json>", with the interval from your budget planning
(e.g. every 30 minutes).
