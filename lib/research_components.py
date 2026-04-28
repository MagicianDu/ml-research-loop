"""
Research Components — core AI-driven research loop components.
Includes ResearchAnalyzer, ChangeProposer, and ChangeExecutor.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from lib.llm_providers import LLMProvider
# SEARCH REGION markers (duplicated here to avoid circular import with scripts)
SEARCH_REGION_START = "# ======= AUTORESEARCH SEARCH REGION START ======="
SEARCH_REGION_END = "# ======= AUTORESEARCH SEARCH REGION END ======="


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class AnalyzeResult:
    """Result of analyzing train.py, experiment history, and metrics trends."""
    current_code_summary: str
    experiment_history_summary: str
    metrics_trend: str
    promising_directions: list[str] = field(default_factory=list)
    risk_directions: list[str] = field(default_factory=list)
    focus_suggestion: str = ""


@dataclass
class ChangeProposal:
    """Proposed change from LLM."""
    change_type: str  # "hyperparam" | "architecture" | "training_strategy"
    target: str       # e.g. "DEPTH", "LR", "NHEAD"
    current_value: str
    proposed_value: str
    reason: str
    confidence: float = 0.5
    llm_model: str = ""
    proposal_attempt: int = 0


@dataclass
class ExecutionResult:
    """Result of executing a change proposal on train.py."""
    success: bool
    change_record: Optional[dict] = None
    error: Optional[str] = None
    rollback: bool = False


# ─── Search Region Parser ──────────────────────────────────────────────────────

def parse_search_region(content: str) -> dict[str, str]:
    """
    Parse the SEARCH REGION from train.py content.
    Returns a dict of {variable_name: current_value_string}.
    """
    pattern = rf"({re.escape(SEARCH_REGION_START)}.*?{re.escape(SEARCH_REGION_END)})"
    match = re.search(pattern, content, flags=re.DOTALL)
    if not match:
        return {}

    region = match.group(1)
    result = {}

    for line in region.splitlines():
        m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.+)", line.strip())
        if m:
            result[m.group(1)] = m.group(2).strip()

    return result


# ─── Research Analyzer ────────────────────────────────────────────────────────

class ResearchAnalyzer:
    """
    Analyzes train.py, experiment history, and metrics trends.
    Generates context for LLM to propose meaningful changes.
    """

    def __init__(self, workspace: Path, task_id: str):
        self.workspace = workspace
        self.task_id = task_id
        self.train_py_path = workspace / "train.py"
        self.experiments_path = workspace / "experiments.json"
        self._experiments_cache: Optional[list[dict]] = None

    def analyze(self) -> AnalyzeResult:
        """Run full analysis and return AnalyzeResult."""
        code_summary = self._analyze_train_py()
        history_summary, trend = self._analyze_history_and_trend()
        promising, risky = self._analyze_directions(history_summary, trend)
        focus = self._suggest_focus(promising, risky, trend)

        return AnalyzeResult(
            current_code_summary=code_summary,
            experiment_history_summary=history_summary,
            metrics_trend=trend,
            promising_directions=promising,
            risk_directions=risky,
            focus_suggestion=focus,
        )

    def _analyze_train_py(self) -> str:
        """Parse SEARCH REGION and summarize current hyperparameters."""
        if not self.train_py_path.exists():
            return "train.py not found"

        content = self.train_py_path.read_text(encoding="utf-8")
        params = parse_search_region(content)

        if not params:
            return "No SEARCH REGION found in train.py"

        lines = ["## 当前 SEARCH REGION 超参数"]
        for name, value in sorted(params.items()):
            lines.append(f"- {name} = {value}")

        # Add model architecture info
        depth_match = re.search(r"DEPTH\s*=\s*(\d+)", content)
        dim_match = re.search(r"DIM\s*=\s*(\d+)", content)
        window_match = re.search(r"WINDOW_SIZE\s*=\s*(\d+)", content)

        lines.append("\n## 当前架构")
        if depth_match:
            lines.append(f"- Transformer层数: {depth_match.group(1)}")
        if dim_match:
            lines.append(f"- 模型维度: {dim_match.group(1)}")
        if window_match:
            lines.append(f"- 上下文窗口: {window_match.group(1)}")

        return "\n".join(lines)

    def _get_experiments(self) -> list[dict]:
        """Load experiments from experiments.json."""
        if self._experiments_cache is not None:
            return self._experiments_cache

        if self.experiments_path.exists():
            try:
                data = json.loads(self.experiments_path.read_text(encoding="utf-8"))
                self._experiments_cache = data.get("experiments", [])
            except json.JSONDecodeError:
                self._experiments_cache = []
        else:
            self._experiments_cache = []

        return self._experiments_cache

    def _analyze_history_and_trend(self) -> tuple[str, str]:
        """Analyze experiment history and compute metrics trend."""
        experiments = self._get_experiments()

        if not experiments:
            return "暂无实验历史", "无数据，无法判断趋势"

        lines = ["## 实验历史（最近10个）"]
        recent = experiments[-10:] if len(experiments) > 10 else experiments

        for exp in recent:
            eid = exp.get("experiment_id", "?")
            params = exp.get("params", {})
            metrics = exp.get("metrics", {})
            accepted = exp.get("accepted", False)
            change_rec = exp.get("change_record", {})

            val = metrics.get("val_bpb", metrics.get("val", "N/A"))
            status = "✅" if accepted else "❌"

            if change_rec:
                target = change_rec.get("target", "?")
                fr = change_rec.get("from", "?")
                to = change_rec.get("to", "?")
                change_desc = f"{target}: {fr}→{to}"
            elif params:
                change_desc = ", ".join(f"{k}={v}" for k, v in params.items())
            else:
                change_desc = "baseline"

            lines.append(f"- {eid}: {change_desc} | val_bpb={val} {status}")

        # Compute trend
        val_bpbs = []
        for exp in experiments:
            metrics = exp.get("metrics", {})
            val = metrics.get("val_bpb", metrics.get("val"))
            if val is not None:
                val_bpbs.append(float(val))

        if len(val_bpbs) >= 3:
            recent_vals = val_bpbs[-5:]
            first = sum(recent_vals[:2]) / 2
            last = sum(recent_vals[-2:]) / 2
            delta = last - first

            if delta < -0.05:
                trend = f"📉 下降趋势 (最近5个均值: {last:.4f} < {first:.4f}, delta={delta:.4f})"
            elif delta > 0.05:
                trend = f"📈 上升趋势 (最近5个均值: {last:.4f} > {first:.4f}, delta={delta:.4f})"
            else:
                trend = f"➡️ 平台期 (最近5个均值基本持平: {last:.4f} vs {first:.4f})"
        else:
            trend = "数据不足，无法判断趋势"

        return "\n".join(lines), trend

    def _analyze_directions(self, history_summary: str, trend: str) -> tuple[list[str], list[str]]:
        """Extract promising and risky directions from experiment history."""
        experiments = self._get_experiments()

        promising = []
        risky = []

        if not experiments:
            return promising, risky

        # Analyze parameter direction correlations
        param_effects: dict[str, list[tuple[str, float]]] = {}  # param -> [(value, val_bpb)]

        for exp in experiments:
            params = exp.get("params", {})
            metrics = exp.get("metrics", {})
            val = metrics.get("val_bpb", metrics.get("val"))
            if val is None:
                continue

            for pname, pval in params.items():
                if pname not in param_effects:
                    param_effects[pname] = []
                param_effects[pname].append((str(pval), float(val)))

        # Compute correlation direction
        for pname, pairs in param_effects.items():
            if len(pairs) < 2:
                continue

            bpbs = [b for _, b in pairs]

            # Simple correlation: check if larger param value tends to lower val_bpb
            avg_low = sum(bpbs[:len(bpbs)//2]) / max(1, len(bpbs)//2)
            avg_high = sum(bpbs[len(bpbs)//2:]) / max(1, len(bpbs) - len(bpbs)//2)

            if avg_high < avg_low - 0.05:
                promising.append(
                    f"{pname} 增大 → val_bpb 降低（历史数据支持）"
                )
            elif avg_high > avg_low + 0.05:
                promising.append(
                    f"{pname} 减小 → val_bpb 降低（历史数据支持）"
                )

        # Add risk directions from failed experiments
        for exp in experiments[-5:]:
            if not exp.get("accepted") and not exp.get("error"):
                params = exp.get("params", {})
                if params:
                    pname = list(params.keys())[0]
                    pval = params[pname]
                    risky.append(f"{pname}={pval} 未能改善（已失败）")

        return promising, risky[:5]  # limit to 5

    def _suggest_focus(self, promising: list[str], risky: list[str], trend: str) -> str:
        """Generate focus suggestion based on analysis."""
        parts = ["## 建议关注的改进方向"]

        if promising:
            parts.append("基于历史数据，以下方向可能有前景：")
            for p in promising[:3]:
                parts.append(f"- {p}")
        else:
            parts.append("暂无明确的成功方向，建议继续探索参数空间")

        if risky:
            parts.append("\n建议回避的方向：")
            for r in risky[:3]:
                parts.append(f"- {r}")

        if "平台期" in trend:
            parts.append("\n当前处于平台期，建议尝试更激进的改动或新方向")
        elif "下降" in trend:
            parts.append("\n指标正在下降，搜索方向有效，继续当前策略")

        return "\n".join(parts)


# ─── Change Proposer ──────────────────────────────────────────────────────────

class ChangeProposer:
    """
    Calls LLM to propose specific changes based on analyze results.
    Falls back to random sampling if LLM fails.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        metric_name: str = "val_bpb",
        metric_direction: str = "minimize",
    ):
        self.llm_provider = llm_provider
        self.metric_name = metric_name
        self.metric_direction = metric_direction
        self.proposal_history: list[ChangeProposal] = []

    def propose(
        self,
        analyze_result: AnalyzeResult,
        attempt: int = 0,
    ) -> Optional[ChangeProposal]:
        """
        Propose a change based on analysis. Returns None on failure.
        """
        prompt = self._build_prompt(analyze_result, attempt)

        try:
            response = self.llm_provider.generate(prompt)
            proposal = self._parse_response(response, analyze_result, attempt)

            if proposal:
                self.proposal_history.append(proposal)

            return proposal

        except Exception as e:
            print(f"[ChangeProposer] LLM call failed: {e}")
            return None

    def _build_prompt(self, result: AnalyzeResult, attempt: int) -> str:
        """Build LLM prompt from analysis result."""
        system_prompt = f"""你是一个 ML 研究助手，专注于{self.metric_direction} {self.metric_name}。
每次只提出一个具体的改动建议。

改动类型：
- hyperparam: 超参数修改（如 DEPTH, LR, DIM 等 SEARCH REGION 内的变量）
- architecture: 架构修改（如 nhead 数量、层数等模型结构）
- training_strategy: 训练策略修改（如 optimizer、lr_scheduler 等）

约束：
1. 每次只改一个参数
2. 数值改动不超过当前值的 4 倍或 1/4 倍（防止跳变过大）
3. 只修改 SEARCH REGION 内的变量
4. 改动必须有明确的原因和预期效果

请以 JSON 格式输出，字段：change_type, target, current_value, proposed_value, reason, confidence"""

        prompt = f"""{system_prompt}

当前任务：{self.metric_direction} {self.metric_name}

## 当前代码超参
{result.current_code_summary}

## 实验历史
{result.experiment_history_summary}

## 指标趋势
{result.metrics_trend}

## 有前景的方向
{chr(10).join(f"- {d}" for d in result.promising_directions) if result.promising_directions else "暂无"}

## 高风险方向
{chr(10).join(f"- {d}" for d in result.risk_directions) if result.risk_directions else "暂无"}

## 建议关注
{result.focus_suggestion}

## 约束
- 改动必须具体、可执行
- 只修改 SEARCH REGION 内的变量
- 数值不能变化超过4倍

请提出一个改动建议（JSON格式）：
"""
        return prompt

    def _parse_response(
        self,
        response: str,
        analyze_result: AnalyzeResult,
        attempt: int,
    ) -> Optional[ChangeProposal]:
        """Parse LLM response to extract ChangeProposal."""
        # Try to extract JSON from response
        json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
        if not json_match:
            return self._fallback_random(analyze_result)

        try:
            data = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            return self._fallback_random(analyze_result)

        # Validate required fields
        required = ["change_type", "target", "current_value", "proposed_value"]
        if not all(k in data for k in required):
            return self._fallback_random(analyze_result)

        return ChangeProposal(
            change_type=data["change_type"],
            target=data["target"],
            current_value=str(data["current_value"]),
            proposed_value=str(data["proposed_value"]),
            reason=data.get("reason", "No reason provided"),
            confidence=float(data.get("confidence", 0.5)),
            llm_model=self.llm_provider.name,
            proposal_attempt=attempt,
        )

    def _fallback_random(self, analyze_result: AnalyzeResult) -> Optional[ChangeProposal]:
        """Fallback to random sampling when LLM fails."""
        # Parse current params to find a valid target
        content = analyze_result.current_code_summary

        targets = []
        for line in content.splitlines():
            m = re.match(r"-\s+([A-Z_][A-Z0-9_]*)\s*=", line)
            if m:
                targets.append(m.group(1))

        if not targets:
            return None

        import random

        target = random.choice(targets)

        # Get current value
        current_match = re.search(
            rf"{target}\s*=\s*([^\s-]+)",
            content,
        )
        current_value = current_match.group(1) if current_match else "?"

        # Simple random proposal
        proposed_value = str(random.choice([4, 6, 8, 10, 16]))

        return ChangeProposal(
            change_type="hyperparam",
            target=target,
            current_value=current_value,
            proposed_value=proposed_value,
            reason="LLM fallback: random sampling",
            confidence=0.3,
            llm_model="fallback",
            proposal_attempt=0,
        )


