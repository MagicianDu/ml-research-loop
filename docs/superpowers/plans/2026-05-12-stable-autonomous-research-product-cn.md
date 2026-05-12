# 成熟稳定自动科研产品 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 ML Research Loop 从 preview MCP product 推进为可被科研机构、高校实验室、本科高年级和硕博长期使用的成熟稳定自动科研产品。

**Architecture:** 保持混合 MCP 架构：Codex/Claude 作为强模型 planner，ML Research Loop 作为本地执行、证据、实验、patch、评审和归档层；服务端自主 LLM 只作为显式 opt-in。新增能力围绕 `ResearchCase` 长周期状态、环境可复现、自动修复/patch、评测可信度、机构级试用和公开 proof evidence 展开。

**Tech Stack:** Python stdlib + pytest + ruff；现有 MCP stdio service；现有 `lib/fusion_service.py`、`lib/mcp_service.py`、`lib/reproduction_protocol.py`、`lib/experiment_tree.py`、`lib/benchmarks/`、`scripts/release_check.py`、`skills/` 和 `docs/`。

---

## 0. 产品目标和当前边界

### 最终目标

成熟稳定的自动科研产品应支持以下闭环：

1. 读取论文、数据集、代码仓库和已有实验资料。
2. 拆解研究问题、主张、假设、复现任务和评测任务。
3. 自动建立可执行环境，或给出可执行的环境修复计划。
4. 运行训练、评测、日志解析和失败诊断。
5. 根据结果自动提出代码 patch、超参 patch、数据处理 patch 或停止决策。
6. 多轮迭代，持续改进目标指标或明确失败原因。
7. 输出 proof archive、证据索引、实验报告、失败复盘和可复查声明边界。
8. 面向机构用户提供低门槛安装、课程/实验室模板、隐私边界、资源预算和支持流程。

### 当前边界

当前项目已经具备：

- MCP + Skills 入口；
- 研究检索、证据评分和 retrieval diagnostics；
- 固定预算实验运行；
- experiment tree、review handoff、planner actions；
- guarded patch execution；
- reproduction spec、rubric grade report；
- MLE-bench / PaperBench / MemFlow 方向的 proof-run scaffold；
- release gate、CI、fresh checkout、开源文档和 preview demo。

当前仍不能宣称：

- 任意论文可无人值守复现；
- 任意模型效果可自动持续提升；
- 已经具备机构级多用户平台能力；
- 本地 proof set 等同于官方 benchmark 成绩。

## 1. 核心技术挑战

| 挑战 | 为什么难 | 当前基础 | 目标状态 |
| --- | --- | --- | --- |
| 论文理解和证据质量 | 论文主张、实验设置、metric、数据处理细节经常分散在正文、附录、代码和数据卡中 | `research_task`、`read_paper`、evidence citations | 每个 claim 都能绑定 evidence、实验任务和验收标准 |
| 环境可复现 | 真实论文常有 CUDA、系统库、数据路径、私有依赖、版本冲突 | bounded workspace、runtime artifacts | 自动 probe 环境，生成可执行 repair plan 和风险说明 |
| 自动代码修改 | 真实 repo 是多文件、多依赖、多入口，patch 很容易破坏状态 | `apply_client_code_patch`、rollback、syntax/test preflight | 支持多文件小步 patch、测试选择、失败归因和回滚恢复 |
| 长周期规划 | 科研任务跨天、跨轮次、跨证据源，需要状态记忆和阶段门槛 | `experiment_state`、`experiment_tree` | `ResearchCase` 作为长周期状态机，支持继续、暂停、恢复、归档 |
| 评测可信度 | 本地指标、debug fixture、官方 scorer、LLM judge 证据强度不同 | benchmark proof plan/publication/archive | 所有结果带 claim boundary、judge provenance、artifact hash |
| 自动停止条件 | 科研失败不等于任务失败，继续实验也不总是合理 | metric stop policy | 结合预算、方差、失败类型、证据缺口和目标达成度停止 |
| 安全和合规 | 科研数据可能含隐私、未公开数据、机构内部代码和 token | sandbox roots、allowed roots | 增加 redaction、secret scan、institution deployment guide |
| 用户体验 | 科研用户不应理解内部 MCP 细节才能使用 | README、中文产品说明、skills | 形成学生/硕博/PI 三类上手路径和验收脚本 |
| 资源调度 | GPU、长训练、队列、成本、失败重试是机构使用关键 | fixed-budget local execution | 增加 resource profile、queue adapter 预留接口和成本报告 |
| 产品可信度 | 推广需要硬证据，而不是只靠 demo | benchmark evidence index | 每个 release 有公开 proof matrix、真实案例和失败复盘 |

