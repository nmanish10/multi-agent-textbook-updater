from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api import create_app
from core.config import PipelineSettings
from storage.admin_config_store import AdminConfigStore
from storage.run_history_store import RunHistoryStore


class ApiTests(unittest.TestCase):
    def _settings(self, temp_dir: str) -> PipelineSettings:
        root = Path(temp_dir)
        return PipelineSettings(
            input_file="data/sample.md",
            output_dir=str(root / "outputs"),
            canonical_markdown=str(root / "outputs" / "updated_book.md"),
            output_pdf=str(root / "outputs" / "updated_book.pdf"),
            output_docx=str(root / "outputs" / "updated_book.docx"),
            artifact_dir=str(root / "outputs" / "artifacts"),
            update_store_dir=str(root / "outputs" / "update_store"),
            uploads_dir=str(root / "outputs" / "uploads"),
            admin_config_path=str(root / "outputs" / "admin" / "admin_config.json"),
            admin_audit_log_path=str(root / "outputs" / "admin" / "admin_audit_log.jsonl"),
            scheduler_state_path=str(root / "outputs" / "admin" / "scheduler_state.json"),
            run_history_path=str(root / "outputs" / "admin" / "run_history.json"),
        )

    def test_health_and_admin_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self._settings(temp_dir)
            client = TestClient(create_app(settings))

            health = client.get("/api/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["status"], "ok")

            config = client.get("/api/admin/config")
            self.assertEqual(config.status_code, 200)
            self.assertEqual(config.json()["update_frequency"], "weekly")

            updated = client.put(
                "/api/admin/config",
                json={"update_frequency": "daily", "chapter_parallelism": 2, "enabled_sources": ["official"]},
            )
            self.assertEqual(updated.status_code, 200)
            self.assertEqual(updated.json()["update_frequency"], "daily")
            self.assertEqual(updated.json()["enabled_sources"], ["official"])

            schedule = client.get("/api/admin/schedule")
            self.assertEqual(schedule.status_code, 200)
            self.assertIn("due_now", schedule.json())

    def test_books_and_updates_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self._settings(temp_dir)
            settings.ensure_directories()
            history = RunHistoryStore(settings.run_history_path)
            history.append_run(
                {
                    "run_id": "run-1",
                    "book_key": "sample-book",
                    "book_title": "Sample Book",
                    "input_file": "data/sample.md",
                    "artifact_dir": "outputs/artifacts/run-1",
                    "stats": {"final_updates": 1, "accepted_candidates": 1},
                    "outputs": {"markdown": "outputs/updated_book.md"},
                    "admin_config": {"update_frequency": "weekly"},
                    "input_fingerprint": "abc123",
                }
            )
            update_store_path = Path(settings.update_store_dir) / "sample-book.json"
            update_store_path.write_text(
                """
                {
                  "book_key": "sample-book",
                  "chapters": {
                    "ch1": [
                      {
                        "chapter_id": "ch1",
                        "section_id": "1.1",
                        "title": "New Benchmark",
                        "text": "A strong new result.",
                        "why_it_matters": "It changes the state of the art.",
                        "sources": [],
                        "source": "https://example.com",
                        "scores": {"final_score": 0.9},
                        "mapping_rationale": "Fits the benchmarks section",
                        "update_id": "u1",
                        "status": "active"
                      }
                    ]
                  },
                  "history": []
                }
                """.strip(),
                encoding="utf-8",
            )
            parsed_book_path = Path(settings.artifact_dir) / "run-1" / "book"
            parsed_book_path.mkdir(parents=True, exist_ok=True)
            (parsed_book_path / "parsed_book.json").write_text(
                json.dumps(
                    {
                        "book_title": "Sample Book",
                        "metadata": None,
                        "parse_report": None,
                        "chapters": [
                            {
                                "chapter_id": "ch1",
                                "title": "Introduction",
                                "content": "Chapter overview",
                                "sections": [
                                    {
                                        "section_id": "1.1",
                                        "title": "Benchmarks",
                                        "content": "Benchmarking context for the chapter.",
                                        "blocks": [],
                                        "metadata": None,
                                    },
                                    {
                                        "section_id": "1.2",
                                        "title": "Methods",
                                        "content": "Methods section context.",
                                        "blocks": [],
                                        "metadata": None,
                                    },
                                ],
                                "metadata": None,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            client = TestClient(create_app(settings))
            books = client.get("/api/books")
            self.assertEqual(books.status_code, 200)
            self.assertEqual(len(books.json()["books"]), 1)
            self.assertEqual(books.json()["books"][0]["book_key"], "sample-book")

            book = client.get("/api/books/sample-book")
            self.assertEqual(book.status_code, 200)
            self.assertEqual(book.json()["book"]["book_title"], "Sample Book")

            updates = client.get("/api/books/sample-book/updates")
            self.assertEqual(updates.status_code, 200)
            self.assertEqual(len(updates.json()["updates"]), 1)
            self.assertEqual(updates.json()["updates"][0]["title"], "New Benchmark")

            chapters = client.get("/api/books/sample-book/chapters")
            self.assertEqual(chapters.status_code, 200)
            self.assertEqual(chapters.json()["chapters"][0]["chapter_id"], "ch1")
            self.assertTrue(chapters.json()["chapters"][0]["sections"][0]["has_updates"])

            chapter = client.get("/api/books/sample-book/chapters/ch1")
            self.assertEqual(chapter.status_code, 200)
            self.assertEqual(chapter.json()["title"], "Introduction")
            self.assertEqual(chapter.json()["sections"][0]["section_id"], "1.1")
            self.assertEqual(chapter.json()["updates"][0]["title"], "New Benchmark")

    def test_run_endpoint_returns_not_due_without_executing_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self._settings(temp_dir)
            store = AdminConfigStore(
                settings.admin_config_path,
                settings.admin_audit_log_path,
                settings.scheduler_state_path,
            )
            store.mark_run_completed(run_id="previous-run")
            client = TestClient(create_app(settings))

            with patch("app.api.run_pipeline") as mocked_run:
                response = client.post("/api/pipeline/run", json={"run_if_due": True})

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "not_due")
            mocked_run.assert_not_called()

    def test_run_endpoint_returns_job_and_exposes_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self._settings(temp_dir)
            client = TestClient(create_app(settings))

            with patch("app.api.run_pipeline", return_value={"run_id": "run-async", "stats": {}}):
                response = client.post("/api/pipeline/run", json={"input_file": "data/sample.md"})

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["status"], "queued")
            self.assertIn("job_id", payload)

            job = client.get(f"/api/pipeline/jobs/{payload['job_id']}")
            self.assertEqual(job.status_code, 200)
            job_payload = job.json()
            self.assertEqual(job_payload["status"], "completed")
            self.assertEqual(job_payload["summary"]["run_id"], "run-async")
            self.assertIn("Pipeline job", job_payload["logs"])

    def test_upload_endpoint_stores_supported_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self._settings(temp_dir)
            client = TestClient(create_app(settings))

            response = client.post(
                "/api/books/upload",
                files={"file": ("sample.md", b"# Sample Book\n\n## Section\n\nContent", "text/markdown")},
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["status"], "uploaded")
            self.assertTrue(Path(payload["stored_path"]).exists())

    def test_review_endpoints_expose_and_apply_review_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = self._settings(temp_dir)
            settings.ensure_directories()
            run_dir = Path(settings.artifact_dir) / "run-123"
            (run_dir / "review").mkdir(parents=True, exist_ok=True)
            (run_dir / "chapters" / "ch1").mkdir(parents=True, exist_ok=True)
            (run_dir / "book").mkdir(parents=True, exist_ok=True)

            RunHistoryStore(settings.run_history_path).append_run(
                {
                    "run_id": "run-123",
                    "book_key": "sample-book",
                    "book_title": "Sample Book",
                    "input_file": "data/sample.md",
                    "artifact_dir": str(run_dir),
                    "stats": {"final_updates": 1, "accepted_candidates": 1},
                    "outputs": {"markdown": "outputs/updated_book.md"},
                    "admin_config": {"update_frequency": "weekly"},
                    "input_fingerprint": "abc123",
                }
            )
            (run_dir / "review" / "review_pack.json").write_text(
                json.dumps(
                    {
                        "book_title": "Sample Book",
                        "accepted_updates": [
                            {
                                "chapter_id": "ch1",
                                "chapter_title": "Intro",
                                "section_id": "1.1",
                                "proposed_subsection_id": "",
                                "title": "New Benchmark",
                                "why_it_matters": "Important",
                                "mapping_rationale": "Fits section",
                                "source_summary": "https://example.com",
                                "scores": {"final_score": 0.9},
                                "review_decision": "",
                                "review_notes": "",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (run_dir / "review" / "review_queue.csv").write_text(
                "chapter_id,chapter_title,section_id,proposed_subsection_id,title,source_summary,score_summary,review_decision,review_notes\n"
                "ch1,Intro,1.1,,New Benchmark,https://example.com,final_score=0.9,,\n",
                encoding="utf-8",
            )
            (run_dir / "chapters" / "ch1" / "written_updates.json").write_text(
                json.dumps(
                    [
                        {
                            "chapter_id": "ch1",
                            "section_id": "1.1",
                            "title": "New Benchmark",
                            "text": "A strong new result.",
                            "why_it_matters": "It changes the state of the art.",
                            "sources": [],
                            "source": "https://example.com",
                            "scores": {"final_score": 0.9},
                            "mapping_rationale": "Fits section",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (run_dir / "book" / "parsed_book.json").write_text(
                json.dumps(
                    {
                        "book_title": "Sample Book",
                        "metadata": None,
                        "parse_report": None,
                        "chapters": [],
                    }
                ),
                encoding="utf-8",
            )

            client = TestClient(create_app(settings))
            review_runs = client.get("/api/review/runs")
            self.assertEqual(review_runs.status_code, 200)
            self.assertEqual(review_runs.json()["runs"][0]["run_id"], "run-123")

            review_run = client.get("/api/review/runs/run-123")
            self.assertEqual(review_run.status_code, 200)
            self.assertEqual(review_run.json()["review_pack"]["book_title"], "Sample Book")
            self.assertEqual(review_run.json()["review_queue"][0]["section_context"], "")
            self.assertEqual(review_run.json()["review_queue"][0]["proposed_text"], "A strong new result.")

            applied = client.post(
                "/api/review/runs/run-123/apply",
                json={
                    "rows": [
                        {
                            "chapter_id": "ch1",
                            "chapter_title": "Intro",
                            "section_id": "1.1",
                            "proposed_subsection_id": "",
                            "title": "New Benchmark",
                            "source_summary": "https://example.com",
                            "score_summary": "final_score=0.9",
                            "review_decision": "approve",
                            "review_notes": "Looks good",
                        }
                    ],
                    "export_docx_enabled": False,
                    "export_pdf_enabled": False,
                },
            )
            self.assertEqual(applied.status_code, 200)
            self.assertEqual(applied.json()["status"], "applied")
            self.assertTrue((run_dir / "review" / "approved_book.md").exists())


if __name__ == "__main__":
    unittest.main()
