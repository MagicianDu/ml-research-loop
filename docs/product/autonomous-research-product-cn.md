# 成熟稳定自动科研产品目标

本文档定义 ML Research Loop 的成熟稳定自动科研产品目标。它高于 preview MCP product 的推广目标：preview 证明客户端能接入和跑通受控 demo，成熟产品必须证明真实科研闭环可以长期、可恢复、可审计地运行。

## 用户分层

| 用户 | 主要任务 | 产品必须降低的门槛 |
| --- | --- | --- |
| 本科高年级 | 阅读论文、复现实验、理解指标和失败原因 | 给出课程级任务模板、低资源实验、清晰的证据索引和失败解释 |
| 硕博 | 从论文主张生成实验计划，持续迭代模型、数据处理和评测 | 维护长周期 research case，保留假设、证据、patch、结果和停止条件 |
| 科研工程师 | 把研究代码、数据和评测流程产品化，诊断环境和训练失败 | 提供环境 probe、受控 patch、日志解析、rollback 和 proof archive |
| PI/实验室负责人 | 判断项目是否可复查、可教学、可部署和可控成本 | 提供机构 pilot 验收、隐私边界、资源预算、风险记录和汇总报告 |

## 成熟产品定义

成熟稳定自动科研产品不是单次演示脚本，而是一个可被科研团队反复使用的执行层。它应当支持从论文、数据集、代码仓库和已有实验材料出发，拆解研究主张、建立证据索引、运行实验、诊断失败、提出受控 patch、多轮迭代，并输出可复查的报告、artifact hash 和 claim boundary。

成熟稳定自动科研产品的最低定义：

- 每个研究任务都能被表达为可恢复的 long-running case，而不是散落的临时 JSON。
- 每个结果都能追溯到输入、命令、日志、指标、patch 和评审结论。
- 每轮论文复现、实验、patch、失败和 rollback 都能沉淀为可检索的长期研究记忆，而不是只留在一次性 artifact 中。
- 每个对外声明都必须标注证据等级，区分本地 proof、debug fixture、official harness 和人工复核。
- 失败是产品状态的一部分：环境缺失、数据不可用、指标退化、patch 被拒绝和预算耗尽都必须被结构化记录。
- 默认架构保持人类或客户端强模型在环；服务端自主 LLM 只能显式 opt-in。

## 阶段边界

| 阶段 | 可以宣称 | 不能宣称 | 进入下一阶段的条件 |
| --- | --- | --- | --- |
| preview | MCP/Skills 能被 Codex、Claude 等客户端接入；受控 demo、golden path、patch/reproduction scaffold 可运行 | 不能宣称任意论文可无人值守复现，不能宣称本地 proof 是官方 benchmark | 文档、contract、acceptance、release gate 和最小 proof matrix 稳定 |
| beta | 多个真实或半真实 research case 能跨轮次恢复；机构 pilot 可按模板执行；失败和限制能被审计 | 不能宣称已达到机构级多用户 SaaS，也不能宣称自动实验总能提升指标 | pilot 反馈闭环、环境 probe、ResearchCase、proof archive 和回归集稳定 |
| stable | 安装、运行、恢复、升级、artifact 保留和隐私边界都有稳定合约；典型任务有可复查 proof | 不能宣称替代研究者判断，不能把局部 benchmark 结果泛化成所有研究任务能力 | 版本化合约、公开 proof、稳定支持流程、机构级验收和回滚策略完备 |

## 单篇真实论文复现试点

产品进入 beta 前，需要至少跑通一个单篇真实论文复现试点。该试点不是完整 SOTA 复现，而是把一篇公开论文中的一个 bounded claim 转成 ResearchCase，完成环境 probe、最小实验、客户端强模型 handoff、guarded patch 或参数迭代，以及 proof archive。

