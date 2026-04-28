"""
generate_program_md — dynamically generate program.md from TaskDefinition.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lib.task_protocol import TaskDefinition


def generate_program_md(task: "TaskDefinition") -> str:
    """
    Generate complete program.md content from TaskDefinition.
    This is the instruction file given to the AI research agent.
    """

    # Hyperparameter space as JSON
    hp_space_json = json.dumps(
        {k: vars(v) for k, v in task.hyperparameter_space.items()},
        indent=2,
        ensure_ascii=False,
    )

    # Dataset description
    dataset_desc = f"- Name: {task.dataset.name}\n"
    dataset_desc += f"- Path: {task.dataset.path}\n"
    if task.dataset.train_split:
        dataset_desc += f"- Train split: {task.dataset.train_split} samples\n"
    if task.dataset.val_split:
        dataset_desc += f"- Val split: {task.dataset.val_split} samples\n"

    # Metric description
    metric_desc = f"- Metric: {task.metric.name}\n"
    metric_desc += f"- Direction: {task.metric.direction.value} (lower is {'better' if task.metric.direction.value == 'minimize' else 'worse'})\n"
    if task.metric.threshold:
        metric_desc += f"- Target: {task.metric.threshold}\n"

    # Objective
    direction_word = "minimize" if task.metric.direction.value == "minimize" else "maximize"
    objective = f"{direction_word} {task.metric.name}"

    program = f"""# Research Agent Instructions

You are an autonomous ML researcher running experiments on a GPT model.

## Current Objective
{objective}

## Dataset
{dataset_desc}

## Optimization Metric
{metric_desc}

## Hyperparameter Search Space
```json
{hp_space_json}
```

## Constraints
- **ONLY edit** the section between `# ======= AUTORESEARCH SEARCH REGION START =======` 
  and `# ======= AUTORESEARCH SEARCH REGION END =======` in `train.py`
- **DO NOT edit** `prepare.py` or any other file
- Each experiment must finish within **{task.budget.experiment_duration_seconds // 60} minutes**
- Maximum **{task.budget.max_experiments} experiments** total
- Target: reach {objective}

## Experiment Protocol
1. Read `train.py` and understand the current architecture
2. Identify ONE improvement to make within the search region
3. Implement the change
4. Run training: `python train.py`
5. Parse the validation metric from stdout (look for `val_bpb=` or `val_loss=`)
6. If metric improved: keep the change, propose next improvement
7. If metric worsened: revert the change, try a different approach
8. Log every experiment to `experiment_log.json`

## Output Format
After each experiment, the system will automatically:
- Accept/reject based on metric improvement
- Record the result
- Update progress

## Success Criteria
- Reach the target metric OR complete max experiments
- Log all experiments with params, metric, and accept/reject status

## Important Notes
- Be systematic: change one thing at a time
- If stuck (no improvement after 5 experiments), try a different category:
  - Architecture (depth, width, attention)
  - Optimizer (lr, weight decay, optimizer type)
  - Training schedule (lr decay, warmup, batch size)
- Prioritize changes with highest expected impact

Start now. Analyze train.py first.
"""
    return program
