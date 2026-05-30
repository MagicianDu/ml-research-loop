# CP-Bench Submittable Proof Track Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 CP-Bench 接成第一条真实 Hugging Face 可提交 leaderboard proof 线，用外部可提交 artifact 验证 ML Research Loop 的自动 proposal、受控执行、失败回滚和 proof archive 能力。

**Architecture:** 新增 `cp_bench` benchmark adapter，保持和现有 Smol WorldCup / MLE-bench / PaperBench adapter 相同边界：Codex/Claude 负责 proposal，MCP/CLI 负责下载公开规则、生成 submission、运行本地 evaluator、解析指标、写 artifact。外部上传必须走人工确认 gate，默认只生成 dry-run 和 proof bundle，不自动提交。

**Tech Stack:** Python 3.10/3.13、pytest、ruff、huggingface_hub、subprocess sandbox、JSONL artifact、现有 `ml-loop hf-eval` CLI、现有 MCP service。

---

## 文件边界

- Create: `lib/benchmarks/cp_bench.py`
  - 负责 CP-Bench target contract、submission validation、summary parser、local eval runner、artifact writer。
- Modify: `lib/benchmarks/__init__.py`
  - 导出 CP-Bench adapter。
- Modify: `scripts/cli.py`
  - 新增 `ml-loop hf-eval cp-bench-verify`、`cp-bench-baseline`、`cp-bench-proposal-round`、`cp-bench-submission-gate`。
- Modify: `lib/mcp_service.py`
  - 新增 `write_cp_bench_live_verification`、`run_cp_bench_local_baseline`、`run_cp_bench_proposal_round`、`write_cp_bench_submission_gate`。
- Create: `tests/unit/test_cp_bench_adapter.py`
  - 覆盖 target contract、JSONL validation、summary parser、artifact shape 和 claim boundary。
- Modify: `tests/unit/test_cli.py`
  - 覆盖新增 CLI 子命令。
- Modify: `tests/unit/test_mcp_service.py`
  - 覆盖 MCP tool manifest 和 allowed-root guard。
- Create: `docs/hf-evaluation/cp-bench-p0/`
  - 保存 P0 live verification artifact。
- Create: `docs/hf-evaluation/cp-bench-submittable-proof-cn.md`
  - 中文 proof 说明和边界。
- Modify: `docs/evidence/benchmark-results-index-cn.md`
  - 索引 CP-Bench proof，但在真实提交前保持 `official_scores_claimed=false`。

## Task 1: P0 Target Contract

**Files:**
- Create: `lib/benchmarks/cp_bench.py`
- Create: `tests/unit/test_cp_bench_adapter.py`
- Create: `docs/hf-evaluation/cp-bench-p0/README.md`

- [x] **Step 1: 写 target contract 测试**

在 `tests/unit/test_cp_bench_adapter.py` 增加：

```python
from lib.benchmarks.cp_bench import build_cp_bench_target_contract


def test_cp_bench_target_contract_preserves_claim_boundary():
    contract = build_cp_bench_target_contract()

    assert contract["target_id"] == "cp-bench-constraint-modeling"
    assert contract["official_scores_claimed"] is False
    assert contract["submission_format"]["file_extension"] == ".jsonl"
    assert contract["submission_format"]["required_keys"] == ["id", "model"]
    assert "CPMpy" in contract["supported_frameworks"]
    assert "MiniZinc" in contract["supported_frameworks"]
    assert "OR-Tools" in contract["supported_frameworks"]
```

- [x] **Step 2: 运行 RED**

```bash
.venv/bin/python -m pytest -q tests/unit/test_cp_bench_adapter.py::test_cp_bench_target_contract_preserves_claim_boundary
```

预期：因为 `lib.benchmarks.cp_bench` 尚不存在而失败。

- [x] **Step 3: 实现最小 contract**

在 `lib/benchmarks/cp_bench.py` 定义常量 URL、支持 framework、submission schema，并实现 `build_cp_bench_target_contract()`。返回字段必须包含 `target_id`、`urls`、`submission_format`、`supported_frameworks`、`local_eval_command_template`、`manual_submission_required=true`、`official_scores_claimed=false`。

- [x] **Step 4: 运行 GREEN**

```bash
.venv/bin/python -m pytest -q tests/unit/test_cp_bench_adapter.py::test_cp_bench_target_contract_preserves_claim_boundary
```

预期：通过。

P0 执行补充：