当前已固化两个受限真实论文试点：`MemFlow: Intent-Driven Memory Orchestration for Small Language Model Agents`（arXiv:2605.03312）验证 memory-routing bounded claim，`Adam: A Method for Stochastic Optimization`（arXiv:1412.6980）验证 optimizer-convergence bounded claim。二者都必须先通过 P0 准入闸门；若任务、metric、数据计划、算法计划或资源预算不满足要求，应被拒绝并保留拒绝报告。当前 proof 已从 fixture-only 提升到 curated public mini-slice，并写出 `dataset-provenance.json` 和 `human-review-report.json`；所有试点输出仍必须保持 `official_scores_claimed=false`，并明确本地公开小样本、替代数据或受限复核都不能当作官方 benchmark。

## 架构职责

- **MCP 服务**：负责可审计执行，包括 research evidence、实验运行、日志读取、patch preflight、rollback、artifact 管理、proof archive 和 compatibility contract。
- **Skills**：负责把 Codex/Claude 的操作流程固化为可复用的研究工作流，声明工具顺序、输入输出、失败恢复和人工确认边界。
- **Research Memory Layer**：负责长期经验复用。项目采用 Graphiti + cognee 作为可选基础设施候选，但必须通过自有 `ResearchMemoryCard` schema、provenance、privacy policy 和 MCP contract 暴露能力。
- **客户端模型**：负责理解用户目标、阅读证据、选择工具、提出下一步实验或代码改动，并在高风险动作前请求确认。
- **服务端 LLM**：默认关闭；只在用户明确选择无人值守或自动规划模式时参与，并且必须记录模型来源、输入边界、预算和人工接管点。

## Proposal Contract 产品入口

成熟产品里的 proposal contract 是 client-side proposal planner contract：
Codex/Claude 作为客户端 planner，MCP 服务端不默认调用大模型。服务端职责是
打包 context、校验 proposal contract、执行 guarded experiment、写 reflection
和归档 memory/proof archive；服务端 LLM 只能作为显式 opt-in 的无人值守能力。

客户端最短验收路径保持为：

`context -> validate -> reflect`

完整链路是：

`build context -> client proposal -> validate -> execute guarded experiment -> reflect -> memory/proof archive`

这一路径对应的产品目标是：快速诊断、生成 proposal、执行受控迭代、识别稳定收益与回滚失败方向。
验收时必须保留 `official_scores_claimed=false`，并用 `dev/canary/holdout`
一致性判断方向是否值得继续。单次本地提升、debug proof、局部 dev gain 或
Codex/Claude review 都不能写成官方成绩，也不能写成稳定产品结论。

## 不能宣称的能力

当前和未来 release 都必须保留以下边界，除非有独立证据链支持：

- 不能宣称任意论文都可以无人值守复现。
- 不能宣称任意模型、数据集或任务的指标都会自动提升。
- 不能宣称本地 fixture、debug proof 或小样本 proof 等同于官方 benchmark 成绩。
- 不能宣称已经替代 PI、审稿人或领域专家的研究判断。
- 不能宣称默认具备机构级多用户权限、队列、计费、审计和数据隔离平台能力。
- 不能宣称服务端 LLM 默认会安全处理私有代码、未公开数据或敏感信息。

## 机构 pilot 验收标准

机构 pilot 应以可复查证据为准，而不是演示观感。一个 pilot 至少应完成：

1. 新环境安装和 MCP 客户端接入，记录 Python、依赖、运行目录、allowed roots 和 release gate 输出。
2. 运行一个课程级或实验室级 bounded research case，生成 evidence、experiment、patch 或 reproduction artifact。
3. 对每个 claim 标注 evidence level，并明确哪些只是本地 proof，哪些接近官方或公开评测。
4. 触发至少一个失败或拒绝路径，例如缺数据、测试失败、patch stale、指标退化或预算耗尽，并验证恢复说明。
5. 输出 pilot report，包含资源消耗、隐私边界、artifact retention、用户反馈和下一步 gap。
6. PI/实验室负责人确认：系统用于辅助科研执行和审计，不替代最终研究判断。
