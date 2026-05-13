# MemFlow 单篇真实论文复现试点

本文档记录 `MemFlow: Intent-Driven Memory Orchestration for Small Language Model Agents`（arXiv:2605.03312）作为单篇真实论文复现试点的候选方案。它不是完整复现承诺，而是 P0 选题闸门、P1 ResearchCase 绑定和 P2 环境检查的人工可读说明。

## 论文信息

| 字段 | 内容 |
| --- | --- |
| 论文 | MemFlow: Intent-Driven Memory Orchestration for Small Language Model Agents |
| 标识 | arXiv:2605.03312 |
| 候选定位 | 小模型 agent 的意图驱动记忆编排 |
| 试点类型 | 单篇论文 bounded claim 复现 |
| 官方成绩声明 | `official_scores_claimed=false` |

## 为什么选择这篇论文作为候选

这篇论文与 ML Research Loop 的产品目标贴合：它关注 agent、记忆、检索、任务效果和迭代式系统设计，天然适合作为“论文理解 -> 最小实验 -> 客户端强模型提出改动 -> MCP 执行和归档”的试点对象。

但它仍必须通过 P0 准入闸门。只有在确认任务、metric、数据计划、算法实现计划和本机预算都足够明确后，才能进入真实实验闭环。

## 目标 Claim

试点只关注一个 bounded claim：

> 在一个小型、可公开或 fixture-backed 的任务上，意图驱动的记忆/证据路由比简单基线更能选择与问题相关的上下文，从而提升指定 metric。

该 claim 是局部工程复现目标，不等同于原论文完整主张。

## 不复现的内容

本试点不复现：

- 原论文全部实验表格。
- 原论文可能使用的完整 benchmark 集合。
- 大模型或长时 GPU 训练流程。
- 官方 leaderboard 或官方 benchmark 成绩。
- 多论文 idea 融合创新。

## Metric

默认 metric 为 `accuracy` 或等价的任务成功率。若后续读取论文和代码后发现原始 metric 更适合本机短时复现，应在 `paper-selection-report.json` 中替换，并解释原因。

Metric 必须满足：

- 可由脚本稳定计算；
- 输出为 JSON；
- 有明确方向，例如 `higher_is_better`；
- 不冒充原论文官方指标。

## 数据计划

优先级如下：

1. 使用论文或代码明确引用的公开小型数据。
2. 使用公开 benchmark 的小切片。
3. 使用 curated public mini-slice；如果公开切片不可用，再降级为 fixture-backed substitute dataset。

当前 P7 proof 使用项目内置的 curated public mini-slice。该切片由 arXiv 公开论文信息和 abstract-level 描述人工转写为小型意图路由样例，不保存论文原文长摘录。它可以作为产品执行闭环 proof，但不能作为原论文官方结果。

如果降级使用替代数据，所有报告必须写明：

```json
{
  "substitute_data": true,
  "official_scores_claimed": false
}
```

## 最小实验设计

最小实验只需要证明产品闭环，而不是证明原论文完整结论：

1. 建立 simple baseline：不做意图路由，使用固定顺序或简单相似度选择上下文。
2. 建立 MemFlow-shaped ablation：增加轻量 intent/router 规则或可解释的上下文选择策略。
3. 在同一份小数据上计算同一 metric。
4. 输出 `baseline-metrics.json`、`ablation-metrics.json` 和 `iteration-comparison.json`。

## 资源预算

默认预算：

- 单次实验不超过 15 分钟。
- 默认 CPU 可运行。
- 不依赖私有 API key。
- 不要求下载大模型权重。
- 网络下载必须显式启用。

若超过预算，本论文只能进入分析报告或后续重资源复现计划，不能作为当前真实试点。

## 风险和替代方案

| 风险 | 处理 |
| --- | --- |
| 原论文数据或代码不可直接使用 | 切换到小型公开切片或 fixture-backed substitute dataset。 |
| 原始 metric 不适合短时本机实验 | 使用局部任务 metric，并明确不能对应原论文主表。 |
| 算法描述不足 | 降级为 MemFlow-shaped ablation，不宣称复现完整算法。 |
| 指标无提升 | 记录失败复盘；产品仍可验证可执行、可审计、可迭代能力。 |
| 证据不足 | 不进入宣传证据索引，只进入失败案例库。 |

