from __future__ import annotations

from typing import Dict, List

from core.models import Book


def validate_book_structure(book: Book) -> Dict[str, List[str] | int]:
    warnings: List[str] = []
    stats = {
        "chapters": len(book.chapters),
        "sections": sum(len(chapter.sections) for chapter in book.chapters),
        "empty_sections": 0,
        "short_chapters": 0,
    }

    if not book.chapters:
        warnings.append("No chapters found")

    for chapter in book.chapters:
        if len(chapter.content.split()) < 100:
            warnings.append(f"Short chapter content: {chapter.chapter_id} {chapter.title}")
            stats["short_chapters"] += 1

        if not chapter.sections:
            warnings.append(f"Chapter missing sections: {chapter.chapter_id} {chapter.title}")

        for section in chapter.sections:
            if len(section.content.split()) < 20:
                warnings.append(f"Short section content: {section.section_id} {section.title}")
                stats["empty_sections"] += 1

    return {"warnings": warnings, **stats}
