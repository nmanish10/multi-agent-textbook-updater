from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List

from core.models import WrittenUpdate


def book_store_key(input_file: str, book_title: str) -> str:
    stem = Path(input_file).stem or "book"
    title_slug = re.sub(r"[^a-z0-9]+", "-", (book_title or stem).lower()).strip("-")
    return title_slug or stem.lower()


def update_identity(update: WrittenUpdate) -> str:
    raw = "|".join(
        [
            update.chapter_id,
            update.section_id,
            update.title,
            (update.source or ""),
            ",".join(source.url or source.title for source in update.sources),
        ]
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


class PersistentUpdateStore:
    def __init__(self, base_dir: str, input_file: str, book_title: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.store_key = book_store_key(input_file, book_title)
        self.path = self.base_dir / f"{self.store_key}.json"

    def load(self) -> dict:
        if not self.path.exists():
            return {"book_key": self.store_key, "chapters": {}, "history": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def chapter_updates(self, chapter_id: str) -> List[WrittenUpdate]:
        data = self.load()
        entries = data.get("chapters", {}).get(chapter_id, [])
        return [WrittenUpdate(**entry) for entry in entries]

    def save_chapter_state(
        self,
        chapter_id: str,
        updates: List[WrittenUpdate],
        removed_updates: List[WrittenUpdate],
        run_id: str,
    ) -> Path:
        data = self.load()
        data.setdefault("chapters", {})[chapter_id] = [
            {
                **update.model_dump(mode="json"),
                "update_id": update_identity(update),
                "status": "active",
            }
            for update in updates
        ]
        history = data.setdefault("history", [])
        for removed in removed_updates:
            history.append(
                {
                    "run_id": run_id,
                    "chapter_id": chapter_id,
                    "update_id": update_identity(removed),
                    "title": removed.title,
                    "section_id": removed.section_id,
                    "status": "replaced",
                }
            )
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return self.path
