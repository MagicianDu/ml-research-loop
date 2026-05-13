# 单篇真实论文复现试点 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 选择一篇满足约束的 arXiv 公开论文，完成一次真实、可审计、可重复的单篇论文复现试点。目标不是完整 SOTA 复现，而是把一个核心 claim 或 ablation 转成 ResearchCase，跑通本机短时实验和一次可解释的自动迭代，并沉淀为后续论文复现和多论文 idea 融合的标准流程。

**Architecture:** 继续采用混合 MCP 架构：Codex/Claude 负责论文理解、代码审查、patch 设计和下一步决策；ML Research Loop MCP 负责本地证据管理、环境检查、实验执行、结果解析、guarded patch、proof archive 和 release gate。服务端智能仍保持显式 opt-in，不把 `run_ai_autoresearch` 作为默认自动决策层。

**Tech Stack:** Python stdlib + pytest + ruff；现有 `lib/research_case.py`、`lib/environment_probe.py`、`lib/autonomous_loop.py`、`lib/reproduction_protocol.py`、`lib/proof_release_index.py`、`lib/fusion_service.py`、`lib/mcp_service.py`、`scripts/research_env_probe.py`、`scripts/autonomous_research_demo.py`、`scripts/proof_release_index.py`、`scripts/release_check.py`、MCP stdio service 和 `docs/evidence/` proof index。

---

## 0. 背景和产品定位

这个试点服务于产品目标，而不是服务于某一篇论文本身。

当前产品要证明的核心能力是：

1. 能把真实论文拆成可执行研究任务。
2. 能把论文 claim、metric、数据、代码、实验环境和结果绑定在同一个证据链里。
3. 能在本机短时间内跑出一个 bounded reproduction 或 ablation，而不是只生成计划。
4. 能把实验结果回传给 Codex/Claude，让客户端强模型提出代码或超参改动。
5. 能安全执行一次小步 patch 或参数迭代，并比较前后指标。
6. 能把成功和失败都归档为 proof archive，明确不能宣称什么。

默认候选论文沿用之前讨论过的 `MemFlow: Intent-Driven Memory Orchestration for Small Language Model Agents`（arXiv:2605.03312），但它只是候选，不是硬绑定。P0 必须重新检查它是否满足本计划的六条准入条件；如果不满足，应输出拒绝原因并替换为更适合的公开论文。

## 1. 论文准入条件

候选论文只有满足以下条件，才能进入真实试点：

| 条件 | 验收标准 |
| --- | --- |
| arXiv 公开 | 有公开 arXiv ID、PDF/摘要可读取，允许在文档中引用论文元数据。 |
| 任务和 metric 清晰 | 至少能抽取一个任务、一个目标 metric、一个 baseline 或 ablation 对比。 |
| 数据可获得 | 数据公开可下载，或可以定义一个不冒充原始 benchmark 的小型替代数据。 |
| 算法足够明确 | 有公开代码，或论文描述足以实现一个最小核心模块/ablation。 |
| 本机可短时运行 | CPU 或本机轻量资源可在目标预算内完成；默认单次实验不超过 15 分钟。 |
| 目标是核心 claim | 明确只复现一个 bounded claim 或 ablation，不宣称完整 SOTA 或官方成绩。 |

如果候选论文缺少官方代码、数据过大、依赖不可安装、metric 不清晰，仍可以进入“分析报告”，但不能进入实验闭环。

## 2. 成功定义

本试点成功不等于达到论文 SOTA。

本试点成功必须同时满足：

1. 生成一份 `paper-selection-report.json`，明确候选论文为什么被接受或拒绝。
2. 生成一份 `ResearchCase`，包含目标 claim、evidence refs、metric、数据计划、资源预算、禁止宣称项。
3. 完成环境 probe，输出 ready/blocked/repair_plan，而不是让用户猜缺什么。
4. 至少跑通一次 baseline 或最小 ablation 实验，并生成可解析 metrics。
5. 至少完成一次由客户端强模型决策的改动闭环：代码 patch、配置 patch 或超参 patch 三选一。
6. 对比 patch 前后结果，输出 continuation/stop decision。
7. 生成 proof archive，包含 artifact hash、命令、日志、metrics、claim boundary 和复盘。
8. 更新中文标准流程文档，让下一篇论文可以复用同一套入口和验收清单。

