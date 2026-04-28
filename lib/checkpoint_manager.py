"""
CheckpointManager — checkpoint / resume for ml-research-loop tasks.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from lib.task_protocol import WORKSPACE_ROOT


CHECKPOINTS_DIR = WORKSPACE_ROOT / "checkpoints"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CheckpointManager:
    """
    Manages task-level checkpoint存档与恢复。

    目录结构：
        checkpoints/<task_id>/
        ├── checkpoint_manifest.json
        ├── task_definition.json
        ├── experiments.json
        ├── best/
        │   ├── model.pt
        │   ├── train.py
        │   └── metadata.json
        └── runs/
            ├── run-001/
            └── run-002/
    """

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.checkpoint_root = CHECKPOINTS_DIR / task_id
        self.best_dir = self.checkpoint_root / "best"
        self.runs_dir = self.checkpoint_root / "runs"

    # ── 存档 ────────────────────────────────────────────────────────────────

    def save_checkpoint(
        self,
        experiment_id: str,
        experiments_json: dict,
        workdir: Path,
        is_new_best: bool = False,
        best_val: Optional[float] = None,
        best_params: Optional[dict] = None,
    ) -> None:
        """
        每次实验结束后调用，保存 checkpoint。

        Args:
            experiment_id: 当前实验 ID（如 exp-003）
            experiments_json: ExperimentStore 序列化的 dict
            workdir: 当前 workdir 路径
            is_new_best: 本次是否产生了新的最佳模型
            best_val: 当前最佳指标值
            best_params: 当前最佳超参
        """
        self.checkpoint_root.mkdir(parents=True, exist_ok=True)

        # 1. 保存 experiments.json 快照到 runs/
        run_dir = self.runs_dir / f"run-{self._next_run_id()}"
        run_dir.mkdir(parents=True, exist_ok=True)
        self._atomic_write(
            run_dir / "experiments.json",
            json.dumps(experiments_json, indent=2, ensure_ascii=False),
        )

        # 2. 保存当前 train.py（通用存档）
        train_py = workdir / "train.py"
        if train_py.exists():
            shutil.copy2(train_py, run_dir / "train.py")

        # 3. 若本次是新的 best，存档 best 模型
        if is_new_best and best_val is not None:
            self.best_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(train_py, self.best_dir / "train.py")

            model_pt = workdir / "model.pt"
            if model_pt.exists():
                shutil.copy2(model_pt, self.best_dir / "model.pt")

            # 写入 best 元信息
            self._atomic_write(
                self.best_dir / "metadata.json",
                json.dumps({
                    "experiment_id": experiment_id,
                    "best_val": best_val,
                    "best_params": best_params,
                    "saved_at": now_iso(),
                }, indent=2, ensure_ascii=False),
            )

        # 4. 更新 checkpoint manifest
        self._update_manifest(
            experiment_id=experiment_id,
            completed_experiments=self._get_completed_ids(run_dir),
            best_val=best_val,
            best_params=best_params,
        )

    def save_task_definition(self, task_def: "TaskDefinition") -> None:  # noqa: F821
        """存档任务定义（任务启动时调用）。"""
        self.checkpoint_root.mkdir(parents=True, exist_ok=True)
        self._atomic_write(
            self.checkpoint_root / "task_definition.json",
            json.dumps(task_def.to_dict(), indent=2, ensure_ascii=False),
        )

    # ── 恢复 ────────────────────────────────────────────────────────────────

    def load_checkpoint(self, task_id: str) -> Optional[dict]:
        """返回最新 checkpoint 的 manifest，无存档则返回 None。"""
        manifest_path = self.checkpoint_root / "checkpoint_manifest.json"
        if not manifest_path.exists():
            return None
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def has_checkpoint(self, task_id: str) -> bool:
        """检测是否有可恢复的 checkpoint。"""
        return (self.checkpoint_root / "checkpoint_manifest.json").exists()

    def get_best_checkpoint(self, task_id: str) -> Optional[dict]:
        """返回最佳 checkpoint 的完整存档信息。"""
        manifest_path = self.checkpoint_root / "checkpoint_manifest.json"
        if not manifest_path.exists():
            return None

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        best_dir = self.checkpoint_root / "best"

        result = {
            "manifest": manifest,
            "best_val": manifest.get("best_val"),
            "best_params": manifest.get("best_params"),
            "model_path": str(best_dir / "model.pt") if (best_dir / "model.pt").exists() else None,
            "train_py_path": str(best_dir / "train.py") if (best_dir / "train.py").exists() else None,
            "metadata_path": str(best_dir / "metadata.json") if (best_dir / "metadata.json").exists() else None,
        }
        return result

    def get_best_model_path(self) -> Optional[Path]:
        """返回最佳模型路径，无则返回 None。"""
        p = self.best_dir / "model.pt"
        return p if p.exists() else None

    # ── 辅助 ───────────────────────────────────────────────────────────────

    def _next_run_id(self) -> str:
        """返回下一个 run 目录编号。"""
        if not self.runs_dir.exists():
            return "001"
        existing = sorted(self.runs_dir.iterdir())
        if not existing:
            return "001"
        last = existing[-1].name  # e.g. "run-003"
        num = int(last.split("-")[1]) + 1
        return f"{num:03d}"

    def _get_completed_ids(self, run_dir: Path) -> list[str]:
        """从 experiments.json 中提取已完成 experiment_id 列表。"""
        experiments_file = run_dir / "experiments.json"
        if not experiments_file.exists():
            return []
        try:
            data = json.loads(experiments_file.read_text(encoding="utf-8"))
            return [e["experiment_id"] for e in data.get("experiments", [])]
        except (json.JSONDecodeError, KeyError):
            return []

    def _update_manifest(
        self,
        experiment_id: str,
        completed_experiments: list[str],
        best_val: Optional[float],
        best_params: Optional[dict],
    ) -> None:
        """原子上写 checkpoint_manifest.json。"""
        manifest = {
            "task_id": self.task_id,
            "experiment_id": experiment_id,
            "last_experiment_index": self._parse_exp_index(experiment_id),
            "completed_experiment_ids": completed_experiments,
            "best_val": best_val,
            "best_params": best_params,
            "saved_at": now_iso(),
        }
        self._atomic_write(
            self.checkpoint_root / "checkpoint_manifest.json",
            json.dumps(manifest, indent=2, ensure_ascii=False),
        )

    def _parse_exp_index(self, experiment_id: str) -> int:
        """从 experiment_id 提取数字索引（如 exp-003 → 2）。"""
        try:
            return int(experiment_id.split("-")[1]) - 1
        except (IndexError, ValueError):
            return -1

    def _atomic_write(self, path: Path, content: str) -> None:
        """使用 tempfile + rename 实现原子写入。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}_tmp_",
            suffix=".json",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
