from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from core.models import Book, Chapter, Section, WrittenUpdate
from review.decision_ingest import write_review_decision_outputs
from storage.artifact_store import ArtifactStore


class ReviewDecisionIngestTests(unittest.TestCase):
    def test_review_queue_can_generate_approved_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ArtifactStore(temp_dir, "run-2")
            book = Book(
                book_title="Decision Book",
                chapters=[
                    Chapter(
                        chapter_id="1",
                        title="Architecture",
                        content="Architecture overview",
                        sections=[Section(section_id="1.1", title="Overview", content="Core section text.")],
                    )
                ],
            )
            updates = [
                WrittenUpdate(
                    chapter_id="1",
                    section_id="1.1",
                    proposed_subsection_id="1.1.1",
                    title="Approved Update",
                    text="Approved Update\n\nThis update should appear in the approved export.",
                    source="https://example.com/approved",
                ),
                WrittenUpdate(
                    chapter_id="1",
                    section_id="1.1",
                    proposed_subsection_id="1.1.2",
                    title="Rejected Update",
                    text="Rejected Update\n\nThis update should not appear in the approved export.",
                    source="https://example.com/rejected",
                ),
            ]

            store.write_json("book/parsed_book.json", book.model_dump(mode="json"))
            store.write_json("chapters/1/written_updates.json", [item.model_dump(mode="json") for item in updates])

            queue_path = store.base_path / "review" / "review_queue.csv"
            queue_path.parent.mkdir(parents=True, exist_ok=True)
            with queue_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "chapter_id",
                        "chapter_title",
                        "section_id",
                        "proposed_subsection_id",
                        "title",
                        "source_summary",
                        "score_summary",
                        "review_decision",
                        "review_notes",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "chapter_id": "1",
                        "chapter_title": "Architecture",
                        "section_id": "1.1",
                        "proposed_subsection_id": "1.1.1",
                        "title": "Approved Update",
                        "source_summary": "https://example.com/approved",
                        "score_summary": "",
                        "review_decision": "approve",
                        "review_notes": "Looks good.",
                    }
                )
                writer.writerow(
                    {
                        "chapter_id": "1",
                        "chapter_title": "Architecture",
                        "section_id": "1.1",
                        "proposed_subsection_id": "1.1.2",
                        "title": "Rejected Update",
                        "source_summary": "https://example.com/rejected",
                        "score_summary": "",
                        "review_decision": "reject",
                        "review_notes": "Not strong enough.",
                    }
                )

            outputs = write_review_decision_outputs(str(store.base_path), str(queue_path))

            approved_markdown = Path(outputs["approved_book_markdown"]).read_text(encoding="utf-8")
            summary = Path(outputs["summary"]).read_text(encoding="utf-8")
            self.assertIn("Approved Update", approved_markdown)
            self.assertNotIn("Rejected Update", approved_markdown)
            self.assertIn('"approved_count": 1', summary)
            self.assertIn('"rejected_count": 1', summary)
            self.assertTrue(Path(outputs["approved_book_docx"]).exists())
            self.assertTrue(Path(outputs["approved_book_docx_manifest"]).exists())
            self.assertIn("approved_book_pdf_success", outputs)
            self.assertTrue(Path(outputs["approved_book_pdf_manifest"]).exists())


if __name__ == "__main__":
    unittest.main()
