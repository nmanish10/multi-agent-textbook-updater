from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Tuple

from bs4 import BeautifulSoup

from rendering.export_utils import build_export_manifest, write_export_manifest


TEXTBOOK_PRINT_CSS = """
@page {
  size: A4;
  margin: 26mm 18mm 24mm 18mm;
  @frame header_frame {
    -pdf-frame-content: header_content;
    left: 18mm;
    width: 174mm;
    top: 8mm;
    height: 10mm;
  }
  @frame footer_frame {
    -pdf-frame-content: footer_content;
    left: 18mm;
    width: 174mm;
    top: 279mm;
    height: 10mm;
  }
}
body {
  font-family: Georgia, serif;
  line-height: 1.68;
  color: #222;
  font-size: 11pt;
}
#header_content {
  color: #556b7a;
  font-size: 9pt;
  border-bottom: 1px solid #d7e0e6;
  padding-bottom: 4px;
}
#footer_content {
  color: #556b7a;
  font-size: 9pt;
  border-top: 1px solid #d7e0e6;
  padding-top: 4px;
  text-align: right;
}
.book-shell {
  counter-reset: figure table;
}
.title-page {
  text-align: center;
  padding: 6rem 2rem 8rem;
  page-break-after: always;
}
.title-page h1 {
  font-family: 'Aptos Display', 'Segoe UI', sans-serif;
  color: #17324d;
  font-size: 28pt;
  margin-bottom: 1.25rem;
  border: none;
  page-break-before: auto;
}
.title-page p {
  text-align: center;
  color: #556b7a;
  font-style: italic;
}
h1, h2, h3 {
  font-family: 'Aptos Display', 'Segoe UI', sans-serif;
}
h1 {
  color: #17324d;
  border-bottom: 2px solid #17324d;
  padding-bottom: 0.4rem;
  margin-top: 2.8rem;
  page-break-before: always;
}
h1:first-of-type {
  page-break-before: auto;
  margin-top: 0;
}
h2 {
  color: #1c5d7f;
  margin-top: 2rem;
}
h3 {
  color: #22485f;
  margin-top: 1.5rem;
}
p {
  margin: 0 0 0.9rem 0;
  text-align: justify;
}
ul {
  margin-left: 1.25rem;
  margin-bottom: 1rem;
}
li {
  margin-bottom: 0.2rem;
}
em {
  color: #3f5d73;
}
hr {
  border: none;
  border-top: 1px solid #c7d3dc;
  margin: 1.6rem 0;
}
img {
  display: block;
  margin: 1rem auto 0.4rem;
  max-width: 90%;
  height: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  margin: 1rem 0 1.25rem;
  font-size: 10pt;
}
th, td {
  border: 1px solid #c7d3dc;
  padding: 0.45rem 0.55rem;
  vertical-align: top;
}
th {
  background: #eef4f7;
  color: #17324d;
}
blockquote {
  border-left: 4px solid #7da4ba;
  margin: 1rem 0;
  padding: 0.6rem 1rem;
  background: #f6fafc;
  color: #365062;
}
.toc-section {
  background: #f9fbfc;
  border: 1px solid #dce7ee;
  padding: 1rem 1.15rem;
  margin: 1rem 0 1.4rem;
}
.toc-section ul {
  list-style: none;
  margin-left: 0;
  padding-left: 0;
}
.toc-section li {
  margin-bottom: 0.35rem;
}
.recent-advances {
  border: 1px solid #d9e7f0;
  background: #f4f9fc;
  padding: 0.8rem 1rem;
}
.sources-section ul {
  margin-top: 0.2rem;
}
"""


def _extract_book_title(markdown_text: str, markdown_path: Path) -> str:
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return markdown_path.stem.replace("_", " ").title()


def _decorate_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    first_h2 = soup.find("h2")
    if first_h2 and "table of contents" in first_h2.get_text(" ", strip=True).lower():
        current = first_h2
        toc_nodes = [current]
        sibling = current.find_next_sibling()
        while sibling and sibling.name in {"ul", "ol"}:
            toc_nodes.append(sibling)
            sibling = sibling.find_next_sibling()
        wrapper = soup.new_tag("section", attrs={"class": "toc-section"})
        first_h2.insert_before(wrapper)
        for node in toc_nodes:
            wrapper.append(node.extract())

    for h2 in soup.find_all("h2"):
        heading = h2.get_text(" ", strip=True).lower()
        if heading == "recent advances":
            wrapper = soup.new_tag("section", attrs={"class": "recent-advances"})
            h2.insert_before(wrapper)
            wrapper.append(h2.extract())
            sibling = wrapper.find_next_sibling()
            while sibling and sibling.name not in {"h1", "h2"}:
                next_sibling = sibling.find_next_sibling()
                wrapper.append(sibling.extract())
                sibling = next_sibling

    for strong in soup.find_all("strong"):
        if strong.get_text(" ", strip=True).lower() == "sources":
            parent = strong.parent
            if parent:
                parent["class"] = (parent.get("class", []) or []) + ["sources-section"]

    return str(soup)


def build_print_ready_html(markdown_text: str, markdown_path: str = "book.md") -> str:
    import markdown

    md_path = Path(markdown_path)
    book_title = _extract_book_title(markdown_text, md_path)
    html = markdown.markdown(markdown_text, extensions=["extra", "sane_lists", "tables"])
    content = _decorate_html(html)

    return f"""<html>
<head>
  <meta charset="utf-8">
  <title>{book_title}</title>
  <style>{TEXTBOOK_PRINT_CSS}</style>
</head>
<body>
  <div id="header_content">{book_title}</div>
  <div id="footer_content">Page <pdf:pagenumber> of <pdf:pagecount></div>
  <div class="book-shell">
    <section class="title-page">
      <h1>{book_title}</h1>
      <p>Updated textbook export generated by the Multi-Agent Textbook Update System.</p>
    </section>
    {content}
  </div>
</body>
</html>"""


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

    full_html = build_print_ready_html(md_path.read_text(encoding="utf-8"), str(md_path))
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
