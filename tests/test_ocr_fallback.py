from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core.models import Book, Chapter, Section
from ingestion.parsers import pdf_parser


class OcrFallbackTests(unittest.TestCase):
    def test_ocr_runtime_status_reports_disabled_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OCR_ENABLED", None)
            ok, message = pdf_parser._ocr_runtime_status()
            self.assertFalse(ok)
            self.assertIn("disabled", message.lower())

    def test_ocr_runtime_status_reports_missing_dependencies(self) -> None:
        with patch.dict(os.environ, {"OCR_ENABLED": "true"}, clear=False):
            with patch("builtins.__import__", side_effect=ModuleNotFoundError("missing")):
                ok, message = pdf_parser._ocr_runtime_status()
                self.assertFalse(ok)
                self.assertIn("dependencies", message.lower())

    def test_parse_pdf_document_reports_unavailable_ocr_strategy_when_recommended(self) -> None:
        fake_book = Book(
            book_title="OCR Candidate",
            chapters=[
                Chapter(
                    chapter_id="1",
                    title="Scanned Chapter",
                    content="Enough text for a chapter " * 20,
                    sections=[Section(section_id="1.1", title="Overview", content="Enough section text " * 20)],
                )
            ],
        )
        with patch.object(pdf_parser, "_analyze_pdf_pages", return_value=(3, True, ["OCR suggested"])):  # scanned
            with patch.object(pdf_parser, "_ocr_runtime_status", return_value=(False, "OCR runtime unavailable")):
                with patch.object(pdf_parser, "_run_strategy", return_value=(fake_book, {"strategy": "pdfplumber_bridge", "score": 22.0, "chapters": 1, "sections": 1, "warnings": []})):
                    with patch.object(pdf_parser, "_extract_pdf_images", return_value=[]):
                        book = pdf_parser.parse_pdf_document("data/sample.pdf")
        self.assertIsNotNone(book.parse_report)
        self.assertTrue(any(score["strategy"] == "ocr_fallback" for score in book.parse_report.candidate_scores))
        self.assertIn("OCR runtime unavailable", " ".join(book.parse_report.warnings))


if __name__ == "__main__":
    unittest.main()
