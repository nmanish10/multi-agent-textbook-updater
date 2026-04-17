from __future__ import annotations

import json
import unittest
from pathlib import Path

from ingestion.pipeline import load_book


class ParserSnapshotTests(unittest.TestCase):
    def test_sample_markdown_parser_summary_matches_snapshot(self) -> None:
        book = load_book("data/sample.md")
        summary = {
            "book_title": book.book_title,
            "chapters": len(book.chapters),
            "sections": sum(len(chapter.sections) for chapter in book.chapters),
            "chapter_titles": [chapter.title for chapter in book.chapters],
            "warnings": book.parse_report.warnings if book.parse_report else [],
        }

        snapshot_path = Path("tests/snapshots/sample_md_parser_summary.json")
        expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
        self.assertEqual(summary, expected)

    def test_pdf_parser_eval_exposes_candidate_scores(self) -> None:
        book = load_book("data/sample.pdf")
        self.assertIsNotNone(book.parse_report)
        self.assertGreaterEqual(book.parse_report.chapters_detected, 1)
        self.assertGreaterEqual(len(book.parse_report.candidate_scores), 2)
        self.assertTrue(any(score["strategy"] == "pdfplumber_bridge" for score in book.parse_report.candidate_scores))
        self.assertIsInstance(book.parse_report.scanned_pages, int)
        self.assertIsInstance(book.parse_report.ocr_recommended, bool)


if __name__ == "__main__":
    unittest.main()
