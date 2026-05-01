from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field


load_dotenv()


UpdateFrequency = Literal["daily", "weekly", "monthly", "manual"]


class AdminConfig(BaseModel):
    update_frequency: UpdateFrequency = Field(default="weekly")
    chapter_parallelism: int = Field(default=1, ge=1, le=8)
    max_updates_per_chapter: int = Field(default=3, ge=1, le=20)
    max_total_updates_per_chapter: int = Field(default=5, ge=1, le=50)
    min_accept_score: float = Field(default=0.78, ge=0.0, le=1.0)
    min_relevance: float = Field(default=0.75, ge=0.0, le=1.0)
    min_credibility: float = Field(default=0.70, ge=0.0, le=1.0)
    min_significance: float = Field(default=0.65, ge=0.0, le=1.0)
    enabled_sources: list[str] = Field(default_factory=lambda: ["openalex", "arxiv", "web", "official"])
    render_pdf: bool = Field(default=True)
    render_docx: bool = Field(default=True)
    generate_review_pack: bool = Field(default=True)


def next_scheduled_run(update_frequency: UpdateFrequency, *, from_time: datetime | None = None) -> datetime | None:
    reference = from_time or datetime.now(timezone.utc)
    if update_frequency == "manual":
        return None
    if update_frequency == "daily":
        return reference + timedelta(days=1)
    if update_frequency == "weekly":
        return reference + timedelta(days=7)
    return reference + timedelta(days=30)


class PipelineSettings(BaseModel):
    input_file: str = Field(default="data/sample.pdf")
    output_dir: str = Field(default="outputs")
    canonical_markdown: str = Field(default="outputs/updated_book.md")
    output_pdf: str = Field(default="outputs/updated_book.pdf")
    output_docx: str = Field(default="outputs/updated_book.docx")
    artifact_dir: str = Field(default="outputs/artifacts")
    update_store_dir: str = Field(default="outputs/update_store")
    uploads_dir: str = Field(default="outputs/uploads")
    generate_review_pack: bool = Field(default=True)
    demo_mode: bool = Field(default=True)
    max_updates_per_chapter: int = Field(default=3)
    max_total_updates_per_chapter: int = Field(default=5)
    retrieval_preview_limit: int = Field(default=5)
    chapter_limit: Optional[int] = Field(default=1)
    chapter_parallelism: int = Field(default=1)
    render_pdf: bool = Field(default=True)
    render_docx: bool = Field(default=True)
    pandoc_command: str = Field(default="pandoc")
    ocr_enabled: bool = Field(default=False)
    tesseract_cmd: str = Field(default="")
    poppler_path: str = Field(default="")
    min_accept_score: float = Field(default=0.78)
    min_relevance: float = Field(default=0.75)
    min_credibility: float = Field(default=0.70)
    min_significance: float = Field(default=0.65)
    enabled_sources: list[str] = Field(default_factory=lambda: ["openalex", "arxiv", "web", "official"])
    admin_config_path: str = Field(default="outputs/admin/admin_config.json")
    admin_audit_log_path: str = Field(default="outputs/admin/admin_audit_log.jsonl")
    scheduler_state_path: str = Field(default="outputs/admin/scheduler_state.json")
    run_history_path: str = Field(default="outputs/admin/run_history.json")

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
            uploads_dir=os.getenv("UPLOADS_DIR", "outputs/uploads"),
            generate_review_pack=os.getenv("GENERATE_REVIEW_PACK", "true").lower() == "true",
            demo_mode=demo_default,
            max_updates_per_chapter=int(os.getenv("MAX_UPDATES_PER_CHAPTER", "3")),
            max_total_updates_per_chapter=int(os.getenv("MAX_TOTAL_UPDATES_PER_CHAPTER", "5")),
            retrieval_preview_limit=int(os.getenv("RETRIEVAL_PREVIEW_LIMIT", "5")),
            chapter_limit=int(chapter_limit) if chapter_limit else (1 if demo_default else None),
            chapter_parallelism=int(os.getenv("CHAPTER_PARALLELISM", "1")),
            render_pdf=os.getenv("RENDER_PDF", "true").lower() == "true",
            render_docx=os.getenv("RENDER_DOCX", "true").lower() == "true",
            pandoc_command=os.getenv("PANDOC_COMMAND", "pandoc"),
            ocr_enabled=os.getenv("OCR_ENABLED", "false").lower() == "true",
            tesseract_cmd=os.getenv("TESSERACT_CMD", ""),
            poppler_path=os.getenv("POPPLER_PATH", ""),
            min_accept_score=float(os.getenv("MIN_ACCEPT_SCORE", "0.78")),
            min_relevance=float(os.getenv("MIN_RELEVANCE", "0.75")),
            min_credibility=float(os.getenv("MIN_CREDIBILITY", "0.70")),
            min_significance=float(os.getenv("MIN_SIGNIFICANCE", "0.65")),
            enabled_sources=[
                item.strip()
                for item in os.getenv("ENABLED_SOURCES", "openalex,arxiv,web,official").split(",")
                if item.strip()
            ],
            admin_config_path=os.getenv("ADMIN_CONFIG_PATH", "outputs/admin/admin_config.json"),
            admin_audit_log_path=os.getenv("ADMIN_AUDIT_LOG_PATH", "outputs/admin/admin_audit_log.jsonl"),
            scheduler_state_path=os.getenv("SCHEDULER_STATE_PATH", "outputs/admin/scheduler_state.json"),
            run_history_path=os.getenv("RUN_HISTORY_PATH", "outputs/admin/run_history.json"),
        )

    def ensure_directories(self) -> None:
        for value in [
            self.output_dir,
            self.artifact_dir,
            self.update_store_dir,
            self.uploads_dir,
            str(Path(self.admin_config_path).parent),
            str(Path(self.scheduler_state_path).parent),
            str(Path(self.run_history_path).parent),
        ]:
            Path(value).mkdir(parents=True, exist_ok=True)

    def apply_admin_config(self, admin_config: AdminConfig) -> None:
        self.max_updates_per_chapter = admin_config.max_updates_per_chapter
        self.max_total_updates_per_chapter = admin_config.max_total_updates_per_chapter
        self.chapter_parallelism = admin_config.chapter_parallelism
        self.min_accept_score = admin_config.min_accept_score
        self.min_relevance = admin_config.min_relevance
        self.min_credibility = admin_config.min_credibility
        self.min_significance = admin_config.min_significance
        self.enabled_sources = list(admin_config.enabled_sources)
        self.render_pdf = admin_config.render_pdf
        self.render_docx = admin_config.render_docx
        self.generate_review_pack = admin_config.generate_review_pack
