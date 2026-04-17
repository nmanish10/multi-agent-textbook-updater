from __future__ import annotations

from pathlib import Path

from core.models import Book
from ingestion.normalization.repair import normalize_book
from ingestion.normalization.validation import validate_book_structure
from ingestion.parsers.docx_parser import parse_docx_document
from ingestion.parsers.html_parser import parse_html_document
from ingestion.parsers.markdown_parser import parse_markdown_document
from ingestion.parsers.pdf_parser import parse_pdf_document


def load_book(file_path: str) -> Book:
    suffix = Path(file_path).suffix.lower()
    if suffix == ".md":
        book = parse_markdown_document(file_path)
    elif suffix == ".pdf":
        book = parse_pdf_document(file_path)
    elif suffix == ".docx":
        book = parse_docx_document(file_path)
    elif suffix in {".html", ".htm"}:
        book = parse_html_document(file_path)
    else:
        raise ValueError(f"Unsupported file format: {suffix}")

    book, _normalization_warnings = normalize_book(book, file_path)
    validation = validate_book_structure(book)
    if book.parse_report:
        book.parse_report.warnings.extend(validation["warnings"])
    return book
