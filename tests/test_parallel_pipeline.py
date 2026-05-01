from __future__ import annotations

import asyncio
import unittest

from app.run_pipeline import _run_chapter_jobs
from core.config import PipelineSettings
from core.run_context import create_run_artifacts
from storage.artifact_store import ArtifactStore


class ParallelPipelineTests(unittest.TestCase):
    def test_parallel_runner_preserves_chapter_order(self) -> None:
        class Chapter:
            def __init__(self, chapter_id: str):
                self.chapter_id = chapter_id
                self.title = f"Chapter {chapter_id}"
                self.content = ""

        async def fake_to_thread(func, *args, **kwargs):
            return {"index": args[0], "chapter_id": args[1].chapter_id, "final_updates": [], "accepted_updates": [], "retrieval_results": [], "analysis": None, "query_plan": None, "candidates_generated": 0, "accepted_candidates": 0, "chapters_processed": 0}

        settings = PipelineSettings(chapter_parallelism=2)
        artifacts = create_run_artifacts(settings)
        store = ArtifactStore("outputs/artifacts", "test-run-order")

        import app.run_pipeline as pipeline_module

        original_to_thread = pipeline_module.asyncio.to_thread
        pipeline_module.asyncio.to_thread = fake_to_thread
        try:
            results = asyncio.run(
                _run_chapter_jobs(
                    [Chapter("1"), Chapter("2"), Chapter("3")],
                    settings,
                    artifacts,
                    store,
                    update_store=None,
                )
            )
        finally:
            pipeline_module.asyncio.to_thread = original_to_thread

        self.assertEqual([item["chapter_id"] for item in results], ["1", "2", "3"])


if __name__ == "__main__":
    unittest.main()
