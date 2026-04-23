from __future__ import annotations

import unittest
from pathlib import Path

from agents.ranker import competitive_replacement
from core.models import SourceRecord, WrittenUpdate
from storage.update_store import PersistentUpdateStore


class CompetitiveReplacementTests(unittest.TestCase):
    def test_competitive_replacement_keeps_best_updates(self) -> None:
        existing = [
            {
                "candidate_title": "Legacy Update",
                "summary": "Older but acceptable update",
                "mapped_section_id": "1.1",
                "source_title": "Legacy Source",
                "url": "https://example.com/legacy",
                "scores": {"final_score": 0.80, "decision": "accept"},
            }
        ]
        new = [
            {
                "candidate_title": "Better Update",
                "summary": "New stronger update",
                "mapped_section_id": "1.2",
                "source_title": "New Source",
                "url": "https://example.com/new",
                "scores": {"final_score": 0.92, "decision": "accept"},
            },
            {
                "candidate_title": "Weaker Update",
                "summary": "New weaker update",
                "mapped_section_id": "1.3",
                "source_title": "Weak Source",
                "url": "https://example.com/weak",
                "scores": {"final_score": 0.76, "decision": "accept"},
            },
        ]
        survivors, removed = competitive_replacement(existing, new, threshold=2)
        survivor_titles = {item["candidate_title"] for item in survivors}
        removed_titles = {item["candidate_title"] for item in removed}
        self.assertIn("Better Update", survivor_titles)
        self.assertIn("Legacy Update", survivor_titles)
        self.assertIn("Weaker Update", removed_titles)

    def test_persistent_update_store_roundtrip(self) -> None:
        temp_dir = Path("outputs/test_update_store")
        temp_dir.mkdir(parents=True, exist_ok=True)
        store = PersistentUpdateStore(str(temp_dir), "data/book.pdf", "Book Title")
        update = WrittenUpdate(
            chapter_id="1",
            section_id="1.1",
            title="Stored Update",
            text="Stored Update\n\nBody",
            source="https://example.com",
            sources=[SourceRecord(title="Example", url="https://example.com", source_type="web")],
            scores={"final_score": 0.88, "decision": "accept"},
        )
        store.save_chapter_state("1", [update], [], "run-1")
        loaded = store.chapter_updates("1")
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].title, "Stored Update")


if __name__ == "__main__":
    unittest.main()