- [x] 新增 `write_cp_bench_live_verification` writer，写出 `cp-bench-live-verification.json` 和 `cp-bench-target-contract.md`。
- [x] 新增 CLI：`ml-loop hf-eval cp-bench-verify --output-dir docs/hf-evaluation/cp-bench-p0 --no-raw --json`。
- [x] 新增 MCP 工具：`write_cp_bench_live_verification`，默认只做公开 URL 检查，不提交、不上传、不声明成绩。
- [x] 2026-05-23 已完成一次真实 P0 live verification，四个 critical check 均 reachable，结果见 `docs/hf-evaluation/cp-bench-p0/`。

## Task 2: JSONL Validation And Summary Parser

**Files:**
- Modify: `lib/benchmarks/cp_bench.py`
- Modify: `tests/unit/test_cp_bench_adapter.py`

- [x] **Step 1: 写 submission validation 测试**

覆盖三种情况：合法 JSONL、缺少 `model`、空文件。合法行示例：

```json
{"id":"csplib__csplib_001_car_sequencing","model":"print({\"sequence\": [0]})"}
```

断言合法结果 `status="valid"`，非法结果 `status="invalid"` 且包含 `error_message`。

- [x] **Step 2: 写 summary parser 测试**

用 CP-Bench `summary.txt` 片段测试解析：

```text
Overall Evaluation Statistics:
  Total Submitted Models that also exist in the dataset: 2
  Models That Ran Successfully (out of submitted models): 1/2
  Submission coverage perc: 1.23%
  Error perc: 50.00%
  Consistency perc: 0.62%
  Final Solution Accuracy perc: 0.62%
```

断言 parser 输出 `submitted_models=2`、`runtime_success="1/2"`、`coverage_percent=1.23`、`final_solution_accuracy_percent=0.62`。

- [x] **Step 3: 实现 validation 和 parser**

实现 `validate_cp_bench_submission(path)` 和 `parse_cp_bench_summary(text)`；只解析现有公开 evaluator 输出，不自定义新的分数口径。

- [x] **Step 4: 运行定向测试**

```bash
.venv/bin/python -m pytest -q tests/unit/test_cp_bench_adapter.py
```

预期：通过。

## Task 3: P1 Local Baseline Artifact

**Files:**
- Modify: `lib/benchmarks/cp_bench.py`
- Modify: `scripts/cli.py`
- Modify: `tests/unit/test_cp_bench_adapter.py`
- Modify: `tests/unit/test_cli.py`

- [x] **Step 1: 写 artifact shape 测试**

调用 `write_cp_bench_local_baseline(output_dir, limit=1, framework="CPMpy", dry_run=True)`，断言输出：

- `status="written"`
- `official_scores_claimed=false`
- `submission_path`
- `summary_path`
- `artifact_manifest_path`
- `manual_submission_required=true`

- [x] **Step 2: 实现 dry-run baseline writer**

先不调用外部 evaluator，生成一个最小 JSONL、模拟 summary、artifact manifest 和 README。`dry_run=false` 留给 Task 4 调用 evaluator；`dry_run=true` 必须不访问网络。

- [x] **Step 3: 接 CLI**

新增：

```bash
ml-loop hf-eval cp-bench-baseline --output-dir .demo_runs/hf-eval/cp-bench-p1 --limit 1 --framework CPMpy --dry-run --json
```

JSON 输出必须包含 `official_scores_claimed=false`。

- [x] **Step 4: 运行 CLI smoke**

```bash
ml-loop hf-eval cp-bench-baseline --output-dir .demo_runs/hf-eval/cp-bench-p1-smoke --limit 1 --framework CPMpy --dry-run --json
```

预期：退出码 0，写出 JSONL 和 manifest。

P1 执行补充：

- [x] 新增 `validate_cp_bench_submission`，覆盖合法 JSONL、缺少 `model` 和空文件。
- [x] 新增 `parse_cp_bench_summary`，按公开 `user_eval.py` summary 字段解析 coverage、runtime success、error、consistency 和 final accuracy。
- [x] 新增 `write_cp_bench_local_baseline` dry-run writer，写出 `submission.jsonl`、`summary.txt`、`cp-bench-local-baseline-report.json`、`runtime-profile.json`、`artifact-manifest.json` 和 `README.md`。
- [x] 新增 CLI：`ml-loop hf-eval cp-bench-baseline --output-dir docs/hf-evaluation/cp-bench-p1 --limit 1 --framework CPMpy --dry-run --json`。
- [x] 新增 MCP 工具：`run_cp_bench_local_baseline`，Codex/Claude 可通过 MCP 触发同一条 dry-run baseline 路径。
- [x] 2026-05-23 已完成一次 P1 dry-run baseline artifact，结果见 `docs/hf-evaluation/cp-bench-p1/`。

