from __future__ import annotations

import re
from bs4 import BeautifulSoup

from core.console import ensure_utf8_console
from core.models import Block, Book, Chapter, ParseMetadata, ParseReport, Section
from ingestion.parsers.assets import copy_local_asset


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _section_from_heading(chapter_id: str, heading_text: str, index: int) -> tuple[str, str]:
    match = re.match(r"^(\d+(?:\.\d+)*)\s+(.*)$", heading_text)
    if match:
        return match.group(1), match.group(2).strip()
    return f"{chapter_id}.{index}", heading_text


def parse_html_document(file_path: str) -> Book:
    ensure_utf8_console()
    with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
        soup = BeautifulSoup(handle.read(), "html.parser")

    title = _clean_text(soup.title.get_text()) if soup.title else "HTML Book"
    warnings = []

    content_root = soup.body or soup
    elements = content_root.find_all(["h1", "h2", "h3", "p", "li", "img", "figcaption", "blockquote", "table"])

    chapters = []
    current_chapter = None
    current_sections = []
    current_section = None
    chapter_buffer = []
    section_buffer = []
    section_blocks = []
    chapter_index = 0
    section_index = 0
    pending_caption = ""
    assets_detected = 0

    def flush_section():
        nonlocal current_section, section_buffer, current_sections, section_blocks
        if not current_section:
            return
        content = "\n".join(text for text in section_buffer if text).strip()
        if content:
            current_sections.append(
                Section(
                    section_id=current_section["id"],
                    title=current_section["title"],
                    content=content,
                    blocks=section_blocks or [Block(text=content)],
                    metadata=ParseMetadata(
                        source_path=file_path,
                        source_format="html",
                        parser_name="html_parser",
                        confidence=0.9,
                    ),
                )
            )
        current_section = None
        section_buffer = []
        section_blocks = []

    def flush_chapter():
        nonlocal current_chapter, chapter_buffer, current_sections, section_index, section_blocks
        if not current_chapter:
            return
        flush_section()
        content = "\n".join(text for text in chapter_buffer if text).strip()
        if content:
            chapters.append(
                Chapter(
                    chapter_id=current_chapter["id"],
                    title=current_chapter["title"],
                    content=content,
                    sections=current_sections or [
                        Section(
                            section_id=f"{current_chapter['id']}.1",
                            title="Overview",
                            content=content,
                            blocks=section_blocks or [Block(text=content)],
                            metadata=ParseMetadata(
                                source_path=file_path,
                                source_format="html",
                                parser_name="html_parser",
                                confidence=0.8,
                            ),
                        )
                    ],
                    metadata=ParseMetadata(
                        source_path=file_path,
                        source_format="html",
                        parser_name="html_parser",
                        confidence=0.9,
                    ),
                )
            )
        current_chapter = None
        chapter_buffer = []
        current_sections = []
        section_index = 0
        section_blocks = []

    for element in elements:
        text = _clean_text(element.get_text(" ", strip=True))

        if element.name == "h1":
            if not text:
                continue
            flush_chapter()
            chapter_index += 1
            heading = text.replace("Chapter ", "").strip() if text.lower().startswith("chapter ") else text
            current_chapter = {"id": str(chapter_index), "title": heading}
            continue

        if element.name in {"h2", "h3"}:
            if not text:
                continue
            if not current_chapter:
                chapter_index += 1
                current_chapter = {"id": str(chapter_index), "title": "Introduction"}
                warnings.append(f"Section heading found before chapter heading: {text}")
            flush_section()
            section_index += 1
            section_id, section_title = _section_from_heading(current_chapter["id"], text, section_index)
            current_section = {"id": section_id, "title": section_title}
            continue

        if element.name == "figcaption":
            if not text:
                continue
            pending_caption = text
            if section_blocks and section_blocks[-1].block_type == "image":
                section_blocks[-1].caption = text
            continue

        if element.name == "img":
            if current_chapter is None:
                chapter_index += 1
                current_chapter = {"id": str(chapter_index), "title": "Introduction"}
                warnings.append("Image found before chapter heading; inserted Introduction chapter")
            src = element.get("src", "")
            alt = _clean_text(element.get("alt", ""))
            local_path = src
            if src and not src.startswith(("http://", "https://", "data:")):
                local_path = copy_local_asset(file_path, src)

            image_block = Block(
                block_type="image",
                asset_type="image",
                asset_path=local_path,
                alt_text=alt,
                caption=pending_caption,
                text=alt or pending_caption or "Image",
                mime_type="image",
                confidence=0.95,
            )
            assets_detected += 1
            if current_section:
                section_blocks.append(image_block)
                section_buffer.append(f"![{alt or 'Image'}]({local_path})")
                if pending_caption:
                    section_buffer.append(f"*{pending_caption}*")
            else:
                if not current_sections:
                    section_index += 1
                    current_section = {"id": f"{current_chapter['id']}.{section_index}", "title": "Overview"}
                    warnings.append(f"Implicit overview section created for chapter {current_chapter['id']} to preserve images")
                    section_blocks.append(image_block)
                    section_buffer.append(f"![{alt or 'Image'}]({local_path})")
                    if pending_caption:
                        section_buffer.append(f"*{pending_caption}*")
                else:
                    current_sections[-1].blocks.append(image_block)
                    current_sections[-1].content = (
                        current_sections[-1].content + f"\n![{alt or 'Image'}]({local_path})"
                    ).strip()
                chapter_buffer.append(f"![{alt or 'Image'}]({local_path})")
                if pending_caption:
                    chapter_buffer.append(f"*{pending_caption}*")
            pending_caption = ""
            continue

        if element.name == "blockquote":
            if not text:
                continue
            if current_chapter is None:
                chapter_index += 1
                current_chapter = {"id": str(chapter_index), "title": "Introduction"}
                warnings.append("Callout found before chapter heading; inserted Introduction chapter")
            if current_section is None:
                section_index += 1
                current_section = {"id": f"{current_chapter['id']}.{section_index}", "title": "Overview"}
            callout_block = Block(
                block_type="callout",
                text=text,
                label="Note",
                confidence=0.9,
            )
            section_blocks.append(callout_block)
            section_buffer.append(f"> {text}")
            chapter_buffer.append(f"> {text}")
            continue

        if element.name == "table":
            rows = []
            for row in element.find_all("tr"):
                cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
                if any(cells):
                    rows.append(cells)
            if not rows:
                continue
            if current_chapter is None:
                chapter_index += 1
                current_chapter = {"id": str(chapter_index), "title": "Introduction"}
                warnings.append("Table found before chapter heading; inserted Introduction chapter")
            if current_section is None:
                section_index += 1
                current_section = {"id": f"{current_chapter['id']}.{section_index}", "title": "Overview"}
            table_block = Block(
                block_type="table",
                text="\n".join(" | ".join(row) for row in rows),
                rows=rows,
                label="Table",
                confidence=0.9,
            )
            section_blocks.append(table_block)
            section_buffer.append(table_block.text)
            chapter_buffer.append(table_block.text)
            continue

        if not text:
            continue

        if current_chapter is None:
            chapter_index += 1
            current_chapter = {"id": str(chapter_index), "title": "Introduction"}
            warnings.append("Body text found before chapter heading; inserted Introduction chapter")

        chapter_buffer.append(text)
        if current_section:
            section_buffer.append(text)
            section_blocks.append(Block(text=text, block_type="paragraph"))

    flush_chapter()

    return Book(
        book_title=title,
        chapters=chapters,
        metadata=ParseMetadata(
            source_path=file_path,
            source_format="html",
            parser_name="html_parser",
            confidence=0.9,
        ),
        parse_report=ParseReport(
            parser_name="html_parser",
            strategy_used="html_parser",
            chapters_detected=len(chapters),
            sections_detected=sum(len(chapter.sections) for chapter in chapters),
            assets_detected=assets_detected,
            warnings=warnings,
        ),
    )
