import re
from schemas.schemas import Book, Chapter, Section


def parse_markdown(file_path: str) -> Book:
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    chapters = []
    current_chapter = None
    current_section = None

    chapter_content = []
    section_content = []
    sections = []

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            continue

        # -------------------------
        # CHAPTER
        # -------------------------
        if line.startswith("# "):
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

            chapter_id = str(len(chapters) + 1)

            current_chapter = {
                "id": chapter_id,
                "title": line.replace("# ", "")
            }

            chapter_content = []
            sections = []
            current_section = None
            section_content = []

        # -------------------------
        # SECTION
        # -------------------------
        elif line.startswith("## "):
            if current_section:
                sections.append(
                    Section(
                        section_id=current_section["id"],
                        title=current_section["title"],
                        content="\n".join(section_content)
                    )
                )

            title = line.replace("## ", "")

            # try extracting real section number
            match = re.match(r"(\d+\.\d+)\s+(.*)", title)

            if match:
                section_id = match.group(1)
                title = match.group(2)
            else:
                section_id = f"{current_chapter['id']}.{len(sections)+1}"

            current_section = {
                "id": section_id,
                "title": title
            }

            section_content = []

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

    return Book(book_title="Markdown Book", chapters=chapters)