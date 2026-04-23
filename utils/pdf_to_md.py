import os
import re
from collections import Counter
from statistics import median

import pdfplumber


# -------------------------
# CLEAN LINE
# -------------------------
def clean_line(text):
    text = text.replace("\r", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# -------------------------
# DETECT REPEATING HEADERS/FOOTERS
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


# =========================================================
# FONT-AWARE HEADING DETECTION
# =========================================================

def _extract_line_font_info(page):
    """Extract lines with their dominant font size from pdfplumber character data.

    Returns list of (text, font_size, is_bold) tuples for each line.
    pdfplumber gives us character-level data including fontname and size,
    which is far more reliable than regex for heading detection.
    """
    try:
        chars = page.chars
    except Exception:
        return []

    if not chars:
        return []

    # Group characters by approximate y-position (same line)
    lines_by_y = {}
    for char in chars:
        # Round y to nearest 2pt to group characters on the same line
        y_key = round(char.get("top", 0) / 2) * 2
        if y_key not in lines_by_y:
            lines_by_y[y_key] = []
        lines_by_y[y_key].append(char)

    result = []
    for y_key in sorted(lines_by_y.keys()):
        line_chars = sorted(lines_by_y[y_key], key=lambda c: c.get("x0", 0))
        if not line_chars:
            continue

        text = "".join(c.get("text", "") for c in line_chars).strip()
        text = clean_line(text)
        if not text:
            continue

        # Dominant font size = most common size among characters in this line
        sizes = [c.get("size", 0) for c in line_chars if c.get("text", "").strip()]
        if not sizes:
            continue
        font_size = max(set(sizes), key=sizes.count)

        # Detect bold from font name
        fontnames = [c.get("fontname", "") for c in line_chars if c.get("text", "").strip()]
        dominant_font = max(set(fontnames), key=fontnames.count) if fontnames else ""
        is_bold = any(marker in dominant_font.lower() for marker in ["bold", "bd", "heavy", "black"])

        result.append((text, font_size, is_bold))

    return result


def _compute_body_font_size(all_line_info):
    """Determine the body text font size (most common size across all pages)."""
    all_sizes = [size for _, size, _ in all_line_info if size > 0]
    if not all_sizes:
        return 12.0
    # Body text is the most frequently occurring font size
    return max(set(all_sizes), key=all_sizes.count)


def classify_heading_level(text, font_size, is_bold, body_size):
    """Classify a line as chapter heading, section heading, or body text
    based on font metrics relative to body text size.

    Returns: 'chapter', 'section', or None (body text)
    """
    if font_size <= 0 or body_size <= 0:
        return None

    ratio = font_size / body_size

    # Chapter headings: significantly larger than body text (typically 1.5x+)
    if ratio >= 1.45:
        return "chapter"

    # Section headings: moderately larger or same-size bold (typically 1.15x+)
    if ratio >= 1.15:
        return "section"

    # Bold text at body size with short length — likely a sub-heading
    if is_bold and ratio >= 0.95 and len(text.split()) <= 10:
        return "section"

    return None


# =========================================================
# EXPANDED CHAPTER/SECTION REGEX PATTERNS
# =========================================================

CHAPTER_PATTERNS = [
    # "Chapter 1: Introduction" / "Chapter 1 Introduction"
    re.compile(r"^chapter\s+\d+\s*[:.\-–—]?\s+.+", re.IGNORECASE),
    # "Chapter I: Introduction" (Roman numerals)
    re.compile(r"^chapter\s+[IVXLCDM]+\s*[:.\-–—]?\s+.+", re.IGNORECASE),
    # "CHAPTER 1 INTRODUCTION" (all caps)
    re.compile(r"^CHAPTER\s+\d+\s*[:.\-–—]?\s*.+"),
    # "Part I: Foundations" / "Part 1: Foundations"
    re.compile(r"^part\s+(?:\d+|[IVXLCDM]+)\s*[:.\-–—]?\s+.+", re.IGNORECASE),
]

SECTION_PATTERNS = [
    # "1.1 Introduction" / "1.1. Introduction"
    re.compile(r"^(\d+\.\d+\.?\s+[A-Za-z][^\d]{0,80})"),
    # "1.1.1 Sub-topic"
    re.compile(r"^(\d+\.\d+\.\d+\.?\s+[A-Za-z][^\d]{0,80})"),
]


def is_valid_heading_text(line):
    """Validate that a heading candidate is actually a heading, not garbage."""
    if len(line.split()) < 2 or len(line) > 150:
        return False
    # Reject math/formula lines
    if any(x in line for x in ["=", "Σ", "λ", "|", "∈", "→", "∀", "∃"]):
        return False
    # Reject lines that look like sentences (end with period followed by more text)
    if line.endswith(".") and len(line.split()) > 12:
        return False
    return True


def match_chapter_pattern(line):
    """Try to match a line against known chapter patterns."""
    for pattern in CHAPTER_PATTERNS:
        if pattern.match(line):
            return True
    return False


def extract_sections_from_line(line):
    """Extract section patterns from a line."""
    for pattern in SECTION_PATTERNS:
        matches = pattern.findall(line)
        if matches:
            return matches
    return []


# =========================================================
# TOC EXTRACTION
# =========================================================

def _is_toc_line(line):
    """Detect TOC-style lines like 'Chapter 1: Intro ........... 5'"""
    return bool(re.search(r"\.{3,}\s*\d+\s*$", line) or
                re.search(r"\s{3,}\d+\s*$", line))


def is_toc_page(lines):
    """Detect if a page is a Table of Contents page."""
    toc_score = sum(1 for l in lines if _is_toc_line(l))
    section_score = sum(1 for l in lines if re.match(r"\d+\.\d+", l))
    return toc_score >= 3 or section_score > 5


def extract_toc_structure(pages):
    """Extract chapter/section structure from TOC pages.

    Returns a list of {'level': 'chapter'|'section', 'title': str} entries
    that can guide heading detection in the body text.
    """
    toc_entries = []
    for page_lines in pages:
        if not is_toc_page(page_lines):
            continue

        for line in page_lines:
            # Remove page numbers and dot leaders
            cleaned = re.sub(r"\.{2,}\s*\d+\s*$", "", line).strip()
            cleaned = re.sub(r"\s{3,}\d+\s*$", "", cleaned).strip()

            if not cleaned:
                continue

            if match_chapter_pattern(cleaned):
                toc_entries.append({"level": "chapter", "title": cleaned})
            elif re.match(r"\d+\.\d+", cleaned):
                toc_entries.append({"level": "section", "title": cleaned})

    return toc_entries


# =========================================================
# ALL CAPS HEADING
# =========================================================
def is_all_caps_heading(line):
    if len(line.split()) > 8:
        return False
    return line.isupper() and len(line) > 5


# =========================================================
# SAFE PARAGRAPH MERGE
# =========================================================
def merge_lines(lines):
    merged = []
    buffer = ""

    for line in lines:
        if not buffer:
            buffer = line
            continue

        # Handle hyphenated line breaks
        if buffer.endswith("-"):
            buffer = buffer[:-1] + line
            continue

        # Sentence boundary detection
        if (
            buffer.endswith(".")
            or buffer.endswith(":")
            or buffer.endswith("?")
            or buffer.endswith("!")
            or line.startswith("#")  # Markdown headings always start new line
            or re.match(r"\d+\.\d+", line)
            or match_chapter_pattern(line)
        ):
            merged.append(buffer)
            buffer = line
        else:
            buffer += " " + line

    if buffer:
        merged.append(buffer)

    return merged


# =========================================================
# DEDUPLICATE
# =========================================================
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


# =========================================================
# MAIN CONVERTER — FONT-AWARE + REGEX HYBRID
# =========================================================
def convert_pdf_to_md(pdf_path, output_path="outputs/converted.md"):

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    all_lines = []
    all_line_info = []  # (text, font_size, is_bold) from ALL pages
    pages_raw = []      # raw text lines per page
    pages_font = []     # font-annotated lines per page

    # =========================================================
    # PASS 1: Extract text with font metadata
    # =========================================================
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Drop top 8% and bottom 8% to filter out noisy headers/footers
            bbox = (0, page.height * 0.08, page.width, page.height * 0.92)
            try:
                cropped = page.crop(bbox)
            except ValueError:
                cropped = page

            # Get font-annotated lines
            font_lines = _extract_line_font_info(cropped)
            pages_font.append(font_lines)
            all_line_info.extend(font_lines)

            # Also get plain text for fallback/noise detection
            try:
                text = cropped.extract_text(layout=True) or ""
            except Exception:
                text = page.extract_text(layout=True) or ""

            raw_lines = []
            for line in text.split("\n"):
                line = clean_line(line)
                if line:
                    raw_lines.append(line)
                    all_lines.append(line)
            pages_raw.append(raw_lines)

    # =========================================================
    # COMPUTE BODY FONT SIZE
    # =========================================================
    body_size = _compute_body_font_size(all_line_info)
    print(f"📏 Detected body font size: {body_size:.1f}pt")

    # =========================================================
    # DETECT REPEATING HEADERS/FOOTERS
    # =========================================================
    repeating = detect_repeating_lines(all_lines)

    # =========================================================
    # EXTRACT TOC STRUCTURE (optional guide)
    # =========================================================
    toc_entries = extract_toc_structure(pages_raw)
    toc_chapter_titles = {
        entry["title"].lower().strip()
        for entry in toc_entries
        if entry["level"] == "chapter"
    }
    if toc_entries:
        print(f"📑 Extracted {len(toc_entries)} TOC entries ({len(toc_chapter_titles)} chapters)")

    # =========================================================
    # PASS 2: Build Markdown with font-aware heading detection
    # =========================================================
    md_lines = []
    seen_chapters = set()
    found_chapter = False

    for page_idx, (raw_lines, font_lines) in enumerate(zip(pages_raw, pages_font)):

        # Skip TOC pages
        if is_toc_page(raw_lines):
            print(f"⚠️ Skipping TOC page {page_idx + 1}")
            continue

        # Build a font lookup: text -> (font_size, is_bold)
        font_lookup = {}
        for text, size, bold in font_lines:
            font_lookup[text] = (size, bold)

        cleaned = [l for l in raw_lines if not is_noise(l, repeating)]

        for line in cleaned:

            font_size, is_bold = font_lookup.get(line, (body_size, False))
            heading_level = classify_heading_level(line, font_size, is_bold, body_size)

            # =========================================================
            # CHAPTER DETECTION (font-first, regex-fallback)
            # =========================================================
            is_chapter = False

            # Method 1: Font says it's a chapter-level heading
            if heading_level == "chapter" and is_valid_heading_text(line):
                is_chapter = True

            # Method 2: Regex pattern match
            if not is_chapter and match_chapter_pattern(line) and is_valid_heading_text(line):
                is_chapter = True

            # Method 3: TOC cross-reference — if this text appeared in TOC as a chapter
            if not is_chapter and toc_chapter_titles and line.lower().strip() in toc_chapter_titles:
                is_chapter = True

            if is_chapter and line not in seen_chapters:
                seen_chapters.add(line)
                found_chapter = True
                print(f"📘 VALID Chapter: {line}")
                md_lines.append(f"\n# {line}\n")
                continue

            # =========================================================
            # SECTION DETECTION (font-first, regex-fallback)
            # =========================================================
            is_section = False
            section_text = line

            # Method 1: Font says it's a section-level heading
            if heading_level == "section" and is_valid_heading_text(line):
                is_section = True

            # Method 2: ALL CAPS heading
            if not is_section and is_all_caps_heading(line):
                is_section = True
                section_text = line.title()

            # Method 3: Regex pattern match (e.g., "1.2 Title")
            if not is_section:
                section_matches = extract_sections_from_line(line)
                if section_matches:
                    for sec in section_matches:
                        md_lines.append(f"\n## {sec.strip()}\n")
                        line = line.replace(sec, "").strip()
                    if line.strip():
                        md_lines.append(line.strip())
                    continue

            if is_section:
                md_lines.append(f"\n## {section_text}\n")
                continue

            # =========================================================
            # NORMAL TEXT
            # =========================================================
            if line.strip():
                md_lines.append(line.strip())

    # =========================================================
    # MERGE AFTER STRUCTURE
    # =========================================================
    md_lines = merge_lines(md_lines)

    # =========================================================
    # FALLBACK if no chapters found
    # =========================================================
    if not found_chapter:
        print("⚠️ No chapters detected → fallback mode")

        new_md = []
        for line in md_lines:
            if re.match(r"^\d+\s+[A-Za-z]", line):
                new_md.append(f"\n# {line}\n")
            else:
                new_md.append(line)

        md_lines = new_md

    # =========================================================
    # FINAL CLEAN
    # =========================================================
    md_lines = deduplicate(md_lines)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"✅ Font-aware PDF → Markdown: {output_path}")

    return output_path