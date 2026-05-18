# HF External Evaluation Track Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Hugging Face 外部 competition、leaderboard 和 evaluation 作为 ML Research Loop 的下一条产品验收轨道。

**Architecture:** 新增一条只读、保守、可测试的 HF 外部评测目标选择层：仓库保存候选目标清单，CLI/MCP 后续可以读取清单并生成 proof plan，但默认不上传、不提交、不声明官方成绩。它复用现有 benchmark proof、release evidence、public claims map 和中文产品文档体系。

**Tech Stack:** Python 3.10/3.13、argparse、pytest、现有 `ml-loop` CLI、Hugging Face Hub 文档和公开 URL、中文文档。

---

## 文件边界

- 新增 `docs/hf-evaluation/target-shortlist.json`：结构化记录候选 HF 外部评测目标、URL、metric、风险、验收条件和 claim boundary。
- 新增 `docs/hf-evaluation/hf-external-eval-track-cn.md`：中文产品/研发说明，解释为什么先选 Smol AI WorldCup、如何进入 Frugal AI Challenge、哪些不能宣传。
- 新增 `lib/benchmarks/hf_external_eval.py`：读取、校验、排序候选目标，并输出 HF external eval proof plan。
- 修改 `lib/benchmarks/__init__.py`：导出 HF external eval helper。
- 修改 `scripts/cli.py`：新增 `ml-loop hf-eval shortlist` 和 `ml-loop hf-eval plan`。
- 新增 `tests/unit/test_hf_external_eval.py`：约束清单 schema、排序、plan 输出和 claim boundary。
- 修改 `README.md` 和 `docs/evidence/benchmark-results-index-cn.md`：增加外部 HF 评测轨道入口，但继续声明当前没有官方 HF 成绩。

## TODO

- [x] **T1: 固化 HF 候选目标清单**
  - [x] 记录 Smol AI WorldCup、Frugal AI Challenge、TuringBench-2、HF eval results 和 private competition pilot。
  - [x] 每个目标必须包含 URL、metric、submission mode、resource fit、risk、acceptance 和 claim boundary。
  - [x] 保持 `official_scores_claimed=false`。

- [x] **T2: 新增 HF external eval helper**
  - [x] 实现 `load_hf_eval_targets()`，校验 JSON 顶层和目标字段。
  - [x] 实现 `select_hf_eval_targets()`，按 `product_fit_score` 排序。
  - [x] 实现 `build_hf_external_eval_plan()`，选定 target 并生成分阶段 proof plan。
  - [x] 实现 `write_hf_external_eval_plan()`，写 JSON 和 Markdown。

- [x] **T3: 新增 CLI 入口**
  - [x] `ml-loop hf-eval shortlist --json` 输出候选清单。
  - [x] `ml-loop hf-eval plan --target-id ... --output-dir ... --json` 写 proof plan。
  - [x] CLI 默认不访问 token、不上传、不提交。

- [x] **T4: 文档和公开声明边界**
  - [x] README 增加 HF 外部评测轨道。
  - [x] benchmark evidence index 增加候选外部评测说明。
  - [x] 文档明确当前不能宣传 official HF leaderboard score。

- [x] **T5: 测试和验收**
  - [x] 新增单测覆盖清单、plan、Markdown 输出。
  - [x] 运行定向 pytest。
  - [x] 运行 ruff。
  - [x] 运行 CLI smoke。

## 验收标准

- `ml-loop hf-eval shortlist --json` 能输出至少 5 个候选目标。
- 首选目标是 `smol-ai-worldcup-shift`。
- `ml-loop hf-eval plan --target-id smol-ai-worldcup-shift --output-dir <dir> --json` 生成 `hf-external-eval-plan.json` 和 `.md`。
- 所有输出都包含 `official_scores_claimed=false`。
- README 和 benchmark evidence index 不把候选目标说成已取得外部成绩。