## 2. File Structure

| File | Responsibility |
| --- | --- |
| `docs/product/autonomous-research-product-cn.md` | 定义成熟自动科研产品目标、用户画像、产品边界和机构试用标准。 |
| `docs/evidence/autonomous-product-proof-matrix-cn.md` | 按能力维度索引 proof evidence、benchmark evidence、失败案例和声明边界。 |
| `docs/institution-pilot-guide-cn.md` | 面向高校/科研机构 pilot 的安装、课堂/实验室试用、数据安全和反馈流程。 |
| `lib/research_case.py` | 新增长周期 `ResearchCase` 状态、claim、evidence、experiment milestone 和 stop criteria 数据结构。 |
| `tests/unit/test_research_case.py` | 验证 `ResearchCase` claim/evidence/experiment 状态聚合和声明边界。 |
| `lib/environment_probe.py` | 检测 Python、包、GPU、数据路径、命令入口、写权限和潜在 secret。 |
| `scripts/research_env_probe.py` | CLI 输出环境 readiness JSON，供 MCP、docs 和 pilot 使用。 |
| `tests/unit/test_environment_probe.py` | 验证环境 probe 的 blocked/ready/repair_plan 分类。 |
| `lib/autonomous_loop.py` | 编排 research case 的多轮状态推进，不直接调用未授权 LLM。 |
| `tests/unit/test_autonomous_loop.py` | 验证 loop state、预算、stop decision、failure recovery 和 artifact handoff。 |
| `scripts/autonomous_research_demo.py` | 运行一个小型 end-to-end 自动科研 case demo。 |
| `tests/integration/test_autonomous_research_demo.py` | 验证 demo 可重复运行并生成 report/proof matrix entry。 |
| `skills/ml-research-loop-autonomous-research/SKILL.md` | 新 skill：指导 Codex/Claude 使用 ResearchCase 长周期自动科研流程。 |
| `tests/unit/test_skill_packages.py` | 增加新 skill manifest 和安装检查。 |
| `docs/release-checklist.md` | 增加 mature product gate、pilot gate 和 proof matrix gate。 |
| `scripts/release_check.py` | 把新 demo 和新单测纳入 release gate。 |

## 3. Milestone Roadmap

### P0: 产品目标固化和证据矩阵

**目标：** 先让项目不再围绕“能否 preview”摇摆，明确成熟自动科研产品的能力模型、用户分层、技术挑战和证据门槛。

**Files:**
- Create: `docs/product/autonomous-research-product-cn.md`
- Create: `docs/evidence/autonomous-product-proof-matrix-cn.md`
- Modify: `docs/development-roadmap-cn.md`
- Modify: `docs/product-overview-cn.md`
- Test: `tests/unit/test_mcp_delivery_docs.py`

- [x] **Step 1: 写文档存在性测试**

在 `tests/unit/test_mcp_delivery_docs.py` 增加：

```python
from pathlib import Path


def test_autonomous_research_product_docs_are_present() -> None:
    root = Path(__file__).resolve().parents[2]
    required = [
        root / "docs/product/autonomous-research-product-cn.md",
        root / "docs/evidence/autonomous-product-proof-matrix-cn.md",
    ]
    for path in required:
        text = path.read_text(encoding="utf-8")
        assert "成熟稳定自动科研产品" in text
        assert "不能宣称" in text
```

- [x] **Step 2: 运行测试确认失败**

Run:

```bash
python3 -m pytest tests/unit/test_mcp_delivery_docs.py::test_autonomous_research_product_docs_are_present -q
```

Expected: FAIL，缺少两个文档。

- [x] **Step 3: 写产品目标文档**

创建 `docs/product/autonomous-research-product-cn.md`，必须包含：

- 用户分层：本科高年级、硕博、科研工程师、PI/实验室负责人；
- 成熟产品定义；
- preview/beta/stable 三阶段边界；
- MCP/Skills/客户端模型/服务端 LLM 职责；
- 不能宣称的能力；
- 机构 pilot 验收标准。

