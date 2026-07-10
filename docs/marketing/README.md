# ML Research Loop 宣传物料包

这组材料用于 v0.1.0-preview 对外传播。核心原则是：可以积极讲清楚项目差异，但所有 benchmark 和复现相关表述必须保留证据边界，不能把本地 proof run、debug harness 或 Codex-assisted review 包装成 leaderboard 成绩。

## 对外一句话

ML Research Loop 是 Codex、Claude 可调用的 MCP + Skills 机器学习研究执行层：强模型负责规划、审查和改代码，本地服务负责检索证据、跑实验、管理 artifact、做 patch 护栏和产出可复核结果。

## 物料清单

| 文件 | 用途 |
| --- | --- |
| [one-pager-cn.md](one-pager-cn.md) | 中文一页式产品说明，适合 GitHub README、微信群、私信预览 |
| [launch-posts.md](launch-posts.md) | GitHub、X/LinkedIn、Reddit/Hacker News、微信群/朋友圈发布话术 |
| [demo-video-guide-cn.md](demo-video-guide-cn.md) | 录屏发布说明、字幕脚本、截图建议和传播注意事项 |
| [../evidence/benchmark-results-index-cn.md](../evidence/benchmark-results-index-cn.md) | 可复核 benchmark evidence 总索引 |
| [../open-source-positioning-cn.md](../open-source-positioning-cn.md) | 开源差异化说明 |
| [../preview-feedback-cn.md](../preview-feedback-cn.md) | 试用反馈指南 |

## 允许宣传的事实

- MCP client acceptance 当前显示 `status: passed`，服务名 `ml-research-loop`，暴露 `94` 个工具，contract version 为 `2026-07-10.preview.v1`。
- 项目融合了 ml-intern 的研究检索/证据组织能力与 autoresearch 的固定预算实验/代码和超参迭代能力。
- 本地 MLE-bench `spooky-author-identification` bridge smoke 用 fake fixture + deterministic fake scorer 跑通 workspace/patch/grade/archive 插件闭环（baseline 与 patch log loss 均为 `1.08468`，未改善，不代表模型效果）。
- PaperBench official debug split `rice` 已跑通 dummy solver + dummy judge 的 harness path。
- 同一 PaperBench debug artifact 已产出 Codex-assisted rubric review，审查分 `0.0`，用于展示诚实证据边界和 keyless review 流程。
- 项目提供 MCP 工具、skills、artifact archive、feedback bundle、benchmark proof lifecycle 和 guarded patch execution。

## 禁止宣传的说法

- 不要说已经拿到 MLE-bench leaderboard 成绩。
- 不要说已经拿到 official PaperBench score。
- 不要把 PaperBench dummy judge 的 `mean score: 1.0` 说成真实论文复现质量。
- 不要承诺无人值守稳定完成任意论文复现。
- 不要宣称服务端自带 GPT-5.5 级模型能力；默认架构是 Codex/Claude 作为 planner，MCP 服务作为执行层。

## 推荐传播顺序

1. GitHub README 顶部保持技术可信度：定位、quick start、证据索引。
2. 发布压缩版录屏，并在描述中链接 evidence index。
3. 用 [launch-posts.md](launch-posts.md) 的短文案发给 ML agent、MCP、科研自动化方向的用户。
4. 引导试用者跑 [../preview-feedback-cn.md](../preview-feedback-cn.md) 中的 5 分钟试用，并把反馈贴到 GitHub issue。
5. 收集失败案例，优先转成 installation、MCP config、benchmark proof run 三类问题。

## 当前最佳传播主线

> This is not another research chatbot. It is the missing execution layer for strong coding agents doing ML research.

中文可以说成：

> 这不是又一个研究聊天机器人，而是给 Codex/Claude 这类强模型补齐本地机器学习研究执行层。
