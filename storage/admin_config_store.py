from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.config import AdminConfig, next_scheduled_run


class AdminConfigStore:
    def __init__(self, config_path: str, audit_log_path: str, scheduler_state_path: str):
        self.config_path = Path(config_path)
        self.audit_log_path = Path(audit_log_path)
        self.scheduler_state_path = Path(scheduler_state_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.scheduler_state_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> AdminConfig:
        if not self.config_path.exists():
            config = AdminConfig()
            self.save(config, actor="system", reason="initialize_default_config")
            return config
        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        return AdminConfig(**payload)

    def save(self, config: AdminConfig, *, actor: str = "system", reason: str = "update") -> Path:
        self.config_path.write_text(
            json.dumps(config.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.append_audit_entry(
            actor=actor,
            action=reason,
            payload=config.model_dump(mode="json"),
        )
        return self.config_path

    def update(self, updates: dict[str, Any], *, actor: str = "admin", reason: str = "manual_update") -> AdminConfig:
        current = self.load()
        merged = current.model_copy(update=updates)
        self.save(merged, actor=actor, reason=reason)
        return merged

    def append_audit_entry(self, *, actor: str, action: str, payload: dict[str, Any]) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "action": action,
            "payload": payload,
        }
        with self.audit_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def load_scheduler_state(self) -> dict[str, Any]:
        if not self.scheduler_state_path.exists():
            return {
                "last_run_utc": None,
                "last_run_id": None,
            }
        return json.loads(self.scheduler_state_path.read_text(encoding="utf-8"))

    def save_scheduler_state(self, payload: dict[str, Any]) -> Path:
        self.scheduler_state_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return self.scheduler_state_path

    def mark_run_completed(self, *, run_id: str, completed_at: datetime | None = None) -> dict[str, Any]:
        finished = completed_at or datetime.now(timezone.utc)
        state = {
            "last_run_utc": finished.isoformat(),
            "last_run_id": run_id,
        }
        self.save_scheduler_state(state)
        self.append_audit_entry(actor="system", action="mark_run_completed", payload=state)
        return state

    def scheduler_snapshot(self, *, now: datetime | None = None) -> dict[str, Any]:
        config = self.load()
        state = self.load_scheduler_state()
        reference = now or datetime.now(timezone.utc)
        last_run_raw = state.get("last_run_utc")
        last_run = datetime.fromisoformat(last_run_raw) if last_run_raw else None
        next_run = next_scheduled_run(config.update_frequency, from_time=last_run or reference)
        due_now = False
        if config.update_frequency != "manual":
            due_now = last_run is None or (next_run is not None and reference >= next_run)
        return {
            "update_frequency": config.update_frequency,
            "last_run_utc": state.get("last_run_utc"),
            "last_run_id": state.get("last_run_id"),
            "next_run_utc": next_run.isoformat() if next_run else None,
            "manual_only": next_run is None,
            "due_now": due_now,
            "scheduler_state_path": str(self.scheduler_state_path),
        }
