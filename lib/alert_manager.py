"""
AlertManager — unified alert management for ml-research-loop tasks.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from lib.task_protocol import RESULTS_DIR


class AlertSeverity(str, Enum):
    HIGH = "high"      # 🔴 需立即处理
    MEDIUM = "medium"  # 🟡 需关注
    LOW = "low"        # 🟢 通知


class AlertType(str, Enum):
    DOOM_LOOP = "doom_loop"
    TASK_CRASH = "task_crash"
    TASK_TIMEOUT = "task_timeout"
    BUDGET_EXCEEDED = "budget_exceeded"
    DISK_LOW = "disk_low"
    SUBAGENT_DEAD = "subagent_dead"
    METRIC_STALLED = "metric_stalled"


@dataclass
class Alert:
    alert_id: str
    type: AlertType
    severity: AlertSeverity
    triggered_at: str
    experiment_index: int
    message: str
    context: dict = field(default_factory=dict)
    recommended_action: str = ""

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "type": self.type.value if isinstance(self.type, AlertType) else self.type,
            "severity": self.severity.value if isinstance(self.severity, AlertSeverity) else self.severity,
            "triggered_at": self.triggered_at,
            "experiment_index": self.experiment_index,
            "message": self.message,
            "context": self.context,
            "recommended_action": self.recommended_action,
        }


@dataclass
class AlertManifest:
    task_id: str
    alerts: list[Alert] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "alerts": [a.to_dict() if isinstance(a, Alert) else a for a in self.alerts],
            "summary": self.summary,
        }


class AlertManager:
    """
    统一管理任务告警。
    告警写入 results/<task_id>-alerts.json。
    """

    DOOM_LOOP_THRESHOLD = 5
    STALL_THRESHOLD = 10

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.alerts_file = RESULTS_DIR / f"{task_id}-alerts.json"
        self._manifest = AlertManifest(task_id=task_id)
        self._load_existing()

    def _load_existing(self) -> None:
        """加载已有告警文件。"""
        if not self.alerts_file.exists():
            return
        try:
            data = json.loads(self.alerts_file.read_text(encoding="utf-8"))
            self._manifest = AlertManifest(
                task_id=self.task_id,
                alerts=[Alert(**a) for a in data.get("alerts", [])],
                summary=data.get("summary", {}),
            )
        except (json.JSONDecodeError, TypeError):
            pass

    def send_alert(
        self,
        alert_type: str,
        message: str,
        severity: str = "medium",
        experiment_index: int = 0,
        context: Optional[dict] = None,
        recommended_action: str = "",
    ) -> Alert:
        """
        触发一个新告警。
        """
        at = AlertType(alert_type) if isinstance(alert_type, str) else alert_type
        sev = AlertSeverity(severity) if isinstance(severity, str) else severity

        alert = Alert(
            alert_id=f"alert-{uuid.uuid4().hex[:8]}",
            type=at,
            severity=sev,
            triggered_at=datetime.now(timezone.utc).isoformat(),
            experiment_index=experiment_index,
            message=message,
            context=context or {},
            recommended_action=recommended_action,
        )
        self._manifest.alerts.append(alert)
        self._save()
        return alert

    def get_alerts(self) -> list[Alert]:
        """返回所有告警列表。"""
        return self._manifest.alerts

    def clear_alerts(self) -> None:
        """清除所有告警。"""
        self._manifest.alerts = []
        self._manifest.summary = {}
        self._save()

    def has_high_alert(self) -> bool:
        """检查是否有未处理的高优先级告警。"""
        return any(
            a.severity == AlertSeverity.HIGH
            for a in self._manifest.alerts
        )

    def _severity_for(self, alert_type: AlertType) -> AlertSeverity:
        mapping = {
            AlertType.DOOM_LOOP: AlertSeverity.HIGH,
            AlertType.TASK_CRASH: AlertSeverity.HIGH,
            AlertType.TASK_TIMEOUT: AlertSeverity.MEDIUM,
            AlertType.BUDGET_EXCEEDED: AlertSeverity.LOW,
            AlertType.DISK_LOW: AlertSeverity.HIGH,
            AlertType.SUBAGENT_DEAD: AlertSeverity.HIGH,
            AlertType.METRIC_STALLED: AlertSeverity.MEDIUM,
        }
        return mapping.get(alert_type, AlertSeverity.MEDIUM)

    def _save(self) -> None:
        self._manifest.summary = {
            "total_alerts": len(self._manifest.alerts),
            "high_severity": sum(
                1 for a in self._manifest.alerts if a.severity == AlertSeverity.HIGH
            ),
            "medium_severity": sum(
                1 for a in self._manifest.alerts if a.severity == AlertSeverity.MEDIUM
            ),
            "low_severity": sum(
                1 for a in self._manifest.alerts if a.severity == AlertSeverity.LOW
            ),
            "most_recent_at": (
                self._manifest.alerts[-1].triggered_at
                if self._manifest.alerts else None
            ),
        }
        self.alerts_file.parent.mkdir(parents=True, exist_ok=True)
        self.alerts_file.write_text(
            json.dumps(self._manifest.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
