# Stable Promotion Evidence 中文实施计划

> **给后续 agentic worker：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐项执行。任务状态使用 checkbox（`- [ ]`）追踪。

**目标：** 补齐 stable promotion 前最关键的真实任务 proof archive、可下载 release artifact 和外部 pilot feedback 收集/验收路径。

**架构：** 不伪造外部反馈，不把本地 proof 说成官方榜单成绩。新增的 proof 发布逻辑只把已存在的真实运行产物复制到 release evidence root，重写公开 archive metadata，去掉本机绝对路径，并继续保持 `official_scores_claimed=false`。外部 pilot feedback 只建立严格 schema 和 readiness 检查；没有真实外部用户输入时 blocker 必须保留。

**技术栈：** Python 3.13、pytest、ruff、hatchling/build、现有 `fresh_checkout_check.py` stable readiness、proof archive schema、中文文档。

---

## 文件边界

- 新增 `scripts/publish_release_evidence.py`：把 real-paper `proof-manifest.json` 和已有 benchmark `proof-archive.json` 发布到 `docs/evidence/proof-archives/`，复制 artifact，重写公开 metadata，生成 release index。
- 修改 `scripts/fresh_checkout_check.py`：让外部 pilot feedback 计数只接受真实、已脱敏、非模板的结构化反馈。
- 新增/修改 `tests/unit/test_publish_release_evidence.py`、`tests/unit/test_fresh_checkout_check.py`：覆盖 proof 发布、路径脱敏、feedback 计数。
- 新增 `docs/pilot-feedback/README.md`、`docs/pilot-feedback/pilot-feedback.schema.json`：说明外部反馈如何提交和为什么模板不计数。
- 修改 release/evidence 文档：更新当前 stable gap，说明本轮已补 release evidence 和 dist artifact，但外部 feedback 仍需真实用户。
- 生成 `docs/evidence/proof-archives/...` 和 `docs/evidence/proof-release-index/...`：提交小型、可复核 proof archive，不提交 `.demo_runs/`。
- 生成 `dist/*.whl`、`dist/*.tar.gz`、`dist/SHA256SUMS`：作为当前 checkout 的可下载 release artifact。

## TODO

- [x] **T1: 真实 proof archive 发布脚本**
  - [x] 写单测：real-paper manifest 转成 stable readiness 可识别的 proof archive。
  - [x] 写单测：已有 benchmark archive 发布后不包含本机绝对路径。
  - [x] 实现脚本：支持 `--real-paper-manifest name:path:description` 和 `--benchmark-archive name:path:description`。
  - [x] 运行定向测试和 ruff。

- [x] **T2: 外部 pilot feedback readiness 严格化**
  - [x] 写单测：README、schema、example/template 不计入 external feedback。
  - [x] 写单测：三个 `feedback_type=external_pilot`、`status=received`、`redacted=true` 的真实 JSON 才能清除 blocker。
  - [x] 实现 `_external_pilot_feedback_count` 的结构化计数。
  - [x] 新增中文反馈目录说明和 JSON schema。

- [x] **T3: 发布当前已有 proof evidence**
  - [x] 用脚本发布 MemFlow real-paper pilot、Adam real-paper pilot。
  - [x] 生成 proof release index。
  - [x] 更新 README、benchmark/evidence/release 文档，删除“checkout 未保留对应 artifact”的过时表述。
  - [x] 保留 claim boundary：仍不宣称 leaderboard、任意论文复现或自动保证提升。
  - [x] 决策记录：未提交 release-check 的 MLE-bench fake-bin archive，避免把本地 fake harness 误包装成 stable official/debug benchmark proof。

- [x] **T4: 构建 release artifact**
  - [x] 安装构建工具到本地 venv。
  - [x] 构建 wheel 和 sdist 到 `dist/`。
  - [x] 写 `dist/SHA256SUMS`。
  - [x] 运行 stable readiness，确认 `missing_downloadable_release_artifact` 已消失。

- [x] **T5: 最终验收**
  - [x] 运行新增单测、相关文档测试、fresh checkout readiness。
  - [x] 运行完整 release gate。
  - [x] 检查 git diff、避免提交 `.demo_runs/`。
  - [x] 如全部通过，整理提交。

## 验收标准

- `scripts/fresh_checkout_check.py --stable-readiness` 不再报告 `missing_real_task_proof_archives` 和 `missing_downloadable_release_artifact`。
- `missing_external_pilot_feedback` 仍保留，除非确实存在三份真实外部反馈；不能用模板或 README 冒充。
- 已提交 proof archives 不包含本机绝对路径或密钥。
- `dist/SHA256SUMS` 与实际 wheel/sdist 字节匹配。
- 完整 release gate 通过或报告真实 blocker。
