# Proposal Prompt 与自动实验迭代方法调研

日期：2026-05-21
分支：`codex/proposal-methods-research`
范围：调研是否已有论文或 GitHub 项目讨论“由 Codex/Claude/LLM 根据实验 artifacts 提出下一轮改进 proposal，再由系统执行、评分、回滚、沉淀经验”的方法。覆盖 prompt 优化、ML 实验 agent、自动科研、代码进化和记忆/多 agent 方向。

## 结论先行

这个方向已有明确相关工作，不是孤立想法。最接近本项目目标的组合是：

1. `OPRO / PromptAgent / PromptBreeder / GEPA / TextGrad`：证明 LLM 可以根据历史候选、分数、错误反馈生成更好的 prompt 或文本组件。
2. `AIDE / MLAgentBench / MLE-bench / DS-Agent`：证明 ML 实验可以被建模成 agent 读写代码、运行实验、分析结果、继续迭代的闭环。
3. `The AI Scientist / CodeScientist / Agent Laboratory`：证明科研流程可以拆成文献、假设、实验、报告、review，但它们通常更偏“生成研究产物”，不一定适合直接作为稳定产品内核。
4. `FunSearch / OpenEvolve / CORAL`：证明 LLM + evaluator + population/evolution/search 能降低纯 prompt 一步建议的随机性。
5. `Auto Research with Specialist Agents Develops Effective and Non-Trivial Training Recipes` 与 `karpathy/autoresearch`：最贴近我们现在要做的“proposal、code diff、真实实验、失败标签、反馈塑造下一步”的产品形态。

因此，我们应该设计一个 **Proposal Prompt Contract**，但不要把它理解成普通 prompt。它应该是一个“客户端大模型规划器协议”：Codex/Claude 负责基于 artifacts 生成结构化 proposal，MCP 服务负责执行、评分、归档、回滚和记忆更新。后续可以吸收 GEPA/TextGrad 的反思机制、AIDE 的树搜索、DS-Agent 的 case-based memory、CORAL 的多 worktree 协作，但第一版应保持受控、可验收。

## 相关工作地图

| 类别 | 代表工作/项目 | 核心方法 | 对本项目的启发 | 直接复用判断 |
| --- | --- | --- | --- | --- |
| LLM-as-optimizer | OPRO | prompt 中放历史候选和分数，让 LLM 生成下一批候选 | proposal prompt 应包含历史 proposal、指标和失败原因 | 可吸收方法，不必直接依赖代码 |
| 反思式 prompt evolution | GEPA | 基于轨迹、工具输出、错误反馈做自然语言反思和 Pareto 演化 | 我们可把 failure cases、dev/canary delta、rollback reason 作为 textual feedback | 高价值，可后续做 adapter |
| 文本梯度 | TextGrad | 用 LLM 反馈作为“文本梯度”优化 prompt、代码等变量 | 可把 scorer/judge 的失败解释转成 proposal 的改进梯度 | 可借鉴 API 思路，谨慎引入依赖 |
| 搜索式 prompt agent | PromptAgent | MCTS 搜索 prompt 状态，基于错误反馈优化 | proposal 不应只线性迭代，可保留候选树 | 可吸收树搜索结构 |
| 自进化 prompt | PromptBreeder | 同时进化 task prompt 和 mutation prompt | proposal prompt 本身可以版本化和优化 | 后续研究项，不作为 P0 |
| ML 实验 agent | MLAgentBench | agent 读写文件、运行实验、检查输出并改进模型 | 明确实验 agent 的能力边界和失败点 | 用作评测/设计参考 |
| 代码空间树搜索 | AIDE | 把 ML engineering 建模为代码空间 tree search；metric feedback 指导剪枝 | 与我们“proposal -> patch -> eval -> rollback”高度一致 | 架构强相关，可深挖但不生搬硬套 |
| Kaggle/ML agent benchmark | MLE-bench | 75 个 Kaggle 任务评测 ML engineering agent | 可用于后续外部证明路径；也提示污染和资源问题 | 作为评测目标而非内核 |
| Case-based data science | DS-Agent | 用 Kaggle case memory 指导实验计划和代码生成 | 与 Graphiti/cognee 记忆系统天然契合 | 可复用 case-based reasoning 模式 |
| 自动科研 | The AI Scientist | idea/code/experiment/visualization/paper/review 全流程 | 说明端到端可行，但容易过度承诺 | 吸收 review 和 claim boundary，不直接照搬 |
| 代码实验科研 | CodeScientist | 论文片段 + codeblock 的 genetic search，重视 code review/replication | 多论文 idea 融合可借鉴“文献片段 + action codeblock”组合 | 适合中长期路线 |
| LLM + evaluator 程序搜索 | FunSearch | frozen LLM 生成程序，evaluator 防幻觉，保留多样性 | 强调“可执行 evaluator 是核心”，不是 LLM 自说自话 | 架构原则可复用 |
| 代码进化 agent | OpenEvolve | LLM 生成代码变体，evaluator pool/程序库/岛模型保留多样性 | 后续做代码级 recipe search 时可参考 | 可作为 P3/P4 参考，不宜先引入 |
| 极简自动实验闭环 | karpathy/autoresearch | agent 改训练脚本，短训练，metric 判断，keep/discard | 与当前项目 autoresearch 侧一致，是最小闭环基线 | 已吸收，应继续产品化 |
| Specialist auto-research | Auto Research with Specialist Agents | 每个 trial 带 hypothesis、code edit、evaluator outcome、feedback、failure labels | 与我们要做的 proposal contract 最贴近 | 高优先级参考 |
| 多 agent 自进化基础设施 | CORAL | 多 worktree、多 agent、共享状态、grader daemon、heartbeat 反思 | 与 Codex/Claude 多客户端 + MCP 执行架构相近 | 后续多 agent scale 参考 |

