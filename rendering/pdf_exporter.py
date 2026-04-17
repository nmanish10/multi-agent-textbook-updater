from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Tuple

from rendering.export_utils import build_export_manifest, write_export_manifest


TEXTBOOK_HTML_TEMPLATE = """<html><head><meta charset="utf-8"><style>
@page {{ size: A4; margin: 24mm 18mm; }}
body {{ font-family: Georgia, serif; line-height: 1.68; color: #222; font-size: 11pt; }}
h1, h2, h3 {{ font-family: 'Segoe UI', Arial, sans-serif; }}
h1 {{ color: #17324d; border-bottom: 2px solid #17324d; padding-bottom: 0.4rem; margin-top: 2.8rem; page-break-before: always; }}
h1:first-of-type {{ page-break-before: auto; margin-top: 0; }}
h2 {{ color: #1c5d7f; margin-top: 2rem; }}
h3 {{ color: #22485f; margin-top: 1.5rem; }}
p {{ margin: 0 0 0.9rem 0; text-align: justify; }}
ul {{ margin-left: 1.25rem; margin-bottom: 1rem; }}
li {{ margin-bottom: 0.2rem; }}
em {{ color: #3f5d73; }}
hr {{ border: none; border-top: 1px solid #c7d3dc; margin: 1.6rem 0; }}
img {{ display: block; margin: 1rem auto; max-width: 90%; height: auto; }}
</style></head><body>{content}</body></html>"""
def export_pdf(markdown_file: str, output_pdf: str, pandoc_command: str = "pandoc") -> Tuple[bool, str, Path]:
    md_path = Path(markdown_file)
    pdf_path = Path(output_pdf)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    pandoc = shutil.which(pandoc_command)
    if pandoc:
        try:
            subprocess.run(
                [pandoc, str(md_path), "-o", str(pdf_path), "--toc"],
                check=True,
                capture_output=True,
                text=True,
            )
            manifest = build_export_manifest(
                format_name="pdf",
                source_markdown=str(md_path),
                output_file=str(pdf_path),
                engine="pandoc",
                success=True,
            )
            return True, "pandoc", write_export_manifest(output_pdf, manifest)
        except subprocess.CalledProcessError as exc:
            note = exc.stderr.strip() or exc.stdout.strip()
            manifest = build_export_manifest(
                format_name="pdf",
                source_markdown=str(md_path),
                output_file=str(pdf_path),
                engine="pandoc",
                success=False,
                note=note,
            )
            return False, f"pandoc failed: {note}", write_export_manifest(output_pdf, manifest)

    try:
        import markdown
        from xhtml2pdf import pisa
    except ImportError:
        note = "No PDF exporter available. Install pandoc or xhtml2pdf+markdown."
        manifest = build_export_manifest(
            format_name="pdf",
            source_markdown=str(md_path),
            output_file=str(pdf_path),
            engine="none",
            success=False,
            note=note,
        )
        return False, note, write_export_manifest(output_pdf, manifest)

    html = markdown.markdown(md_path.read_text(encoding="utf-8"), extensions=["extra", "sane_lists"])
    full_html = TEXTBOOK_HTML_TEMPLATE.format(content=html)
    with pdf_path.open("w+b") as handle:
        status = pisa.CreatePDF(full_html, dest=handle)
    if status.err:
        note = "xhtml2pdf encountered rendering errors."
        manifest = build_export_manifest(
            format_name="pdf",
            source_markdown=str(md_path),
            output_file=str(pdf_path),
            engine="xhtml2pdf",
            success=False,
            note=note,
        )
        return False, note, write_export_manifest(output_pdf, manifest)
    manifest = build_export_manifest(
        format_name="pdf",
        source_markdown=str(md_path),
        output_file=str(pdf_path),
        engine="xhtml2pdf",
        success=True,
    )
    return True, "xhtml2pdf", write_export_manifest(output_pdf, manifest)
