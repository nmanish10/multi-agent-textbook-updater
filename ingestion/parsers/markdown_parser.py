from __future__ import annotations

import re

from core.console import ensure_utf8_console
from core.models import Block, Book, Chapter, ParseMetadata, ParseReport, Section
from ingestion.parsers.assets import copy_local_asset
from utils.md_parser import parse_markdown as legacy_parse_markdown


IMAGE_PATTERN = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<path>[^)]+)\)")


def _blocks_from_markdown(content: str, source_path: str) -> list[Block]:
    blocks: list[Block] = []
    lines = (content or "").splitlines()
    index = 0
    while index < len(lines):
        raw_line = lines[index]
        line = raw_line.strip()
        if not line:
            index += 1
            continue

        image_match = IMAGE_PATTERN.fullmatch(line)
        if image_match:
            asset_reference = image_match.group("path").strip()
            alt_text = image_match.group("alt").strip()
            asset_path = asset_reference
            if asset_reference and not asset_reference.startswith(("http://", "https://", "data:")):
                asset_path = copy_local_asset(source_path, asset_reference)
            blocks.append(
                Block(
                    block_type="image",
                    asset_type="image",
                    asset_path=asset_path,
                    alt_text=alt_text,
                    text=alt_text or "Image",
                    confidence=0.95,
                )
            )
            index += 1
            continue

        if line.startswith(">"):
            callout_lines = []
            while index < len(lines):
                candidate = lines[index].strip()
                if not candidate.startswith(">"):
                    break
                callout_lines.append(candidate.lstrip(">").strip())
                index += 1
            text = "\n".join(part for part in callout_lines if part)
            if text:
                blocks.append(
                    Block(
                        block_type="callout",
                        text=text,
                        label="Note",
                        confidence=0.9,
                    )
                )
            continue

        if "|" in line:
            table_lines = []
            lookahead = index
            while lookahead < len(lines):
                candidate = lines[lookahead].strip()
                if "|" not in candidate:
                    break
                table_lines.append(candidate)
                lookahead += 1
            rows = _table_rows_from_markdown(table_lines)
            if rows:
                blocks.append(
                    Block(
                        block_type="table",
                        text="\n".join(" | ".join(row) for row in rows),
                        rows=rows,
                        label="Table",
                        confidence=0.9,
                    )
                )
                index = lookahead
                continue

        if line.startswith("*") and line.endswith("*") and len(line) > 2:
            blocks.append(
                Block(
                    block_type="caption",
                    text=line.strip("*").strip(),
                    confidence=0.9,
                )
            )
            index += 1
            continue

        blocks.append(Block(text=line, block_type="paragraph"))
        index += 1

    return blocks


def _table_rows_from_markdown(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in lines:
        stripped = line.strip().strip("|")
        if not stripped:
            continue
        cells = [cell.strip() for cell in stripped.split("|")]
        if not any(cells):
            continue
        if all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells):
            continue
        rows.append(cells)
    return rows


def _fallback_parse_markdown(file_path: str) -> Book:
    raw = open(file_path, "r", encoding="utf-8", errors="ignore").read().splitlines()
    book_title = "Markdown Book"
    chapters: list[Chapter] = []
    current_chapter = None
    current_sections: list[Section] = []
    current_section = None
    chapter_buffer: list[str] = []
    section_buffer: list[str] = []

    def flush_section() -> None:
        nonlocal current_section, section_buffer, current_sections
        if not current_section:
            return
        content = "\n".join(line for line in section_buffer if line.strip()).strip()
        blocks = _blocks_from_markdown(content, file_path)
        if content or blocks:
            current_sections.append(
                Section(
                    section_id=current_section["id"],
                    title=current_section["title"],
                    content=content,
                    blocks=blocks or [Block(text=content)],
                )
            )
        current_section = None
        section_buffer = []

    def flush_chapter() -> None:
        nonlocal current_chapter, current_sections, current_section, chapter_buffer, section_buffer
        if not current_chapter:
            return
        flush_section()
        content = "\n".join(line for line in chapter_buffer if line.strip()).strip()
        sections = current_sections
        if not sections and content:
            sections = [
                Section(
                    section_id=f"{current_chapter['id']}.1",
                    title="Overview",
                    content=content,
                    blocks=_blocks_from_markdown(content, file_path) or [Block(text=content)],
                )
            ]
        chapters.append(
            Chapter(
                chapter_id=current_chapter["id"],
                title=current_chapter["title"],
                content=content,
                sections=sections,
            )
        )
        current_chapter = None
        current_sections = []
        current_section = None
        chapter_buffer = []
        section_buffer = []

    for line in raw:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            if book_title == "Markdown Book" and not title.lower().startswith("chapter "):
                book_title = title
                continue
            flush_chapter()
            current_chapter = {"id": str(len(chapters) + 1), "title": title}
            continue
        if stripped.startswith("## "):
            if current_chapter is None:
                continue
            flush_section()
            section_label = stripped[3:].strip()
            match = re.match(r"^(\d+(?:\.\d+)*)\s+(.*)$", section_label)
            if match:
                current_section = {"id": match.group(1), "title": match.group(2).strip()}
            else:
                current_section = {
                    "id": f"{current_chapter['id']}.{len(current_sections) + 1}",
                    "title": section_label,
                }
            continue

        if current_chapter is None:
            book_title = stripped if book_title == "Markdown Book" else book_title
            continue
        chapter_buffer.append(stripped)
        if current_section:
            section_buffer.append(stripped)

    flush_chapter()
    return Book(book_title=book_title, chapters=chapters)


def parse_markdown_document(file_path: str) -> Book:
    ensure_utf8_console()
    raw_markdown = open(file_path, "r", encoding="utf-8", errors="ignore").read()
    structured_hint = any(marker in raw_markdown for marker in ("![", "\n>", "\n|", "\n```"))
    parsed = _fallback_parse_markdown(file_path) if structured_hint else legacy_parse_markdown(file_path)
    if not parsed.chapters:
        parsed = _fallback_parse_markdown(file_path)
    sections_detected = 0
    assets_detected = 0

    for chapter in parsed.chapters:
        chapter.metadata = ParseMetadata(
            source_path=file_path,
            source_format="markdown",
            parser_name="legacy_markdown_parser",
            confidence=0.92,
        )
        for section in chapter.sections:
            section.blocks = _blocks_from_markdown(section.content, file_path) or [Block(text=section.content)]
            section.metadata = ParseMetadata(
                source_path=file_path,
                source_format="markdown",
                parser_name="legacy_markdown_parser",
                confidence=0.9,
            )
            sections_detected += 1
            assets_detected += sum(1 for block in section.blocks if block.block_type == "image")

    parsed.metadata = ParseMetadata(
        source_path=file_path,
        source_format="markdown",
        parser_name="legacy_markdown_parser",
        confidence=0.92,
    )
    parsed.parse_report = ParseReport(
        parser_name="legacy_markdown_parser",
        chapters_detected=len(parsed.chapters),
        sections_detected=sections_detected,
        assets_detected=assets_detected,
    )
    return parsed
