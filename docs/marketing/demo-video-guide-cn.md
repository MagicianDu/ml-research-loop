# 录屏 Demo 发布说明

## 当前录屏资产

本地已经生成一份发布用压缩版录屏：

```text
.demo_runs/recording/ml-research-loop-launch-demo-720p.mp4
```

公开视频资产：

```text
https://github.com/MagicianDu/ml-research-loop/releases/download/v0.1.0-preview/ml-research-loop-launch-demo-720p.mp4
```

原始录屏在：

```text
.demo_runs/recording/ml-research-loop-launch-demo.mov
```

`.demo_runs/` 是运行产物目录，不进入 git。发布时建议把 `720p.mp4` 上传到 GitHub release asset、YouTube、Bilibili、X/LinkedIn 或项目主页，然后在 README 或发布帖里引用公开视频链接。

## 视频标题

```text
ML Research Loop: MCP + Skills execution layer for Codex/Claude ML research
```

中文标题：

```text
ML Research Loop：给 Codex/Claude 使用的机器学习研究执行层
```

## 视频描述

```text
ML Research Loop is an MCP + Skills execution layer for Codex and Claude doing ML research.

This demo shows:
1. MCP client acceptance passing with 30 exposed tools.
2. Benchmark readiness contract with honest claim boundaries.
3. Public evidence index for MLE-bench and PaperBench proof artifacts.
4. Codex-assisted PaperBench review that records score 0.0 instead of turning dummy artifacts into fake reproduction claims.

Repo: https://github.com/MagicianDu/ml-research-loop
Evidence index: docs/evidence/benchmark-results-index-cn.md
```

## 字幕脚本

```text
ML Research Loop is not another research chatbot.

It is an MCP and Skills execution layer for Codex and Claude.

The client model plans, reviews, edits code, and proposes hyperparameters.

The local service executes research retrieval, bounded experiments, guarded patches, artifact archiving, and benchmark proof workflows.

In this preview, MCP client acceptance passes with 30 exposed tools.

The benchmark readiness contract keeps public claims honest.

The evidence index records an MLE-bench proof run, a PaperBench debug harness run, and a Codex-assisted PaperBench review.

The PaperBench review score is 0.0, because the debug artifact uses a dummy solver and dummy judge.

That boundary is intentional: the project is built to preserve evidence, not to inflate claims.

Next step: stronger real reproduction attempts and official harness paths.
```

## 推荐配图

- 使用录屏首屏或 MCP acceptance 输出作为 GitHub release 封面。
- 使用证据索引表格作为第二张截图，突出 “proof run / debug harness / Codex-assisted review” 的边界。
- 不建议使用只有 logo 或抽象渐变的图；当前项目最有说服力的是工具契约和证据表。

## 发布前检查

```bash
ls -lh .demo_runs/recording/ml-research-loop-launch-demo-720p.mp4
file .demo_runs/recording/ml-research-loop-launch-demo-720p.mp4
```

发布文案中必须保留：

- `not a leaderboard claim`
- `not an official PaperBench score`
- `dummy harness proves integration, not reproduction quality`
- `Codex/Claude are the planner; MCP service is the controlled execution layer`

## 后续可改进版本

- 录一版更短的 45 秒社媒版本，只保留问题、架构、证据三屏。
- 录一版客户端实操版，展示 Codex/Claude 真实调用 `mlResearchLoop`。
- 等真实 reproduction attempt 产出后，新增一版 benchmark proof video。
