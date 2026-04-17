import re
from schemas.schemas import Book, Chapter, Section


# -------------------------
# CLEAN LINE
# -------------------------
def clean_line(line: str) -> str:
    line = re.sub(r"\s+", " ", line.strip())
    return line


# -------------------------
# STRONG TEXT CLEANING (🔥 FIXED)
# -------------------------
def clean_content(lines):
    cleaned = []

    for l in lines:
        l = l.strip()

        if len(l) < 5:
            continue

        # Remove pure junk
        if re.fullmatch(r"[^\w\s]+", l):
            continue

        # Remove heavy math garbage
        if any(x in l for x in ["Σ", "λ", "∑", "∈", "|"]):
            continue

        cleaned.append(l)

    text = " ".join(cleaned)

    # 🔥 FIX MERGED WORDS (Safer regex)
    # Only split if a lowercase letter is immediately followed by a capital letter
    # This prevents acronyms from being destroyed while fixing "bestProfessionals"
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)

    # Remove lingering hyphens from bad extraction
    text = text.replace("- ", "")

    # Normalize spacing
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# -------------------------
# VALID CHAPTER
# -------------------------
def is_valid_chapter(title):
    title = title.strip()

    # too short
    if len(title.split()) < 3:
        return False

    # too long
    if len(title) > 120:
        return False

    # ends like sentence
    if title.endswith("."):
        return False

    # math garbage
    if any(x in title for x in ["=", "Σ", "λ", "|", "∈", "p("]):
        return False

    # junk words
    bad_words = ["purchases", "patterns", "records", "dataset"]
    if title.lower() in bad_words:
        return False

    return True


# -------------------------
# VALID SECTION
# -------------------------
def is_valid_section_title(title):
    if len(title.split()) > 12:
        return False
    return True


# -------------------------
# EXTRACT SECTION ID
# -------------------------
def extract_section_id(title, chapter_id, fallback_index):
    match = re.match(r"(\d+(\.\d+)*)\s+(.*)", title)

    if match:
        return match.group(1), match.group(3).strip()

    return f"{chapter_id}.{fallback_index}", title


# -------------------------
# FINALIZE SECTION
# -------------------------
def finalize_section(current_section, section_content, sections, seen_ids):

    if not current_section:
        return

    content = clean_content(section_content)

    if not content or len(content) < 40:
        return

    if current_section["id"] in seen_ids:
        return

    seen_ids.add(current_section["id"])

    sections.append(
        Section(
            section_id=current_section["id"],
            title=current_section["title"],
            content=content
        )
    )


# -------------------------
# FINALIZE CHAPTER
# -------------------------
def finalize_chapter(current_chapter, chapter_content, sections, chapters, seen_titles):

    if not current_chapter:
        return

    title = current_chapter["title"].lower()

    # 🔥 DEDUPLICATION
    if title in seen_titles:
        return

    seen_titles.add(title)

    content = clean_content(chapter_content)

    # 🔥 STRONG FILTER
    if not content or len(content.split()) < 80:
        print("⚠️ Skipping weak/empty chapter")
        return

    if not sections:
        sections = [
            Section(
                section_id=f"{current_chapter['id']}.1",
                title="Overview",
                content=content
            )
        ]

    chapters.append(
        Chapter(
            chapter_id=current_chapter["id"],
            title=current_chapter["title"],
            content=content,
            sections=sections
        )
    )


# -------------------------
# MAIN PARSER
# -------------------------
def parse_markdown(file_path: str) -> Book:

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    chapters = []
    seen_titles = set()

    current_chapter = None
    current_section = None

    chapter_content = []
    section_content = []
    sections = []
    seen_section_ids = set()

    section_counter = 1

    for raw_line in lines:
        line = clean_line(raw_line)

        if not line:
            continue

        # -------------------------
        # CHAPTER
        # -------------------------
        if line.startswith("# "):

            title = line.replace("# ", "").strip()

            # 🔥 STRICT FILTER
            if not is_valid_chapter(title):
                continue

            finalize_section(current_section, section_content, sections, seen_section_ids)
            finalize_chapter(current_chapter, chapter_content, sections, chapters, seen_titles)

            chapter_id = str(len(chapters) + 1)

            current_chapter = {
                "id": chapter_id,
                "title": title
            }

            print(f"📘 PARSED Chapter: {title}")

            # reset
            chapter_content = []
            sections = []
            seen_section_ids = set()
            current_section = None
            section_content = []
            section_counter = 1

        # -------------------------
        # SECTION
        # -------------------------
        elif line.startswith("##"):

            if not current_chapter:
                continue

            finalize_section(current_section, section_content, sections, seen_section_ids)

            title = re.sub(r"^#+\s+", "", line).strip()

            if not is_valid_section_title(title):
                continue

            section_id, title = extract_section_id(
                title,
                current_chapter["id"],
                section_counter
            )

            section_counter += 1

            current_section = {
                "id": section_id,
                "title": title
            }

            section_content = []

        # -------------------------
        # CONTENT
        # -------------------------
        else:
            if current_chapter:
                chapter_content.append(line)

            if current_section:
                section_content.append(line)

    # -------------------------
    # FINAL FLUSH
    # -------------------------
    finalize_section(current_section, section_content, sections, seen_section_ids)
    finalize_chapter(current_chapter, chapter_content, sections, chapters, seen_titles)

    print(f"\n📊 Parsed Book: {len(chapters)} chapters\n")

    return Book(
        book_title="Markdown Book",
        chapters=chapters
    )