# fastText 完整复现与迭代提升证据实施计划

> **给后续 agentic worker：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐项执行。任务状态使用 checkbox（`- [ ]`）追踪。

**目标：** 把 fastText/AG News 轨道固化为用户可直接验收的“完整复现核心实验 -> 客户端 proposal 迭代提升 -> proof archive/release bundle”证据链。

**架构：** 继续使用现有 `full_reproduction_run.py` 和 `lib/full_reproduction_harness.py` 作为执行层，不重写训练逻辑。新增的是发布层和用户验收层：把 P4/P5 fastText proof manifest 转成 `docs/evidence/proof-archives/` 下的正式 release proof archive，并在中文文档中明确用户如何看到论文被复现、指标如何提升、哪些 claim 仍被阻断。

**技术栈：** Python 3.13、pytest、ruff、现有 fastText full reproduction harness、proof release index、中文 Markdown 文档。

---

## 文件边界

- 修改 `scripts/publish_release_evidence.py`：新增 `--fasttext-release-manifest name:path:description`，读取 P5 `release-proof-manifest.json`，复制 release tarball、checksum、review checklist、multi-round report 和 release manifest，生成可索引 proof archive。
- 修改 `tests/unit/test_publish_release_evidence.py`：覆盖 fastText release manifest 发布、路径脱敏、metric summary、download bundle sha256。
- 生成 `docs/evidence/proof-archives/fasttext-ag-news-full-reproduction-20260517/`：提交完整复现与迭代提升 proof archive。
- 更新 `docs/evidence/proof-release-index/`：让 release proof index 同时包含 MemFlow、Adam 和 fastText 完整复现轨道。
- 新增 `docs/reproduction-pilot/fasttext-full-reproduction-user-trial-cn.md`：给用户说明试用时怎么看 baseline、patch 提升、失败/回滚、proof bundle 和 claim boundary。
- 更新 `README.md`、`docs/evidence/benchmark-results-index-cn.md`、`docs/evidence/autonomous-product-proof-matrix-cn.md`：把 fastText 完整复现 proof archive 作为当前产品能力证据入口。

## TODO

- [x] **T1: 计划和资产确认**
  - [x] 确认本机已有完整 AG News CSV、fastText binary、P2+++ baseline、P3 improvement、P4 proof 和 P5 release bundle。
  - [x] 确认当前 gap 是“证据已存在但未进入最新 release proof archive/index，用户验收入口不够集中”。

- [x] **T2: 发布脚本支持 fastText 完整复现证据**
  - [x] 写单测：给定 P5 `release-proof-manifest.json`，发布后生成 `proof-archive.json`、`artifact-index.json`、`publication/proof-publication.json`。
  - [x] 写单测：发布出的 archive 不包含本机绝对路径，且保留 `baseline_p_at_1`、`p_at_1`、`delta`、`improved`、`failure_count`、`rollback_events`。
  - [x] 实现 `publish_fasttext_release_archive` 和 CLI 参数 `--fasttext-release-manifest`。
  - [x] 运行定向测试和 ruff。

- [x] **T3: 发布真实 fastText proof archive**
  - [x] 使用现有 `.demo_runs/p5-fasttext-real/release-proof/release-proof-manifest.json` 发布 `fasttext-ag-news-full-reproduction-20260517`。
  - [x] 重新生成 `docs/evidence/proof-release-index/proof-release-index.json` 和 `.md`。
  - [x] 校验 proof archive 和 index 不含本机绝对路径。

- [x] **T4: 用户验收文档**
  - [x] 新增中文试用文档，按“复现成功怎么看、提升怎么看、失败/回滚怎么看、下载包怎么复核、不能宣称什么”组织。
  - [x] 更新 README 的 proof matrix 和文档入口。
  - [x] 更新 benchmark/evidence/product proof 文档，把 fastText archive 作为“完整复现核心实验轨道”的证据。

- [x] **T5: 验收和提交**
  - [x] 运行 `pytest tests/unit/test_publish_release_evidence.py -q`。
  - [x] 运行 `pytest tests/unit/test_mcp_delivery_docs.py tests/unit/test_proof_release_index.py -q`。
  - [x] 运行 `ruff check scripts/publish_release_evidence.py tests/unit/test_publish_release_evidence.py`。
  - [x] 运行 `scripts/fresh_checkout_check.py --stable-readiness`，确认仍是诚实的 beta/stable 边界。
  - [x] 运行完整 `scripts/release_check.py --json`。
  - [x] 提交本轮改动。

## 验收标准

- `proof-release-index.md` 中能看到 `fasttext-ag-news-full-reproduction-20260517`。
- 用户能从中文试用文档直接看到：论文 ID、数据规模、baseline `P@1=0.914`、patch 后 `P@1=0.916`、delta `+0.002`、多轮 proposal 中 1 个失败样例和 1 次 rollback。
- 发布出的 public proof archive 不包含本机绝对路径或 `.demo_runs` 私有路径。
- 所有新增证据保持 `official_scores_claimed=false`，并继续阻断 official leaderboard、完整所有表格、无人值守任意科研提升等过度 claim。