## Task 4: Local Evaluator Integration

**Files:**
- Modify: `lib/benchmarks/cp_bench.py`
- Modify: `tests/unit/test_cp_bench_adapter.py`
- Modify: `docs/hf-evaluation/cp-bench-submittable-proof-cn.md`

- [x] **Step 1: 增加 evaluator availability check**

实现 `probe_cp_bench_local_evaluator()`，检查 Python 包 `datasets`、`click`、`cpmpy`、`minizinc`、`ortools` 是否可用，并将缺失项写入 `missing_dependencies`。缺失依赖时返回 `status="blocked_missing_dependencies"`，不能静默失败。

- [x] **Step 2: 增加真实 evaluator runner**

实现 `run_cp_bench_local_eval(submission_path, output_dir, framework, dataset_version="verified", timeout_seconds=60)`，调用缓存的或 vendored `user_eval.py`。所有 subprocess 参数必须是 list，不使用 shell；超时、非零退出、summary 缺失都要写入 failure artifact。

- [x] **Step 3: 文档记录依赖安装**

在 CP-Bench proof 文档中列出可选依赖：

```bash
pip install datasets click cpmpy minizinc ortools
```

说明 MiniZinc solver 可能需要单独安装，P1 dry-run 不依赖它。

- [x] **Step 4: 运行可用性 smoke**

```bash
ml-loop hf-eval cp-bench-baseline --output-dir .demo_runs/hf-eval/cp-bench-p1 --limit 1 --framework CPMpy --json
```

若依赖不足，验收为产生 `blocked_missing_dependencies` artifact，而不是崩溃。

P2 执行补充：

- [x] 新增 `probe_cp_bench_local_evaluator`，显式探测 `datasets`、`click`、`cpmpy`、`minizinc`、`ortools`，缺依赖时返回 `blocked_missing_dependencies`。
- [x] 新增 `run_cp_bench_local_eval`，使用 list-form subprocess 调用公开 `user_eval.py`，并覆盖缺依赖、超时、非零退出和 summary 缺失 artifact。
- [x] `ml-loop hf-eval cp-bench-baseline` 新增 `--timeout-seconds`；`--dry-run` 缺省关闭时进入真实 evaluator dependency gate。
- [x] MCP `run_cp_bench_local_baseline` 新增 `timeout_seconds` 参数；`dry_run=false` 时触发同一条 P2 路径。
- [x] 2026-05-23 已完成 P2 smoke，结果为 `blocked_missing_dependencies`：本机可用 `click`，缺少 `datasets`、`cpmpy`、`minizinc`、`ortools`，artifact 见 `docs/hf-evaluation/cp-bench-p2/`。

## Task 5: Proposal Round And Rollback Evidence

**Files:**
- Modify: `lib/benchmarks/cp_bench.py`
- Modify: `lib/mcp_service.py`
- Modify: `tests/unit/test_cp_bench_adapter.py`
- Modify: `tests/unit/test_mcp_service.py`

- [x] **Step 1: 定义 proposal contract**

Proposal JSON 必须包含：

- `proposal_id`
- `hypothesis`
- `change_type`，仅允许 `prompt_profile`、`code_patch`、`framework_switch`
- `expected_metric`
- `risk`
- `rollback_plan`

- [x] **Step 2: 实现 guarded proposal round**

`run_cp_bench_proposal_round()` 接收 baseline artifact 和 proposal JSON。若 change_type 不在 allowlist，返回 `rejected_by_guard` 并写 rollback evidence。若执行成功，输出 before/after summary 和 decision。

- [x] **Step 3: 接 MCP**

MCP 工具只执行本地 proposal round，不做外部上传。`write_cp_bench_submission_gate` 只写待人工确认的提交包。

- [x] **Step 4: 跑 MCP schema 测试**

```bash
.venv/bin/python -m pytest -q tests/unit/test_mcp_service.py tests/unit/test_cp_bench_adapter.py
```

预期：通过。

P3 执行补充：

