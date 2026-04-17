from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from docx import Document
from docx.document import Document as _Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from core.console import ensure_utf8_console
from core.models import Block, Book, Chapter, ParseMetadata, ParseReport, Section
from ingestion.parsers.assets import write_binary_asset


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _looks_like_chapter(text: str, style_name: str) -> bool:
    style_name = (style_name or "").lower()
    return (
        text.lower().startswith("chapter ")
        or "heading 1" in style_name
    )


def _looks_like_section(text: str, style_name: str) -> bool:
    style_name = (style_name or "").lower()
    return bool(re.match(r"^\d+\.\d+", text)) or "heading 2" in style_name or "heading 3" in style_name


def _section_parts(chapter_id: str, text: str, index: int) -> tuple[str, str]:
    match = re.match(r"^(\d+(?:\.\d+)*)\s+(.*)$", text)
    if match:
        return match.group(1), match.group(2).strip()
    return f"{chapter_id}.{index}", text


def _extract_paragraph_images(paragraph, document, source_path: str, image_index: int):
    blocks = []
    embeds = paragraph._element.xpath(".//*[local-name()='blip']")
    for embed in embeds:
        rel_id = embed.get(qn("r:embed"))
        if not rel_id or rel_id not in document.part.related_parts:
            continue
        part = document.part.related_parts[rel_id]
        content_type = getattr(part, "content_type", "image/png")
        extension = ".png"
        if "/" in content_type:
            extension = "." + content_type.split("/")[-1].replace("jpeg", "jpg")
        asset_path = write_binary_asset(source_path, f"docx_image_{image_index}{extension}", part.blob)
        blocks.append(
            Block(
                block_type="image",
                asset_type="image",
                asset_path=asset_path,
                mime_type=content_type,
                alt_text="Embedded image",
                text="Embedded image",
                confidence=0.95,
            )
        )
        image_index += 1
    return blocks, image_index


def _iter_block_items(document: _Document):
    body = document.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def _extract_table_block(table) -> Block | None:
    rows = []
    for row in table.rows:
        cells = [_clean_text(cell.text) for cell in row.cells]
        if any(cells):
            rows.append(cells)
    if not rows:
        return None
    return Block(
        block_type="table",
        text="\n".join(" | ".join(row) for row in rows),
        rows=rows,
        label="Table",
        confidence=0.88,
    )