- [x] **Step 4: 写 proof matrix 文档**

创建 `docs/evidence/autonomous-product-proof-matrix-cn.md`，按能力维度列出：

| Capability | Current evidence | Gap | Next proof |
| --- | --- | --- | --- |
| Research evidence | provider quality benchmark | 长论文 claim extraction 不足 | ResearchCase claim/evidence fixture |
| Experiment loop | golden path / real-data demo | 长周期恢复不足 | autonomous_research_demo |
| Patch loop | guarded patch demos | 多文件真实 repo 仍弱 | multi-file patch proof |
| Reproduction | PaperBench/MemFlow proof scaffolds | 真实复现闭环不足 | official/debug proof archive |
| Institution readiness | docs/skills | pilot materials 不足 | pilot guide + feedback loop |

- [x] **Step 5: 更新路线图链接**

在 `docs/development-roadmap-cn.md` 和 `docs/product-overview-cn.md` 添加两个新文档链接，并声明成熟产品目标高于 preview 推广目标。

- [x] **Step 6: 运行测试**

Run:

```bash
python3 -m pytest tests/unit/test_mcp_delivery_docs.py::test_autonomous_research_product_docs_are_present -q
```

Expected: PASS。

### P1: ResearchCase 长周期科研状态模型

**目标：** 用一个持久化状态对象表达“一个科研任务”的完整生命周期，而不是把论文、实验、patch、证据散落在不同结果里。

**Files:**
- Create: `lib/research_case.py`
- Create: `tests/unit/test_research_case.py`
- Modify: `lib/fusion_service.py`
- Modify: `lib/mcp_service.py`

- [x] **Step 1: 写 ResearchCase 单测**

创建 `tests/unit/test_research_case.py`：

```python
from lib.research_case import (
    EvidenceRef,
    ResearchCase,
    ResearchClaim,
    ResearchMilestone,
    summarize_research_case,
)


def test_research_case_summarizes_claims_evidence_and_milestones() -> None:
    case = ResearchCase(
        case_id="case-memflow-mini",
        objective="Reproduce one bounded MemFlow claim",
        claims=[
            ResearchClaim(
                claim_id="claim-routing",
                text="Intent routing improves evidence selection",
                status="supported_local",
                evidence_refs=[
                    EvidenceRef(
                        source_id="paper-1",
                        artifact_path="docs/evidence/memflow.md",
                        quote="intent-driven memory orchestration",
                        strength="paper_claim",
                    )
                ],
            )
        ],
        milestones=[
            ResearchMilestone(
                milestone_id="exp-001",
                kind="experiment",
                status="passed",
                artifact_path=".demo_runs/case/metrics.json",
                metric_name="answer_accuracy",
                metric_value=0.57,
            )
        ],
        forbidden_claims=["official benchmark score"],
    )

    summary = summarize_research_case(case)

    assert summary["case_id"] == "case-memflow-mini"
    assert summary["supported_claim_count"] == 1
    assert summary["passed_milestone_count"] == 1
    assert summary["official_scores_claimed"] is False
    assert summary["forbidden_claims"] == ["official benchmark score"]
```

- [x] **Step 2: 运行测试确认失败**

Run:

```bash
python3 -m pytest tests/unit/test_research_case.py -q
```

Expected: FAIL，`lib.research_case` 不存在。

- [x] **Step 3: 实现 ResearchCase 数据结构**

创建 `lib/research_case.py`，实现：

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal


ClaimStatus = Literal["unsupported", "supported_local", "blocked", "needs_evidence"]
EvidenceStrength = Literal["paper_claim", "dataset_card", "code_reference", "runtime_artifact", "weak"]
MilestoneKind = Literal["research", "environment", "experiment", "patch", "review", "proof_archive"]
MilestoneStatus = Literal["pending", "passed", "failed", "blocked"]


@dataclass(frozen=True)
class EvidenceRef:
    source_id: str
    artifact_path: str
    quote: str
    strength: EvidenceStrength

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ResearchClaim:
    claim_id: str
    text: str
    status: ClaimStatus
    evidence_refs: list[EvidenceRef] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["evidence_refs"] = [item.to_dict() for item in self.evidence_refs]
        return data


