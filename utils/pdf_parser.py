import pdfplumber
import re
from schemas.schemas import Book, Chapter, Section


def clean_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"\s+", " ", line)
    return line


def is_valid_chapter(line: str) -> bool:
    match = re.search(r"chapter\s+(\d+)", line, re.IGNORECASE)
    if not match:
        return False

    words_before = line[:match.start()].strip().split()
    if len(words_before) > 1:
        return False

    if not ("/" in line or ":" in line):
        return False

    if len(line) > 80:
        return False

    return True


def is_valid_section(line: str) -> bool:
    if not re.match(r"^\d+\.\d+", line):
        return False

    if len(line) > 80:
        return False

    lower = line.lower()

    if any(q in lower for q in [
        "what", "list", "describe", "explain",
        "define", "how", "why"
    ]):
        return False

    if any(x in lower for x in [
        "review questions",
        "problems",
        "recommended reading",
        "key terms"
    ]):
        return False

    if re.search(r"\d{3}$", line):
        return False

    return True


def extract_section(line: str):
    match = re.match(r"^(\d+\.\d+)\s*(.*)", line)

    if not match:
        return None, None

    section_id = match.group(1)
    title = match.group(2).strip()

    return section_id, title


def parse_pdf(file_path: str) -> Book:
    text = ""
    seen_chapters = set()

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    lines = text.split("\n")

    chapters = []
    current_chapter = None
    current_section = None

    chapter_content = []
    section_content = []
    sections = []

    seen_sections = set()

    for raw_line in lines:
        line = clean_line(raw_line)

        if not line or len(line) < 3:
            continue

        # -------------------------
        # CHAPTER
        # -------------------------
        if is_valid_chapter(line):

            match = re.search(r"chapter\s+(\d+)", line, re.IGNORECASE)
            if not match:
                continue

            chapter_num = match.group(1)

            if chapter_num in seen_chapters:
                continue

            seen_chapters.add(chapter_num)

            if current_chapter:
                if current_section:
                    sections.append(
                        Section(
                            section_id=current_section["id"],
                            title=current_section["title"],
                            content="\n".join(section_content)
                        )
                    )

                chapters.append(
                    Chapter(
                        chapter_id=current_chapter["id"],
                        title=current_chapter["title"],
                        content="\n".join(chapter_content),
                        sections=sections
                    )
                )

            title = re.sub(r"^\d+\s+", "", line)
            title = re.sub(r"\s+", " ", title).strip()

            current_chapter = {
                "id": chapter_num,
                "title": title
            }

            chapter_content = []
            sections = []
            current_section = None
            section_content = []
            seen_sections.clear()

        # -------------------------
        # SECTION
        # -------------------------
        elif is_valid_section(line):

            section_id, title = extract_section(line)

            if not section_id or section_id in seen_sections:
                continue

            seen_sections.add(section_id)

            if current_section:
                sections.append(
                    Section(
                        section_id=current_section["id"],
                        title=current_section["title"],
                        content="\n".join(section_content)
                    )
                )

            current_section = {
                "id": section_id,
                "title": title
            }

            section_content = []

        # -------------------------
        # CONTENT
        # -------------------------
        else:
            chapter_content.append(line)

            if current_section:
                section_content.append(line)

    if current_chapter:
        if current_section:
            sections.append(
                Section(
                    section_id=current_section["id"],
                    title=current_section["title"],
                    content="\n".join(section_content)
                )
            )

        chapters.append(
            Chapter(
                chapter_id=current_chapter["id"],
                title=current_chapter["title"],
                content="\n".join(chapter_content),
                sections=sections
            )
        )

    return Book(book_title="PDF Book", chapters=chapters)