## 关键发现

### 1. 只写一个“更聪明的 prompt”不够

OPRO、PromptAgent、GEPA、TextGrad 都说明：LLM 能生成更好的下一步候选，但效果依赖三件事：

- 历史候选和分数必须结构化；
- 失败反馈必须可读、可定位；
- 候选必须经过外部 evaluator，而不是由 LLM 自己判断成功。

这意味着本项目的 proposal prompt 应该只负责“提出候选”，不能负责“宣布成功”。成功与否必须由 MCP 的评测、dev/canary/holdout gate、rollback 逻辑决定。

### 2. 当前最匹配的是“closed empirical loop”，不是“自动写论文”

The AI Scientist 和 Agent Laboratory 覆盖完整科研流程，但它们的目标更接近生成 paper/research report。本项目的商业价值更应该先落在：

- 给定真实任务；
- 找到 baseline；
- 生成可执行 proposal；
- 运行真实实验；
- 判断是否稳定提升；
- 保留失败和回滚证据；
- 把经验进入记忆系统；
- 再指导下一轮。

这与最新 auto-research specialist agents 的表述高度一致：输出不是单个 checkpoint 或论文，而是可审计的 proposal、code diff、实验、分数和失败标签轨迹。

### 3. AIDE 的树搜索比线性循环更适合后续扩展

当前我们手动跑的 `p3-dev-v2 -> semantic-v1 -> semantic-v2` 本质上还是线性探索。AIDE 和 PromptAgent 提醒我们：当候选变多时，需要树或 Pareto frontier，而不是只保留一个“当前版本”。

第一版可以继续线性 5 轮，但 artifact schema 应预留：

- `parent_proposal_id`
- `proposal_family`
- `mutation_source`
- `score_delta`
- `rollback_reason`
- `promote_to_default`
- `continue_branch`

这样后面可以自然演进到 tree search。

### 4. 记忆系统不是附加功能，而是 proposal 质量的核心

DS-Agent 的 case-based reasoning、GEPA 的轨迹反思、CORAL 的共享状态都指向同一个结论：下一轮 proposal 的质量取决于系统能否复用过去经验。

对本项目来说，Graphiti/cognee 这类记忆层应该服务于 proposal prompt：

