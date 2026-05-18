# Hugging Face 外部评测轨道

本文档把“参加 Hugging Face 上的公开比赛、leaderboard 或 evaluation”固化为产品验收路线。目标不是刷榜，而是用外部可复核目标证明 ML Research Loop 能完成：

- 研究目标选择；
- baseline 建立；
- Codex/Claude 生成 proposal；
- MCP 执行实验或评测；
- 指标对比、失败记录、回滚；
- proof archive 和公开声明边界。

## 当前结论

优先从 `smol-ai-worldcup-shift` 开始。原因是它直接对应“小型 LLM 能力和效率”方向，数据集公开、题量小、适合本机快速跑 baseline，也适合把 prompt、解码参数、模型路由或轻量微调纳入迭代闭环。

第二优先级是 `frugal-ai-challenge-text`。它更接近“深度学习算法/文本分类比赛”，而且同时衡量 accuracy 与资源消耗，商业化表达更强；但正式提交需要部署 HF Space，必须先 live verification。

完整候选清单见 [target-shortlist.json](target-shortlist.json)。

## 分阶段目标

| 阶段 | 目标 | 验收 |
| --- | --- | --- |
| P0 | 目标清单和声明边界 | `ml-loop hf-eval shortlist --json` 能输出候选，且 `official_scores_claimed=false` |
| P1 | 选定第一个外部目标 | 生成 `hf-external-eval-plan.json/.md`，明确数据、metric、baseline、迭代和 proof 入口 |
| P2 | 本地 HF-compatible baseline | 读取公开数据或规则，跑出本地 baseline，生成 artifact manifest |
| P3 | 一轮自动迭代 | Codex/Claude 提出 proposal，MCP 执行，比较指标并记录失败/回滚 |
| P4 | 外部提交 dry-run 或人工提交 | 生成提交文件或 Space API，人工确认后才能上传 |
| P5 | 可宣传 proof | proof archive、public claims map、benchmark index 和 release evidence 一致 |

## 声明边界

在没有完成外部平台提交并可公开复核前，只允许宣传：

- “已接入 Hugging Face 外部评测候选目标”；
- “已生成 local HF-compatible proof plan”；
- “已完成本地 baseline / 迭代 proof archive”。

不能宣传：

- official leaderboard score；
- 第三方比赛成绩；
- 任意论文或任意模型都能自动提升；
- 没有 proof archive 的口头结果。

## 使用方式

查看候选目标：

```bash
ml-loop hf-eval shortlist --json
```

生成第一个目标的 proof plan：

```bash
ml-loop hf-eval plan \
  --target-id smol-ai-worldcup-shift \
  --output-dir .demo_runs/hf-eval/smol-ai-worldcup-plan \
  --json
```

当前命令只做规划和本地文件输出，不会提交 Hugging Face，不会上传模型或结果，也不会声明官方成绩。

## 与现有架构的关系

这条轨道复用现有分层：

- Codex/Claude：选择目标、读数据、分析失败样例、提出 proposal；
- Skills：约束 workflow、声明边界、人工确认点；
- MCP/CLI：执行候选清单读取、baseline、patch/eval 和 artifact 写入；
- proof archive：保存可复核证据；
- public claims map：控制可宣传内容。

## 信息来源

- Hugging Face Competition Space 文档：https://huggingface.co/docs/competitions/main/competition_space
- Hugging Face Leaderboards and Evaluations 文档：https://huggingface.co/docs/leaderboards/en/index
- Smol AI WorldCup 数据集：https://huggingface.co/datasets/ginigen-ai/smol-worldcup
- TuringBench-2 Questions 数据集：https://huggingface.co/datasets/roc-hci/TuringBench-2-Questions
- Frugal AI Challenge submission portal：https://huggingface.co/spaces/frugal-ai-challenge/submission-portal
