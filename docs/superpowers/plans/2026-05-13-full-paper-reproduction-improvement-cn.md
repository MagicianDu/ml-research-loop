# 完整论文复现与自动提升闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前 bounded real-paper pilot 升级为“完整复现一个核心实验轨道，然后由 Codex/Claude + MCP 闭环做有效提升”的产品能力。

**Architecture:** 继续采用混合架构：Codex/Claude 负责论文理解、代码审查、patch/超参建议和停止判断；MCP 服务负责环境探测、数据准备、训练执行、评测、artifact/proof archive、claim boundary 和回滚。本机硬件按 Apple M5 Max、64GB 统一内存建模，第一阶段仍先选一篇低风险论文做出可复查的完整复现轨道，后续再扩大到 Apple Silicon / MPS 可承受的小型深度学习训练。

**Tech Stack:** Python stdlib、pytest、ruff、PyTorch MPS 可用性探测、现有 MCP service、`ResearchCase`、`environment_probe`、proof archive、release gate。目标论文首选 `Bag of Tricks for Efficient Text Classification` / fastText，因为官方资料明确它是轻量文本分类库，适合先建立稳定 baseline；M5 Max 64GB 让后续小型 CV/NLP 深度学习论文进入可评估范围。

---

## 0. 目标边界

当前项目已经能做两个 bounded pilot：MemFlow 和 Adam。下一阶段要证明的是更强能力：

1. 从论文选择进入完整复现目标，而不是只做局部 toy claim。
2. 复现论文的一个核心实验轨道，例如 fastText 的 supervised text classification。
3. 跑出 baseline，并与论文/官方脚本的目标表述绑定。
4. 让 Codex/Claude 根据结果提出可控改动。
5. MCP 执行改动、评测、记录 diff、保留失败轮次。
6. 用 holdout/test metric 证明相对本地 baseline 有提升。
7. 保持 `official_scores_claimed=false`，除非真实跑过官方 scorer 或论文官方复现脚本。

本阶段不承诺：

- 任意论文自动完整复现。
- 一次性复现论文所有表格。
- 官方 leaderboard / SOTA 成绩。
- 无人值守自动科研。

## 1. 目标论文选择

首选目标：`Bag of Tricks for Efficient Text Classification`（arXiv:1607.01759）。

选择理由：

- 论文任务和 metric 清晰：文本分类，P@1 / accuracy。
- 官方 fastText 工具链公开，支持 supervised text classification。
- 官方资料说明 fastText 是轻量库，适合标准硬件；它仍适合作为第一条低风险完整闭环。
- 论文摘要强调 CPU 训练速度，适合本机复现；本机 M5 Max 64GB 也可以支撑后续更重的小型深度学习 baseline。
- 完整复现轨道可以先限定为一个公开文本分类数据集，而不是所有论文表格。

备选目标：`mixup: Beyond Empirical Risk Minimization`（arXiv:1710.09412）。

推迟理由：

- 官方 CIFAR-10 repo 要求 GPU/NCCL 和旧 Python/PyTorch。
- 更适合作为第二个完整复现实验，不适合作为第一条稳定闭环。
- 由于本机是 Apple M5 Max 64GB，后续可以评估是否把 mixup 迁移到 PyTorch MPS/现代训练脚本，而不是直接使用旧 repo。

## 2. 文件结构

| 文件 | 职责 |
| --- | --- |
| `docs/superpowers/plans/2026-05-13-full-paper-reproduction-improvement-cn.md` | 本计划。 |
| `lib/full_reproduction.py` | 完整复现目标选择、target spec、claim boundary 和验收条件的纯函数。 |
| `scripts/full_reproduction_target.py` | CLI：生成目标论文 target spec 和中文说明。 |
| `docs/reproduction-pilot/full-reproduction-fasttext-target-cn.md` | fastText 完整复现目标说明。 |
| `docs/reproduction-pilot/full-reproduction-target.json` | 机器可读 target spec。 |
| `tests/unit/test_full_reproduction.py` | P0 目标选择、拒绝/延期逻辑、artifact 写入测试。 |
| `docs/development-roadmap-cn.md` | 后续加入 P1-P4 进展入口。 |

## 3. P0 计划固化和目标选择

**验收条件：**

- `fastText` 目标被接受为 `accepted_for_full_reproduction_track`。
- `mixup` 目标被标记为 `deferred_needs_gpu_or_legacy_stack`。
- 生成 JSON 和中文 markdown target spec。
- spec 明确 baseline、improvement gate、artifact 清单、禁止宣称项。

- [ ] **Step 1: 写失败测试**

```bash
.venv/bin/python -m pytest tests/unit/test_full_reproduction.py -q
```

预期：因为 `lib.full_reproduction` 不存在而失败。

- [ ] **Step 2: 实现 `lib/full_reproduction.py`**

实现数据结构：

```python
FullReproductionCandidate
FullReproductionTargetSpec
evaluate_full_reproduction_candidate(candidate)
write_full_reproduction_target(spec, output_dir)
```

- [ ] **Step 3: 实现 CLI**

```bash
.venv/bin/python scripts/full_reproduction_target.py \
  --paper-id arxiv:1607.01759 \
  --output-dir docs/reproduction-pilot \
  --json
```

预期输出包含：

```json
{
  "status": "completed",
  "decision": "accepted_for_full_reproduction_track",
  "paper_id": "arxiv:1607.01759",
  "official_scores_claimed": false
}
```

- [ ] **Step 4: 跑测试和 ruff**

```bash
.venv/bin/python -m pytest tests/unit/test_full_reproduction.py -q
.venv/bin/ruff check lib/full_reproduction.py scripts/full_reproduction_target.py tests/unit/test_full_reproduction.py
```

## 4. P1 完整复现 harness

**目标：** 从 target spec 进入真实训练/评测流程。

**验收条件：**

- 能准备一个公开文本分类数据集。
- 能把数据转为 fastText supervised 格式。
- 能训练 baseline。
- 能解析 P@1 / accuracy。
- 能写出 `baseline-report.json`。

计划文件：

- `lib/full_reproduction_harness.py`
- `scripts/full_reproduction_run.py`
- `tests/integration/test_full_reproduction_harness.py`

## 5. P2 论文 baseline 对齐

**目标：** 复现论文一个核心实验轨道，而不是只跑 toy slice。

**验收条件：**

- 记录论文目标表述、数据版本、训练命令、评测命令。
- 本地 baseline 有稳定复跑结果。
- 结果和论文主张之间有明确差距说明。
- 不把本地结果宣称为官方成绩。

## 6. P3 自动提升闭环

**目标：** 让 Codex/Claude 基于结果提出改动，MCP 执行并验证。

**验收条件：**

- 至少一轮可控 patch 或超参 patch。
- 写出 diff、preflight、训练日志、评测报告。
- 若指标提升，则接受；若下降，则回滚并记录失败原因。

## 7. P4 证明有效提升

**目标：** 在 holdout/test metric 上证明相对本地 baseline 的提升。

**验收条件：**

- 至少 3 次重复或固定 seed 复跑。
- improvement report 包含 mean/std 或逐 seed 结果。
- proof archive 记录 baseline、patch、evaluation、review。
- public claims map 只允许“local full-reproduction track improvement”，阻断官方/SOTA声明。

## 8. 当前推进顺序

1. 完成 P0 target spec。
2. 完成 P1 harness：数据准备、fastText supervised 格式、Python fallback baseline、评测解析和 `client-handoff.json`。
3. P1 绿后再跑 P2 baseline。
4. baseline 可信后再接入 P3 自动提升。

这个顺序不能跳。没有完整 baseline，就不能声称“有效提升”。