- 检索相似论文复现案例；
- 检索相似失败类型；
- 检索过去有效的 prompt/profile/routing/训练 recipe；
- 检索副作用和回滚原因；
- 把这些以 evidence cards 的形式喂给 Codex/Claude。

### 5. 失败标签必须一等公民化

多篇工作都强调 evaluator feedback。对我们尤其重要的是失败不应该只是 log，而应成为 proposal prompt 的输入：

- `metric_regression`
- `canary_not_confirmed`
- `h_axis_drop`
- `overfit_to_dev`
- `runtime_error`
- `timeout`
- `invalid_patch`
- `too_broad_change`
- `leakage_risk`
- `cost_too_high`

这些标签可以让 Codex/Claude 不再重复同类错误，也能支撑产品宣传里的“可审计自动迭代”。

## 推荐吸收路径

### P0：先做 Proposal Prompt Contract

目标：把 Codex/Claude 的 proposal 输出变成可验证 JSON，而不是自由文本建议。

建议字段：

```json
{
  "proposal_id": "round-005-confidence-calibration-v1",
  "hypothesis": "短句假设，必须能被一个实验验证",
  "evidence_used": [
    {
      "artifact": "dev_report",
      "observation": "confidence_calibration 类别失败率高",
      "metric": "category_score_delta"
    }
  ],
  "change_surface": "prompt_profile | routing | decoding | data | training_recipe | code_patch | model_choice",
  "change_spec": {
    "single_primary_variable": true,
    "target_file_or_profile": "p3-dev-v2",
    "allowed_scope": "只修改 confidence calibration prompt block"
  },
  "expected_effect": {
    "primary_metric": "SHIFT",
    "target_categories": ["confidence_calibration"],
    "expected_direction": "increase",
    "acceptable_tradeoff": "H 不下降超过 1.0"
  },
  "validation_plan": {
    "first_split": "dev",
    "promotion_split": "canary",
    "max_rounds": 1,
    "rollback_if": ["H_drop_gt_1", "SHIFT_delta_lt_0", "failure_count_increase_gt_2"]
  },
  "risk_assessment": {
    "overfit_risk": "medium",
    "leakage_risk": "low",
    "runtime_cost": "low"
  },
  "next_if_success": "promote_candidate_profile",
  "next_if_failure": "rollback_and_try_training_data_route",
  "claim_boundary": "local diagnostic proposal only; no official score claimed"
}
```

### P1：把 proposal prompt 与 MCP artifact 串起来

输入不应该是自然语言聊天记录，而应该是 MCP 输出的 artifact bundle：

- baseline report；
- dev/canary report；
- category deltas；
- failure samples；
- previous proposal history；
- rollback summary；
- memory cards；
- budget/resource constraints；
- allowed action space。

Codex/Claude 在客户端读取这些 artifact 后生成 proposal JSON。MCP 校验 schema、执行安全检查、跑实验并写回结果。

### P2：加入反思与记忆增强

每轮完成后生成 `proposal_reflection.md/json`：

- 这轮假设是否成立；
- 实验结果是否支持继续；
- 失败属于哪个类型；
- 是否出现副作用；
- 这条经验应该写入记忆库的哪种 card；
- 下一轮应继续同分支、切换分支还是扩大 action space。

这一步吸收 GEPA/TextGrad/DS-Agent，但保持本项目已有 MCP 边界。

### P3：从线性循环升级为小规模树搜索

当 P0-P2 稳定后，再引入：

- proposal family；
- parent/child；
- best-so-far；
- Pareto frontier；
- diversity constraint；
- branch budget；
- canary promotion gate。

这一步吸收 AIDE、PromptAgent、OpenEvolve/FunSearch 的思想。

## 对本项目架构的直接影响

当前“Codex/Claude + MCP + skills + memory”的混合架构方向是正确的，但需要明确职责：

- Codex/Claude：读取 artifacts、做高层推理、生成 proposal、做代码 review。
- Skills：把任务流程固化成客户端可执行 SOP，例如“读报告 -> 生成 proposal -> 调 MCP -> 审查结果”。
- MCP：负责工具、执行、评分、artifact、schema validation、rollback、proof archive。
- Graphiti/cognee memory：负责跨任务经验检索和失败模式复用。
- 本地/远端 evaluator：负责真实 metric，不让 LLM 自评替代实验。

