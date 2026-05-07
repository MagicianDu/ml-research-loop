# PaperBench Official Debug Dummy Result

日期：2026-05-07

本文记录一次官方 PaperBench debug split 的 dummy solver + dummy judge 跑通结果。它证明 ML Research Loop 的 benchmark integration 已经能够准备官方 PaperBench repo/data、启动 Docker/Alcatraz runtime，并走完 rollout、reproduction、grading 三阶段。

## 结论

- Benchmark：PaperBench
- Paper split：`debug`
- Paper sample：`rice`
- Solver：`paperbench.solvers.dummy.solver:PaperBenchDummySolver`
- Judge scaffold：`dummy`
- Run group：`2026-05-07T10-08-00-UTC_run-group_dummy`
- 任务数：`1`
- mean score：`1.0`
- complete tries：`1`
- rollout failures：`0`
- reproduction failures：`0`
- grading failures：`0`
- reproduction mean time：约 `2.06s`
- 产物：`submission.tar.gz`、`submission_executed.tar.gz`、`submission_executed_metadata.json`、`submission_executed_grader_output_0.json`、`grade.json`、`group.log`

## 本轮补齐的官方前置条件

- 成功拉取官方 Frontier Evals / PaperBench repo。
- 成功用 Git LFS hydrate debug 样本 `rice` 的 paper、PDF、rubric 和 assets。
- 成功启动 Docker Desktop，本机 Docker daemon 版本为 `29.4.0`。
- 成功使用本地 `pb-env:latest` 和 `pb-reproducer:latest` image。
- 成功规避当前官方 README 与代码不一致的问题：显式设置 `AlcatrazComputerRuntime`、`LocalConfig` 和 `pull_from_registry=false`。
- reproduction 阶段使用 `AlcatrazComputerRuntimeNoJupyter`，避免 `pb-reproducer:latest` 没有 `python/pip` 命令导致的 Jupyter runtime 检查失败。

## 不能声明的内容

- 这不是 PaperBench 真实论文复现能力分数。
- 这不是 real judge / LLM judge 结果。
- 这不是官方 leaderboard 或公开排名成绩。
- 本轮 judge 是 dummy judge，`score=1.0` 只能说明 harness path 跑通，不能说明复现质量。
- real judge path 仍需要真实 `OPENAI_API_KEY` 或 `GRADER_OPENAI_API_KEY`。

## 本地证据路径

这些路径位于 `.demo_runs`，默认不进入 git；它们用于本机复核和后续整理公开 artifact。

- Run group log：`.demo_runs/hard-results/paperbench-debug-dummy-20260507/runs/2026-05-07T10-08-00-UTC_run-group_dummy/group.log`
- Grade report：`.demo_runs/hard-results/paperbench-debug-dummy-20260507/runs/2026-05-07T10-08-00-UTC_run-group_dummy/rice_4d24d8f3-f350-46ef-9b03-73e889e9cd93/grade.json`
- Agent metadata：`.demo_runs/hard-results/paperbench-debug-dummy-20260507/runs/2026-05-07T10-08-00-UTC_run-group_dummy/rice_4d24d8f3-f350-46ef-9b03-73e889e9cd93/metadata.json`
- Executed metadata：`.demo_runs/hard-results/paperbench-debug-dummy-20260507/runs/2026-05-07T10-08-00-UTC_run-group_dummy/rice_4d24d8f3-f350-46ef-9b03-73e889e9cd93/submissions/2026-05-07T10-08-10-UTC/submission_executed_metadata.json`
- Dummy grader output：`.demo_runs/hard-results/paperbench-debug-dummy-20260507/runs/2026-05-07T10-08-00-UTC_run-group_dummy/rice_4d24d8f3-f350-46ef-9b03-73e889e9cd93/submissions/2026-05-07T10-08-10-UTC/submission_executed_grader_output_0.json`

## 对产品能力的证明

这次结果证明的是 PaperBench 方向的官方 harness 接入能力：

1. 能处理官方 debug paper 的 LFS 数据和 rubric。
2. 能在本地 Docker/Alcatraz runtime 中启动 PaperBench task。
3. 能生成并执行 submission archive。
4. 能走完 reproduction 与 grading 阶段。
5. 能把 run group、task、submission、grade artifacts 留在可审计路径中。

## 下一步

1. 把 PaperBench debug dummy path 封装成 ML Research Loop 的一键 probe/run 工具。
2. 增加 publication guard：dummy judge 的 `score=1.0` 不得进入能力分数宣传。
3. 已补充 Codex-assisted rubric review，对这份 dummy run 形成非官方审查报告，并把结论纳入 proof archive。详见 `docs/evidence/paperbench-codex-review-rice-20260507-cn.md`。
4. 准备真实 grader key 后跑 real judge debug path。
5. 用客户端模型替换 dummy solver，产出第一份真实论文复现尝试。
