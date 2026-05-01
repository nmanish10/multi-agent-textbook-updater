from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from core.console import ensure_utf8_console
from core.models import Block, Book, ParseMetadata, ParseReport
from ingestion.parsers.assets import write_binary_asset
from pypdf import PdfReader
from utils.md_parser import parse_markdown as legacy_parse_markdown
from utils.pdf_to_md import clean_line, convert_extracted_pages_to_md, convert_pdf_to_md


def _is_valid_chapter(line: str) -> bool:
    if len(line.split()) < 3 or len(line) > 120:
        return False
    if any(x in line for x in ["=", "Σ", "λ", "|", "∈"]):
        return False
    if re.search(r"\d+\.\d+", line):
        return False
    return True


def _convert_pdf_to_md_pypdf(pdf_path: str, output_path: str) -> str:
    reader = PdfReader(pdf_path)
    pages_raw: List[List[str]] = []

    for page in reader.pages:
        text = page.extract_text() or ""
        raw_lines: List[str] = []
        for line in text.split("\n"):
            cleaned = clean_line(line)
            if cleaned:
                raw_lines.append(cleaned)
        pages_raw.append(raw_lines)

    return convert_extracted_pages_to_md(pages_raw, output_path=output_path)


def _ocr_runtime_status() -> tuple[bool, str]:
    if os.getenv("OCR_ENABLED", "false").lower() != "true":
        return False, "OCR disabled by configuration"

    try:
        import pytesseract  # noqa: F401
        import pdf2image  # noqa: F401
    except Exception as exc:
        return False, f"OCR dependencies unavailable: {exc}"

    tesseract_cmd = os.getenv("TESSERACT_CMD", "").strip()
    if tesseract_cmd:
        if not Path(tesseract_cmd).exists():
            return False, f"Tesseract command not found at {tesseract_cmd}"
        return True, "OCR runtime ready"

    if shutil.which("tesseract"):
        return True, "OCR runtime ready"

    return False, "Tesseract executable not found in PATH; set TESSERACT_CMD or install Tesseract"


def _convert_pdf_to_md_ocr(pdf_path: str, output_path: str) -> str:
    import pytesseract
    from pdf2image import convert_from_path

    tesseract_cmd = os.getenv("TESSERACT_CMD", "").strip()
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    poppler_path = os.getenv("POPPLER_PATH", "").strip() or None
    images = convert_from_path(pdf_path, dpi=200, poppler_path=poppler_path)
    pages_raw: List[List[str]] = []
    for image in images:
        text = pytesseract.image_to_string(image) or ""
        page_lines: List[str] = []
        for line in text.splitlines():
            cleaned = clean_line(line)
            if cleaned:
                page_lines.append(cleaned)
        pages_raw.append(page_lines)

    return convert_extracted_pages_to_md(pages_raw, output_path=output_path)


def _score_book(book: Book) -> Tuple[float, List[str]]:
    warnings: List[str] = []
    chapters = len(book.chapters)
    sections = sum(len(chapter.sections) for chapter in book.chapters)
    total_words = sum(len(chapter.content.split()) for chapter in book.chapters)
    weak_chapters = [chapter.chapter_id for chapter in book.chapters if len(chapter.content.split()) < 120]

    if chapters == 0:
        warnings.append("No chapters parsed")
    if sections == 0:
        warnings.append("No sections parsed")
    if weak_chapters:
        warnings.append(f"Weak chapters detected: {', '.join(weak_chapters)}")

    score = (
        chapters * 8.0
        + sections * 2.0
        + min(total_words / 250.0, 20.0)
        - len(weak_chapters) * 2.5
    )
    return score, warnings


def _attach_metadata(
    parsed: Book,
    file_path: str,
    parser_name: str,
    confidence: float,
    candidate_scores: List[dict],
    warnings: List[str],
    scanned_pages: int = 0,
    ocr_recommended: bool = False,
) -> Book:
    sections_detected = 0
    assets_detected = 0
    low_confidence_chapters = []

    for chapter in parsed.chapters:
        chapter_confidence = confidence if chapter.sections else max(0.55, confidence - 0.2)
        if chapter_confidence < 0.8:
            low_confidence_chapters.append(chapter.chapter_id)
        chapter.metadata = ParseMetadata(
            source_path=file_path,
            source_format="pdf",
            parser_name=parser_name,
            confidence=chapter_confidence,
        )
        for section in chapter.sections:
            existing_blocks = [block for block in section.blocks if block.block_type == "image"]
            section.blocks = existing_blocks + [Block(text=section.content)]
            section.metadata = ParseMetadata(
                source_path=file_path,
                source_format="pdf",
                parser_name=parser_name,
                confidence=max(0.6, chapter_confidence - 0.05),
            )
            sections_detected += 1
            assets_detected += len(existing_blocks)

    parsed.metadata = ParseMetadata(
        source_path=file_path,
        source_format="pdf",
        parser_name=parser_name,
        confidence=confidence,
    )
    parsed.parse_report = ParseReport(
        parser_name=parser_name,
        strategy_used=parser_name,
        chapters_detected=len(parsed.chapters),
        sections_detected=sections_detected,
        assets_detected=assets_detected,
        warnings=warnings,
        scanned_pages=scanned_pages,
        ocr_recommended=ocr_recommended,
        low_confidence_chapters=low_confidence_chapters,
        candidate_scores=candidate_scores,
    )
    return parsed


