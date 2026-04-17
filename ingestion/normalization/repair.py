from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

from core.models import Block, Book, Chapter, ParseMetadata, ParseReport, Section


def _slug_title(file_path: str) -> str:
    stem = Path(file_path).stem.replace("_", " ").replace("-", " ").strip()
    return stem.title() if stem else "Updated Textbook"


def _normalize_title(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    return text


def _normalize_content(text: str) -> str:
    text = (text or "").replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_numeric_section(section_id: str) -> bool:
    return bool(re.fullmatch(r"\d+(?:\.\d+)*", (section_id or "").strip()))


def _repair_section_id(chapter_id: str, fallback_index: int) -> str:
    return f"{chapter_id}.{fallback_index}"


def normalize_book(book: Book, file_path: str) -> Tuple[Book, List[str]]:
    warnings: List[str] = []

    book.book_title = _normalize_title(book.book_title)
    if not book.book_title or book.book_title.lower() in {"markdown book", "pdf book"}:
        book.book_title = _slug_title(file_path)
        warnings.append("Book title inferred from file name")

    normalized_chapters: List[Chapter] = []
    for chapter_index, chapter in enumerate(book.chapters, start=1):
        chapter.chapter_id = str(chapter.chapter_id or chapter_index)
        chapter.title = _normalize_title(chapter.title) or f"Chapter {chapter.chapter_id}"
        chapter.content = _normalize_content(chapter.content)

        if chapter.metadata is None:
            chapter.metadata = ParseMetadata(source_path=file_path, source_format=Path(file_path).suffix.lstrip("."))

        normalized_sections: List[Section] = []
        seen_section_ids = set()
        for section_index, section in enumerate(chapter.sections, start=1):
            section.title = _normalize_title(section.title) or f"Section {chapter.chapter_id}.{section_index}"
            section.content = _normalize_content(section.content)

            repaired = False
            if not section.section_id or not _is_numeric_section(section.section_id):
                section.section_id = _repair_section_id(chapter.chapter_id, section_index)
                repaired = True

            if section.section_id in seen_section_ids:
                section.section_id = _repair_section_id(chapter.chapter_id, section_index)
                repaired = True

            if repaired:
                warnings.append(
                    f"Section id repaired in chapter {chapter.chapter_id}: {section.title} -> {section.section_id}"
                )

            seen_section_ids.add(section.section_id)

            if not section.blocks:
                section.blocks = [Block(text=section.content)]

            if section.metadata is None:
                section.metadata = ParseMetadata(
                    source_path=file_path,
                    source_format=Path(file_path).suffix.lstrip("."),
                    confidence=chapter.metadata.confidence if chapter.metadata else 0.8,
                )

            normalized_sections.append(section)

        if not normalized_sections and chapter.content:
            warnings.append(f"Inserted overview section for chapter {chapter.chapter_id}")
            normalized_sections.append(
                Section(
                    section_id=f"{chapter.chapter_id}.1",
                    title="Overview",
                    content=chapter.content,
                    blocks=[Block(text=chapter.content)],
                    metadata=ParseMetadata(
                        source_path=file_path,
                        source_format=Path(file_path).suffix.lstrip("."),
                        confidence=chapter.metadata.confidence if chapter.metadata else 0.75,
                    ),
                )
            )

        prefixes = {section.section_id.split(".")[0] for section in normalized_sections if section.section_id}
        if prefixes and len(prefixes) > 1:
            warnings.append(
                f"Mixed section numbering prefixes in chapter {chapter.chapter_id}: {', '.join(sorted(prefixes))}"
            )

        chapter.sections = normalized_sections
        normalized_chapters.append(chapter)

    book.chapters = normalized_chapters

    if book.parse_report is None:
        book.parse_report = ParseReport(parser_name="normalized_pipeline")

    book.parse_report.chapters_detected = len(book.chapters)
    book.parse_report.sections_detected = sum(len(chapter.sections) for chapter in book.chapters)
    book.parse_report.warnings.extend(warnings)

    return book, warnings