@dataclass(frozen=True)
class ResearchMilestone:
    milestone_id: str
    kind: MilestoneKind
    status: MilestoneStatus
    artifact_path: str | None = None
    metric_name: str | None = None
    metric_value: float | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ResearchCase:
    case_id: str
    objective: str
    claims: list[ResearchClaim] = field(default_factory=list)
    milestones: list[ResearchMilestone] = field(default_factory=list)
    forbidden_claims: list[str] = field(default_factory=list)
    official_scores_claimed: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "objective": self.objective,
            "claims": [item.to_dict() for item in self.claims],
            "milestones": [item.to_dict() for item in self.milestones],
            "forbidden_claims": list(self.forbidden_claims),
            "official_scores_claimed": self.official_scores_claimed,
        }


def summarize_research_case(case: ResearchCase) -> dict[str, object]:
    return {
        "case_id": case.case_id,
        "objective": case.objective,
        "supported_claim_count": sum(1 for claim in case.claims if claim.status == "supported_local"),
        "blocked_claim_count": sum(1 for claim in case.claims if claim.status == "blocked"),
        "passed_milestone_count": sum(1 for item in case.milestones if item.status == "passed"),
        "failed_milestone_count": sum(1 for item in case.milestones if item.status == "failed"),
        "official_scores_claimed": bool(case.official_scores_claimed),
        "forbidden_claims": list(case.forbidden_claims),
    }
```

- [x] **Step 4: 运行单测**

Run:

```bash
python3 -m pytest tests/unit/test_research_case.py -q
```

Expected: PASS。

- [x] **Step 5: 通过 MCP manifest 暴露 ResearchCase 能力**

修改 `lib/mcp_service.py`：

- 在 `REQUIRED_TOOLS` 追加 `plan_research_case`；
- 在 `TOOL_CONTRACT_DESCRIPTIONS` 添加说明；
- 在 service manifest 的 planning signals 中加入 `research_case`。

- [x] **Step 6: 增加 MCP manifest 测试**

在 `tests/unit/test_mcp_service.py` 增加断言：

```python
def test_service_manifest_exposes_research_case_signal() -> None:
    manifest = call_tool("get_service_manifest", {})
    assert "plan_research_case" in manifest["tools"]
    assert "research_case" in manifest["planning_signals"]
```

具体 helper 名称以现有 `tests/unit/test_mcp_service.py` 为准，不新增第二套 MCP test harness。

### P2: 环境可复现和修复计划

**目标：** 让产品能判断“这个论文/代码/数据任务为什么跑不起来”，并输出机器可读 repair plan。

**Files:**
- Create: `lib/environment_probe.py`
- Create: `scripts/research_env_probe.py`
- Create: `tests/unit/test_environment_probe.py`
- Create: `tests/integration/test_research_env_probe_script.py`
- Modify: `docs/release-checklist.md`

- [ ] **Step 1: 写环境 probe 单测**

创建 `tests/unit/test_environment_probe.py`：

```python
from pathlib import Path

from lib.environment_probe import probe_research_environment


def test_probe_reports_missing_required_files(tmp_path: Path) -> None:
    payload = probe_research_environment(
        workspace=tmp_path,
        required_files=["train.py", "data/train.csv"],
        required_commands=["python3"],
    )

    assert payload["status"] == "blocked"
    assert payload["missing_files"] == ["train.py", "data/train.csv"]
    assert payload["repair_plan"][0]["kind"] == "create_or_mount_file"
    assert payload["official_scores_claimed"] is False
```

- [ ] **Step 2: 实现环境 probe**

创建 `lib/environment_probe.py`，最小实现检查：

- workspace 是否存在；
- required files 是否存在；
- required commands 是否在 `PATH`；
- 是否存在 `.env`、`*_TOKEN` 字样文件名或可疑 token 片段；
- 输出 `status in {"ready", "blocked"}`；
- 输出 `repair_plan`。

- [ ] **Step 3: 增加 CLI**

创建 `scripts/research_env_probe.py`，支持：

```bash
python3 scripts/research_env_probe.py \
  --workspace . \
  --required-file train.py \
  --required-command python3 \
  --json
