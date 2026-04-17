from __future__ import annotations

import os

from rendering.pdf_exporter import export_pdf


def generate_pdf(book, updates, output_file="outputs/updated_book.pdf"):
    markdown_file = "outputs/updated_book.md"
    if not os.path.exists(markdown_file):
        print(f"Cannot find {markdown_file} to generate PDF.")
        return

    ok, engine, manifest_path = export_pdf(markdown_file, output_file)
    if ok:
        print(f"PDF successfully generated via {engine} at {output_file}")
        print(f"Export manifest: {manifest_path}")
    else:
        print(f"PDF generation skipped: {engine}")
        print(f"Export manifest: {manifest_path}")
