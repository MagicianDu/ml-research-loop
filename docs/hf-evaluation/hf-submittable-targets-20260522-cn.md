# Hugging Face 可提交目标筛选报告

日期：2026-05-22

## 结论

当前外部验证路线需要从 Smol AI WorldCup 转向真实可提交目标。Smol 已经证明本地 provider 评测、proposal loop、dev/canary、scorer audit 和 proof archive 能跑通，但它的公开 Space 目前限制固定模型入口，不能直接提交本地 LM Studio / DeepSeek / Qwen predictions。因此它适合继续作为本地诊断集，不适合作为第一条市场竞争力证明。

第一优先级建议改为 **CP-Bench Leaderboard**。它要求提交 `.jsonl`，每行包含问题 `id` 和可运行的 constraint model 代码；官方 Space 也提供本地 `user_eval.py` 评测逻辑。这个目标能直接检验 ML Research Loop 的核心产品能力：让 Codex/Claude 提 proposal，MCP 生成/校验/运行代码，产出可提交 artifact，再通过外部 leaderboard 路径证明改进是否成立。

第二优先级是 **AI-Tx Challenge** 或 **Frugal AI Challenge**。AI-Tx 有明确的 HF Space API 提交流程和 private test 评估，但医学 QA 合规压力更高；Frugal AI 更贴近效率型 ML 产品叙事，但需要再次确认当前 portal 是否仍接受有效提交。

## 筛选标准

| 标准 | 含义 |
| --- | --- |
| 可提交性 | 必须有公开提交入口，不能只支持本地评测。 |
| 可复核性 | 必须能留下提交文件、日志、公开 URL、评测摘要或 leaderboard 记录。 |
| 资源适配 | 能在本机 M5 Max / 64GB 或普通 HF Space/Job 上做小步迭代。 |
| 产品相关性 | 能体现 proposal、自动实验、失败回滚、记忆复用和 proof archive。 |
| 声明边界 | 未完成外部提交前，不能宣传官方成绩或排名。 |

## 候选目标

| 排名 | 目标 | 当前判断 | 适配原因 | 主要风险 |
| --- | --- | --- | --- | --- |
| 1 | CP-Bench Leaderboard | 第一优先级 | JSONL 代码提交、本地 evaluator、leaderboard 展示，最适合验证“自动 proposal -> 可运行代码 -> 本地评测 -> 外部提交”闭环 | 需要安装/隔离 constraint modeling 依赖；live app 状态需 P0 再核验 |
| 2 | AI-Tx Challenge | 第二优先级 | HF Space `/answer_question` API、private test、明确 small/large/unrestricted tiers | 医学 QA 合规要求高，训练数据/代码披露规则更严格 |
| 3 | Frugal AI Challenge | 第二优先级候补 | 文本分类与既有 fastText/AG News 经验接近，性能和资源效率兼顾 | 当前有效提交状态需重新 live verification |
| 4 | TuringBench-2 | 候补 | 题量小、可做 predictions dry-run | leaderboard 版本和有效入口需要确认 |
| 5 | Smol AI WorldCup | 本地诊断保留 | 已有完整本地评测和 proposal proof，可继续训练“5 轮内找稳定方向”的产品能力 | 不适合作为第一条 HF 可提交竞争力证明 |

## CP-Bench 首轮 Proof 路径

P0 只做 live verification 和 target contract：

- 确认 CP-Bench dataset、leaderboard Space、submission format、本地 evaluator、支持 framework、license 和当前运行状态；
- 下载或缓存 template submission / `user_eval.py` / dataset metadata；
- 不上传、不提交、不声明成绩。

P1 做本地 harness adapter：

- 生成一个极小 CPMPy baseline submission；
- 调用本地 evaluator 或等价 parser；
- 输出 submission JSONL、summary、runtime profile、failure cases 和 artifact manifest。

P2 做 Codex-assisted proposal round：

- 基于失败样例生成候选 code patch 或 prompt/profile；
- 受控执行，比较 coverage、runtime error、consistency、final solution accuracy；
- 失败 proposal 必须进入 rollback evidence。

P3 做 submission gate：

- 生成外部提交包和短 PDF report 草案；
- 人工确认 HF token、成本、规则和是否公开；
- 成功提交后，将提交记录、公开 URL、结果页、hash 和截图/API 响应纳入 proof archive。

## 公开声明边界

现在只能说：

- “已识别并规划 Hugging Face 可提交目标”；
- “CP-Bench 是下一条优先外部 proof 线”；
- “Smol WorldCup 已作为本地诊断和 proposal loop proof 跑通”。

现在不能说：

- “已经取得 Hugging Face leaderboard 成绩”；
- “CP-Bench 已提交或已排名”；
- “任意论文/任意模型都能自动提升”；
- “本地诊断分数等同于外部竞争力”。

## 信息来源

- Hugging Face Competition Space 文档：https://huggingface.co/docs/competitions/main/competition_space
- Hugging Face leaderboard 文档：https://huggingface.co/docs/competitions/main/leaderboard
- Hugging Face benchmark leaderboard data 文档：https://huggingface.co/docs/hub/leaderboard-data-guide
- CP-Bench Leaderboard Space：https://huggingface.co/spaces/kostis-init/CP-Bench-Leaderboard
- CP-Bench dataset：https://huggingface.co/datasets/kostis-init/CP-Bench
- AI-Tx Challenge model submission：https://aitxchallenge.org/models/
