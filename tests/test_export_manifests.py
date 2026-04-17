from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rendering.export_utils import build_export_manifest, write_export_manifest


class ExportManifestTests(unittest.TestCase):
    def test_shared_manifest_contains_expected_fields(self) -> None:
        manifest = build_export_manifest(
            format_name="pdf",
            source_markdown="outputs/updated_book.md",
            output_file="outputs/updated_book.pdf",
            engine="xhtml2pdf",
            success=True,
            note="",
        )
        self.assertEqual(manifest["format"], "pdf")
        self.assertEqual(manifest["engine"], "xhtml2pdf")
        self.assertTrue(manifest["success"])

    def test_shared_manifest_writer_uses_format_specific_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = str(Path(temp_dir) / "updated_book.docx")
            manifest = build_export_manifest(
                format_name="docx",
                source_markdown=None,
                output_file=output_file,
                engine="python-docx",
                success=True,
            )
            manifest_path = write_export_manifest(output_file, manifest)
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(str(manifest_path).endswith(".docx.export.json"))
            self.assertEqual(loaded["format"], "docx")


if __name__ == "__main__":
    unittest.main()