## 验收口径

进入实验前必须有：

- `paper-selection-report.json`
- `ResearchCase`
- `environment-probe.json`
- 明确的 forbidden claims

实验完成后至少应有：

- `baseline-metrics.json`
- `client-handoff.json`
- `iteration-comparison.json`
- `proof-manifest.json`

只有这些 artifact 都存在且 `official_scores_claimed=false`，才能把本试点纳入产品 proof archive。

## 当前 P7 公开小切片命令

默认 release gate 使用公开小切片跑通 baseline：

```bash
python3 scripts/real_paper_reproduction_pilot.py \
  --paper-id arxiv:2605.03312 \
  --output-dir .demo_runs/real_paper_pilot/memflow \
  --run-baseline \
  --use-public-mini-slice \
  --json
```

该命令会写出：

- `paper-selection-report.json`
- `research-case.json`
- `environment-probe.json`
- `baseline-metrics.json`
- `ablation-metrics.json`
- `experiment-summary.json`
- `dataset-provenance.json`
- `run-log.txt`
- `client-handoff.json`

当前公开小切片只用于验证产品闭环：baseline 使用简单首条记忆选择，ablation 使用意图匹配路由。即使本地 metric 提升，也只能说明该 bounded pipeline 可执行、可审计、可交给 Codex/Claude 继续决策，不能说明已经复现原论文完整结果。

## 当前 P7 受控迭代命令

baseline 完成后，可以运行一次客户端建议形态的受控配置 patch：

```bash
python3 scripts/real_paper_reproduction_pilot.py \
  --paper-id arxiv:2605.03312 \
  --output-dir .demo_runs/real_paper_pilot/memflow \
  --run-iteration \
  --use-public-mini-slice \
  --json
```

该命令要求同一 `output-dir` 下已经存在 `baseline-metrics.json`。它会写出：

- `client-routing-patch.json`
- `patched-metrics.json`
- `iteration-comparison.json`

当前 patch 范围限制为 `routing heuristic configuration`，不会修改仓库源码。`iteration-comparison.json` 只比较本地公开小切片 metric，下一步仍应扩展到更大的公开切片或官方 debug harness。

## 当前 P8 复核报告命令

baseline/iteration 完成后，先写出受限复核报告：

```bash
python3 scripts/real_paper_reproduction_pilot.py \
  --paper-id arxiv:2605.03312 \
  --output-dir .demo_runs/real_paper_pilot/memflow \
  --write-review-report \
  --reviewer local-operator \
  --review-decision approved_with_limitations \
  --json
```

该命令会写出 `human-review-report.json`，记录 reviewer、review status、artifact checklist、允许的 bounded public claim、被阻断的 official benchmark/full reproduction/SOTA claim，以及“更强声明仍需要人工复核”的边界。

## 当前 P8 Proof Archive 命令

baseline/iteration/review 完成后，可以把本地 artifacts 固化为 proof archive 和公开声明索引：

```bash
python3 scripts/real_paper_reproduction_pilot.py \
  --paper-id arxiv:2605.03312 \
  --output-dir .demo_runs/real_paper_pilot/memflow \
  --archive-proof \
  --proof-dir proof_runs/real-paper-pilot/memflow \
  --update-evidence-index \
  --json
```

该命令会写出：

- `proof_runs/real-paper-pilot/memflow/proof-manifest.json`
- `proof_runs/real-paper-pilot/memflow/artifacts/*`
- `docs/evidence/real-paper-pilot-index.json`
- `docs/evidence/public-claims-map.json`

`proof-manifest.json` 保存 artifact role、归档路径、sha256、metric summary、命令、环境、dataset provenance、human review 和 limitations。`public-claims-map.json` 只有在 `review_status=approved_with_limitations` 时才允许“bounded real-paper pilot with auditable local public-slice artifacts”；“完整复现 MemFlow 或取得官方 benchmark/SOTA 成绩”被显式阻断。

fixture-only 路径仍可用于本地开发 smoke test，但必须显式使用 `--use-fixture-data`，并且 proof strength 只能是 `local_substitute_data`。
