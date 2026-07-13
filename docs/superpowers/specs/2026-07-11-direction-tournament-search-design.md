# 方向锦标赛搜索(Direction Tournament Search)设计

日期:2026-07-11
状态:设计已确认,待实施计划
语言:中文(与讨论语言一致)

## 背景与动机

项目的最终目标(见《项目背景书》)是一个 24/7 无人值守的研究 agent,核心是两个能力:

1. **复现能力**:对给定论文/问题先跑出可用的 baseline(或解决问题的雏形拿到初版结果);
2. **多方向优化能力**:提出多个有效的优化方向,每个方向用有限的几轮迭代判断潜力,
   最终在有限尝试的基础上选出最优方案。

2026-07-11 的代码调研确认:**能力 2 在当前代码库中不存在**,尽管有多个名字相近的机制。
调研结论(均已按 file:line 核实):

- `run_multi_optimizer_candidate_race` 生成多候选但不执行实验
  (`executes_experiment: False`),gate 结果需外部提供,只取 top-1,无多轮轨迹比较;
- `ml-loop proposal search`(`lib/proposal_search.py`)是对**已完成结果**的纯汇总器,
  自身不执行任何实验;`branch_budget` 限制候选数量,"每候选轮数"概念不存在;
- `lib/experiment_tree.py` 名为树实为链表:每个节点的 parent 恒为"上一个成功节点",
  任何节点都不会有两个子节点;`loop_policy` 只对单条线给 stop/continue;
- `method_search` ask/tell 可批量生成候选,但全库无 `proposal_family` 概念
  (在 `lib/failure_driven_proposal.py` 中 grep 零命中),跨轮记忆只有算子级权重;
- 最接近的 `run_method_search_trajectory` / `run_real_benchmark_readiness_run`
  真实跑 3-5 轮、每轮评估多候选、选每轮 winner,但**每轮重启全部候选源**,
  无淘汰机制,`best_path` 只是对各轮独立 winner 取 max,不会把预算集中给强方向。

因此需要新建一层搜索策略。整体工作拆为两个子项目:

- **子项目 1(本设计)**:多方向锦标赛搜索算法;
- **子项目 2(另行设计)**:24/7 无人值守编排(cron 触发、成本闸门、结果推送)。
  先前已确认的编排决策记录于此备查:外部编排复用 Claude Code headless/cron 能力;
  保留自动验证+回滚、取消人工确认;停止条件为轮数上限/达标/成本上限/时长上限;
  结束时主动推送总结。

## 参考设计哲学:Karpathy autoresearch

