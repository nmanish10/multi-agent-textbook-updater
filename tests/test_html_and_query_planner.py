from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from core.models import ChapterAnalysis
from ingestion.pipeline import load_book
from research.query_planner import build_query_plan
from rendering.markdown_renderer import render_book_markdown


class HtmlAndQueryPlannerTests(unittest.TestCase):
    def test_html_ingestion_parses_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.html"
            source.write_text(
                """
                <html>
                  <head><title>HTML Networks</title></head>
                  <body>
                    <h1>Chapter 1: Foundations</h1>
                    <h2>1.1 Basics</h2>
                    <p>Networking fundamentals and protocol concepts.</p>
                    <h2>1.2 Routing</h2>
                    <p>Routing determines how packets move through the network.</p>
                  </body>
                </html>
                """,
                encoding="utf-8",
            )

            book = load_book(str(source))
            self.assertEqual(book.metadata.source_format, "html")
            self.assertEqual(book.book_title, "HTML Networks")
            self.assertGreaterEqual(len(book.chapters), 1)
            self.assertGreaterEqual(sum(len(ch.sections) for ch in book.chapters), 2)

    def test_html_ingestion_preserves_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            image_path = temp_path / "diagram.png"
            Image.new("RGB", (32, 20), color=(30, 90, 140)).save(image_path)

            source = temp_path / "visual.html"
            source.write_text(
                f"""
                <html>
                  <head><title>Visual Book</title></head>
                  <body>
                    <h1>Chapter 1: Vision</h1>
                    <p>Introductory explanation before any numbered subsection.</p>
                    <img src="{image_path.name}" alt="Architecture diagram" />
                    <figcaption>Figure 1. Overall architecture.</figcaption>
                    <h2>1.1 Pipeline</h2>
                    <p>The pipeline mixes parsing, retrieval, and rendering.</p>
                  </body>
                </html>
                """,
                encoding="utf-8",
            )

            book = load_book(str(source))
            first_section = book.chapters[0].sections[0]
            image_blocks = [block for block in first_section.blocks if block.block_type == "image"]
            self.assertEqual(len(image_blocks), 1)
            self.assertTrue(Path(image_blocks[0].asset_path).exists())
            self.assertEqual(image_blocks[0].caption, "Figure 1. Overall architecture.")
            rendered = render_book_markdown(book, [])
            self.assertIn("![Architecture diagram]", rendered)
            self.assertIn("*Figure 1. Overall architecture.*", rendered)

    def test_html_ingestion_preserves_tables_and_callouts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "structured.html"
            source.write_text(
                """
                <html>
                  <head><title>Structured HTML</title></head>
                  <body>
                    <h1>Chapter 1: Systems</h1>
                    <h2>1.1 Overview</h2>
                    <blockquote>Important note for students reviewing this section.</blockquote>
                    <table>
                      <tr><th>Component</th><th>Purpose</th></tr>
                      <tr><td>Parser</td><td>Extract structure</td></tr>
                    </table>
                    <p>Follow-up explanation after the table.</p>
                  </body>
                </html>
                """,
                encoding="utf-8",
            )

            book = load_book(str(source))
            blocks = book.chapters[0].sections[0].blocks
            self.assertTrue(any(block.block_type == "callout" for block in blocks))
            self.assertTrue(any(block.block_type == "table" for block in blocks))
            rendered = render_book_markdown(book, [])
            self.assertIn("> Important note for students reviewing this section.", rendered)
            self.assertIn("| Component | Purpose |", rendered)

    def test_query_planner_creates_refined_queries(self) -> None:
        analysis = ChapterAnalysis(
            summary="A chapter about network routing and congestion control.",
            key_concepts=["routing", "congestion control", "packet switching"],
            search_queries=[
                "recent routing protocol advances",
                "modern congestion control techniques",
            ],
        )

        plan = build_query_plan("1", analysis, demo_mode=False)
        self.assertEqual(plan.chapter_id, "1")
        self.assertEqual(len(plan.base_queries), 2)
        self.assertEqual(len(plan.refined_queries), 2)
        self.assertTrue(all("focusing on" in query for query in plan.refined_queries))
        self.assertIn("routing", plan.reasoning_summary.lower())


if __name__ == "__main__":
    unittest.main()
