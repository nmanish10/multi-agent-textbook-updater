from __future__ import annotations

import unittest
from pathlib import Path

from core.models import Book, Chapter, Section, WrittenUpdate
from rendering.markdown_renderer import render_book_markdown


class RendererSnapshotTests(unittest.TestCase):
    def test_canonical_markdown_matches_snapshot(self) -> None:
        book = Book(
            book_title="Golden Book",
            chapters=[
                Chapter(
                    chapter_id="1",
                    title="Signals and Systems",
                    content="Overview text",
                    sections=[
                        Section(
                            section_id="1.1",
                            title="Sampling Theory",
                            content="Sampling converts continuous signals into discrete values for processing.",
                        ),
                        Section(
                            section_id="1.2",
                            title="Transforms",
                            content="Transforms help analyze signals in alternate domains.",
                        ),
                    ],
                )
            ],
        )
        updates = [
            WrittenUpdate(
                chapter_id="1",
                section_id="1.2",
                title="Wavelet Extensions",
                text=(
                    "Wavelet Extensions\n\n"
                    "Section 1.2 now benefits from newer wavelet-based sparse analysis methods "
                    "for non-stationary signals.\n\n"
                    "This matters because students can connect classical transform intuition "
                    "to modern multiresolution representations."
                ),
                source="https://example.com",
            )
        ]

        rendered = render_book_markdown(book, updates)
        expected = Path("tests/snapshots/renderer_golden_output.md").read_text(encoding="utf-8").strip() + "\n"
        self.assertEqual(rendered, expected)

    def test_book_without_updates_has_no_recent_advances_block(self) -> None:
        book = Book(
            book_title="No Updates Book",
            chapters=[
                Chapter(
                    chapter_id="1",
                    title="Core Concepts",
                    content="Foundational content.",
                    sections=[Section(section_id="1.1", title="Intro", content="Important foundational material.")],
                )
            ],
        )
        rendered = render_book_markdown(book, [])
        self.assertNotIn("## Recent Advances", rendered)


if __name__ == "__main__":
    unittest.main()