```

- [ ] **Step 4: 增加集成测试**

创建 `tests/integration/test_research_env_probe_script.py`，用临时目录跑 CLI，断言 JSON 可解析且缺文件时 `status=blocked`。

- [ ] **Step 5: release checklist 增加验收**

在 `docs/release-checklist.md` 增加：

```bash
python3 scripts/research_env_probe.py --workspace . --required-command python3 --json
```

### P3: 自动科研 Loop Controller

**目标：** 把“读资料、计划、实验、评审、patch、停止”组织成可恢复的状态机，避免每个 demo 都是一次性脚本。

**Files:**
- Create: `lib/autonomous_loop.py`
- Create: `tests/unit/test_autonomous_loop.py`
- Create: `scripts/autonomous_research_demo.py`
- Create: `tests/integration/test_autonomous_research_demo.py`
- Modify: `scripts/release_check.py`
- Modify: `skills/ml-research-loop-planner/SKILL.md`

- [ ] **Step 1: 写 loop policy 单测**

创建 `tests/unit/test_autonomous_loop.py`：

```python
from lib.autonomous_loop import decide_next_autonomous_action


def test_loop_stops_when_budget_exhausted() -> None:
    decision = decide_next_autonomous_action(
        case_summary={"supported_claim_count": 1, "failed_milestone_count": 0},
        budget={"max_rounds": 3, "completed_rounds": 3},
        latest_review={"loop_decision": {"decision": "continue"}},
    )

    assert decision["action"] == "stop"
    assert decision["reason_category"] == "budget_exhausted"