def parse_docx_document(file_path: str) -> Book:
    ensure_utf8_console()
    document = Document(file_path)
    book_title = _clean_text(document.core_properties.title)

    chapters = []
    current_chapter = None
    current_sections = []
    current_section = None
    chapter_buffer = []
    section_buffer = []
    section_blocks = []
    chapter_index = 0
    section_indices = defaultdict(int)
    warnings = []
    image_index = 1
    assets_detected = 0

    def ensure_overview_section():
        nonlocal current_section
        if current_section or current_chapter is None:
            return
        current_section = {"id": f"{current_chapter['id']}.1", "title": "Overview"}
        if section_indices[current_chapter["id"]] == 0:
            section_indices[current_chapter["id"]] = 1

    def flush_section():
        nonlocal current_section, section_buffer, current_sections, section_blocks
        if not current_section:
            return
        content = "\n".join(part for part in section_buffer if part).strip()
        if content:
            current_sections.append(
                Section(
                    section_id=current_section["id"],
                    title=current_section["title"],
                    content=content,
                    blocks=section_blocks or [Block(text=content)],
                    metadata=ParseMetadata(
                        source_path=file_path,
                        source_format="docx",
                        parser_name="docx_parser",
                        confidence=0.9,
                    ),
                )
            )
        current_section = None
        section_buffer = []
        section_blocks = []

    def flush_chapter():
        nonlocal current_chapter, chapter_buffer, current_sections, section_indices, section_blocks
        if not current_chapter:
            return
        flush_section()
        content = "\n".join(part for part in chapter_buffer if part).strip()
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
                                source_format="docx",
                                parser_name="docx_parser",
                                confidence=0.82,
                            ),
                        )
                    ],
                    metadata=ParseMetadata(
                        source_path=file_path,
                        source_format="docx",
                        parser_name="docx_parser",
                        confidence=0.9,
                    ),
                )
            )
        current_chapter = None
        chapter_buffer = []
        current_sections = []
        section_indices = defaultdict(int)
        section_blocks = []

    for item in _iter_block_items(document):
        if isinstance(item, Table):
            table_block = _extract_table_block(item)
            if not table_block:
                continue
            if current_chapter is None:
                chapter_index += 1
                current_chapter = {"id": str(chapter_index), "title": "Introduction"}
                warnings.append("Table found before chapter heading; inserted Introduction chapter")
            if not current_section:
                ensure_overview_section()
            section_blocks.append(table_block)
            section_buffer.append(table_block.text)
            chapter_buffer.append(table_block.text)
            continue

        paragraph = item
        text = _clean_text(paragraph.text)
        paragraph_images, image_index = _extract_paragraph_images(paragraph, document, file_path, image_index)
        assets_detected += len(paragraph_images)
        style_name = getattr(paragraph.style, "name", "")
        if not book_title and "title" in style_name.lower() and text:
            book_title = text
            continue
        if not text:
            if paragraph_images:
                if current_chapter is None:
                    chapter_index += 1
                    current_chapter = {"id": str(chapter_index), "title": Path(file_path).stem.replace("_", " ").title()}
                    warnings.append("Image found before chapter heading; inserted fallback chapter")
                ensure_overview_section()
                for image_block in paragraph_images:
                    section_blocks.append(image_block)
                    section_buffer.append(f"![{image_block.alt_text}]({image_block.asset_path})")
                    chapter_buffer.append(f"![{image_block.alt_text}]({image_block.asset_path})")
            continue
        if _looks_like_chapter(text, style_name):
            flush_chapter()
            chapter_index += 1
            current_chapter = {"id": str(chapter_index), "title": text.replace("Chapter ", "").strip() if text.lower().startswith("chapter ") else text}
            continue

        if _looks_like_section(text, style_name):
            if not current_chapter:
                warnings.append(f"Section found before chapter: {text}")
                chapter_index += 1
                current_chapter = {"id": str(chapter_index), "title": f"Chapter {chapter_index}"}
            flush_section()
            section_indices[current_chapter["id"]] += 1
            section_id, section_title = _section_parts(current_chapter["id"], text, section_indices[current_chapter["id"]])
            current_section = {"id": section_id, "title": section_title}
            continue

        if current_chapter is None:
            chapter_index += 1
            current_chapter = {"id": str(chapter_index), "title": "Introduction"}

        block_type = "callout" if "quote" in style_name.lower() else "paragraph"
        chapter_buffer.append(text)
        if not current_section:
            ensure_overview_section()
        if current_section:
            section_buffer.append(text if block_type == "paragraph" else f"> {text}")
            section_blocks.append(Block(text=text, block_type=block_type, label="Note" if block_type == "callout" else ""))
            for image_block in paragraph_images:
                section_blocks.append(image_block)
                section_buffer.append(f"![{image_block.alt_text}]({image_block.asset_path})")
                chapter_buffer.append(f"![{image_block.alt_text}]({image_block.asset_path})")

    flush_chapter()

    return Book(
        book_title=book_title or "DOCX Book",
        chapters=chapters,
        metadata=ParseMetadata(
            source_path=file_path,
            source_format="docx",
            parser_name="docx_parser",
            confidence=0.9,
        ),
        parse_report=ParseReport(
            parser_name="docx_parser",
            strategy_used="docx_parser",
            chapters_detected=len(chapters),
            sections_detected=sum(len(chapter.sections) for chapter in chapters),
            assets_detected=assets_detected,
            warnings=warnings,
        ),
    )