本试点不能宣称：

- 任意论文都能无人值守复现。
- 已经达到官方 benchmark 成绩。
- 已经完成多论文 idea 融合创新。
- 本地 debug 或替代数据结果等同于原论文主表结果。

## 3. 文件结构

| File | Responsibility |
| --- | --- |
| `docs/reproduction-pilot/memflow-single-paper-pilot-cn.md` | 记录默认候选论文的试点目标、claim、metric、数据/替代数据、资源预算和边界。 |
| `docs/reproduction-pilot/reproduction-case-template-cn.md` | 沉淀通用单篇论文复现模板，供后续论文复用。 |
| `lib/reproduction_pilot.py` | 新增论文筛选、case spec、实验结果摘要和 proof manifest 的纯函数逻辑。 |
| `scripts/real_paper_reproduction_pilot.py` | CLI 编排 P0-P5，默认只执行本地可控步骤，网络下载必须显式参数开启。 |
| `tests/unit/test_reproduction_pilot.py` | 覆盖论文准入、claim boundary、artifact manifest、拒绝路径。 |
| `tests/integration/test_real_paper_reproduction_pilot.py` | 用 fixture 跑通一次最小试点，验证输出结构和 proof archive。 |
| `docs/evidence/real-paper-pilot-index.json` | 索引真实论文试点 artifact，记录 claim 强度和 `official_scores_claimed=false`。 |
| `docs/evidence/public-claims-map.json` | 发布前声明映射：每个宣传 claim 必须绑定 proof artifact 或明确为 roadmap。 |
| `docs/evidence/autonomous-product-proof-matrix-cn.md` | 增补真实论文试点证据行，区分 local proof、debug proof、official proof。 |
| `docs/product/autonomous-research-product-cn.md` | 增补“单篇论文真实试点”作为 beta gate。 |
| `docs/release-checklist.md` | 增加真实论文试点 release gate 和不能宣称项检查。 |
| `scripts/release_check.py` | 增加可选 stable-readiness evidence 检查，不把缺失真实 proof 误判为 preview 失败。 |
| `README.md` | 增补中文/英文入口链接，说明如何从 MCP 客户端启动试点。 |

## 4. P0: 选题和 claim 可行性闸门

**目标：** 在写实验代码前先证明候选论文适合作为试点，避免把产品能力验证变成一篇不适合本机复现的论文攻坚。

- [ ] **Step 1: 写准入单测**

Create `tests/unit/test_reproduction_pilot.py`:

```python
from lib.reproduction_pilot import (
    PaperCandidate,
    evaluate_paper_candidate,
)


def test_candidate_requires_public_paper_metric_data_and_bounded_claim() -> None:
    candidate = PaperCandidate(
        paper_id="arxiv:2605.03312",
        title="MemFlow: Intent-Driven Memory Orchestration for Small Language Model Agents",
        arxiv_url="https://arxiv.org/abs/2605.03312",
        task="bounded memory-routing ablation",
        metric="accuracy",
        dataset_plan="small public or fixture-backed substitute dataset",
        algorithm_plan="minimal intent-router ablation",
        resource_budget_minutes=15,
        target_claim="intent-driven routing improves evidence selection on the bounded task",
        official_scores_claimed=False,
    )

    report = evaluate_paper_candidate(candidate)

    assert report.decision == "accepted_for_pilot"
    assert report.official_scores_claimed is False
    assert not report.reject_reasons
```

- [ ] **Step 2: 实现候选论文评估模型**

Create `lib/reproduction_pilot.py` with:

- `PaperCandidate`
- `PaperSelectionReport`
- `evaluate_paper_candidate(candidate)`
- `reject_candidate(candidate, reasons)`

Acceptance:

