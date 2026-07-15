# 无人值守编排(Unattended Orchestration)设计 —— 子项目 2

日期:2026-07-15
状态:设计已确认,待实施计划
语言:中文(与讨论语言一致)
前置:方向锦标赛引擎(子项目 1),spec 见
`docs/superpowers/specs/2026-07-11-direction-tournament-search-design.md`,
实现在 `lib/tournament_search.py`(2026-07-11 完成,MCP 工具 `tournament`)。

## 背景与目标

项目最终目标是 24/7 无人值守的研究 agent。子项目 1 交付了"赛内"的确定性:
方向锦标赛引擎把调度、判定、淘汰、预算、停止全部做成状态机,LLM 只出现在
两个提案点。但引擎是被动的——每一步都要有人(或会话)去调 `tournament`
工具。本子项目交付"赛外"的确定性:让整条 pipeline 从 baseline 生产到最终
通知,在没有人盯着的情况下自动推进。

既定决策(子项目 1 brainstorming 时已确认,记录于其 spec):

- 外部编排:复用 Claude Code 的定时/headless 能力,不自建 API agent loop;
- 保留自动验证+回滚,取消人工确认;
- 停止条件:轮数上限 / 达标 / 成本上限 / 时长上限;
- 结束时主动推送总结。

本轮 brainstorming 新确认的四个决策:

1. **Phase A 进入 v1**:baseline 缺失时自动跑 fastText 现有复现管线
   (纯确定性脚本,不需要 LLM);fastText 二进制/数据缺失则预检失败、
   通知后停止。
2. **调度机制 v1 默认 Claude Code 定时任务**;驱动逻辑本身与触发机制无关,
   系统 crontab + `claude -p` 或会话内循环同样能拉起它。
3. **单次唤醒预算:干到受阻或达到单次上限**——引擎终止 / 本次已跑满 N 轮
   (默认 3,可配)/ 本次已用满 T 分钟(默认 20,可配),任一到即保存退出。
4. **成本闸门用"最大唤醒次数"做硬顶**:驱动状态文件记唤醒计数,代码检查,
   超限即通知+注销。token 级精确计费明确标注为超出范围(轮数上限已经
   线性约束了 LLM 提案次数;唤醒硬顶堵住"反复空转不消耗轮数"的病态循环)。

## 方案选择

选定**薄代码层 + 驱动 skill**("策略在 skill,执法在代码")。被否掉的候选:

- **纯 skill/prompt 驱动,零新代码**:唤醒计数、预算检查、通知幂等全部
  退化为 prompt 约束,跨几百次唤醒必然漂移,违背"停止条件是代码不是
  模型记性"的既定哲学。
- **全代码常驻 daemon + LLM API**:重走 `run_ai_autoresearch` 的路,与
  "复用 Codex/Claude 能力"的既定决策直接冲突,列出仅为完整性。

## 核心原则

延续子项目 1:**LLM 出场点不增加**(仍然只有方向生成与每轮提案两处);
驱动层把所有"可数的"东西——唤醒、单次预算、Phase A、通知幂等——放进
确定性代码。每次唤醒都是全新会话,恢复完全依赖两个状态文件。

## 架构

```
Claude Code 定时任务(prompt 只有一句:"用 tournament-driver skill 驱动 <job.json>")
        │ 按 cron 唤醒全新会话
        ▼
驱动会话(LLM,读 skill 策略)──出场点:生成 K 个方向 / 每轮提案
        │ MCP `tournament` 工具(6 stage → 8 stage,additive)
        ▼
lib/tournament_driver.py(新,确定性)         lib/tournament_search.py(引擎,不动)
  driver_tick / driver_finish                  状态机、执行器、报告
        ▼                                            ▼
  driver-state.json(驱动账本)                  state.json / report.json
        └────────────── job.json(唯一输入,人写一次)──────────────┘
```

### job.json(唯一输入)

定时任务的 prompt 不携带参数,全部配置在 job 文件里:

```json
{
  "job_id": "fasttext-agnews-overnight-01",
  "runtime_root": "...", "run_id": "run-1", "target_id": "fasttext-ag-news",
  "target": { "kind": "fasttext", "target_spec": "...", "train_csv": "...",
              "test_csv": "...", "fasttext_binary": "..." },
  "tournament_config": { "k": 4, "initial_rounds_per_arm": 3, "halving": 2,
    "epsilon": 0.001, "metric": "P@1", "direction": "maximize",
    "budgets": { "max_total_rounds": 40, "max_wall_seconds": 86400,
                 "target_value": 0.92 } },
  "baseline_artifact": "路径(可以尚不存在,fastText 目标会自动生产)",
  "driver": { "max_wakeups": 100, "per_wake_max_rounds": 3,
              "per_wake_max_minutes": 20 },
  "notify": { "on_stop": true }
}
```

