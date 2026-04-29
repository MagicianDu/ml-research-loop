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
    guidance = _render_program_md_overrides(task)
    if guidance:
        program = program.rstrip() + "\n\n" + guidance + "\n"
    research_context = _render_research_context(task)
    if research_context:
        program = program.rstrip() + "\n\n" + research_context + "\n"
    return program


def _render_program_md_overrides(task: "TaskDefinition") -> str:
    """Render task-level guidance injected by ml-intern or review feedback."""
    overrides = task.program_md_overrides
    if not (
        overrides.focus_areas
        or overrides.forbidden_changes
        or overrides.hints
    ):
        return ""

    lines = ["## Research Guidance", ""]
    if overrides.focus_areas:
        lines.extend(["### Focus Areas", ""])
        lines.extend(f"- {area}" for area in overrides.focus_areas)
        lines.append("")
    if overrides.forbidden_changes:
        lines.extend(["### Forbidden Changes", ""])
        lines.extend(f"- {change}" for change in overrides.forbidden_changes)
        lines.append("")
    if overrides.hints:
        lines.extend(["### Hints", ""])
        lines.extend(f"- {hint}" for hint in overrides.hints)

    return "\n".join(lines).rstrip()


def _render_research_context(task: "TaskDefinition") -> str:
    """Render ml-intern research context and hypotheses into program.md."""
    if not task.research_context and not task.hypotheses:
        return ""

    lines = ["## Research Context", ""]
    context = task.research_context or {}

    objective = context.get("objective")
    if objective:
        lines.extend(["### Research Objective", objective, ""])

    sources = context.get("sources", [])
    if sources:
        lines.append("### Sources")
        for source in sources:
            source_type = source.get("source_type", "source")
            title = source.get("title", "")
            summary = source.get("summary", "")
            lines.append(f"- [{source_type}] {title}: {summary}")
            if source.get("url"):
                lines.append(f"  URL: {source['url']}")
        lines.append("")

    findings = context.get("findings", [])
    if findings:
        lines.append("### Findings")
        for finding in findings:
            lines.append(f"- {finding.get('finding_id')}: {finding.get('claim', '')}")
            if finding.get("relevance"):
                lines.append(f"  Relevance: {finding['relevance']}")
        lines.append("")

    if task.hypotheses:
        lines.append("## Hypotheses To Validate")
        for hypothesis in task.hypotheses:
            lines.append(f"- {hypothesis.get('hypothesis_id')}: {hypothesis.get('title')}")
            lines.append(f"  Rationale: {hypothesis.get('rationale', '')}")
            for change in hypothesis.get("proposed_changes", []):
                lines.append(f"  Proposed change: {change}")

    return "\n".join(lines)
