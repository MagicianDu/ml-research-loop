# Product Examples

These examples are the supported product smoke flows for Codex and Claude MCP
clients.

## stable template demos

List deterministic templates:

```bash
ml-loop demo list
```

Run the fastest local byte-LM template. The JSON output includes `status`,
`task_id`, `best_metric`, `task_file`, `result_file`, `workspace`, and
`dataset_file`:

```bash
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
ml-loop demo run --template byte-lm-smoke --runtime-root .demo_runs/byte-lm-smoke --json
```

Initialize without running when you want Codex or Claude to inspect and execute
the task through MCP:

```bash
ml-loop demo init --template paper-guided-byte-lm --runtime-root .demo_runs/paper-guided-byte-lm
```

Current templates:

| Template | Use |
| --- | --- |
| `byte-lm-smoke` | Fast one-experiment local byte language-model smoke |
| `byte-lm-depth-sweep` | Two-experiment metric comparison template |
| `paper-guided-byte-lm` | Local byte-LM task with paper evidence and reproduction fields |

## benchmark adapter compatibility

Check which benchmark adapter flows are currently available:

```bash
ml-loop benchmark readiness --json
```

Run the combined compatibility smoke for both MLE-bench-shaped and
PaperBench-shaped flows:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
ml-loop benchmark smoke --runtime-root .demo_runs/benchmark-adapter-smoke --json
```

Probe whether this machine has the official MLE-bench and PaperBench harness
prerequisites. This is read-only and does not download data, build containers,
grade submissions, call APIs, or claim official scores:

```bash
ml-loop benchmark probe --json
```

Build a client-readable proof-run plan from that probe. This is still
read-only: it decides whether an official debug/small proof run is blocked or
ready, lists missing prerequisites, and keeps `official_scores_claimed=false`.

```bash
ml-loop benchmark proof-plan --json
```

Write a setup bundle for the external evaluation environment. The bundle
contains a redacted env example, manual setup commands, official references, and
artifact requirements; it does not install dependencies, download data, write
secrets, or claim official scores:

```bash
ml-loop benchmark setup-bundle --output-dir .demo_runs/proof-setup --json
```

After an external official debug/small run produces artifacts, write a guarded
publication bundle. The manifest should point to command lines, config,
environment, logs, reports, and limitations. If `official_scores_claimed=true`,
the manifest must also include score evidence or the bundle will be blocked:

```bash
ml-loop benchmark publication-bundle \
  --manifest .demo_runs/proof-artifacts/manifest.json \
  --artifact-root .demo_runs/proof-artifacts \
  --output-dir .demo_runs/proof-publication \
  --json
```

Then archive the same complete artifacts with SHA-256 indexes for MCP/client
review:

```bash
ml-loop benchmark archive-proof \
  --manifest .demo_runs/proof-artifacts/manifest.json \
  --artifact-root .demo_runs/proof-artifacts \
  --output-dir .demo_runs/proof-archive \
  --json
```

Run the local MLE-bench-shaped compatibility spike. This produces a fixture
competition, an ML Research Loop task, `submission.csv`, `metadata.json`, and
`benchmark_report.json`; it is explicitly not an official MLE-bench leaderboard
submission and reports `official_mle_bench=false`.

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mle_bench_adapter_demo.py --runtime-root .demo_runs/mle-bench-spike --json
```

Run the deterministic PaperBench-shaped adapter demo. This exercises Agent
Rollout, Reproduction, and Grading with local artifacts, but it is not an
official PaperBench leaderboard submission and always reports
`official_paperbench=false`:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/paperbench_adapter_demo.py --runtime-root .demo_runs/paperbench-adapter --json
```

## synthetic

Run the deterministic synthetic MCP loop:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_golden_path.py --max-experiments 1 --experiment-duration 30
```

## local real-data

Run the reusable fixture task from `examples/tasks/mcp-real-data-task.json` with
a generated local byte dataset:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_real_data_demo.py --max-experiments 1 --experiment-duration 30
```

## local reproduction rubric

Run the deterministic reproduction-readiness and rubric grading smoke. This uses
the local real-data fixture and does not require Docker, GPU, network, or LLM
credentials:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_reproduction_demo.py --max-experiments 1 --experiment-duration 30 --json
```

## paper-guided

Ask the MCP client to call `research_task`, then `propose_hypotheses`, then
`run_hypothesis_experiment`. The planner should inspect `evidence_citations`,
`provider_coverage_gate`, and `code_change_plan.next_experiment_plan` before
using `run_next_experiment_from_review`.

## client patch optimization

When Codex or Claude wants to propose its own one-parameter SEARCH REGION move,
call `run_client_patch_experiment` with a `change_proposal` built from the
latest `experiment_state.current_code.search_region`. Inspect
`patch_execution.mode == "task_patch_only"` and `loop_decision` before the next
round.

Run the repeatable client-patch smoke:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_client_patch_demo.py --max-experiments 1 --experiment-duration 30
```

When Codex or Claude needs to apply a true workspace code diff, call
`apply_client_code_patch` with a workspace-relative unified diff, `allowed_files`,
and a small `test_command`. The repeatable real task/code benchmark validates
this direct patch path against the local real-data fixture:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_real_task_code_benchmark.py --max-experiments 1 --experiment-duration 30
```

## provider quality

Run the provider-quality benchmark pack to verify paper-heavy and dataset-heavy
research payloads include provider counts, cache hits, rate-limit diagnostics,
evidence citations, source rankings, and recovery hints:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
python3 scripts/mcp_provider_quality_benchmark.py
```

## failed-run debugging

When `review_research_results` returns failed experiments, call
`get_experiment_logs`, inspect `failure_summary`, and only then run
`run_next_experiment_from_review` or a patched `run_hypothesis_experiment`.
