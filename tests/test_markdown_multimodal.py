from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from ingestion.pipeline import load_book
from rendering.markdown_renderer import render_book_markdown


class MarkdownMultimodalTests(unittest.TestCase):
    def test_markdown_ingestion_preserves_local_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            image_path = temp_path / "figure.png"
            Image.new("RGB", (40, 24), color=(80, 110, 160)).save(image_path)

            source = temp_path / "illustrated.md"
            source.write_text(
                (
                    "# Chapter 1: Foundations\n\n"
                    "## 1.1 Overview\n\n"
                    "A short introduction.\n\n"
                    "![System diagram](figure.png)\n\n"
                    "*Figure 1. System overview.*\n\n"
                    "Additional context after the figure.\n"
                ),
                encoding="utf-8",
            )

            book = load_book(str(source))
            blocks = book.chapters[0].sections[0].blocks
            image_blocks = [block for block in blocks if block.block_type == "image"]
            self.assertEqual(len(image_blocks), 1)
            self.assertTrue(Path(image_blocks[0].asset_path).exists())
            self.assertGreaterEqual(book.parse_report.assets_detected, 1)

            rendered = render_book_markdown(book, [])
            self.assertIn("![System diagram]", rendered)
            self.assertIn("*Figure 1. System overview.*", rendered)

    def test_markdown_ingestion_preserves_tables_and_callouts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "structured.md"
            source.write_text(
                (
                    "# Structured Systems\n\n"
                    "# Chapter 1: Reliability\n\n"
                    "## 1.1 Signals\n\n"
                    "> Important: preserve callout context for revision notes.\n>\n"
                    "> This should remain a quoted block.\n\n"
                    "| Component | Role |\n"
                    "| --- | --- |\n"
                    "| Parser | Normalizes input |\n"
                    "| Renderer | Publishes output |\n\n"
                    "Additional explanation after the structured blocks.\n"
                ),
                encoding="utf-8",
            )

            book = load_book(str(source))
            blocks = book.chapters[0].sections[0].blocks
            self.assertTrue(any(block.block_type == "callout" for block in blocks))
            self.assertTrue(any(block.block_type == "table" for block in blocks))

            rendered = render_book_markdown(book, [])
            self.assertIn("> Important: preserve callout context", rendered)
            self.assertIn("| Component | Role |", rendered)
            self.assertIn("| Parser | Normalizes input |", rendered)


if __name__ == "__main__":
    unittest.main()