def _extract_pdf_images(file_path: str, parsed: Book) -> List[str]:
    reader = PdfReader(file_path)
    extracted = []
    chapters = parsed.chapters
    if not chapters:
        return extracted

    current_chapter_index = 0
    chapter_titles = [chapter.title.lower() for chapter in chapters]

    for page_index, page in enumerate(reader.pages):
        page_text = (page.extract_text() or "").lower()
        for idx, title in enumerate(chapter_titles):
            if title and title in page_text:
                current_chapter_index = idx

        try:
            images = list(page.images)
        except Exception:
            images = []

        for image_idx, image in enumerate(images, start=1):
            try:
                extension = Path(image.name).suffix or ".png"
                asset_path = write_binary_asset(
                    file_path,
                    f"pdf_page_{page_index + 1}_image_{image_idx}{extension}",
                    image.data,
                )
                chapter = chapters[min(current_chapter_index, len(chapters) - 1)]
                target_section = chapter.sections[0] if chapter.sections else None
                if target_section:
                    target_section.blocks.append(
                        Block(
                            block_type="image",
                            asset_type="image",
                            asset_path=asset_path,
                            mime_type="image",
                            alt_text=f"Extracted figure from page {page_index + 1}",
                            text=f"Extracted figure from page {page_index + 1}",
                            page_start=page_index + 1,
                            page_end=page_index + 1,
                            confidence=0.65,
                        )
                    )
                    target_section.content += f"\n![Extracted figure from page {page_index + 1}]({asset_path})"
                extracted.append(asset_path)
            except Exception:
                continue
    return extracted


def _analyze_pdf_pages(file_path: str) -> tuple[int, bool, list[str]]:
    reader = PdfReader(file_path)
    scanned_pages = 0
    warnings: list[str] = []
    total_pages = len(reader.pages)

    for page_index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        text_chars = len(re.sub(r"\s+", "", text))
        try:
            image_count = len(list(page.images))
        except Exception:
            image_count = 0
        if text_chars < 40 and image_count > 0:
            scanned_pages += 1
        elif text_chars < 20:
            scanned_pages += 1
        if image_count >= 3 and text_chars < 120:
            warnings.append(f"Page {page_index} appears image-heavy and may need OCR or manual review")

    ocr_recommended = total_pages > 0 and scanned_pages >= max(1, total_pages // 3)
    if ocr_recommended:
        warnings.append(
            f"Detected {scanned_pages} low-text PDF pages out of {total_pages}; OCR fallback is recommended for best results"
        )
    return scanned_pages, ocr_recommended, warnings


def _run_strategy(
    strategy_name: str,
    converter: Callable[[str, str], str],
    file_path: str,
) -> Tuple[Book, Dict]:
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{strategy_name}.md") as temp_file:
        temp_path = temp_file.name

    try:
        markdown_path = converter(file_path, temp_path)
        parsed = legacy_parse_markdown(markdown_path)
        score, warnings = _score_book(parsed)
        details = {
            "strategy": strategy_name,
            "score": round(score, 2),
            "chapters": len(parsed.chapters),
            "sections": sum(len(chapter.sections) for chapter in parsed.chapters),
            "warnings": warnings,
        }
        return parsed, details
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def parse_pdf_document(file_path: str) -> Book:
    ensure_utf8_console()

    scanned_pages, ocr_recommended, page_warnings = _analyze_pdf_pages(file_path)

    strategies: List[Tuple[str, Callable[[str, str], str]]] = [
        ("pdfplumber_bridge", convert_pdf_to_md),
        ("pypdf_bridge", _convert_pdf_to_md_pypdf),
    ]
    ocr_available, ocr_status = _ocr_runtime_status()
    if ocr_available and ocr_recommended:
        strategies.append(("ocr_fallback", _convert_pdf_to_md_ocr))

    candidates: List[Tuple[Book, Dict]] = []
    candidate_scores: List[dict] = []

    for strategy_name, converter in strategies:
        try:
            parsed, details = _run_strategy(strategy_name, converter, file_path)
            candidates.append((parsed, details))
            candidate_scores.append(details)
        except Exception as exc:
            candidate_scores.append(
                {
                    "strategy": strategy_name,
                    "score": -1,
                    "chapters": 0,
                    "sections": 0,
                    "warnings": [f"Strategy failed: {exc}"],
                }
            )

    if ocr_recommended and not ocr_available:
        candidate_scores.append(
            {
                "strategy": "ocr_fallback",
                "score": -1,
                "chapters": 0,
                "sections": 0,
                "warnings": [ocr_status],
            }
        )

    if not candidates:
        raise ValueError("All PDF parsing strategies failed")

    best_book, best_details = max(candidates, key=lambda item: item[1]["score"])
    warnings = list(best_details.get("warnings", []))
    warnings.extend(
        [
            f"Alternative strategy {score['strategy']} scored {score['score']}"
            for score in candidate_scores
            if score["strategy"] != best_details["strategy"] and score["score"] >= 0
        ]
    )

    confidence = 0.9 if best_details["score"] >= 20 else 0.82 if best_details["score"] >= 12 else 0.72
    warnings.extend(page_warnings)
    if ocr_recommended:
        warnings.append(ocr_status)
    parsed = _attach_metadata(
        best_book,
        file_path,
        best_details["strategy"],
        confidence,
        candidate_scores,
        warnings,
        scanned_pages=scanned_pages,
        ocr_recommended=ocr_recommended,
    )
    extracted_images = _extract_pdf_images(file_path, parsed)
    if parsed.parse_report and extracted_images:
        parsed.parse_report.warnings.append(f"Extracted {len(extracted_images)} PDF images")
        parsed.parse_report.assets_detected += len(extracted_images)
    return parsed
