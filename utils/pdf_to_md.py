import pdfplumber
import re
import os
from collections import Counter


# -------------------------
# CLEAN LINE
# -------------------------
def clean_line(text):
    text = text.replace("\r", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# -------------------------
# DETECT REPEATING HEADERS
# -------------------------
def detect_repeating_lines(all_lines):
    counts = Counter(all_lines)
    return {line for line, c in counts.items() if c > 5 and len(line) < 80}


# -------------------------
# NOISE FILTER
# -------------------------
def is_noise(line, repeating):
    if not line or len(line) < 3:
        return True

    if line in repeating:
        return True

    if re.fullmatch(r"\d+", line):
        return True

    if re.fullmatch(r"[^\w\s]+", line):
        return True

    return False


# -------------------------
# VALID CHAPTER
# -------------------------
def is_valid_chapter(line):
    if len(line.split()) < 3:
        return False

    if len(line) > 120:
        return False

    if any(x in line for x in ["=", "Σ", "λ", "|", "∈"]):
        return False

    if re.search(r"\d+\.\d+", line):
        return False  # avoid inline sections

    return True


# -------------------------
# DETECT CHAPTER
# -------------------------
def extract_chapter(line):
    match = re.match(r"chapter\s+\d+[:\s].*", line, re.IGNORECASE)
    if match and is_valid_chapter(line):
        return line.strip()
    return None


# -------------------------
# DETECT SECTION
# -------------------------
def extract_sections(line):
    pattern = r"(\d+\.\d+\s+[A-Za-z][^0-9]{0,80})"
    return re.findall(pattern, line)


# -------------------------
# ALL CAPS HEADING
# -------------------------
def is_all_caps_heading(line):
    if len(line.split()) > 8:
        return False
    return line.isupper() and len(line) > 5


# -------------------------
# TOC DETECTION
# -------------------------
def is_toc_page(lines):
    count = sum(1 for l in lines if re.match(r"\d+\.\d+", l))
    return count > 5


# -------------------------
# SAFE PARAGRAPH MERGE (🔥 FIXED)
# -------------------------
def merge_lines(lines):
    merged = []
    buffer = ""

    for line in lines:
        if not buffer:
            buffer = line
            continue

        # 🔥 FIX 1: Handle hyphenated line breaks (e.g., "pro-\nfessional" -> "professional")
        if buffer.endswith("-"):
            buffer = buffer[:-1] + line
            continue

        # 🔥 FIX 2: Better sentence boundary detection
        if (
            buffer.endswith(".")
            or buffer.endswith(":")
            or buffer.endswith("?")
            or buffer.endswith("!")
            or line.startswith("Chapter")
            or re.match(r"\d+\.\d+", line)
        ):
            merged.append(buffer)
            buffer = line
        else:
            buffer += " " + line

    if buffer:
        merged.append(buffer)

    return merged


# -------------------------
# DEDUPLICATE
# -------------------------
def deduplicate(lines):
    seen = set()
    result = []

    for l in lines:
        key = re.sub(r"\W+", "", l.lower())

        if len(key) < 20:
            result.append(l)
            continue

        if key in seen:
            continue

        seen.add(key)
        result.append(l)

    return result


# -------------------------
# MAIN CONVERTER
# -------------------------
def convert_pdf_to_md(pdf_path, output_path="outputs/converted.md"):

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    all_lines = []
    pages = []

    # -------------------------
    # EXTRACT TEXT
    # -------------------------
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Drop top 8% and bottom 8% to filter out noisy headers/footers
            bbox = (0, page.height * 0.08, page.width, page.height * 0.92)
            try:
                cropped = page.crop(bbox)
                text = cropped.extract_text(layout=True)
            except ValueError:
                # Fallback if crop fails on weird sized pages
                text = page.extract_text(layout=True)
                
            if not text:
                continue

            lines = []
            for line in text.split("\n"):
                line = clean_line(line)
                if line:
                    lines.append(line)
                    all_lines.append(line)

            pages.append(lines)

    # -------------------------
    # DETECT HEADERS
    # -------------------------
    repeating = detect_repeating_lines(all_lines)

    md_lines = []
    seen_chapters = set()
    found_chapter = False

    # -------------------------
    # PROCESS PAGES
    # -------------------------
    for page in pages:

        if is_toc_page(page):
            print("⚠️ Skipping TOC page")
            continue

        cleaned = [l for l in page if not is_noise(l, repeating)]

        for line in cleaned:

            # -------------------------
            # CHAPTER
            # -------------------------
            chapter = extract_chapter(line)
            if chapter and chapter not in seen_chapters:
                seen_chapters.add(chapter)
                found_chapter = True
                print(f"📘 VALID Chapter: {chapter}")
                md_lines.append(f"\n# {chapter}\n")
                continue

            # -------------------------
            # ALL CAPS → SECTION
            # -------------------------
            if is_all_caps_heading(line):
                md_lines.append(f"\n## {line.title()}\n")
                continue

            # -------------------------
            # SECTION
            # -------------------------
            sections = extract_sections(line)
            if sections:
                for sec in sections:
                    md_lines.append(f"\n## {sec.strip()}\n")
                    line = line.replace(sec, "")

            # -------------------------
            # NORMAL TEXT
            # -------------------------
            if line.strip():
                md_lines.append(line.strip())

    # -------------------------
    # MERGE AFTER STRUCTURE
    # -------------------------
    md_lines = merge_lines(md_lines)

    # -------------------------
    # FALLBACK
    # -------------------------
    if not found_chapter:
        print("⚠️ No chapters detected → fallback mode")

        new_md = []
        for line in md_lines:
            if re.match(r"^\d+\s+[A-Za-z]", line):
                new_md.append(f"\n# {line}\n")
            else:
                new_md.append(line)

        md_lines = new_md

    # -------------------------
    # FINAL CLEAN
    # -------------------------
    md_lines = deduplicate(md_lines)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"✅ Clean PDF → Markdown: {output_path}")

    return output_path