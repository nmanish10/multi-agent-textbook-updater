from __future__ import annotations

import copy
import csv
import json
import logging
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.run_pipeline import run_pipeline
from core.config import AdminConfig, PipelineSettings
from core.logging import StructuredFormatter
from core.models import Book
from review.decision_ingest import write_review_decision_outputs
from storage.admin_config_store import AdminConfigStore
from storage.run_history_store import RunHistoryStore


class RunPipelineRequest(BaseModel):
    input_file: str | None = None
    output_dir: str | None = None
    chapter_limit: int | None = None
    full_run: bool = False
    skip_pdf: bool = False
    skip_docx: bool = False
    skip_review_pack: bool = False
    run_if_due: bool = False


class AdminConfigPatch(BaseModel):
    update_frequency: str | None = None
    chapter_parallelism: int | None = Field(default=None, ge=1, le=8)
    max_updates_per_chapter: int | None = Field(default=None, ge=1, le=20)
    max_total_updates_per_chapter: int | None = Field(default=None, ge=1, le=50)
    min_accept_score: float | None = Field(default=None, ge=0.0, le=1.0)
    min_relevance: float | None = Field(default=None, ge=0.0, le=1.0)
    min_credibility: float | None = Field(default=None, ge=0.0, le=1.0)
    min_significance: float | None = Field(default=None, ge=0.0, le=1.0)
    enabled_sources: list[str] | None = None
    render_pdf: bool | None = None
    render_docx: bool | None = None
    generate_review_pack: bool | None = None


class ReviewDecisionRow(BaseModel):
    chapter_id: str
    chapter_title: str = ""
    section_id: str
    proposed_subsection_id: str = ""
    title: str
    source_summary: str = ""
    score_summary: str = ""
    review_decision: str = ""
    review_notes: str = ""


class ReviewDecisionPayload(BaseModel):
    rows: list[ReviewDecisionRow]
    export_docx_enabled: bool = True
    export_pdf_enabled: bool = True


def _admin_store(settings: PipelineSettings) -> AdminConfigStore:
    return AdminConfigStore(
        settings.admin_config_path,
        settings.admin_audit_log_path,
        settings.scheduler_state_path,
    )


def _run_history_store(settings: PipelineSettings) -> RunHistoryStore:
    return RunHistoryStore(settings.run_history_path)


