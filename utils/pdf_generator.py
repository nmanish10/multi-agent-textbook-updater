from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.units import inch
from collections import defaultdict


def generate_pdf(book, updates, output_file="outputs/updated_book.pdf"):

    doc = SimpleDocTemplate(
        output_file,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )

    styles = getSampleStyleSheet()

    # -------------------------
    # CUSTOM STYLES
    # -------------------------
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Title'],
        spaceAfter=20
    )

    chapter_style = ParagraphStyle(
        'ChapterStyle',
        parent=styles['Heading1'],
        spaceBefore=20,
        spaceAfter=12
    )

    section_style = ParagraphStyle(
        'SectionStyle',
        parent=styles['Heading2'],
        spaceBefore=12,
        spaceAfter=8
    )

    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        alignment=TA_JUSTIFY,
        firstLineIndent=20,
        spaceAfter=10
    )

    content = []

    # -------------------------
    # BOOK TITLE
    # -------------------------
    content.append(Paragraph(book.book_title, title_style))

    for chapter in book.chapters:

        # -------------------------
        # CHAPTER TITLE
        # -------------------------
        title = chapter.title
        if not title.lower().startswith("chapter"):
            title = f"Chapter {chapter.chapter_id}: {title}"

        content.append(Paragraph(title, chapter_style))

        # -------------------------
        # GROUP UPDATES BY SECTION
        # -------------------------
        section_updates_map = defaultdict(list)

        for upd in updates:
            if upd.get("section_id", "").startswith(chapter.chapter_id):
                section_updates_map[upd["section_id"]].append(upd)

        # -------------------------
        # WRITE CONTENT + UPDATES
        # -------------------------
        for section in chapter.sections:

            content.append(
                Paragraph(f"{section.section_id} {section.title}", section_style)
            )

            content.append(Paragraph(section.content, body_style))

            # 🔥 INSERT UPDATES INSIDE SECTION
            section_updates = section_updates_map.get(section.section_id, [])

            for upd in section_updates:

                text_block = upd.get("text", "").strip()

                if not text_block:
                    continue

                # split into paragraphs properly
                parts = text_block.split("\n")

                for part in parts:
                    if part.strip():
                        content.append(Paragraph(part.strip(), body_style))

                content.append(Spacer(1, 10))

    # -------------------------
    # BUILD PDF
    # -------------------------
    doc.build(content)

    print(f"✅ PDF generated at {output_file}")