- 缺失 arXiv URL 必须拒绝。
- 缺失 metric 必须拒绝。
- 缺失数据计划必须拒绝。
- `official_scores_claimed=True` 必须拒绝。
- 资源预算超过默认上限必须标记为 blocked 或 requires_override。

- [ ] **Step 3: 生成候选论文选择报告**

Create `scripts/real_paper_reproduction_pilot.py` with a `--select-only` mode:

```bash
python3 scripts/real_paper_reproduction_pilot.py \
  --paper-id arxiv:2605.03312 \
  --output-dir .demo_runs/real_paper_pilot/memflow \
  --select-only \
  --json
```

Expected artifact:

```text
.demo_runs/real_paper_pilot/memflow/paper-selection-report.json
```

Required fields:

- `paper_id`
- `title`
- `arxiv_url`
- `target_claim`
- `target_metric`
- `dataset_plan`
- `algorithm_plan`
- `resource_budget_minutes`
- `decision`
- `reject_reasons`
- `official_scores_claimed`

## 5. P1: ResearchCase 绑定论文证据和实验目标

**目标：** 把论文 claim 转成现有 `ResearchCase`，让后续实验、patch、proof archive 都围绕同一个 case 运行。

- [ ] **Step 1: 创建试点说明文档**

Create `docs/reproduction-pilot/memflow-single-paper-pilot-cn.md`.

Required sections:

- 论文信息；
- 为什么选择或暂不选择该论文；
- 目标 claim；
- 不复现的内容；
- metric；
- 数据计划；
- 最小实验设计；
- 资源预算；
- 风险和替代方案；
- `official_scores_claimed=false`。

- [ ] **Step 2: 把 selection report 转成 ResearchCase**

Extend `lib/reproduction_pilot.py`:

- `build_research_case_from_selection(report)`
- `write_research_case(case, output_dir)`

Acceptance:

- `ResearchCase.objective` 必须包含 bounded claim。
- `ResearchCase.forbidden_claims` 必须包含 official benchmark / full SOTA 相关禁止宣称。
- evidence refs 至少包含 paper metadata 和 local plan artifact。
- case summary 能被 MCP 或 CLI 返回。

- [ ] **Step 3: MCP 可读摘要**

Modify `lib/fusion_service.py` or `lib/mcp_service.py` only if existing API cannot expose case summary.

Acceptance:

- MCP 客户端能拿到 `case_id`、`objective`、`target_metric`、`forbidden_claims`、`next_steps`。
- 不新增默认服务端 LLM 调用。

## 6. P2: 环境 probe 和可重复执行入口

**目标：** 在实验前检查依赖、数据、写权限和资源预算，失败时给出 repair plan。

- [ ] **Step 1: 增加 probe fixture 测试**

Add tests in `tests/unit/test_reproduction_pilot.py` or `tests/unit/test_environment_probe.py`:

```python
from lib.reproduction_pilot import (
    PilotRunConfig,
    probe_pilot_environment,
)


def test_pilot_probe_reports_repair_plan_when_dataset_missing(tmp_path) -> None:
    config = PilotRunConfig(
        case_id="case-memflow-mini",
        data_path=tmp_path / "missing-dataset.jsonl",
        output_dir=tmp_path / "out",
        max_runtime_seconds=60,
    )

    report = probe_pilot_environment(config)

    assert report.status == "blocked"
    assert "dataset_missing" in report.blockers
    assert report.repair_plan
```

- [ ] **Step 2: CLI 增加 `--probe-only`**

Command:

```bash
python3 scripts/real_paper_reproduction_pilot.py \
  --paper-id arxiv:2605.03312 \
  --output-dir .demo_runs/real_paper_pilot/memflow \
  --probe-only \
  --json
```

Acceptance:

- 输出 `environment-probe.json`。
- 结果包含 Python 版本、包状态、数据状态、写权限、资源预算、repair plan。
- secret-risk filename 只能报告风险，不能读取 secret 内容。

## 7. P3: 最小 baseline/ablation 实验

**目标：** 跑通一个短时、可重复、可解释的实验，而不是只生成文档。