```

- [ ] **Step 2: 实现 loop decision**

创建 `lib/autonomous_loop.py`，至少支持：

- `budget_exhausted`；
- `needs_failure_debugging`；
- `needs_more_evidence`；
- `continue_experiment`；
- `write_proof_archive`。

所有输出必须包含：

```python
{
    "action": "...",
    "reason_category": "...",
    "requires_human_confirmation": bool,
    "official_scores_claimed": False,
}
```

- [ ] **Step 3: 增加 demo 脚本**

创建 `scripts/autonomous_research_demo.py`，用现有小任务 fixture 运行：

1. research context；
2. hypothesis；
3. one bounded experiment；
4. review；
5. autonomous loop decision；
6. JSON report。

- [ ] **Step 4: 集成进 release gate**

修改 `scripts/release_check.py`，增加 `autonomous-research-demo` check。该 check 必须短、小、无网络依赖。

- [ ] **Step 5: 更新 planner skill**

修改 `skills/ml-research-loop-planner/SKILL.md`，增加规则：

- 长周期科研任务优先创建或读取 `ResearchCase`；
- 每轮实验后先读取 `loop_decision`；
- 遇到 `requires_human_confirmation=true` 时停止并汇报；
- 不把 local proof 说成 official score。

### P4: 可信评测和 Proof Evidence 升级

**目标：** 将每个对外能力声明绑定到可下载、可 hash、可复跑的 evidence。

**Files:**
- Modify: `lib/benchmarks/proof_archive.py`
- Modify: `lib/benchmarks/proof_publication.py`
- Create: `lib/proof_release_index.py`
- Create: `scripts/proof_release_index.py`
- Create: `tests/unit/test_proof_release_index.py`
- Create: `tests/integration/test_proof_release_index_script.py`
- Modify: `docs/evidence/autonomous-product-proof-matrix-cn.md`

- [ ] **Step 1: 增加 release index 测试**

写测试要求 indexer 读取：

- `proof-archive.json`；
- `artifact-index.json`；
- `publication/proof-publication.json`。

并输出：

- `official_scores_claimed=false`；
- `blocked_public_claims`；
- artifact sha256；
- Markdown index。

- [ ] **Step 2: 实现 release indexer**

实现 `write_proof_release_index(entries, output_dir)`，不得复制 `.demo_runs` 原始大目录，只索引 archive metadata 和 hash。

- [ ] **Step 3: 生成 proof matrix entry**

更新 `docs/evidence/autonomous-product-proof-matrix-cn.md`，新增一节：

- proof archive path；
- judge type；
- metric；
- claim boundary；
- blocked claims。

### P5: 机构 Pilot 和教学试用包

**目标：** 让高校/科研机构不是“看懂 README 后自己摸索”，而是能按场景试用并反馈。

**Files:**
- Create: `docs/institution-pilot-guide-cn.md`
- Create: `examples/pilot/student-byte-lm/README.md`
- Create: `examples/pilot/reproduction-mini/README.md`
- Create: `examples/pilot/lab-benchmark/README.md`
- Create: `.github/ISSUE_TEMPLATE/pilot_feedback.yml`
- Modify: `README.md`

- [ ] **Step 1: 写 pilot guide**

`docs/institution-pilot-guide-cn.md` 必须包含：

- 30 分钟本科实验；
- 2 小时硕博论文复现 mini lab；
- 1 天实验室 benchmark trial；
- 数据安全注意事项；
- 失败反馈模板；
- 预期输入/输出 artifact。

- [ ] **Step 2: 增加三个 pilot examples**

每个 example README 都必须包含：

- 适合对象；
- 运行命令；
- 预期输出；
- 常见失败；
- 应提交的反馈文件。

- [ ] **Step 3: GitHub issue template**

创建 `.github/ISSUE_TEMPLATE/pilot_feedback.yml`，字段包括：

- 用户角色；
- 客户端：Codex / Claude Code / Claude Desktop；
- OS；
- Python version；
- demo command；
- failure log；
- redacted feedback bundle path；
- 是否愿意访谈。

### P6: Beta/Stable 产品门槛

**目标：** 定义什么时候可以从 preview 进入 beta，再进入 stable。

**Files:**
- Modify: `docs/release-notes.md`
- Modify: `docs/release-checklist.md`
- Modify: `docs/client-compatibility-matrix.md`
- Modify: `scripts/fresh_checkout_check.py`

- [ ] **Step 1: Beta gate**

Beta 必须满足：

- clean checkout install；
- MCP client acceptance；
- skills install dry-run；
- bounded demo；
- autonomous research demo；
- proof matrix 至少 3 条；
- pilot guide 完成；
- 已知限制明确。

- [ ] **Step 2: Stable gate**

Stable 必须满足：

- 合约版本冻结；
- 兼容矩阵覆盖 Codex、Claude Code、Claude Desktop；
- 至少 3 个外部用户 pilot feedback；
- 至少 2 个真实任务 proof archive；
- 至少 1 个官方或官方 debug benchmark proof；
- 所有 public claims 都有 proof matrix entry；
- release artifact 可下载并 hash 复核。

- [ ] **Step 3: fresh checkout 增加 stable readiness 输出**

修改 `scripts/fresh_checkout_check.py`，增加 `--stable-readiness` 选项，输出：

```json
{
  "status": "preview_ready",
  "beta_blockers": [],
  "stable_blockers": ["missing_external_pilot_feedback"]
}
```

## 4. 验收命令

每个阶段至少运行：

```bash
python3 -m pytest tests/unit/test_research_case.py tests/unit/test_environment_probe.py tests/unit/test_autonomous_loop.py -q
python3 -m pytest tests/integration/test_research_env_probe_script.py tests/integration/test_autonomous_research_demo.py -q
ruff check lib/ scripts/ tests/
python3 scripts/release_check.py --json
git diff --check
```

如果当前阶段还没有实现某个测试文件，只运行该阶段新增的测试和现有 release gate。

## 5. 推进顺序

1. **先做 P0**：产品目标和 proof matrix，不写清楚目标会导致后续 demo 继续发散。
2. **再做 P1**：ResearchCase 是成熟自动科研产品的状态核心。
3. **再做 P2/P3**：环境 probe 和 autonomous loop 解决“真实任务跑不起来”和“多轮状态丢失”的主要问题。
4. **再做 P4**：proof evidence 升级，避免产品宣传没有硬证据。
5. **最后做 P5/P6**：机构试用和 beta/stable 门槛，让产品走向真实用户。

## 6. 自审结论

- 该计划覆盖产品目标、技术挑战、核心状态模型、环境可复现、自动 loop、证据发布、机构 pilot 和 beta/stable release gate。
- 计划不把服务端 LLM 作为默认智能来源，继续保留 Codex/Claude planner 与 MCP executor 解耦。
- 计划把“成熟稳定自动科研产品”拆成可验收能力，而不是停留在宣传语。
- 最大技术风险是 P3：真实长周期自动科研 loop 很容易在失败恢复、环境修复、评价可信度和资源预算之间互相牵制，因此必须先用小型 deterministic demo 和 proof matrix 收紧边界，再扩大真实任务。
