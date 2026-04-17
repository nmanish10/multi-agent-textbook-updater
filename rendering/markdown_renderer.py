from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Iterable, List

from core.models import Book, WrittenUpdate


def _clean_text(text: str) -> str:
    return (text or "").strip().replace("\r", "")


def _source_lines(update: WrittenUpdate) -> List[str]:
    if update.sources:
        src = update.sources[0]
        lines = []
        if src.title and src.date:
            lines.append(f"{src.title} ({src.date})")
        elif src.title:
            lines.append(src.title)
        if src.url:
            lines.append(src.url)
        return lines
    if update.source:
        return [update.source]
    return []


def _relative_asset_path(asset_path: str) -> str:
    if not asset_path:
        return asset_path
    normalized = asset_path.replace("\\", "/")
    marker = "outputs/"
    if normalized.startswith(marker):
        return normalized[len(marker):]
    return normalized


def _render_section_blocks(lines: List[str], section) -> None:
    for block in section.blocks:
        if block.block_type == "image" and block.asset_path:
            alt = block.alt_text or block.text or "Image"
            lines.extend([f"![{alt}]({_relative_asset_path(block.asset_path)})", ""])
            if block.caption:
                lines.extend([f"*{block.caption}*", ""])
        elif block.block_type == "table" and block.rows:
            rows = block.rows
            header = rows[0]
            lines.append("| " + " | ".join(header) + " |")
            lines.append("| " + " | ".join(["---"] * len(header)) + " |")
            for row in rows[1:]:
                padded = row + [""] * max(0, len(header) - len(row))
                lines.append("| " + " | ".join(padded[: len(header)]) + " |")
            lines.append("")
        elif block.block_type == "callout" and block.text:
            for paragraph in [part.strip() for part in block.text.split("\n") if part.strip()]:
                lines.append(f"> {paragraph}")
            lines.append("")
        elif block.block_type == "caption" and block.text:
            lines.extend([f"*{_clean_text(block.text)}*", ""])
        elif block.text:
            cleaned = _clean_text(block.text)
            if cleaned:
                lines.extend([cleaned, ""])


def assign_subsection_ids(updates: Iterable[WrittenUpdate]) -> List[WrittenUpdate]:
    counts = defaultdict(int)
    assigned = []

    for update in updates:
        data = update.model_copy(deep=True)
        counts[data.section_id] += 1
        data.proposed_subsection_id = data.proposed_subsection_id or f"{data.section_id}.{counts[data.section_id]}"
        assigned.append(data)

    return assigned


def _build_toc(book: Book, updates_by_chapter: dict) -> List[str]:
    lines = ["## Table of Contents", ""]
    for chapter in book.chapters:
        chapter_title = chapter.title
        if not chapter_title.lower().startswith("chapter"):
            chapter_title = f"Chapter {chapter.chapter_id}: {chapter_title}"
        lines.append(f"- {chapter_title}")
        for section in chapter.sections:
            lines.append(f"  - {section.section_id} {section.title}")
        if updates_by_chapter.get(chapter.chapter_id):
            lines.append(f"  - Chapter {chapter.chapter_id} Recent Advances")
    lines.append("")
    return lines


def _chapter_update_summary(chapter_updates: List[WrittenUpdate]) -> List[str]:
    if not chapter_updates:
        return []
    lines = [
        "This chapter includes the following curated update placements:",
        "",
    ]
    for update in chapter_updates:
        lines.append(f"- {update.proposed_subsection_id} linked to Section {update.section_id}")
    lines.append("")
    return lines


def render_book_markdown(book: Book, updates: List[WrittenUpdate]) -> str:
    updates_by_chapter = defaultdict(list)
    for update in assign_subsection_ids(updates):
        updates_by_chapter[update.chapter_id].append(update)

    lines: List[str] = [f"# {book.book_title}", "", "---", ""]
    lines.extend(_build_toc(book, updates_by_chapter))

    for chapter in book.chapters:
        title = chapter.title
        if not title.lower().startswith("chapter"):
            title = f"Chapter {chapter.chapter_id}: {title}"
        lines.extend([f"# {title}", ""])

        for section in chapter.sections:
            lines.extend([f"## {section.section_id} {section.title}", ""])
            if section.blocks:
                _render_section_blocks(lines, section)
            else:
                for paragraph in [p for p in section.content.split("\n") if _clean_text(p)]:
                    cleaned = _clean_text(paragraph)
                    if cleaned:
                        lines.extend([cleaned, ""])

        chapter_updates = sorted(
            updates_by_chapter.get(chapter.chapter_id, []),
            key=lambda item: (item.section_id, item.proposed_subsection_id or ""),
        )
        if not chapter_updates:
            continue

        lines.extend(["---", "", "## Recent Advances", ""])
        lines.extend(_chapter_update_summary(chapter_updates))
        for update in chapter_updates:
            blocks = [block for block in update.text.split("\n\n") if _clean_text(block)]
            if not blocks:
                continue
            title_line = _clean_text(blocks[0])
            lines.extend([f"### {update.proposed_subsection_id} {title_line}", ""])
            lines.extend([f"_Mapped to Section {update.section_id}_", ""])
            for paragraph in blocks[1:]:
                cleaned = _clean_text(paragraph)
                if len(cleaned) > 20:
                    lines.extend([cleaned, ""])
            source_lines = _source_lines(update)
            if source_lines:
                lines.extend(["**Sources**", ""])
                lines.extend([f"- {line}" for line in source_lines])
                lines.append("")

    return "\n".join(lines).strip() + "\n"


def write_markdown(book: Book, updates: List[WrittenUpdate], output_file: str) -> Path:
    markdown = render_book_markdown(book, updates)
    destination = Path(output_file)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(markdown, encoding="utf-8")
    return destination