- [x] 新增 `validate_cp_bench_proposal`，proposal 必须包含 `proposal_id`、`hypothesis`、`change_type`、`expected_metric`、`risk`、`rollback_plan`。
- [x] `change_type` allowlist 固定为 `prompt_profile`、`code_patch`、`framework_switch`；外部上传类 proposal 会被 `rejected_by_guard`。
- [x] 新增 `run_cp_bench_proposal_round`，写出 `cp-bench-proposal-round-report.json`、`rollback-evidence.json`、`artifact-manifest.json` 和 README。
- [x] 新增 CLI：`ml-loop hf-eval cp-bench-proposal-round --baseline-report ... --proposal ... --output-dir ... --json`。
- [x] 新增 MCP 工具：`run_cp_bench_proposal_round`。
- [x] 2026-05-23 已完成 P3 smoke：MiniZinc `framework_switch` proposal 因 P2 baseline 仍为 `blocked_missing_dependencies`，正确返回 `blocked_pending_local_eval`，artifact 见 `docs/hf-evaluation/cp-bench-p3-proposal-round/`。

## Task 6: Submission Gate And Proof Archive

**Files:**
- Modify: `lib/benchmarks/cp_bench.py`
- Modify: `docs/evidence/benchmark-results-index-cn.md`
- Create: `docs/hf-evaluation/cp-bench-p3-submission-gate/README.md`

- [x] **Step 1: 生成 submission gate bundle**

`write_cp_bench_submission_gate()` 输出：

- `submission.jsonl`
- `submission-report.md`
- `manual-checklist.md`
- `artifact-manifest.json`
- `SHA256SUMS`

- [x] **Step 2: 写 publication guard**

在 gate bundle 中明确：

- 未人工上传前：`external_submission_status="not_submitted"`
- 未出现公开结果前：`official_scores_claimed=false`
- 不能宣传 ranking、leaderboard score 或 official result。

- [x] **Step 3: 更新证据索引**

只添加 CP-Bench dry-run / local-eval proof，不写外部成绩。真实提交成功后再新增一条 official-submission evidence。

- [x] **Step 4: 运行 release checks**

```bash
ruff check .
.venv/bin/python -m pytest -q tests/unit/test_cp_bench_adapter.py tests/unit/test_cli.py tests/unit/test_mcp_service.py
git diff --check
```

预期：全部通过。

P4 执行补充：

- [x] 新增 `write_cp_bench_submission_gate`，输出 `submission.jsonl`、`submission-report.md`、`manual-checklist.md`、`artifact-manifest.json`、`SHA256SUMS` 和 README。
- [x] 新增 CLI：`ml-loop hf-eval cp-bench-submission-gate --submission ... --source-report ... --output-dir ... --json`。
- [x] 新增 MCP 工具：`write_cp_bench_submission_gate`。
- [x] P4 bundle 明确 `external_submission_status=not_submitted`、`official_scores_claimed=false`、`manual_submission_required=true`。
- [x] 2026-05-23 已完成 P4 smoke，artifact 见 `docs/hf-evaluation/cp-bench-p4-submission-gate/`。

## 验收标准

- `ml-loop hf-eval shortlist --json` 的首选目标是 `cp-bench-constraint-modeling`。
- `ml-loop hf-eval plan --target-id cp-bench-constraint-modeling --output-dir ... --json` 能生成 proof plan。
- `ml-loop hf-eval cp-bench-baseline --dry-run --json` 能写出本地 submission artifact。
- 缺少 constraint modeling 依赖时，命令返回可审计 blocked artifact，而不是崩溃。
- MCP manifest 暴露 CP-Bench 本地验证、baseline、proposal round、candidate round 和 submission gate，但不自动上传。
- 所有文档和 JSON 均保持 `official_scores_claimed=false`，直到真实外部提交和公开结果完成。

## Post-P4 Continuation: Real Local Evaluator Proof

- [x] **P5: 安装可选 evaluator 依赖并跑真实 local summary**

已将 CP-Bench 依赖固化为 `ml-research-loop[hf-cp-bench]` extra，并在本机安装 `datasets`、`click`、`cpmpy`、`minizinc`、`ortools`、`tqdm`。由于普通 pip/uv 下载 OR-Tools 多次超时，本次使用可恢复 `curl` 下载 OR-Tools wheel，再用 `uv pip install` 从本地 wheel 安装。

P5 artifact 见 `docs/hf-evaluation/cp-bench-p5-real-local-eval/`。结果：