这样设计的差异性在于：我们不是单纯做 prompt optimizer，也不是单纯做自动科研 demo，而是做“面向研究复现和模型效果持续提升的证据闭环产品”。

## 客户端验收路径

本项目第一版 proposal contract 应明确为 client-side proposal planner contract。
它的目标是让 Codex/Claude 用户按
`context -> validate -> reflect` 的最短链路试跑：

`build context -> client proposal -> validate -> execute guarded experiment -> reflect -> memory/proof archive`

职责边界如下：

- Codex/Claude 在客户端阅读 context bundle，生成结构化 proposal JSON。
- MCP 服务端打包 context、校验 proposal contract、执行 guarded experiment、写
  reflection、归档 memory/proof archive。
- MCP 服务端不默认调用大模型；服务端 LLM 只在用户显式选择无人值守工具时启用。
- 默认 `official_scores_claimed=false`，本地 diagnostic gain、dev 局部提升或 proof
  bundle 都不能描述成官方成绩。
- 路线判断必须看 `dev/canary/holdout` 的一致性；单次本地提升只能说明候选方向，
  不能包装成稳定产品结论。

这个 contract 服务的产品目标不是“提交某个榜单分数”，而是：
快速诊断、生成 proposal、执行受控迭代、识别稳定收益与回滚失败方向。
验收入口可使用即将固化的 `scripts/proposal_contract_smoke.py` 和
`examples/proposal-contract/`；在脚本尚未就绪时，可用同名 CLI/MCP 工具按上述
链路手动执行。

## 需要避免的误区

1. 不要让 Codex 直接“判断自己提出的方案成功了”。成功只能来自 evaluator。
2. 不要把 dev split 的短期提升包装成稳定路线。必须有 canary/holdout。
3. 不要一开始就做大规模自动树搜索。先把 proposal contract 和 artifact 质量做好。
4. 不要把 The AI Scientist 式自动写论文当成当前产品主线。它是中长期能力，不是 P0。
5. 不要让 memory 只做语义搜索。它必须能返回可执行经验：改了什么、为什么改、指标怎么变、为什么失败。

## 建议下一步

1. 在当前调研分支继续写一份 `Proposal Prompt Contract` 设计文档。
2. 从 Smol WorldCup/Qwen3 现有 artifacts 中整理一个输入样例。
3. 手工让 Codex 按 contract 生成 3 个 proposal，验证 schema 是否足够约束。
4. 再决定是否实现 CLI/MCP 工具，例如：
   - `build_proposal_context`
   - `validate_client_proposal`
   - `run_smol_worldcup_proposal_round`
   - `write_proposal_reflection`
5. 后续再考虑是否引入 GEPA/DSPy 或 AIDE tree-search 作为可选后端。

## 2026-05-21 实现状态补充

本轮已把调研建议推进为 preview/new workflow：

- 新增 proposal contract 核心库，负责 context bundle、proposal validation 和
  reflection artifact。
- 新增 CLI 入口 `ml-loop proposal context|validate|reflect|search`。
- 新增 MCP 工具 `build_proposal_context`、
  `validate_client_proposal_contract`、`write_proposal_reflection`、
  `summarize_proposal_search`。
- 新增 Smol WorldCup 专用 proposal 执行入口
  `run_smol_worldcup_proposal_round`，用于把已校验 proposal 接到本地
  OpenAI-compatible 模型评测、evaluation、reflection 和 summary。
- 新增 proposal reflection -> research memory card 同步入口：
  `write_proposal_reflection(memory_store=...)` 和
  `ml-loop proposal reflect --memory-store`。Graphiti/cognee 仍是显式
  opt-in adapter，不作为默认服务端智能。
- 新增真实 Smol WorldCup/Qwen3 本地诊断样例
  `examples/proposal-contract/smol-qwen3/`，用于构造 context bundle 与
  proposal round 验收。
