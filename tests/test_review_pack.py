from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.models import AcceptedUpdate, Book, Chapter, Section, WrittenUpdate
from review.review_pack import build_review_payload, write_review_pack
from storage.artifact_store import ArtifactStore


class ReviewPackTests(unittest.TestCase):
    def test_review_pack_writes_markdown_json_and_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            book = Book(
                book_title="Reviewable Book",
                chapters=[
                    Chapter(
                        chapter_id="1",
                        title="Systems",
                        content="Systems overview",
                        sections=[Section(section_id="1.1", title="Overview", content="Section content.")],
                    )
                ],
            )
            updates = [
                WrittenUpdate(
                    chapter_id="1",
                    section_id="1.1",
                    proposed_subsection_id="1.1.1",
                    title="Adaptive Pipelines",
                    text="Adaptive Pipelines\n\nUpdated textbook content for review.",
                    why_it_matters="Keeps the chapter aligned with current practice.",
                    source="https://example.com/adaptive",
                    scores={"final_score": 8.7, "credibility": 0.92},
                    mapping_rationale="Strong overlap with systems section.",
                )
            ]
            judged = {
                "1": [
                    AcceptedUpdate(
                        chapter_id="1",
                        mapped_section_id="1.1",
                        candidate_title="Adaptive Pipelines",
                        summary="Summary",
                        why_it_matters="Keeps the chapter aligned with current practice.",
                        source="https://example.com/adaptive",
                        scores={"final_score": 8.7},
                    )
                ]
            }
            store = ArtifactStore(temp_dir, "run-1")
            summary = {"run_id": "run-1", "stats": {"chapters_processed": 1, "final_updates": 1}}

            review_paths = write_review_pack(store, book, updates, judged, summary)

            self.assertTrue(Path(review_paths["markdown"]).exists())
            self.assertTrue(Path(review_paths["json"]).exists())
            self.assertTrue(Path(review_paths["csv"]).exists())

            markdown = Path(review_paths["markdown"]).read_text(encoding="utf-8")
            csv_text = Path(review_paths["csv"]).read_text(encoding="utf-8")
            self.assertIn("Reviewer Instructions", markdown)
            self.assertIn("Adaptive Pipelines", markdown)
            self.assertIn("review_decision", csv_text)

    def test_review_payload_includes_parse_report_and_notes_fields(self) -> None:
        book = Book(book_title="Book", chapters=[])
        payload = build_review_payload(book, [], {}, {"run_id": "abc"})

        self.assertIn("parse_report", payload)
        self.assertIn("accepted_updates", payload)
        self.assertEqual(payload["summary"]["run_id"], "abc")


if __name__ == "__main__":
    unittest.main()
