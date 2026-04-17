from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class Block(BaseModel):
    text: str = ""
    block_type: str = "paragraph"
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    confidence: float = 1.0
    asset_path: str = ""
    asset_type: str = ""
    mime_type: str = ""
    caption: str = ""
    alt_text: str = ""
    label: str = ""
    rows: List[List[str]] = Field(default_factory=list)


class ParseMetadata(BaseModel):
    source_path: str = ""
    source_format: str = ""
    parser_name: str = ""
    parser_version: str = "1.0"
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    confidence: float = 1.0


class Section(BaseModel):
    section_id: str
    title: str
    content: str
    blocks: List[Block] = Field(default_factory=list)
    metadata: Optional[ParseMetadata] = None


class Chapter(BaseModel):
    chapter_id: str
    title: str
    content: str
    sections: List[Section] = Field(default_factory=list)
    metadata: Optional[ParseMetadata] = None


class ParseReport(BaseModel):
    parser_name: str
    parser_version: str = "1.0"
    strategy_used: str = ""
    warnings: List[str] = Field(default_factory=list)
    chapters_detected: int = 0
    sections_detected: int = 0
    assets_detected: int = 0
    scanned_pages: int = 0
    ocr_recommended: bool = False
    low_confidence_chapters: List[str] = Field(default_factory=list)
    candidate_scores: List[dict] = Field(default_factory=list)


class Book(BaseModel):
    book_title: str
    chapters: List[Chapter] = Field(default_factory=list)
    metadata: Optional[ParseMetadata] = None
    parse_report: Optional[ParseReport] = None
