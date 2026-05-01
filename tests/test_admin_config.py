from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.config import AdminConfig, PipelineSettings, next_scheduled_run
from storage.admin_config_store import AdminConfigStore


class AdminConfigTests(unittest.TestCase):
    def test_store_roundtrip_and_scheduler_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "admin" / "admin_config.json"
            audit_log_path = Path(temp_dir) / "admin" / "admin_audit_log.jsonl"
            scheduler_state_path = Path(temp_dir) / "admin" / "scheduler_state.json"
            store = AdminConfigStore(str(config_path), str(audit_log_path), str(scheduler_state_path))

            config = store.update(
                {
                    "update_frequency": "daily",
                    "chapter_parallelism": 3,
                    "max_updates_per_chapter": 4,
                    "enabled_sources": ["openalex", "official", "semantic_scholar"],
                },
                actor="tester",
                reason="unit_test_update",
            )

            self.assertEqual(config.update_frequency, "daily")
            self.assertEqual(config.chapter_parallelism, 3)
            self.assertEqual(store.load().max_updates_per_chapter, 4)
            self.assertTrue(audit_log_path.exists())

            snapshot = store.scheduler_snapshot()
            self.assertEqual(snapshot["update_frequency"], "daily")
            self.assertIsNotNone(snapshot["next_run_utc"])
            self.assertFalse(snapshot["manual_only"])
            self.assertTrue(snapshot["due_now"])

            state = store.mark_run_completed(run_id="run-1")
            self.assertEqual(state["last_run_id"], "run-1")

            updated_snapshot = store.scheduler_snapshot()
            self.assertEqual(updated_snapshot["last_run_id"], "run-1")
            self.assertFalse(updated_snapshot["due_now"])

    def test_pipeline_settings_apply_admin_config(self) -> None:
        settings = PipelineSettings()
        admin = AdminConfig(
            update_frequency="monthly",
            chapter_parallelism=2,
            max_updates_per_chapter=2,
            max_total_updates_per_chapter=7,
            min_accept_score=0.81,
            min_relevance=0.77,
            min_credibility=0.73,
            min_significance=0.69,
            enabled_sources=["official"],
            render_pdf=False,
            render_docx=True,
            generate_review_pack=False,
        )

        settings.apply_admin_config(admin)
        self.assertEqual(settings.chapter_parallelism, 2)
        self.assertEqual(settings.max_updates_per_chapter, 2)
        self.assertEqual(settings.max_total_updates_per_chapter, 7)
        self.assertEqual(settings.min_accept_score, 0.81)
        self.assertEqual(settings.enabled_sources, ["official"])
        self.assertFalse(settings.render_pdf)
        self.assertFalse(settings.generate_review_pack)
        self.assertEqual(settings.enabled_sources, ["official"])

    def test_manual_schedule_has_no_next_run(self) -> None:
        self.assertIsNone(next_scheduled_run("manual"))


if __name__ == "__main__":
    unittest.main()