- `status=written`
- `dataset_version=verified`
- `framework=CPMpy`
- `submitted_models=1`
- `runtime_success=1/1`
- `coverage_percent=1.59`
- `final_solution_accuracy_percent=0.0`
- `external_submission_status=not_submitted`
- `official_scores_claimed=false`

- [x] **P6: 基于真实 local baseline 重新跑 proposal guard**

P6 artifact 见 `docs/hf-evaluation/cp-bench-p6-real-proposal-round/`。MiniZinc `framework_switch` proposal 现在基于 P5 baseline 返回 `ready_for_guarded_execution`，但尚未执行代码改动或声明效果提升。

- [x] **P7: 基于真实 local baseline 重新生成 submission gate**

P7 artifact 见 `docs/hf-evaluation/cp-bench-p7-real-submission-gate/`。该 bundle 基于 P5 local eval report 生成，仍为 `external_submission_status=not_submitted`、`official_scores_claimed=false`。

- [x] **P8: 执行第一个真实 CP-Bench candidate/code generation round**

新增 `run_cp_bench_candidate_round` adapter、CLI 和 MCP tool，用 P5 真实 baseline 作为 before summary，运行客户端候选 submission 的本地 evaluator，并写出 `cp-bench-candidate-round-report.json`、`candidate-local-eval/` 和 manifest。

P8 artifact 见 `docs/hf-evaluation/cp-bench-p8-candidate-round/`。本轮候选基于第一题 `csplib__csplib_001_car_sequencing` 的公开 description/input_data 手写 CPMpy 模型，结果：

- `status=improved`
- `decision=candidate_improved`
- `before.final_solution_accuracy_percent=0.0`
- `after.final_solution_accuracy_percent=1.59`
- `metric_delta=1.59`
- `external_submission_status=not_submitted`
- `official_scores_claimed=false`

- [x] **P9: 多题 candidate smoke 和逐题失败定位**

新增 CP-Bench summary 逐题 outcome parser，并接入 `run_cp_bench_candidate_round` report。P9 artifact 见 `docs/hf-evaluation/cp-bench-p9-multi-candidate-round/`。本轮先用真实 evaluator 跑 3 题负控 baseline，再提交 3 行 candidate：第一题沿用可行 CPMpy 候选，后两题保留负控用于验证失败定位。

结果：

- baseline `submitted_models=3`
- baseline `runtime_success=3/3`
- baseline `final_solution_accuracy_percent=0.0`
- candidate `submitted_models=3`
- candidate `runtime_success=3/3`
- candidate `final_solution_accuracy_percent=1.59`
- `metric_delta=1.59`
- `model_outcomes`: 1 题 `final_passed=true`，2 题 `final_passed=false`
- artifact 已净化用户目录绝对路径、项目绝对路径和 macOS 临时目录路径
- `external_submission_status=not_submitted`
- `official_scores_claimed=false`

- [x] **P10: 替换负控行，执行三题真实候选 smoke**

P10 artifact 见 `docs/hf-evaluation/cp-bench-p10-three-real-candidates/`。本轮先重跑 3 题负控 baseline，再把 P9 的两个负控行替换为真实候选：

- `csplib__csplib_001_car_sequencing`：CPMpy 约束模型，通过；
- `csplib__csplib_005_autocorrelation`：数学目标最小化候选，可执行但 evaluator self-consistency/objective 失败；
- `csplib__csplib_008_vessel_loading`：构造式布局候选，通过。

结果：

- baseline `final_solution_accuracy_percent=0.0`
- candidate `final_solution_accuracy_percent=3.17`
- `metric_delta=3.17`
- `model_outcomes`: 2 题 `final_passed=true`，1 题 `final_passed=false`
- 失败定位：autocorrelation 候选得到数学目标更小的 `E=36`，但公开 evaluator 的参考模型口径返回 `E=900`，因此这是 evaluator 口径不一致问题，不是运行失败。
- `external_submission_status=not_submitted`
- `official_scores_claimed=false`

- [x] **P11: 基于 P10 失败原因执行 evaluator-compatible repair**

P11 artifact 见 `docs/hf-evaluation/cp-bench-p11-evaluator-compatible-repair/`。本轮以 P10 candidate local eval 为 baseline，只修复 autocorrelation 行，使其匹配公开 evaluator self-consistency 口径。

结果：