- 新增小规模 proposal frontier helper，输出 best candidate、
  rollback proposals、continue branches 和 claim boundary。该能力吸收
  AIDE/PromptAgent 的树搜索思想，但当前仍是轻量 summary，不是大规模自动搜索。
- 更新客户端文档与 skills SOP。
- context bundle 显式支持 baseline/current/dev/canary、category deltas、
  failure samples、rollback summary、previous proposals、memory cards 和资源约束。
- context/reflection artifacts 默认拒绝覆盖，避免失败 proposal 与 rollback 证据被后续运行静默抹掉。

这些能力仍是 preview，不是 release/stable 公共契约。客户端每次会话仍必须先
调用 `get_service_manifest`，确认工具实际存在、契约版本已知、兼容性通过后再执行。

已经固化进客户端文档和 skills 的约束如下：

- 新一轮 proposal 之前先基于当前 artifacts 构造 context bundle，不能只凭聊天记录
  或记忆印象提出方案。
- Codex/Claude 输出的是结构化 proposal JSON，不执行实验、不自评成功、不声明官方分数。
- proposal 执行前必须经过 schema、allowed action space、
  `single_primary_variable=true` 和 claim boundary 校验。
- 校验通过后才允许进入 `run_client_patch_experiment`、
  `apply_client_code_patch`、`run_fasttext_multi_proposal_loop` 等 guarded MCP
  执行工具。
- 每轮评测后应写入 reflection，保留 dev/canary/holdout delta、失败标签、
  rollback 结论、副作用和下一步建议。
- 失败 proposal、无效 proposal、preflight error、metric regression 和 rollback
  reason 都是后续 proposal prompt 与 memory 的输入，不应被隐藏。
- 默认保持 `official_scores_claimed=false`；本地 diagnostic gain 或 proof bundle
  不能直接升级成 official leaderboard/release claim。

## 参考来源

- AIDE: AI-Driven Exploration in the Space of Code, arXiv:2502.13138: https://arxiv.org/abs/2502.13138
- WecoAI/aideml GitHub: https://github.com/WecoAI/aideml
- MLAgentBench, arXiv:2310.03302: https://arxiv.org/abs/2310.03302
- snap-stanford/MLAgentBench GitHub: https://github.com/snap-stanford/MLAgentBench
- MLE-bench, arXiv:2410.07095: https://arxiv.org/abs/2410.07095
- OPRO / Large Language Models as Optimizers, arXiv:2309.03409: https://arxiv.org/abs/2309.03409
- TextGrad, arXiv:2406.07496: https://arxiv.org/abs/2406.07496
- zou-group/textgrad GitHub: https://github.com/zou-group/textgrad
- GEPA, arXiv:2507.19457: https://arxiv.org/abs/2507.19457
- CerebrasResearch/gepa GitHub: https://github.com/CerebrasResearch/gepa
- PromptAgent, arXiv:2310.16427: https://arxiv.org/abs/2310.16427
- PromptAgent GitHub: https://github.com/maitrix-org/PromptAgent
- PromptBreeder, arXiv:2309.16797: https://arxiv.org/abs/2309.16797
- The AI Scientist, arXiv:2408.06292: https://arxiv.org/abs/2408.06292
- CodeScientist, arXiv:2503.22708: https://arxiv.org/abs/2503.22708
- Agent Laboratory, arXiv:2501.04227: https://arxiv.org/abs/2501.04227
- Agent Laboratory GitHub: https://github.com/SamuelSchmidgall/AgentLaboratory
- DS-Agent, arXiv:2402.17453: https://arxiv.org/abs/2402.17453
- FunSearch, Nature 2024: https://www.nature.com/articles/s41586-023-06924-6
- OpenEvolve GitHub: https://github.com/algorithmicsuperintelligence/openevolve
- karpathy/autoresearch GitHub: https://github.com/karpathy/autoresearch
- Auto Research with Specialist Agents Develops Effective and Non-Trivial Training Recipes, arXiv:2605.05724: https://arxiv.org/abs/2605.05724
- CORAL GitHub: https://github.com/Human-Agent-Society/CORAL
