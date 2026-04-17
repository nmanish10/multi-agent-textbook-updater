from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rendering.export_utils import build_export_manifest, write_export_manifest
from utils.llm import get_prompt_traces, record_prompt_trace, reset_prompt_traces


class OperationalTracingTests(unittest.TestCase):
    def test_prompt_trace_registry_records_entries(self) -> None:
        reset_prompt_traces()
        record_prompt_trace(
            prompt_name="chapter_analysis",
            prompt_version="1.0",
            structured=True,
            temperature=0.1,
            used_system_prompt=True,
            cache_hit=False,
        )
        traces = get_prompt_traces()
        self.assertEqual(len(traces), 1)
        self.assertEqual(traces[0]["prompt_name"], "chapter_analysis")
        self.assertEqual(traces[0]["prompt_version"], "1.0")

    def test_export_manifest_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_pdf = str(Path(temp_dir) / "book.pdf")
            manifest = build_export_manifest(
                format_name="pdf",
                source_markdown="book.md",
                output_file=output_pdf,
                engine="xhtml2pdf",
                success=True,
                note="",
            )
            manifest_path = write_export_manifest(output_pdf, manifest)
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["engine"], "xhtml2pdf")
            self.assertTrue(loaded["success"])


if __name__ == "__main__":
    unittest.main()
