from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def file_fingerprint(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return ""
    digest = hashlib.sha1()
    with file_path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


class RunHistoryStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"runs": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, payload: dict[str, Any]) -> Path:
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return self.path

    def runs_for_book(self, book_key: str) -> list[dict[str, Any]]:
        data = self.load()
        return [entry for entry in data.get("runs", []) if entry.get("book_key") == book_key]

    def append_run(self, entry: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        runs = data.setdefault("runs", [])
        previous = None
        for existing in reversed(runs):
            if existing.get("book_key") == entry.get("book_key"):
                previous = existing
                break

        entry["recorded_at"] = datetime.now(timezone.utc).isoformat()
        entry["version_delta"] = self._compute_delta(previous, entry)
        runs.append(entry)
        self.save(data)
        return entry

    def _compute_delta(self, previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
        if not previous:
            return {"kind": "initial_run"}
        previous_stats = previous.get("stats", {})
        current_stats = current.get("stats", {})
        return {
            "kind": "incremental_run",
            "previous_run_id": previous.get("run_id"),
            "input_changed": previous.get("input_fingerprint") != current.get("input_fingerprint"),
            "config_changed": previous.get("admin_config") != current.get("admin_config"),
            "final_updates_delta": current_stats.get("final_updates", 0) - previous_stats.get("final_updates", 0),
            "accepted_candidates_delta": current_stats.get("accepted_candidates", 0) - previous_stats.get("accepted_candidates", 0),
        }