### driver-state.json(驱动账本)

与引擎 state.json 分离;原子写复用子项目 1 已建立的 mkstemp+fsync 模式。
字段:唤醒计数/上限、Phase A 状态(含失败次数与错误尾巴)、逐次唤醒历史
(开始时间、引擎 ledger 快照、实际执行轮数、退出原因)、通知的
required/sent 标志、驱动层停止原因。

## 两个新 stage 的契约(全部确定性逻辑所在)

### `driver_tick(job)` —— 每次唤醒的第一个调用

1. 读 job → 读/初始化 driver-state → **唤醒计数 +1 并立刻落盘**
   (进门就烧:崩溃也算一次,杜绝无限白嫖唤醒);
2. 查 `max_wakeups` 硬顶,超限 → `action=stop_budget_exhausted`;
3. **预检**:fastText 二进制/数据/spec 存在性,缺 → `action=preflight_failed`
   (带缺失清单);
4. **Phase A**:baseline artifact 不存在 → fastText 目标调现有 harness 函数
   (准备数据 + 二进制 baseline)生产;synthetic 目标直接写最小 baseline
   文件。执行失败记账:第 1 次 → `action=phase_a_retry`(本次唤醒直接
   退出,不通知不注销,等下次唤醒重试);第 2 次 → `preflight_failed`
   (永久,通知+注销)。注意与第 3 步的区分:预检缺件(二进制/数据缺失)
   需要人干预,**立即**永久 `preflight_failed`,不重试;
5. **自动开赛**:锦标赛未 start 则用 job 的 config/target/baseline 调
   `start_tournament`(纯确定性,不需要 LLM);
6. 引擎已停 → `action=finalize`;否则 → `action=proceed`,附:当前
   `pending_action`、best-so-far 摘要、本次唤醒预算(`max_rounds` 与按
   进门时间计算的 `deadline_at`——Phase A 花掉的时间计入本次预算);
7. wake_history 开一条记录,存引擎 ledger 快照(供 finish 差分)。

若上一次唤醒的记录未关闭(会话中途死亡),tick 先将其关闭为
`interrupted`,轮数由 ledger 差分补算。

### `driver_finish(job, mark_notified=false)` —— 每次唤醒的最后一个调用

1. 关闭本次 wake_history(ledger 快照差分算实际轮数,不信会话自报);
2. 引擎已停或驱动层判停 → 用 `build_tournament_report` **代码生成通知文案**
   (job_id、停止原因、冠军方向及 delta、轮数/唤醒数/耗时、report 路径),
   置 `notification.required=true`(重复调用幂等,只构建一次);
3. 通知语义 **at-least-once**:会话推送成功后再调
   `driver_finish(mark_notified=true)` 翻 `sent` 标志;崩在推送与标记之间,
   下次唤醒至多重复推一条,可接受。`mark_notified=true` 的调用只翻标志、
   幂等,不重复关账(wake_history 已在首次 finish 时关闭)。

## 单次唤醒的完整流程(skill 策略)

```
唤醒 → driver_tick(job)
 ├─ action=proceed:
 │   循环直到 [引擎停止 | 本次轮数用满 | 过 deadline]
 │   (deadline 在每个动作之间检查——软上限,最多超出一轮的时长,
 │    轮内由执行器自身的 max_train_seconds 兜底):
 │     pending = need_direction_proposals → 按提案指引生成 K 个 → submit_directions
 │             = need_round_proposal(arm) → 读该 arm 假设+链历史 → 提案 → submit_proposal
 │             = run_round/stage_end/finalize → step(每个 run_round 计 1 轮)
 │   → driver_finish → 若已停:推送通知 → mark_notified → 注销定时任务
 ├─ action=phase_a_retry:
 │   driver_finish → 直接退出(不通知、不注销,等下次唤醒重试)
 └─ action=stop_*/preflight_failed/finalize:
     driver_finish → 推送 → mark_notified → 注销定时任务 → 退出
```

skill(`skills/ml-research-loop-tournament-driver/`)另含两类提案指引
(策略而非代码):

- 方向生成:K 个假设须分属不同参数家族(fastText 例:n-gram/学习率/
  epoch/维度);
