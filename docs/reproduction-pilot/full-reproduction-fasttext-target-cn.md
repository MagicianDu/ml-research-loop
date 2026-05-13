# Bag of Tricks for Efficient Text Classification 完整复现目标

## 目标

本目标用于把 bounded pilot 升级为完整复现轨道。当前 decision 为 `accepted_for_full_reproduction_track`，scope 为 `core_experiment_track`。

| 字段 | 内容 |
| --- | --- |
| 论文 | Bag of Tricks for Efficient Text Classification |
| 论文 ID | `arxiv:1607.01759` |
| 论文链接 | https://arxiv.org/abs/1607.01759 |
| 代码链接 | https://github.com/facebookresearch/fastText |
| 任务 | supervised text classification |
| 主指标 | `accuracy` |
| 数据轨道 | AG News or equivalent public text classification dataset |
| baseline 命令 | `fasttext supervised -input train.txt -output model` |
| evaluation 命令 | `fasttext test model.bin test.txt` |
| 资源画像 | `cpu_standard_hardware` |
| 预计运行时间 | 30 分钟 |

## 完整复现定义

本阶段的“完整复现”指复现论文的一个核心实验轨道：数据准备、baseline 训练、评测、结果归档和人工复核必须闭环。它不是一次性复现所有表格，也不是官方 leaderboard 成绩。

## 自动提升定义

在 baseline 可信之后，客户端模型可以提出 patch 或超参改动；MCP 负责执行、评测、记录 diff 和回滚。只有在 held-out/test 指标优于本地 baseline 时，才能写入 `improvement-report.json`。

## 必需 artifact

- `target-spec.json`
- `dataset-provenance.json`
- `baseline-report.json`
- `evaluation-report.json`
- `client-handoff.json`
- `patch-diff.patch`
- `improvement-report.json`
- `human-review-report.json`
- `proof-manifest.json`

## 当前 blockers

- 无

## 不能宣称

- `full_paper_all_tables`
- `official_benchmark_or_sota`
- `unattended_research_replacement`

所有输出必须保留 `official_scores_claimed=false`，除非后续真实跑过官方 scorer 或论文官方复现脚本并归档完整证据。
