from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field


load_dotenv()


class PipelineSettings(BaseModel):
    input_file: str = Field(default="data/sample.pdf")
    output_dir: str = Field(default="outputs")
    canonical_markdown: str = Field(default="outputs/updated_book.md")
    output_pdf: str = Field(default="outputs/updated_book.pdf")
    output_docx: str = Field(default="outputs/updated_book.docx")
    artifact_dir: str = Field(default="outputs/artifacts")
    update_store_dir: str = Field(default="outputs/update_store")
    generate_review_pack: bool = Field(default=True)
    demo_mode: bool = Field(default=True)
    max_updates_per_chapter: int = Field(default=3)
    max_total_updates_per_chapter: int = Field(default=5)
    retrieval_preview_limit: int = Field(default=5)
    chapter_limit: Optional[int] = Field(default=1)
    render_pdf: bool = Field(default=True)
    render_docx: bool = Field(default=True)
    pandoc_command: str = Field(default="pandoc")
    ocr_enabled: bool = Field(default=False)
    tesseract_cmd: str = Field(default="")
    poppler_path: str = Field(default="")

    @classmethod
    def from_env(cls) -> "PipelineSettings":
        demo_default = os.getenv("DEMO_MODE", "true").lower() == "true"
        chapter_limit = os.getenv("CHAPTER_LIMIT")
        return cls(
            input_file=os.getenv("INPUT_FILE", "data/sample.pdf"),
            output_dir=os.getenv("OUTPUT_DIR", "outputs"),
            canonical_markdown=os.getenv("CANONICAL_MARKDOWN", "outputs/updated_book.md"),
            output_pdf=os.getenv("OUTPUT_PDF", "outputs/updated_book.pdf"),
            output_docx=os.getenv("OUTPUT_DOCX", "outputs/updated_book.docx"),
            artifact_dir=os.getenv("ARTIFACT_DIR", "outputs/artifacts"),
            update_store_dir=os.getenv("UPDATE_STORE_DIR", "outputs/update_store"),
            generate_review_pack=os.getenv("GENERATE_REVIEW_PACK", "true").lower() == "true",
            demo_mode=demo_default,
            max_updates_per_chapter=int(os.getenv("MAX_UPDATES_PER_CHAPTER", "3")),
            max_total_updates_per_chapter=int(os.getenv("MAX_TOTAL_UPDATES_PER_CHAPTER", "5")),
            retrieval_preview_limit=int(os.getenv("RETRIEVAL_PREVIEW_LIMIT", "5")),
            chapter_limit=int(chapter_limit) if chapter_limit else (1 if demo_default else None),
            render_pdf=os.getenv("RENDER_PDF", "true").lower() == "true",
            render_docx=os.getenv("RENDER_DOCX", "true").lower() == "true",
            pandoc_command=os.getenv("PANDOC_COMMAND", "pandoc"),
            ocr_enabled=os.getenv("OCR_ENABLED", "false").lower() == "true",
            tesseract_cmd=os.getenv("TESSERACT_CMD", ""),
            poppler_path=os.getenv("POPPLER_PATH", ""),
        )

    def ensure_directories(self) -> None:
        for value in [self.output_dir, self.artifact_dir, self.update_store_dir]:
            Path(value).mkdir(parents=True, exist_ok=True)