def _load_update_store_payloads(base_dir: str) -> list[dict[str, Any]]:
    root = Path(base_dir)
    if not root.exists():
        return []
    payloads = []
    for path in sorted(root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload.setdefault("book_key", path.stem)
            payloads.append(payload)
        except Exception:
            continue
    return payloads


def _safe_upload_name(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return cleaned or "uploaded_book"


def _book_index(settings: PipelineSettings) -> list[dict[str, Any]]:
    history = _run_history_store(settings).load().get("runs", [])
    updates = {entry.get("book_key"): entry for entry in _load_update_store_payloads(settings.update_store_dir)}
    latest_by_book: dict[str, dict[str, Any]] = {}
    for run in history:
        book_key = run.get("book_key")
        if not book_key:
            continue
        latest_by_book[book_key] = run

    books = []
    for book_key, run in latest_by_book.items():
        update_payload = updates.get(book_key, {})
        chapter_updates = update_payload.get("chapters", {})
        update_count = sum(len(items) for items in chapter_updates.values())
        books.append(
            {
                "book_key": book_key,
                "book_title": run.get("book_title") or book_key,
                "input_file": run.get("input_file"),
                "latest_run_id": run.get("run_id"),
                "artifact_dir": run.get("artifact_dir"),
                "last_recorded_at": run.get("recorded_at"),
                "update_count": update_count,
                "chapters_with_updates": len(chapter_updates),
            }
        )
    return sorted(books, key=lambda item: item.get("last_recorded_at") or "", reverse=True)


def _run_dir(settings: PipelineSettings, run_id: str) -> Path:
    return Path(settings.artifact_dir) / run_id


def _build_run_settings(base_settings: PipelineSettings, payload: RunPipelineRequest) -> PipelineSettings:
    run_settings = copy.deepcopy(base_settings)
    if payload.input_file:
        run_settings.input_file = payload.input_file
    if payload.output_dir:
        run_settings.output_dir = payload.output_dir
    if payload.chapter_limit is not None:
        run_settings.chapter_limit = payload.chapter_limit
    if payload.full_run:
        run_settings.demo_mode = False
        run_settings.chapter_limit = payload.chapter_limit
    if payload.skip_pdf:
        run_settings.render_pdf = False
    if payload.skip_docx:
        run_settings.render_docx = False
    if payload.skip_review_pack:
        run_settings.generate_review_pack = False
    return run_settings


class JobLogHandler(logging.Handler):
    def __init__(self, on_line) -> None:
        super().__init__()
        self.on_line = on_line
        self.setFormatter(StructuredFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.on_line(self.format(record))
        except Exception:
            self.handleError(record)


def _latest_run_for_book(settings: PipelineSettings, book_key: str) -> dict[str, Any] | None:
    history = reversed(_run_history_store(settings).load().get("runs", []))
    for run in history:
        if run.get("book_key") == book_key:
            return run
    return None


def _load_parsed_book(run_dir: Path) -> Book | None:
    path = run_dir / "book" / "parsed_book.json"
    if not path.exists():
        return None
    return Book(**json.loads(path.read_text(encoding="utf-8")))


def _section_context_map(book: Book | None) -> dict[tuple[str, str], dict[str, str]]:
    if not book:
        return {}
    context: dict[tuple[str, str], dict[str, str]] = {}
    for chapter in book.chapters:
        for section in chapter.sections:
            context[(chapter.chapter_id, section.section_id)] = {
                "section_title": section.title,
                "section_context": section.content[:1200],
            }
    return context


def _written_update_map(run_dir: Path) -> dict[tuple[str, str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str, str], dict[str, Any]] = {}
    for path in sorted(run_dir.glob("chapters/*/written_updates.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in payload:
            key = (
                (item.get("chapter_id") or "").strip(),
                (item.get("section_id") or "").strip(),
                (item.get("title") or "").strip().lower(),
            )
            lookup[key] = item
    return lookup


def _review_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def create_app(settings: PipelineSettings | None = None) -> FastAPI:
    base_settings = settings or PipelineSettings.from_env()
    base_settings.ensure_directories()
    app = FastAPI(title="Multi-Agent Textbook Update System API", version="0.1.0")
    jobs: dict[str, dict[str, Any]] = {}
    jobs_lock = threading.Lock()
    cors_origins = [
        origin.strip()
        for origin in os.getenv("API_CORS_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000").split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "textbook-updater-api",
            "api_version": "0.1.0",
        }

    @app.get("/api/admin/config")
    def get_admin_config() -> dict[str, Any]:
        return _admin_store(base_settings).load().model_dump(mode="json")

    @app.put("/api/admin/config")
    def update_admin_config(payload: AdminConfigPatch) -> dict[str, Any]:
        patch = payload.model_dump(exclude_none=True)
        if "update_frequency" in patch:
            AdminConfig(update_frequency=patch["update_frequency"])
        updated = _admin_store(base_settings).update(patch, actor="api", reason="api_update")
        return updated.model_dump(mode="json")

    @app.get("/api/admin/schedule")
    def get_schedule() -> dict[str, Any]:
        return _admin_store(base_settings).scheduler_snapshot()

    @app.get("/api/admin/run-history")
    def get_run_history() -> dict[str, Any]:
        return _run_history_store(base_settings).load()

    @app.get("/api/books")
    def list_books() -> dict[str, Any]:
        return {"books": _book_index(base_settings)}

    @app.post("/api/books/upload")
    async def upload_book(file: UploadFile = File(...)) -> dict[str, Any]:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in {".pdf", ".md", ".markdown", ".docx", ".html", ".htm"}:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        uploads_root = Path(base_settings.uploads_dir)
        uploads_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_name = _safe_upload_name(Path(file.filename or "uploaded_book").name)
        target_path = uploads_root / f"{timestamp}_{safe_name}"
        content = await file.read()
        target_path.write_bytes(content)
        return {
            "status": "uploaded",
            "filename": file.filename,
            "stored_path": str(target_path),
            "size_bytes": len(content),
        }

    @app.get("/api/books/{book_key}/chapters")
    def get_book_chapters(book_key: str) -> dict[str, Any]:
        latest_run = _latest_run_for_book(base_settings, book_key)
        if not latest_run:
            raise HTTPException(status_code=404, detail="Book not found")

        run_dir = _run_dir(base_settings, latest_run["run_id"])
        book = _load_parsed_book(run_dir)
        if not book:
            raise HTTPException(status_code=404, detail="Parsed book not found")

        store_payloads = {item.get("book_key"): item for item in _load_update_store_payloads(base_settings.update_store_dir)}
        chapter_updates = store_payloads.get(book_key, {}).get("chapters", {})
        chapters = []
        for chapter in book.chapters:
            active_updates = chapter_updates.get(chapter.chapter_id, [])
            update_section_ids = {
                (item.get("section_id") or "").strip()
                for item in active_updates
            }
            sections = [
                {
                    "section_id": section.section_id,
                    "title": section.title,
                    "has_updates": section.section_id in update_section_ids,
                }
                for section in chapter.sections
            ]
            chapters.append(
                {
                    "chapter_id": chapter.chapter_id,
                    "title": chapter.title,
                    "section_count": len(chapter.sections),
                    "update_count": len(active_updates),
                    "sections": sections,
                }
            )

        return {
            "book_key": book_key,
            "book_title": book.book_title,
            "chapters": chapters,
        }

    @app.get("/api/books/{book_key}/chapters/{chapter_id}")
    def get_book_chapter(book_key: str, chapter_id: str) -> dict[str, Any]:
        latest_run = _latest_run_for_book(base_settings, book_key)
        if not latest_run:
            raise HTTPException(status_code=404, detail="Book not found")

        run_dir = _run_dir(base_settings, latest_run["run_id"])
        book = _load_parsed_book(run_dir)
        if not book:
            raise HTTPException(status_code=404, detail="Parsed book not found")

        chapter = next((item for item in book.chapters if item.chapter_id == chapter_id), None)
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")

        store_payloads = {item.get("book_key"): item for item in _load_update_store_payloads(base_settings.update_store_dir)}
        active_updates = store_payloads.get(book_key, {}).get("chapters", {}).get(chapter_id, [])

        return {
            "book_key": book_key,
            "book_title": book.book_title,
            "chapter_id": chapter.chapter_id,
            "title": chapter.title,
            "content": chapter.content,
            "sections": [
                {
                    "section_id": section.section_id,
                    "title": section.title,
                    "content": section.content,
                }
                for section in chapter.sections
            ],
            "updates": active_updates,
        }

    @app.get("/api/books/{book_key}")
    def get_book(book_key: str) -> dict[str, Any]:
        books = {item["book_key"]: item for item in _book_index(base_settings)}
        if book_key not in books:
            raise HTTPException(status_code=404, detail="Book not found")
        store_payloads = {item.get("book_key"): item for item in _load_update_store_payloads(base_settings.update_store_dir)}
        return {
            "book": books[book_key],
            "update_store": store_payloads.get(book_key, {"book_key": book_key, "chapters": {}, "history": []}),
        }

    @app.get("/api/books/{book_key}/updates")
    def get_book_updates(book_key: str) -> dict[str, Any]:
        store_payloads = {item.get("book_key"): item for item in _load_update_store_payloads(base_settings.update_store_dir)}
        if book_key not in store_payloads:
            raise HTTPException(status_code=404, detail="Book updates not found")
        payload = store_payloads[book_key]
        flat_updates = []
        for chapter_id, updates in payload.get("chapters", {}).items():
            for update in updates:
                flat_updates.append({**update, "chapter_id": chapter_id})
        return {
            "book_key": book_key,
            "updates": flat_updates,
            "history": payload.get("history", []),
        }

    @app.get("/api/review/runs")
    def list_review_runs() -> dict[str, Any]:
        runs = []
        history = list(reversed(_run_history_store(base_settings).load().get("runs", [])))
        for run in history:
            run_id = run.get("run_id")
            if not run_id:
                continue
            run_dir = _run_dir(base_settings, run_id)
            review_json = run_dir / "review" / "review_pack.json"
            review_csv = run_dir / "review" / "review_queue.csv"
            if not review_json.exists():
                continue
            runs.append(
                {
                    "run_id": run_id,
                    "book_key": run.get("book_key"),
                    "book_title": run.get("book_title"),
                    "recorded_at": run.get("recorded_at"),
                    "artifact_dir": str(run_dir),
                    "has_review_queue": review_csv.exists(),
                }
            )
        return {"runs": runs}

    @app.get("/api/review/runs/{run_id}")
    def get_review_run(run_id: str) -> dict[str, Any]:
        run_dir = _run_dir(base_settings, run_id)
        review_json = run_dir / "review" / "review_pack.json"
        review_csv = run_dir / "review" / "review_queue.csv"
        if not review_json.exists():
            raise HTTPException(status_code=404, detail="Review pack not found")
        payload = json.loads(review_json.read_text(encoding="utf-8"))
        section_context = _section_context_map(_load_parsed_book(run_dir))
        written_updates = _written_update_map(run_dir)
        enriched_queue = []
        for row in _review_csv_rows(review_csv):
            key = (
                (row.get("chapter_id") or "").strip(),
                (row.get("section_id") or "").strip(),
                (row.get("title") or "").strip().lower(),
            )
            section_info = section_context.get((key[0], key[1]), {})
            written = written_updates.get(key, {})
            enriched_queue.append(
                {
                    **row,
                    "section_title": section_info.get("section_title", ""),
                    "section_context": section_info.get("section_context", ""),
                    "proposed_text": written.get("text", ""),
                    "why_it_matters": written.get("why_it_matters", ""),
                    "mapping_rationale": written.get("mapping_rationale", ""),
                    "source": written.get("source", ""),
                }
            )
        return {
            "run_id": run_id,
            "artifact_dir": str(run_dir),
            "review_pack": payload,
            "review_queue": enriched_queue,
        }

    @app.post("/api/review/runs/{run_id}/apply")
    def apply_review_decisions(run_id: str, payload: ReviewDecisionPayload) -> dict[str, Any]:
        run_dir = _run_dir(base_settings, run_id)
        review_dir = run_dir / "review"
        review_dir.mkdir(parents=True, exist_ok=True)
        review_csv = review_dir / "review_queue.csv"

        with review_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "chapter_id",
                    "chapter_title",
                    "section_id",
                    "proposed_subsection_id",
                    "title",
                    "source_summary",
                    "score_summary",
                    "review_decision",
                    "review_notes",
                ],
            )
            writer.writeheader()
            for row in payload.rows:
                writer.writerow(row.model_dump(mode="json"))

        outputs = write_review_decision_outputs(
            run_dir=str(run_dir),
            review_queue_csv=str(review_csv),
            export_docx_enabled=payload.export_docx_enabled,
            export_pdf_enabled=payload.export_pdf_enabled,
            pandoc_command=base_settings.pandoc_command,
        )
        return {
            "status": "applied",
            "run_id": run_id,
            "outputs": outputs,
            "review_queue_csv": str(review_csv),
        }

    @app.post("/api/pipeline/run")
    def trigger_run(payload: RunPipelineRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
        admin_store = _admin_store(base_settings)
        if payload.run_if_due:
            snapshot = admin_store.scheduler_snapshot()
            if not snapshot["due_now"]:
                return {"status": "not_due", "scheduler": snapshot}

        job_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        with jobs_lock:
            jobs[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "logs": [],
                "summary": None,
                "error": None,
                "created_at": now,
                "updated_at": now,
                "input_file": payload.input_file or base_settings.input_file,
            }

        def append_log(line: str) -> None:
            with jobs_lock:
                job = jobs.get(job_id)
                if not job:
                    return
                job["logs"].append(line)
                if len(job["logs"]) > 1000:
                    job["logs"] = job["logs"][-1000:]
                job["updated_at"] = datetime.now(timezone.utc).isoformat()

        def run_job() -> None:
            root_logger = logging.getLogger()
            handler = JobLogHandler(append_log)
            root_logger.addHandler(handler)
            with jobs_lock:
                jobs[job_id]["status"] = "running"
                jobs[job_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            append_log(f"Pipeline job {job_id} started.")
            try:
                summary = run_pipeline(_build_run_settings(base_settings, payload))
                with jobs_lock:
                    jobs[job_id]["status"] = "completed"
                    jobs[job_id]["summary"] = summary
                    jobs[job_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
                append_log(f"Pipeline job {job_id} completed.")
            except Exception as exc:
                logging.getLogger("textbook_updater.api").exception("Pipeline job failed", extra={"job_id": job_id})
                with jobs_lock:
                    jobs[job_id]["status"] = "failed"
                    jobs[job_id]["error"] = str(exc)
                    jobs[job_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            finally:
                root_logger.removeHandler(handler)

        background_tasks.add_task(run_job)
        return {"status": "queued", "job_id": job_id}

    @app.get("/api/pipeline/jobs/{job_id}")
    def get_pipeline_job(job_id: str) -> dict[str, Any]:
        with jobs_lock:
            job = jobs.get(job_id)
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            return {**job, "logs": "\n".join(job["logs"])}

    return app

app = create_app()