原版 [karpathy/autoresearch](https://github.com/karpathy/autoresearch)(2026-03,~630 行)
的单链贪心循环:读 `program.md` + `train.py` → 提一个改动 → 固定 5 分钟训练 →
看 `val_bpb` → 变好 git commit 成新 baseline,变差 git reset 回滚 → 重复。
三条纪律:只许改指定文件(评估代码禁改)、单一可比指标、人只在开头定方向。

本设计**在每个方向内部完整保留这套纪律**(固定单轮预算、单指标、accept/rollback),
只在其上新增一层锦标赛调度。它的"傻"(可预算、可回滚、可审计)正是敢于无人值守的前提。

## 方案选择

选定 **Successive Halving 锦标赛**。被否掉的候选:

- **Bandit 式连续分配(UCB/Thompson)**:理论样本效率更高,但对单轮噪声敏感、
  停止条件模糊、事后难以解释预算流向。K≈3-6、单轮分钟级的场景下复杂度不划算。
- **均匀探索一轮后全押最优**:等价于只砍一刀的 Successive Halving,慢热方向无第二次机会。
  Successive Halving 在 K 小时自然退化为该方案,故直接实现更一般的形式。

## 核心原则

**LLM 只出现在两个点,其余全部是确定性代码:**

- 出场点①:开赛时提出 K 个互异方向(各带假设 + 第一个具体改动);
- 出场点②:每轮为指定方向提出下一个改动(可读该方向的完整链历史)。

调度、执行、判定、排名、淘汰、预算记账、停止判定全部由确定性状态机完成,
不依赖模型"记得检查预算"。

## 架构

```
┌─ 客户端 LLM (Claude/Codex,经 MCP) ──────────────────┐
│  出场点①:submit_directions(K 个方向)                │
│  出场点②:submit_proposal(单方向单轮改动)             │
└──────────────┬───────────────────────────────────┘
               │ 新增 1 个 stage-dispatch MCP 工具 `tournament`
┌──────────────▼───────────────────────────────────┐
│  锦标赛引擎(新模块 lib/tournament_search.py)          │
│  纯状态机:阶段调度、排名淘汰、预算记账、停止判定          │
│  不调用任何 LLM;唯一事实源是 state.json               │
└──┬──────────────┬──────────────┬─────────────────┘
   ▼              ▼              ▼
 Arm 执行器      方差裁决         state.json
 (复用 guarded   (复用 paired-    (原子写,断点可恢复,
  patch round +   repeat/variance  子项目 2 的驱动层
  回滚)           gate)            直接消费)
```

- 每个方向(arm)持有**独立 workspace 副本与独立 best 基线**,链间互不污染;
  方向内回滚沿用 git-reset 模式。
- 引擎对目标抽象:arm 执行器是小接口 `run_one_round(workspace, proposal) → metrics`。
  v1 首先落地 fastText 执行器(接现有 patch-round);train.py 类目标(byte-lm)
  按同一接口作为第二执行器接入。新目标只需新增执行器,引擎不改。

## 状态模型(单一事实源)

`<runtime_root>/tournament/<run_id>/state.json`,每次状态变更后原子写
(临时文件 + rename):

```json
{
  "run_id": "...", "target_id": "fasttext-ag-news",
  "config": { "k": 4, "initial_rounds_per_arm": 3, "halving": 2,
              "epsilon": 0.001, "metric": "P@1", "direction": "maximize",
              "budgets": { "max_total_rounds": 40, "max_wall_seconds": 28800,
                           "target_value": 0.92 } },
  "baseline": { "value": 0.914, "artifact": "path/to/baseline-report.json" },
  "arms": [ { "arm_id": "a1", "hypothesis": "n-gram 特征方向……",
              "status": "active|pruned|failed",
              "workspace": ".../arms/a1/",
              "best": { "value": 0.916, "round": "a1-r2" },
              "rounds_used": 3, "rounds_allocated": 6,
              "invalid_proposal_streak": 0, "consecutive_failures": 0,
              "history": [ { "round_id": "a1-r1", "proposal": {},
                             "value": 0.915,
                             "decision": "accepted|rejected|failed",
                             "artifacts": "..." } ] } ],
  "stage": { "index": 1, "rounds_per_arm": 3 },
  "ledger": { "total_rounds_used": 9, "wall_seconds_used": 4200,
              "llm_cost_estimate": null },
  "pending_action": { "type": "need_round_proposal", "arm_id": "a2" },
  "stop": { "stopped": false, "reason": null }
}
```

`pending_action` 是关键设计:引擎永远把"下一步等什么"写进状态,系统因此断点可恢复,
且外层驱动退化为三行循环——读 pending → 要提案就让 LLM 提交,否则 step——
驱动层无需理解锦标赛逻辑。

## 运行流程

```
INIT       校验 baseline 存在且指标可读。baseline 是本模块的输入前提
           (fastText 的 9 步复现管线负责生产它,属 Phase A / 子项目 2 范畴)。
DIRECTIONS 引擎挂出 need_direction_proposals(K)
           → LLM 提交 K 个 {方向假设, 第一个改动};引擎做形式校验
             (arm_id 唯一、假设非空且互不重复;语义互异由 LLM 负责),
             建 arm,各分配 R₀ 轮。
ROUND      对每个 active arm 顺序执行(单机一次只跑一个训练):
           ├ 引擎挂出 need_round_proposal(arm, 链历史) → LLM 提交改动
           ├ 执行:guarded patch round(预检 → 跑 → 读指标,失败自动回滚)
           ├ 判定:delta ≥ ε → accept(更新该 arm 的 best 与 workspace)
           │       0 < delta < ε(将成为新 best 的近似平手)→ 同一提案配对
           │         重复执行一次,取均值后重新按 ε 判定(每轮至多一次重复)
           │       其余情况 → reject,workspace 回滚到该 arm 的 best
           └ 写 round 记录 → 检查停止条件
STAGE END  所有 active arm 用完本阶段轮数:按各自 best 排名
           → 淘汰后一半(至少留 1),存活者下阶段轮数 ×2 → 回到 ROUND。
TERMINAL   任一停止条件触发 → 终局报告:冠军方向、完整接受链、全程账本、
           逐方向潜力对比。
```

## 错误处理

原则:失败要记账,但不能无限花。

- **实验轮失败**(训练崩溃/超时/指标解析失败):记 `failed` 轮,
  **计入该 arm 已用轮数**;workspace 自动回滚到该 arm 的 best。
  同一 arm 连续失败 2 轮 → `status=failed`,视同淘汰。
  全部 arm 失败 → 全局停止(`all_arms_failed`)。
- **LLM 提案不合法**(预检不过:改禁区文件/参数不在 allowlist/基于过期状态):
  **不烧轮数**(实验未跑),但 per-arm 连续无效提案计数 +1;
  连续 3 次无效 → 该 arm `failed`(`invalid_proposals`)。
- **引擎进程死亡**:state.json 原子写;每轮有独立 `round_id` 与 artifacts 目录。
  恢复时若 pending 为 `run_round` 且该轮目录存在但无结果记录 →
  保守判该轮 failed 并回滚(半截实验不可信)。
  同一 `round_id` 重复提交提案被拒绝(幂等)。
  workspace 与记录不一致的检测复用现有 stale-state 预检。

## 停止条件与诚实边界

下表前四行在每轮结束与每阶段结束都检查,任一触发即停;末行为咨询性记账,不触发停止:

| 条件 | 引擎能否精确执行 |
| --- | --- |
| 任一 arm 的 best 达到 `target_value` | 精确 |
| `max_total_rounds` 用尽 | 精确 |
| `max_wall_seconds` 用尽 | 精确 |
| 全部 arm 失败/淘汰 | 精确 |
| LLM token/金钱成本上限 | **只记账不执法**:引擎不调 LLM,真正的成本闸门属于子项目 2 的驱动层;ledger 中仅维护咨询性估计 |

只剩 1 个 arm 时不特殊处理:继续按阶段拿轮数,由全局上限或达标终止。

## MCP 工具面

新增 **1 个** stage-dispatch 工具 `tournament`(沿用 2026-07-10 建立的合并惯例)。
纯新增属 additive 变更,按 release-notes 政策预期无需 bump contract version;
实施时同步更新 `REQUIRED_TOOLS` 与 acceptance 断言。

| stage | 作用 | 调用方 |
| --- | --- | --- |
| `start` | 建 run:config + target + baseline 路径 | 驱动层 |
| `status` | 状态摘要 + `pending_action` | 驱动层(每次循环开头) |
| `submit_directions` | 提交 K 个方向 | LLM(出场点①) |
| `submit_proposal` | 为指定 arm 提交本轮改动 | LLM(出场点②) |
| `step` | 执行当前待办的确定性工作(跑实验/阶段结算/终局报告),阻塞式 | 驱动层 |
| `report` | 终局报告 | 驱动层/人 |

CLI 镜像 `ml-loop tournament ...` 供人工调试。
所有 workspace 路径走现有 `ML_RESEARCH_LOOP_ALLOWED_ROOTS` 沙箱。

## 测试策略

以行为测试为主(吸取 2026-07 review 教训:schema 快照测试价值低):

- **单元(核心)**:注入假 arm 执行器(按脚本返回指标序列),断言:
  淘汰数学(每阶段谁存活)、ε 接受/拒绝/平手裁决三条路径、
  四个停止条件的优先级、杀进程后从 state.json 恢复、
  无效提案计数、连续失败处理、原子写行为。
- **集成**:合成目标(指标=参数的确定函数,不跑真训练,秒级):
  4 方向 × 2 阶段,断言解析上已知的最优方向胜出、状态文件轨迹完整。
- **真实冒烟(手动,不进 CI)**:fastText mini 切片
  (现有 `prepare_fasttext_mini_dataset`),2 方向 × 2 轮。
- **MCP 合约**:对临时 runtime root 真调各 stage,行为断言。

## v1 范围外(防止范围爬)

- 跨方向的提案借鉴/合并(v2 候选:决赛前一次组合轮);
- bandit 动态预算分配;
- 多 arm 并行执行(v1 单机顺序跑);
- Phase A(复现/baseline 生产)自动化——属子项目 2;
- 24/7 编排、成本执法、结果推送——属子项目 2;
- 开放式研究探索(自选论文/方向)——远期。

## 文件落点

- `lib/tournament_search.py`:引擎(状态机 + 排名淘汰 + 预算)
- `lib/mcp_service.py`:`tournament` 工具注册与 stage 分发
- `scripts/cli.py`:`ml-loop tournament` 子命令
- `tests/unit/test_tournament_search.py`:单元 + 集成(合成目标)
- 具体参数默认值(K、R₀、ε、失败阈值等)在实施计划中定,
  本文 state.json 示例中的数值为建议默认。
