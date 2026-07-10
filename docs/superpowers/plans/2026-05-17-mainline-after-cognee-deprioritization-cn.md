# Cognee 降级后的主线推进 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Cognee 从主线阻塞项降级为可选实验性 adapter，并把项目资源转向官方/debug proof、记忆治理和 beta 发布准备。

**Architecture:** 项目继续遵守 `docs/product/target-architecture-cn.md` 的 canonical 分层：Codex/Claude 做 planner，Skills 固化流程，MCP Service 做受控执行，Research Memory Layer 以 dependency-free local baseline 为主，Graphiti/cognee 只是可选 adapter。所有新能力必须保持 `official_scores_claimed=false` 的证据边界，除非 publication guard 明确允许更强声明。

**Tech Stack:** Python 3.13、pytest、ruff、MCP stdio、项目自有 `ResearchMemoryCard`/benchmark proof/archive schema、中文产品文档。

---

## 并行边界

这四项可并行推进，但写文件必须分开：

- **A. Cognee 降级与文档边界**：只改 README、roadmap、target architecture、memory infra 文档、productization TODO。
- **B. P15 proof 发布证据**：只改 benchmark/evidence/release docs 和必要的 proof index 脚本或测试。
- **C. P16.3 记忆治理**：改 `lib/research_memory.py`、CLI memory 命令、memory 单测。
- **D. Beta release 准备**：改 fresh checkout/release readiness 脚本、release docs、发行 artifact 检查测试。

如果出现文档冲突，以 `docs/product/target-architecture-cn.md` 和 `docs/evidence/autonomous-product-proof-matrix-cn.md` 为准。

## TODO 总览

- [x] **T1: Cognee 降级为 optional experimental adapter**
  - [x] README、target architecture、research-memory-layer、development roadmap 明确：Cognee 不阻塞 beta/stable，不进入默认最小安装或 release gate。
  - [x] `docs/memory-live-infra-setup-cn.md` 保留最近失败 artifact，明确当前只证明安全失败和可选检索，不证明完整 Cognee indexing。
  - [x] `docs/productization-todos.md` 把 P16 live Graphiti/cognee smoke 改为 optional integration evidence，不作为主线未完成 blocker。
  - [x] 单测覆盖文档措辞：公开 docs 必须同时包含 “optional/可选” 和 “不阻塞 release gate/不是默认依赖”。

- [ ] **T2: P15 官方/debug benchmark proof 证据发布闭环（局部完成，未升级为完整发布级 proof）**
  - [x] 复核现有 MLE-bench spooky、PaperBench rice debug、Codex-assisted review 证据路径是否存在且可读。
  - [ ] 若证据完整，更新 `docs/productization-todos.md` 中 P15 “Run one official or official-debug benchmark path” 为已完成，并保留限制说明。
  - [x] 更新 `docs/evidence/benchmark-results-index-cn.md` 和 `docs/open-source-positioning-cn.md`，把 hard result、debug result、Codex-assisted review 三者证据等级分开。
  - [x] 增加一个轻量测试，保证 public docs 不把 debug dummy / Codex-assisted review 写成 official score。
  - [x] 当前限制：checkout 未保留对应 `.demo_runs` 原始 artifact，因此只能发布文档索引和限制说明，不能声称完整 official/debug benchmark proof 已交付。

- [x] **T3: P16.3 memory cleanup/retention policy**
  - [x] 在 `ResearchMemoryStore` 增加 dependency-free cleanup/retention 方法：按 `keep_last`、`memory_type`、`older_than_days`、`dry_run` 返回候选和执行结果。
  - [x] CLI 增加 `ml-loop memory cleanup --store <path> --dry-run --keep-last N --memory-type <type>`。
  - [x] cleanup 默认不删除 private memory，除非显式 `--include-private`。
  - [x] 单测覆盖 dry-run、不越权删除 private card、保留最新 N 条和执行后 JSONL 可读。
  - [x] 更新 `docs/product/research-memory-layer-cn.md` 和 `SECURITY.md` 的 retention 边界。
  - [x] 额外安全边界：CLI 真实删除必须显式 `--confirm`；建议先 dry-run 再执行。

- [x] **T4: Beta release / clean checkout / release artifact readiness**
  - [x] 检查 `scripts/fresh_checkout_check.py --stable-readiness` 的 beta/stable blocker 输出是否仍符合当前 preview/beta 边界。
  - [x] 增加 beta readiness 文档或命令输出：release gate、client acceptance、skills dry-run、fresh checkout、proof matrix、known limitations。
  - [x] 增加发行 artifact 检查：存在 wheel/sdist 或清楚报告缺失，并输出 hash verification next action。
  - [x] 更新 `docs/release-notes.md` 的 beta 前置条件，说明 Cognee optional 不影响 beta，stable 仍要求官方/debug proof 与 release artifact。
  - [x] 单测覆盖 beta readiness 输出和 release docs 中的 blocker 文案。

## 推荐执行顺序

1. 并行启动 T1/T2/T3/T4 的只读检查。
2. 先合入 T1 文档边界，防止后续误把 Cognee 当 blocker。
3. T3 若触及代码，严格 TDD：先写 cleanup 行为测试，再实现。
4. T2/T4 以证据复核为准，已存在的 hard result 可以升级文档状态；不存在的 artifact 只能保留 blocker。
5. 集成后运行：

```bash
.venv/bin/python -m ruff check lib scripts tests
.venv/bin/python -m pytest tests/unit/test_research_memory.py tests/unit/test_cli.py tests/unit/test_mcp_delivery_docs.py tests/unit/test_release_check.py -q
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON="$(which python3)" .venv/bin/python scripts/release_check.py --json
```

## 验收标准

- Cognee 不再出现在主线 blocker 文案里，但 optional integration 的限制保留。
- P15 evidence index 能让外部读者区分 official-debug bridge smoke、debug dummy harness 和 Codex-assisted review。
- Memory cleanup 可以 dry-run，可以执行，可以保护 private memory，执行后 store 仍可检索。
- Beta readiness 明确 preview/beta/stable 边界，并给出 release artifact/hash 的下一步。
- 完整 release gate 通过，或明确报告阻塞项和下一步命令。