# ─── Change Executor ──────────────────────────────────────────────────────────

class ChangeExecutor:
    """
    Executes LLM-proposed changes on train.py.
    Includes validation and rollback on failure.
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.train_py_path = workspace / "train.py"
        self._backup_path: Optional[Path] = None

    def execute(self, proposal: ChangeProposal) -> ExecutionResult:
        """
        Execute a change proposal on train.py.
        Returns ExecutionResult with success status and details.
        """
        if not self.train_py_path.exists():
            return ExecutionResult(
                success=False,
                error="train.py not found",
                rollback=False,
            )

        supported_change_types = {"hyperparam", "architecture", "training_strategy"}
        if proposal.change_type not in supported_change_types:
            return ExecutionResult(
                success=False,
                error=f"Unsupported change_type: {proposal.change_type}",
                rollback=False,
            )

        # Read current content
        content = self.train_py_path.read_text(encoding="utf-8")

        # Create backup
        backup_path = self.workspace / "train.py.backup"
        shutil.copy2(self.train_py_path, backup_path)
        self._backup_path = backup_path

        # Apply change
        modified_content = self._apply_hyperparam(content, proposal)

        # Validate syntax
        if not self._validate_syntax(modified_content):
            # Rollback
            self._rollback()
            return ExecutionResult(
                success=False,
                error="Syntax validation failed after modification",
                rollback=True,
            )

        # Write modified content
        self.train_py_path.write_text(modified_content, encoding="utf-8")

        # Build change record
        change_record = {
            "change_type": proposal.change_type,
            "target": proposal.target,
            "from": proposal.current_value,
            "to": proposal.proposed_value,
            "reason": proposal.reason,
            "confidence": proposal.confidence,
        }

        return ExecutionResult(
            success=True,
            change_record=change_record,
            error=None,
            rollback=False,
        )

    def _apply_hyperparam(self, content: str, proposal: ChangeProposal) -> str:
        """Apply hyperparameter change to train.py content."""
        # Find and replace the specific parameter in SEARCH REGION
        target = proposal.target
        new_value = proposal.proposed_value

        # Match the SEARCH REGION
        pattern = rf"({re.escape(SEARCH_REGION_START)}.*?{re.escape(SEARCH_REGION_END)})"
        match = re.search(pattern, content, flags=re.DOTALL)
        if not match:
            raise ValueError("SEARCH REGION not found in train.py")

        region_start = match.start()
        region_end = match.end()

        region_content = match.group(1)

        # Find the specific parameter line
        param_pattern = rf"({re.escape(target)}\s*=\s*)([^\n]+)"
        param_match = re.search(param_pattern, region_content)

        if not param_match:
            # Parameter not found in SEARCH REGION, try adding it
            new_line = f"{target} = {new_value}"
            # Append before SEARCH_REGION_END
            new_region = region_content.rstrip() + "\n" + new_line + "\n"
        else:
            # Replace the value
            new_region = (
                region_content[:param_match.start()]
                + f"{target} = {new_value}"
                + region_content[param_match.end():]
            )

        # Reconstruct full content
        modified = content[:region_start] + new_region + content[region_end:]

        return modified

    def _validate_syntax(self, content: str) -> bool:
        """Validate train.py syntax by compiling."""
        import py_compile
        import tempfile

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                encoding="utf-8",
                delete=False,
            ) as f:
                f.write(content)
                f.flush()
                temp_path = f.name

            py_compile.compile(temp_path, doraise=True)
            return True

        except (py_compile.PyCompileError, SyntaxError):
            return False

        finally:
            try:
                import os
                os.unlink(temp_path)
            except Exception:
                pass

    def _rollback(self) -> None:
        """Rollback to backup."""
        if self._backup_path and self._backup_path.exists():
            shutil.copy2(self._backup_path, self.train_py_path)
            self._backup_path.unlink()
            self._backup_path = None