- [ ] **Step 1: 定义最小实验协议**

Create or extend pilot config so it includes:

- `baseline_command`
- `ablation_command`
- `metric_name`
- `metric_direction`
- `max_runtime_seconds`
- `expected_artifacts`

Acceptance:

- 使用小数据或 fixture 时，报告必须写明 `substitute_data=true`。
- metrics 文件必须是 JSON，且能被现有 review/grade/report 工具读取。

- [ ] **Step 2: 实现 bounded run**

Command:

```bash
python3 scripts/real_paper_reproduction_pilot.py \
  --paper-id arxiv:2605.03312 \
  --output-dir .demo_runs/real_paper_pilot/memflow \
  --run-baseline \
  --json
```

Acceptance:

- 生成 `baseline-metrics.json`。
- 生成 `run-log.txt`。
- 生成 `experiment-summary.json`。
- 单次运行不超过配置预算。
- 失败时生成 failure diagnostics，而不是只返回 traceback。

## 8. P4: 客户端强模型驱动的一次自动迭代

**目标：** 验证 MCP 每次把数据回传给 Codex/Claude 后，客户端强模型可以提出具体代码/配置/超参改动，再由 MCP 安全执行。

- [ ] **Step 1: 生成 client handoff bundle**

The run must output:

```text
client-handoff.json
```

Required fields:

- `case_summary`
- `target_claim`
- `metric_before`
- `failure_or_gap`
- `allowed_patch_scope`
- `suggested_next_actions`
- `stop_rules`

- [ ] **Step 2: guarded patch 执行一次小改动**

Use existing guarded patch path where possible. The patch can be one of:

- hyperparameter patch；
- config patch；
- small algorithm branch patch。

Acceptance:

- patch scope 必须受限。
- patch 前后都要有 artifact。
- patch 失败要 rollback 或保留 failure diagnostics。
- 不能写入未授权目录。

- [ ] **Step 3: 对比结果并给出停止/继续决策**

Output:

```text
iteration-comparison.json
```

Required fields:

- `metric_before`
- `metric_after`
- `delta`
- `decision`
- `why`
- `next_recommended_action`

Acceptance:

- 如果指标提升，仍不能自动宣称论文 claim 完全成立。
- 如果指标下降或无变化，必须记录失败归因和下一步建议。

## 9. P5: Proof archive 和宣传证据索引

**目标：** 把这次真实论文试点变成可公开解释的产品证据，而不是隐藏在本地日志里。

- [ ] **Step 1: 生成 proof manifest**

Expected path:

```text
proof_runs/real-paper-pilot/memflow/proof-manifest.json
```

Required fields:

- `case_id`
- `paper_id`
- `claim`
- `claim_strength`
- `official_scores_claimed=false`
- `artifacts`
- `artifact_sha256`
- `commands`
- `environment`
- `metric_summary`
- `limitations`
- `review_status`

- [ ] **Step 2: 更新证据索引**

Create or modify:

- `docs/evidence/real-paper-pilot-index.json`
- `docs/evidence/public-claims-map.json`
- `docs/evidence/autonomous-product-proof-matrix-cn.md`

Acceptance:

- 每个公开宣传 claim 都必须映射到 artifact 或标记为 roadmap。
- 本地替代数据结果必须标记为 `local_substitute_data`。
- proof matrix 不得暗示官方 benchmark 成绩。

## 10. P6: 标准流程沉淀和 release gate

**目标：** 跑通一篇以后，把流程沉淀成下一篇论文可复用的标准作业，而不是一次性脚本。

- [ ] **Step 1: 创建通用模板**

Create `docs/reproduction-pilot/reproduction-case-template-cn.md`.

Required sections:

- 论文准入；
- claim extraction；
- evidence refs；
- metric and dataset；
- environment probe；
- bounded baseline；
- client handoff；
- guarded patch；
- proof archive；
- claim boundary；
- stop/continue rules。

- [ ] **Step 2: 更新 release checklist**

Modify `docs/release-checklist.md`:

- preview release: 不要求真实论文试点必须成功；
- beta release: 至少一个真实论文试点 proof archive；
- stable release: 多个真实任务、外部 pilot 反馈、可下载 release artifact。

- [ ] **Step 3: release_check 增加 evidence gate**

Modify `scripts/release_check.py` and tests:

- preview 缺失真实论文 proof 时不失败；
- stable-readiness 必须报告缺失真实任务 proof；
- 如果 proof manifest 存在，必须校验 artifact path、hash、claim boundary。

Command:

```bash
python3 scripts/release_check.py --json
```

Acceptance:

- 现有 preview gate 继续通过。
- stable-readiness 对真实 proof 的阻塞原因更具体。
- docs 和 code 的 release 边界一致。

## 11. 验收命令

计划执行完成后至少运行：

```bash
python3 -m pytest tests/unit/test_reproduction_pilot.py -q
python3 -m pytest tests/integration/test_real_paper_reproduction_pilot.py -q
python3 scripts/real_paper_reproduction_pilot.py --paper-id arxiv:2605.03312 --output-dir .demo_runs/real_paper_pilot/memflow --select-only --json
python3 scripts/real_paper_reproduction_pilot.py --paper-id arxiv:2605.03312 --output-dir .demo_runs/real_paper_pilot/memflow --probe-only --json
python3 scripts/release_check.py --json
```

如果环境允许并且 P0/P2 通过，再运行：

```bash
python3 scripts/real_paper_reproduction_pilot.py --paper-id arxiv:2605.03312 --output-dir .demo_runs/real_paper_pilot/memflow --run-baseline --json
```

最终验收需要检查：

- `.demo_runs/real_paper_pilot/memflow/paper-selection-report.json`
- `.demo_runs/real_paper_pilot/memflow/environment-probe.json`
- `.demo_runs/real_paper_pilot/memflow/baseline-metrics.json`
- `.demo_runs/real_paper_pilot/memflow/client-handoff.json`
- `.demo_runs/real_paper_pilot/memflow/iteration-comparison.json`
- `proof_runs/real-paper-pilot/memflow/proof-manifest.json`
- `docs/evidence/real-paper-pilot-index.json`
- `docs/evidence/public-claims-map.json`

## 12. 关键风险和处理原则

| 风险 | 处理原则 |
| --- | --- |
| 候选论文不适合短时本机复现 | P0 直接拒绝并记录原因，不硬做。 |
| 数据集过大或下载受限 | 使用小型替代数据，但必须明确 `substitute_data=true`。 |
| 指标无法对齐原论文 | 改为复现局部 claim 或 ablation，不宣称主表成绩。 |
| patch 没有提升 | 记录失败归因；产品能力仍可证明“可迭代和可审计”，不能证明“已优化成功”。 |
| LLM judge 争议 | Codex/Claude review 只能作为 assisted review，不冒充官方 judge。 |
| proof archive 证据不足 | 不进入宣传索引，只进入失败复盘。 |

## 13. 执行顺序

严格按以下顺序推进：

1. P0 论文准入闸门。
2. P1 ResearchCase 绑定。
3. P2 环境 probe。
4. P3 最小 baseline/ablation。
5. P4 客户端强模型 patch 迭代。
6. P5 proof archive。
7. P6 标准流程和 release gate。

任何阶段失败，都先补 failure diagnostics 和 claim boundary，再决定是否换论文或降低目标，不直接跳到宣传材料。

## 14. 完成定义

本计划完成时，项目应能回答：

- 我们选了哪篇真实论文，为什么适合作为试点？
- 我们复现的是哪个 bounded claim，而不是哪些内容？
- 本地跑了什么命令，产出了哪些 artifacts？
- 指标是什么，前后变化是什么？
- Codex/Claude 在闭环里复用了哪些强模型能力？
- MCP 服务实际承担了哪些本地执行和证据职责？
- 这次结果能宣传什么，不能宣传什么？
- 下一篇论文如何复用同一流程？

只有这些问题都有 artifact 支撑，才算完成单篇真实论文复现试点。
