from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from storage.run_history_store import RunHistoryStore, file_fingerprint


class RunHistoryStoreTests(unittest.TestCase):
    def test_file_fingerprint_changes_with_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            sample = Path(tmp_dir) / "sample.txt"
            sample.write_text("alpha", encoding="utf-8")
            first = file_fingerprint(str(sample))
            sample.write_text("beta", encoding="utf-8")
            second = file_fingerprint(str(sample))

        self.assertTrue(first)
        self.assertTrue(second)
        self.assertNotEqual(first, second)

    def test_run_history_records_incremental_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            history_path = Path(tmp_dir) / "run_history.json"
            store = RunHistoryStore(str(history_path))

            first = store.append_run(
                {
                    "run_id": "run-1",
                    "book_key": "book-1",
                    "input_fingerprint": "aaa",
                    "stats": {"final_updates": 1, "accepted_candidates": 2},
                    "admin_config": {"update_frequency": "weekly"},
                }
            )
            second = store.append_run(
                {
                    "run_id": "run-2",
                    "book_key": "book-1",
                    "input_fingerprint": "bbb",
                    "stats": {"final_updates": 3, "accepted_candidates": 4},
                    "admin_config": {"update_frequency": "daily"},
                }
            )

        self.assertEqual(first["version_delta"]["kind"], "initial_run")
        self.assertEqual(second["version_delta"]["kind"], "incremental_run")
        self.assertEqual(second["version_delta"]["previous_run_id"], "run-1")
        self.assertTrue(second["version_delta"]["input_changed"])
        self.assertTrue(second["version_delta"]["config_changed"])
        self.assertEqual(second["version_delta"]["final_updates_delta"], 2)
        self.assertEqual(second["version_delta"]["accepted_candidates_delta"], 2)


if __name__ == "__main__":
    unittest.main()
