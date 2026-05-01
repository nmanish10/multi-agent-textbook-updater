from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from utils.pdf_to_md import (
    build_font_heading_hints,
    convert_extracted_pages_to_md,
    match_chapter_pattern,
    merge_lines,
)


class PdfStructureRecoveryTests(unittest.TestCase):
    def test_chapter_patterns_cover_roman_and_numeric_titles(self) -> None:
        self.assertTrue(match_chapter_pattern("Chapter IV Advanced Topics"))
        self.assertTrue(match_chapter_pattern("1. Introduction"))
        self.assertTrue(match_chapter_pattern("2 Foundations of Learning"))

    def test_toc_guides_chapter_and_section_detection(self) -> None:
        pages_raw = [
            [
                "Contents",
                "Chapter IV Advanced Topics .......... 51",
                "4.1 Reinforcement Learning .......... 53",
                "4.2 Planning .......... 67",
            ],
            [
                "Chapter IV Advanced Topics",
                "4.1 Reinforcement Learning",
                "Reinforcement learning studies sequential decision making.",
            ],
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "converted.md"
            convert_extracted_pages_to_md(pages_raw, output_path=str(output_path))
            rendered = output_path.read_text(encoding="utf-8")

        self.assertIn("# Chapter IV Advanced Topics", rendered)
        self.assertIn("## 4.1 Reinforcement Learning", rendered)
        self.assertNotIn("Contents", rendered)

    def test_merge_lines_handles_page_break_continuation(self) -> None:
        merged = merge_lines(
            [
                "This paragraph explains a complex concept that continues",
                "across the next page without punctuation",
                "## 2.1 New Section",
            ]
        )
        self.assertEqual(
            merged[0],
            "This paragraph explains a complex concept that continues across the next page without punctuation",
        )
        self.assertEqual(merged[1], "## 2.1 New Section")

    def test_font_heading_hints_merge_multiline_headings(self) -> None:
        hints = build_font_heading_hints(
            [
                {"text": "Chapter 5", "font_size": 18.0, "is_bold": True, "top": 40},
                {"text": "Neural Symbolic Systems", "font_size": 18.0, "is_bold": True, "top": 49},
                {"text": "Body paragraph starts here.", "font_size": 11.0, "is_bold": False, "top": 80},
            ],
            body_size=11.0,
        )

        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0]["level"], "chapter")
        self.assertEqual(hints[0]["text"], "Chapter 5 Neural Symbolic Systems")

    def test_font_heading_hints_help_multiline_chapter_rendering(self) -> None:
        pages_raw = [
            [
                "Chapter 5",
                "Neural Symbolic Systems",
                "This chapter introduces a hybrid reasoning paradigm.",
            ]
        ]
        pages_font = [
            [
                {"text": "Chapter 5", "font_size": 18.0, "is_bold": True, "top": 40},
                {"text": "Neural Symbolic Systems", "font_size": 18.0, "is_bold": True, "top": 49},
                {
                    "text": "This chapter introduces a hybrid reasoning paradigm.",
                    "font_size": 11.0,
                    "is_bold": False,
                    "top": 84,
                },
            ]
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "converted.md"
            convert_extracted_pages_to_md(pages_raw, pages_font=pages_font, output_path=str(output_path))
            rendered = output_path.read_text(encoding="utf-8")

        self.assertIn("# Chapter 5 Neural Symbolic Systems", rendered)
        self.assertIn("This chapter introduces a hybrid reasoning paradigm.", rendered)


if __name__ == "__main__":
    unittest.main()