- baseline `final_solution_accuracy_percent=3.17`
- candidate `final_solution_accuracy_percent=4.76`
- `metric_delta=1.59`
- `model_outcomes`: 3 题全部 `final_passed=true`
- 该轮证明失败分析、受控修复、逐题 outcome 和本地 proof 闭环可用；
- 该轮不证明数学目标更优算法、官方 leaderboard 排名或规模化自动解题能力。
- `external_submission_status=not_submitted`
- `official_scores_claimed=false`

- [x] **P12: 10 题 scale proof、proposal context 和 submission decision**

P12 artifact 见 `docs/hf-evaluation/cp-bench-p12-ten-row-scale/`。本轮新增 `build_cp_bench_proposal_context` / `cp-bench-proposal-context`，从 P10 失败 outcome 生成给 Codex/Claude 的 proposal prompt context，然后把本地 evaluator proof 扩到 10 个 verified rows。

结果：

- baseline `submitted_models=10`
- baseline `runtime_success=10/10`
- baseline `final_solution_accuracy_percent=0.0`
- candidate `runtime_success=10/10`
- candidate `final_solution_accuracy_percent=15.87`
- `metric_delta=15.87`
- `model_outcomes`: 10 题全部 `final_passed=true`
- `failure_summary`: `passed=10`、`failed=0`
- `rollback_evidence.rollback_required=false`
- `manual-submission-decision.json`: `decision=defer_external_submission`
- `external_submission_status=not_submitted`
- `official_scores_claimed=false`

关键边界：P12 candidate 使用公开 CP-Bench `model` 字段做 reference replay，因此证明的是 evaluator/proof 管线扩容、逐题 outcome、失败分类、rollback evidence 和 proposal context 能力；不证明 autonomous solving、leaderboard 竞争力或官方提交成绩。

- [x] **P13: 非 reference replay client-generated candidate proof**

P13 artifact 见 `docs/hf-evaluation/cp-bench-p13-client-generated-candidate/`。本轮新增 `write_cp_bench_client_candidate_submission` / `cp-bench-client-candidate`，生成不读取公开 `model` 字段的本地 candidate submission，并写出 `source-audit.json`。

结果：

- source audit `reference_model_field_accessed=false`
- source audit `generated_count=3`
- source audit `fallback_count=7`
- candidate `runtime_success=10/10`
- candidate `final_solution_accuracy_percent=4.76`
- `metric_delta=4.76`
- `model_outcomes`: 3 题 `final_passed=true`，7 题进入失败分类
- `failure_summary`: `passed=3`、`failed=7`
- `rollback_evidence.rollback_required=false`
- `proposal-context/`: 已基于 7 个失败样本生成下一轮 Codex/Claude proposal prompt
- `external_submission_status=not_submitted`
- `official_scores_claimed=false`

关键边界：P13 证明非 reference replay 的 client-generated candidate path 可以在 10-row local proof 上产生本地提升；它仍不证明官方 leaderboard、规模化 autonomous solving 或提交竞争力。下一步应继续扩大非 reference client solver 覆盖率，并把失败样本拆成可执行 proposal/repair 队列。

- [x] **P14: 非 reference client solver coverage expansion**

P14 artifact 见 `docs/hf-evaluation/cp-bench-p14-client-solver-expansion/`。本轮继续使用 `write_cp_bench_client_candidate_submission` / `cp-bench-client-candidate`，把同一 `handcrafted-small-cpmpy-v1` strategy 从 3 个手写 solver 扩展到 9 个 solver，并保留 crossfigures 作为唯一 fallback。

结果：

- source audit `reference_model_field_accessed=false`
- source audit `generated_count=9`
- source audit `fallback_count=1`
- fallback problem id: `csplib__csplib_021_crossfigures`
- candidate `runtime_success=10/10`
- candidate `final_solution_accuracy_percent=14.29`
- `metric_delta=14.29`
- `model_outcomes`: 9 题 `final_passed=true`，1 题进入失败分类
- `failure_summary`: `passed=9`、`failed=1`
- `rollback_evidence.rollback_required=false`
- `proposal-context/`: 已基于 crossfigures 失败样本生成下一轮 Codex/Claude proposal prompt
- `external_submission_status=not_submitted`
- `official_scores_claimed=false`

关键边界：P14 是当前最强的 CP-Bench 非 reference local proof，但仍只是本地 evaluator 结果，不是 Hugging Face 官方 leaderboard、排名或外部提交。下一步应针对 crossfigures 单题建立更细的 solver/proposal proof，或生成人工 submission gate 供人审查是否值得外部试投。
