# 成熟稳定自动科研产品证据矩阵

本文档维护 ML Research Loop 从 preview MCP product 走向成熟稳定自动科研产品所需的 proof matrix。它不是宣传页，而是把能力、当前证据、缺口和下一步证明放在同一张表里，避免把局部 demo 过度解释成稳定产品能力。

## Claim boundary

- 当前证据主要来自本地 release gate、bounded demo、provider quality benchmark、guarded patch demo、PaperBench/MemFlow-shaped scaffold 和文档化流程。
- 这些证据可以说明系统具备受控科研执行层的雏形，但不能宣称已经解决任意论文复现、任意模型优化或机构级平台化部署。
- 本地 proof、debug fixture、compatibility spike 和小样本 proof 不能当作官方 benchmark，除非明确接入官方 harness、保留完整命令/日志/配置，并通过独立可复核流程。
- 对外材料必须区分 `local proof`、`debug fixture`、`official harness probe`、`official benchmark run` 和 `human-reviewed case`。

## Proof matrix

真实论文试点的证据等级必须单独标注：它可以证明产品能够把一篇公开论文转成 bounded ResearchCase 并运行本地闭环，但不能自动提升为官方 benchmark 或完整论文复现证据。

| Capability | Current evidence | Gap | Next proof |
| --- | --- | --- | --- |
| Research evidence | `research_task`、`read_paper`、provider quality benchmark、evidence citations、retrieval diagnostics | 长论文 claim extraction、附录/代码/数据卡联合证据仍不足，证据强弱还需要绑定到 research case | ResearchCase claim/evidence fixture，覆盖论文 claim、数据集证据、代码证据和缺证据恢复 |
| Experiment loop | golden path、real-data demo、fixed-budget experiment、experiment tree、review handoff、loop decision | 长周期恢复、跨天状态、预算耗尽后的继续/停止策略还不稳定 | `autonomous_research_demo` 生成可恢复 case、指标历史、停止理由和 artifact bundle |
| Patch loop | `run_client_patch_experiment`、`apply_client_code_patch`、guarded patch demos、syntax/test preflight、rollback | 多文件真实 repo patch、测试选择和失败归因仍弱，不能证明复杂工程代码可自动安全修改 | multi-file patch proof，记录 diff、preflight、selected tests、rollback 和 metric regression 处理 |
| Reproduction | reproduction spec、rubric grade report、PaperBench/MemFlow proof scaffolds、required files readiness | 真实复现闭环不足，官方 harness 和本地 scaffold 的证据等级容易混淆 | official/debug proof archive，明确 `official_*` 标记、命令、日志、rubric、artifact hash 和人工复核结果 |
| Real paper pilot | `proof_runs/real-paper-pilot/memflow/proof-manifest.json`、`proof_runs/real-paper-pilot/adam/proof-manifest.json`、`dataset-provenance.json`、`human-review-report.json`、`docs/evidence/real-paper-pilot-index.json` 和 `docs/evidence/public-claims-map.json` 已索引 MemFlow routing 与 Adam optimizer 两个 bounded claim 的本地公开小切片 artifact/hash 与 `approved_with_limitations` 复核 | 当前只是 curated public mini-slice，不是官方 benchmark，也不是完整论文复现；复核只允许受限公开表述 | 扩展到更大的公开数据切片或官方 debug harness，引入外部人工复核，并继续保持 `official_scores_claimed=false` |
| Full paper reproduction | `docs/reproduction-pilot/full-reproduction-target.json`、`scripts/full_reproduction_run.py`、`docs/evidence/fasttext-ag-news-real-baseline-20260513-cn.md`、`docs/evidence/fasttext-ag-news-p3-patch-round-20260513-cn.md`、`docs/evidence/fasttext-ag-news-p4-proof-bundle-20260514-cn.md` 和 `docs/evidence/fasttext-ag-news-p5-release-proof-20260514-cn.md` 已把 fastText 论文选为第一个完整复现目标，并完成 P1/P2/P2+/P2++/P2+++/P3/P4/P5：fastText supervised 格式、完整 AG News CSV 转换、真实官方 fastText binary train/test、训练/评测日志、P@1 解析、baseline report、client handoff、allowlisted proposal、patch diff、improvement report、human review、proof manifest、SHA-256 artifact index、多轮 proposal、失败轮次记录、best-so-far rollback summary 和 release proof tarball；真实本地 baseline 为 `P@1=0.914`，P3/P5 `wordNgrams=2` 后为 `P@1=0.916`，P5 记录 2 个 proposal、1 个失败、1 个 rollback event，并生成 checksum 复核通过的 release bundle | 当前证据仍只是一个核心实验轨道的本地 baseline + 受控 patch/multi-round + proof bundle，不是官方 leaderboard、不是论文所有表格，也未证明复杂代码仓库或任意论文可以稳定自动提升 | 扩展到更多论文表格、更多公开数据集、外部复核者下载复核 release bundle，以及更复杂代码仓库的 guarded patch loop |
| Institution readiness | MCP setup、Skills setup、release checklist、client compatibility、product overview | pilot materials、隐私/secret scan、资源预算、课堂/实验室模板和反馈闭环不足 | pilot guide + feedback loop，包含安装验收、失败路径验收、数据边界、资源报告和 PI sign-off |

## 不能宣称

- 不能宣称本地 proof 是官方 benchmark。
- 不能宣称 debug fixture 的分数代表真实论文复现能力。
- 不能宣称 bounded demo 的成功代表任意研究任务都能自动完成。
- 不能宣称 patch loop 能安全修改所有真实仓库。
- 不能宣称 preview MCP product 已经达到成熟稳定自动科研产品状态。

## Proof release index

`scripts/proof_release_index.py` 用于把一个或多个 proof archive 汇总为 release 级证据索引。它只读取 `proof-archive.json`、同目录的 `artifact-index.json` 和 `publication/proof-publication.json`，输出 `proof-release-index.json` 与 `proof-release-index.md`，不会复制 `.demo_runs` 或原始大目录。

索引条目按以下方式表达证据边界：

- proof archive path：记录 `proof_archive`、`artifact_index`、`publication_guard` 的绝对路径，方便 release 后回查原始归档、hash 索引和 publication guard。
- judge type：从 archive 的 artifact manifest 读取 `judge_type`，用于区分 deterministic local judge、LLM judge、official scorer 或人工复核来源。
- metric：从 artifact manifest 读取 `metric` 或 `metric_name`，只说明本地 proof 观察到的指标名，不把它提升为 leaderboard 成绩。
- claim boundary：release index 顶层和每个条目都固定 `official_scores_claimed=false`；即使上游 archive 误写了 official claim，也只作为 `source_official_scores_claimed` 诊断字段暴露。
- blocked claims：继承 publication guard 的 `blocked_public_claims`，并持续阻断 `official leaderboard score` 和 “deterministic local fixture score as official benchmark performance” 这类对外表述。
- artifact hash：Markdown 和 JSON 都保留 artifact role、archive relative path 和 sha256 摘要，支持人工核对和二次复查。

因此，本地 proof release index 只能证明“这些 proof archive、publication guard 和 artifact hash 可被检查”，不能证明本地 proof 是官方 benchmark，也不能替代官方 harness、完整日志和独立复核流程。

## Release 证据门槛

每次面向外部用户的 release 至少应更新以下内容：

1. 当前通过的 release gate 和命令。
2. 新增或退化的 proof matrix 条目。
3. 对外 claim boundary，尤其是官方 benchmark、机构部署和服务端 LLM 自主能力边界。
4. 已知失败案例和恢复建议。
5. artifact retention 与可复查路径。
