# PaperBench Rice Codex-Assisted Review Result

日期：2026-05-07

本文记录一次基于现有 PaperBench official debug `rice` dummy run artifacts 的 Codex-assisted rubric review。它不是官方 PaperBench 分数，而是把已完成的 debug run 证据交给 Codex 按 rubric 审查后，形成的非官方审查报告。

## 结论

- Benchmark：PaperBench
- Paper split：`debug`
- Paper sample：`rice`
- Source run group：`2026-05-07T10-08-00-UTC_run-group_dummy`
- Source run id：`rice_4d24d8f3-f350-46ef-9b03-73e889e9cd93`
- Source judge：`dummy`
- Codex-assisted review score：`0.0`
- PaperBench official score：`null`
- official scores claimed：`false`
- proof archive status：`archivable`
- proof archive artifact count：`14`

## 审查判断

Codex-assisted review 的结论是：这次 run 能证明 official debug harness 的 rollout、reproduction、grading path 跑通，但不能证明论文复现质量。

关键证据：

- `grade.json` 和 `submission_executed_grader_output_0.json` 显示 `judge_type=dummy`，并且 leaf explanation 为 dummy judge 固定给 `1.0`。
- `submission_executed_metadata.json` 显示提交中存在 `reproduce.sh`，但该脚本为空，执行后只产生空 `reproduce.log`、`reproduce.log.creation_time` 和 `venv/`。
- reproduction metadata 显示 `is_valid_git_repo=false`，没有有效提交的复现仓库。
- packet 中没有环境设置代码、policy network、RICE/StateMask/refinement 方法实现、Experiment I-V 输出、表格、图或结果分析。

因此，Codex 审查把 `codex_review_score` 记录为 `0.0`，同时保留 `paperbench_score=null` 和 `official_scores_claimed=false`。

## 本地证据路径

这些路径位于 `.demo_runs`，默认不进入 git；它们用于本机复核和后续整理公开 artifact。

- Review bundle：`.demo_runs/hard-results/paperbench-codex-review-20260507/review-bundle/codex-review-bundle.json`
- Review prompt：`.demo_runs/hard-results/paperbench-codex-review-20260507/review-bundle/codex-review-prompt.md`
- Codex review input：`.demo_runs/hard-results/paperbench-codex-review-20260507/codex-review.json`
- Review report JSON：`.demo_runs/hard-results/paperbench-codex-review-20260507/review-report/codex-review-report.json`
- Review report Markdown：`.demo_runs/hard-results/paperbench-codex-review-20260507/review-report/codex-review-report.md`
- Proof archive JSON：`.demo_runs/hard-results/paperbench-codex-review-20260507/proof-archive/proof-archive.json`
- Proof artifact index：`.demo_runs/hard-results/paperbench-codex-review-20260507/proof-archive/artifact-index.json`
- Publication guard：`.demo_runs/hard-results/paperbench-codex-review-20260507/proof-archive/publication/proof-publication.json`

## 可宣传边界

可以说：

- 项目已能把 PaperBench official debug artifacts 打包成 Codex review packet。
- 项目已能在没有 official real-judge API key 的情况下，生成诚实的 Codex-assisted rubric review。
- 项目已能把 Codex-assisted review report 纳入 proof archive，并通过 publication guard 保留 claim boundary。
- 这次审查发现 dummy run 只有 harness 连通性证据，没有实质论文复现证据。

不能说：

- 不能说这是官方 PaperBench score。
- 不能说这是 leaderboard result。
- 不能说 dummy judge 的 `1.0` 证明论文复现质量。
- 不能说项目已经在 PaperBench real judge 上完成有效论文复现。

## 命令

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 scripts/cli.py benchmark paperbench-codex-review-bundle \
  --run-dir .demo_runs/hard-results/paperbench-debug-dummy-20260507/runs/2026-05-07T10-08-00-UTC_run-group_dummy/rice_4d24d8f3-f350-46ef-9b03-73e889e9cd93 \
  --paper-dir .demo_runs/official-harnesses/frontier-evals-paperbench/project/paperbench/data/papers/rice \
  --output-dir .demo_runs/hard-results/paperbench-codex-review-20260507/review-bundle \
  --json

PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 scripts/cli.py benchmark paperbench-codex-review-report \
  --bundle .demo_runs/hard-results/paperbench-codex-review-20260507/review-bundle/codex-review-bundle.json \
  --review-file .demo_runs/hard-results/paperbench-codex-review-20260507/codex-review.json \
  --output-dir .demo_runs/hard-results/paperbench-codex-review-20260507/review-report \
  --json

PYTHONPATH=.:.venv/lib/python3.13/site-packages /opt/homebrew/Caskroom/miniforge/base/bin/python3 scripts/cli.py benchmark archive-proof \
  --manifest .demo_runs/hard-results/paperbench-codex-review-20260507/proof-artifacts/manifest.json \
  --artifact-root .demo_runs/hard-results/paperbench-codex-review-20260507/proof-artifacts \
  --output-dir .demo_runs/hard-results/paperbench-codex-review-20260507/proof-archive \
  --json
```

## 下一步

1. 用非 dummy solver 产生第一份真实 reproduction attempt。
2. 在具备 `OPENAI_API_KEY` 或 `GRADER_OPENAI_API_KEY` 后跑 official PaperBench real judge debug path。
3. 把 Codex-assisted review 与 real judge report 分开展示，避免把两者混为一个分数。
