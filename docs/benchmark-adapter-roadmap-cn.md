# Benchmark Adapter Roadmap

本文说明当前 benchmark adapter 的产品定位：它是 ML Research Loop 从 MCP preview 走向公开研究复现/自动实验评测的桥，不是官方榜单成绩声明。

## 当前已证明

- MLE-bench 方向已经能生成本地 deterministic fixture、任务文件、run-group metadata、`submission.csv` 和 `benchmark_report.json`。
- PaperBench 方向已经能表达 Agent Rollout、Reproduction、Grading 三阶段，并生成 submission、reproduction report、grade report 和 benchmark report。
- `ml-loop benchmark readiness --json` 和 MCP manifest 已经能暴露当前 adapter readiness。
- `ml-loop benchmark smoke --runtime-root <dir> --json` 已经能一条命令跑完两条 compatibility demo。
- 两条路径都复用现有 ML Research Loop 能力：研究/实验 artifact、bounded local execution、reproduction spec、rubric grade report、日志和结果路径。
- 两条路径都明确输出非官方标记：`official_mle_bench=false`、`official_paperbench=false`。
- 这些产物足够让 Codex/Claude 作为客户端 planner 读取状态、定位证据、判断下一轮实验或复现动作。

## 尚未证明

- 尚未接入官方 MLE-bench competition hydration、Docker/环境构建、`mlebench grade` 的真实评分闭环。
- 尚未接入官方 PaperBench paper samples、direct-submission grading、judge/evaluator 环境和官方 rubric 数据。
- 尚未形成可公开复核的 leaderboard 级结果，也不应该把 compatibility spike 的 demo 分数当成 benchmark score。
- 尚未验证长时间、多任务、外部数据下载和失败恢复在官方 harness 下的稳定性。

## 下一步路线

1. **P13: Benchmark Adapter Productization**
   - 已完成统一的 benchmark compatibility smoke，一次跑完 MLE-bench-shaped 和 PaperBench-shaped demo。
   - 已在 CLI 和 MCP manifest 中暴露 benchmark readiness，而不是只靠文档说明。
   - 把两个 benchmark report 打包进 feedback/reproducibility bundle。

2. **P14: Official Harness Feasibility**
   - 增加只读 probe，检查本机是否具备 MLE-bench / PaperBench 官方 harness 的必要条件。
   - 明确依赖：credentials、数据下载、Docker/环境、运行时间、费用和磁盘需求。
   - 决定官方评测应在本机、CI、还是独立 evaluation 环境执行。

3. **P15: Public Proof Run**
   - 先跑官方 debug 或最小公开任务，产出完整命令、配置、日志、报告和限制说明。
   - 再考虑正式 leaderboard 或公开复现声明。
   - 对外传播时只说可复现的事实，不把本地 fixture 分数包装成官方能力证明。

## 与最终目标的关系

最终目标是把项目做成 Codex/Claude 可调用的 MCP + Skills 产品，用客户端强模型做研究判断、代码修改和超参迭代，服务端负责可靠执行和审计。Benchmark adapter 的价值在于把这种能力放到公开可理解的评测形态里：MLE-bench 偏 ML engineering 自动实验，PaperBench 偏论文复现与证据质量。当前集成完成后，项目具备了评测形态的骨架；下一步要补官方 harness 和可复核 proof run。
