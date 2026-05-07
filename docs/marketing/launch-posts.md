# ML Research Loop 发布话术

这些文案可以直接复制。发布前建议使用当次公开录屏链接、release 链接和 issue 链接；所有 benchmark 表述都刻意保留 claim boundary。

## GitHub Release / README 顶部短介绍

ML Research Loop is an MCP + Skills execution layer for Codex and Claude doing ML research.

It fuses ml-intern-style paper/dataset/code evidence gathering with autoresearch-style fixed-budget experiment loops. The client model plans, reviews, and proposes code or hyperparameter changes; the local MCP service executes retrieval, experiments, guarded patches, artifact archiving, benchmark proof lifecycle, and feedback bundles.

Current preview evidence:

- MCP client acceptance passes with 30 exposed tools and contract `2026-04-30.preview.v1`.
- A local MLE-bench `spooky-author-identification` official scorer proof run improves log loss from `1.08468` to `0.37038`, above the median threshold `0.418785`. This is not a leaderboard claim.
- PaperBench official debug split `rice` harness path runs with dummy solver + dummy judge. This proves harness integration, not reproduction quality.
- The same PaperBench debug artifact has a Codex-assisted rubric review report with score `0.0`, showing an honest evidence boundary and keyless review workflow.

Try the preview and share feedback: <https://github.com/MagicianDu/ml-research-loop>

## X / LinkedIn 短帖

I’m open-sourcing ML Research Loop: an MCP + Skills execution layer for Codex/Claude doing ML research.

The idea: strong coding agents should do planning, review, code edits, and hyperparameter proposals; a local MCP service should execute bounded experiments, preserve artifacts, enforce patch guards, and return evidence.

What it combines:

- ml-intern-style paper/dataset/code evidence gathering
- autoresearch-style fixed-budget experiment loops
- MCP tool contracts + workflow skills
- guarded code patch execution
- benchmark proof artifacts with honest claim boundaries

Preview evidence includes MCP client acceptance, a local MLE-bench proof run, PaperBench debug harness integration, and Codex-assisted rubric review.

Repo: <https://github.com/MagicianDu/ml-research-loop>

## Hacker News / Reddit 版本

Title:

```text
Show HN: ML Research Loop, an MCP execution layer for Codex/Claude ML experiments
```

Post:

```text
I built ML Research Loop, a preview MCP + Skills server for running machine-learning research loops with Codex or Claude as the planner.

The repo is trying to separate responsibilities cleanly:

- Codex/Claude: understand goals, inspect state, review results, propose code or hyperparameter changes.
- Skills: define workflow policy, evidence thresholds, stop rules, and human review boundaries.
- MCP service: execute paper/dataset/code retrieval, fixed-budget training experiments, guarded patches, artifact archiving, benchmark proof lifecycle, and feedback bundles.

It combines ideas from ml-intern and autoresearch. I also borrowed architecture patterns from AIDE and PaperBench, but the project does not vendor their heavy runtime stack by default.

Current evidence is intentionally modest and bounded:

- MCP client acceptance passes with 30 tools.
- A local MLE-bench spooky-author-identification official scorer proof run improved log loss from 1.08468 to 0.37038, above the median threshold. This is not a leaderboard claim.
- PaperBench debug split rice runs through dummy solver + dummy judge, proving harness integration but not reproduction quality.
- A Codex-assisted review over that PaperBench debug artifact records score 0.0 and evidence gaps, which is the point: no fake reproduction claims.

I’m looking for feedback from people building research agents, MCP tools, or automated ML experiment systems.

Repo: https://github.com/MagicianDu/ml-research-loop
```

## 微信群 / 私信中文短版

我最近开源了一个项目：ML Research Loop。

它不是聊天式研究 agent，而是给 Codex/Claude 这类强模型用的本地 MCP + Skills 机器学习研究执行层。强模型负责规划、审查、改代码和调超参；本地服务负责论文/数据集/代码证据检索、固定预算实验、artifact 留存、patch 护栏和 benchmark proof。

目前已经有几类可复核证据：

- MCP client acceptance 通过，暴露 30 个工具；
- 本地 MLE-bench `spooky-author-identification` proof run 从 log loss `1.08468` 改到 `0.37038`，超过 median threshold，但不宣传 leaderboard；
- PaperBench debug harness 跑通 dummy solver + dummy judge；
- 对 PaperBench debug artifact 做了 Codex-assisted review，审查分 `0.0`，用于证明我们会诚实记录证据边界。

如果你在做 ML agent、MCP server、科研自动化或自动实验平台，希望你帮忙试一下，尤其想知道安装、接入 Codex/Claude、跑 demo 哪一步最卡。

Repo: <https://github.com/MagicianDu/ml-research-loop>

## 面向潜在 contributor 的版本

ML Research Loop needs contributors around three hard problems:

1. Better research retrieval: stronger provider quality, cache recovery, evidence citation, and paper/code/dataset linking.
2. Better experiment intelligence: turning reviews into safe code and hyperparameter patches over real tasks.
3. Better proof runs: official harness integration, artifact bundles, and honest benchmark reporting.

The project is intentionally built as MCP + Skills, so Codex/Claude can provide the large-model reasoning while the service stays focused on controlled execution and reproducibility.

Good first feedback is enough: clone it, run the 5-minute preview, connect it to Codex or Claude, and tell us where it breaks.

## 30 秒口播

ML Research Loop 的目标很简单：让 Codex 和 Claude 不只是讨论机器学习实验，而是真的能在本地受控执行研究闭环。

它把 ml-intern 的论文、数据集和代码证据检索，和 autoresearch 的固定预算实验、代码/超参迭代合在一起，再用 MCP 暴露工具，用 skills 约束调用顺序和证据门槛。

现在它已经能跑 MCP 客户端验收、本地 demo、MLE-bench proof path、PaperBench debug harness 和 Codex-assisted review。我们不会把 debug 或 dummy 结果包装成榜单成绩，但它已经足够作为一个 preview 产品请真实用户试用。
