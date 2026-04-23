from __future__ import annotations

import unittest

from rendering.pdf_exporter import build_print_ready_html


class PdfExporterTemplateTests(unittest.TestCase):
    def test_print_ready_html_contains_title_page_and_frames(self) -> None:
        markdown_text = (
            "# Sample Book\n\n"
            "## Table of Contents\n\n"
            "- Chapter 1\n\n"
            "# Chapter 1: Foundations\n\n"
            "## 1.1 Basics\n\n"
            "Core content.\n"
        )
        html = build_print_ready_html(markdown_text, "sample.md")
        self.assertIn("class=\"title-page\"", html)
        self.assertIn("id=\"header_content\"", html)
        self.assertIn("id=\"footer_content\"", html)
        self.assertIn("Sample Book", html)

    def test_print_ready_html_decorates_recent_advances_and_toc(self) -> None:
        markdown_text = (
            "# Sample Book\n\n"
            "## Table of Contents\n\n"
            "- Entry\n\n"
            "# Chapter 1: Foundations\n\n"
            "## Recent Advances\n\n"
            "Paragraph one.\n\n"
            "**Sources**\n\n"
            "- https://example.com\n"
        )
        html = build_print_ready_html(markdown_text, "sample.md")
        self.assertIn("class=\"toc-section\"", html)
        self.assertIn("class=\"recent-advances\"", html)
        self.assertIn("sources-section", html)


if __name__ == "__main__":
    unittest.main()