- 每轮提案:读该方向的已接受链,在假设内迭代;收到 invalid-proposal
  错误要读错误信息修正(引擎三振出局兜底)。

**自熄灭保证**:注销定时任务失败也不会失控——下次唤醒 tick 看到
"已停止+已通知"直接返回 stop,唤醒计数照烧,到 `max_wakeups` 彻底沉默。

## 错误处理

- **会话中途死亡(未调 finish)**:下次 tick 关闭遗留记录为 `interrupted`,
  轮数 ledger 差分补算。引擎侧崩溃安全由子项目 1 的 marker 重放覆盖;
  驱动侧全部原子写,无腐坏路径。
- **Phase A 执行失败**:每次唤醒至多尝试 1 次;第 1 次失败返回
  `phase_a_retry`(静默等待下次唤醒),第 2 次失败 → 永久
  `preflight_failed`,通知+停止,不无限重训(见 tick 契约第 4 步)。
- **job.json 损坏/路径不可用**:tick 结构化报错。此为唯一 prompt 兜底:
  skill 要求会话此时尽力推送错误通知并注销定时任务(代码层连
  driver-state 都无法建立)。诚实标注为 best-effort。
- **时钟**:tick/finish 的 `now_fn` 可注入(测试确定性)。job 模板明确
  提醒 `max_wall_seconds` 是锦标赛创建起的总墙钟,无人值守应设为天级。
- 通知 at-least-once、注销失败自熄灭:见上文契约,不重复。

## 文件落点与工具面

| 文件 | 内容 |
| --- | --- |
| `lib/tournament_driver.py`(新,约 300 行) | `driver_tick`/`driver_finish`/job 校验/Phase A(harness 函数可注入)/driver-state 原子读写。纯 stdlib |
| `lib/mcp_service.py` | `tournament` 工具 stage 6→8(additive,**不 bump contract**);MCP 分发层先读 job,将 `job.runtime_root` 与 job 文件路径过 `_assert_path_allowed` 沙箱再进 lib |
| `scripts/cli.py` | `ml-loop tournament driver-tick\|driver-finish --job <file> [--mark-notified]` |
| `skills/ml-research-loop-tournament-driver/` | 第 5 个仓库 skill:唤醒策略 + 提案指引 + 通知/注销流程 + 手动验收命令 |
| `examples/tournament-jobs/` | `synthetic-demo.json`(离线可跑)+ `fasttext-ag-news.json`(真实模板) |
| README / release-notes | tournament 行更新(6→8 stage)+ additive 变更记录 |

## 测试策略

- **单元(tick)**:首次初始化;唤醒数"进门就烧"(计数落盘先于上限检查的
  崩溃语义);`max_wakeups` 触顶;预检缺件分支;Phase A 触发(注入假的
  baseline 生产函数)与 synthetic 自动写 artifact;自动开赛;已停→finalize;
  proceed 计划的 deadline/ledger 快照字段。
- **单元(finish)**:ledger 差分算轮数;未关闭 wake 的关闭;通知只构建
  一次(重复调用幂等);`mark_notified` 翻转;interrupted-wake 由下次
  tick 补关。
- **集成(进 CI,离线确定性)**:合成目标 + 脚本化"会话替身"(纯 Python
  循环扮演 LLM,提交确定性方向/提案,同子项目 1 测试模式),跑 W 次
  tick→drive→finish 完整无人值守生命周期:断言跨 ≥3 次唤醒完赛、单次
  唤醒轮数从不超上限、通知恰好一次、低 `max_wakeups` 变体以预算原因停止。
- **MCP/CLI 行为测试**:照仓库惯例(真调 stage,行为断言)。
- **手动验收(不进 CI)**:真实 Claude Code 定时任务 + fastText mini 切片,
  命令写进 skill/docs。

## v1 范围外(防止范围爬)

- 多 job 并发/队列(v1:一个 job = 一个定时任务 = 一个 run);
- token 级成本核算(唤醒硬顶 + 轮数上限为诚实近似);
- push 之外的通知渠道;
- 非 fastText 真实目标的 Phase A 自动化;
- 重试退避调参(Phase A 固定"至多 2 次");
- 开放式研究探索(自选论文/方向)——远期。

## 验收口径

与仓库一贯的 claim boundary 一致:本子项目交付的是**本地无人值守编排
能力**的可复核证据(离线合成目标的多唤醒生命周期测试 + 真实 fastText
mini 切片手动冒烟),不宣称任何模型效果或 benchmark 成绩;
`official_scores_claimed=false` 不变。
