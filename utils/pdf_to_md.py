import os
import re
from collections import Counter

import pdfplumber


CHAPTER_PATTERNS = [
    re.compile(r"^chapter\s+\d+\s*[:.\-]?\s+.+", re.IGNORECASE),
    re.compile(r"^chapter\s+[IVXLCDM]+\s*[:.\-]?\s+.+", re.IGNORECASE),
    re.compile(r"^part\s+(?:\d+|[IVXLCDM]+)\s*[:.\-]?\s+.+", re.IGNORECASE),
    re.compile(r"^\d+\.\s+[A-Z][A-Za-z0-9 ,:;()'/-]{2,}$"),
    re.compile(r"^\d+\s+[A-Z][A-Za-z0-9 ,:;()'/-]{2,}$"),
]

SECTION_PATTERNS = [
    re.compile(r"^(\d+\.\d+\.\d+\.?\s+[A-Za-z][^\d]{0,120})"),
    re.compile(r"^(\d+\.\d+\.?\s+[A-Za-z][^\d]{0,120})"),
]


def clean_line(text):
    text = text.replace("\r", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def detect_repeating_lines(all_lines):
    counts = Counter(all_lines)
    return {line for line, count in counts.items() if count > 5 and len(line) < 80}


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


def _extract_line_font_info(page):
    try:
        chars = page.chars
    except Exception:
        return []

    if not chars:
        return []

    lines_by_y = {}
    for char in chars:
        y_key = round(char.get("top", 0) / 2) * 2
        lines_by_y.setdefault(y_key, []).append(char)

    result = []
    for y_key in sorted(lines_by_y):
        line_chars = sorted(lines_by_y[y_key], key=lambda item: item.get("x0", 0))
        text = clean_line("".join(item.get("text", "") for item in line_chars))
        if not text:
            continue

        sizes = [item.get("size", 0) for item in line_chars if item.get("text", "").strip()]
        if not sizes:
            continue
        font_size = max(set(sizes), key=sizes.count)

        fontnames = [item.get("fontname", "") for item in line_chars if item.get("text", "").strip()]
        dominant_font = max(set(fontnames), key=fontnames.count) if fontnames else ""
        is_bold = any(marker in dominant_font.lower() for marker in ["bold", "bd", "heavy", "black"])
        result.append(
            {
                "text": text,
                "font_size": font_size,
                "is_bold": is_bold,
                "top": min(item.get("top", 0) for item in line_chars),
            }
        )
    return result


def _compute_body_font_size(all_line_info):
    sizes = [item.get("font_size", 0) for item in all_line_info if item.get("font_size", 0) > 0]
    if not sizes:
        return 12.0
    return max(set(sizes), key=sizes.count)


def classify_heading_level(text, font_size, is_bold, body_size):
    if font_size <= 0 or body_size <= 0:
        return None

    ratio = font_size / body_size
    if ratio >= 1.45:
        return "chapter"
    if ratio >= 1.15:
        return "section"
    if is_bold and ratio >= 0.95 and len(text.split()) <= 10:
        return "section"
    return None


def is_valid_heading_text(line):
    if len(line.split()) < 2 or len(line) > 150:
        return False
    if any(token in line for token in ["=", "Σ", "λ", "|", "∈", "→", "∀", "∃"]):
        return False
    if line.endswith(".") and len(line.split()) > 12:
        return False
    return True


def match_chapter_pattern(line):
    return any(pattern.match(line) for pattern in CHAPTER_PATTERNS)


def extract_sections_from_line(line):
    matches = []
    for pattern in SECTION_PATTERNS:
        matches.extend(pattern.findall(line))
    return matches


def is_all_caps_heading(line):
    return len(line.split()) <= 8 and line.isupper() and len(line) > 5


def _is_toc_line(line):
    return bool(re.search(r"\.{3,}\s*\d+\s*$", line) or re.search(r"\s{3,}\d+\s*$", line))


def is_toc_page(lines):
    toc_score = sum(1 for line in lines if _is_toc_line(line))
    section_score = sum(1 for line in lines if re.match(r"\d+\.\d+", line))
    return toc_score >= 3 or section_score > 5


def _normalize_heading_key(text):
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _strip_numeric_prefix(text):
    return re.sub(r"^(chapter\s+[ivxlcdm]+\s*[:.\-]?\s*|chapter\s+\d+\s*[:.\-]?\s*|\d+(?:\.\d+)*\.?\s+|part\s+(?:\d+|[ivxlcdm]+)\s*[:.\-]?\s*)", "", text, flags=re.IGNORECASE).strip()


def _heading_key_variants(text):
    base = text.strip()
    variants = {_normalize_heading_key(base)}
    stripped = _strip_numeric_prefix(base)
    if stripped and stripped != base:
        variants.add(_normalize_heading_key(stripped))
    return {variant for variant in variants if variant}


def _is_likely_heading_fragment(text):
    if not is_valid_heading_text(text):
        return False
    if text.endswith((".", ";", "?", "!")):
        return False
    return True


def build_font_heading_hints(page_font_lines, body_size):
    hints = []
    current = None

    for item in page_font_lines:
        text = item.get("text", "")
        font_size = item.get("font_size", body_size)
        is_bold = item.get("is_bold", False)
        top = item.get("top", 0)
        level = classify_heading_level(text, font_size, is_bold, body_size)
        if level and _is_likely_heading_fragment(text):
            if (
                current
                and current["level"] == level
                and abs(top - current["last_top"]) <= max(12, body_size * 1.2)
                and len(current["text"].split()) + len(text.split()) <= 14
            ):
                current["text"] = f"{current['text']} {text}".strip()
                current["last_top"] = top
                current["font_size"] = max(current["font_size"], font_size)
                current["is_bold"] = current["is_bold"] or is_bold
            else:
                if current:
                    hints.append(current)
                current = {
                    "text": text,
                    "level": level,
                    "font_size": font_size,
                    "is_bold": is_bold,
                    "top": top,
                    "last_top": top,
                }
            continue

        if current:
            hints.append(current)
            current = None

    if current:
        hints.append(current)

    return hints


def extract_toc_structure(pages):
    toc_entries = []
    for page_lines in pages:
        if not is_toc_page(page_lines):
            continue

        for line in page_lines:
            cleaned = re.sub(r"\.{2,}\s*\d+\s*$", "", line).strip()
            cleaned = re.sub(r"\s{3,}\d+\s*$", "", cleaned).strip()
            if not cleaned:
                continue
            if match_chapter_pattern(cleaned):
                toc_entries.append({"level": "chapter", "title": cleaned, "keys": sorted(_heading_key_variants(cleaned))})
            elif re.match(r"\d+\.\d+", cleaned):
                toc_entries.append({"level": "section", "title": cleaned, "keys": sorted(_heading_key_variants(cleaned))})
    return toc_entries


def merge_lines(lines):
    merged = []
    buffer = ""

    for line in lines:
        if not buffer:
            buffer = line
            continue

        if buffer.endswith("-"):
            buffer = buffer[:-1] + line
            continue

        current_is_heading = line.startswith("#") or re.match(r"\d+\.\d+", line) or match_chapter_pattern(line)
        previous_looks_complete = buffer.endswith((".", ":", "?", "!", ";"))
        next_starts_sentence = bool(re.match(r"^[A-Z0-9\"'(]", line))
        next_starts_continuation = bool(re.match(r"^[a-z,\-]", line))

        if current_is_heading or previous_looks_complete:
            merged.append(buffer)
            buffer = line
            continue

        if next_starts_continuation or not next_starts_sentence:
            buffer += " " + line
            continue

        if len(buffer.split()) <= 8:
            merged.append(buffer)
            buffer = line
        else:
            buffer += " " + line

    if buffer:
        merged.append(buffer)
    return merged


def deduplicate(lines):
    seen = set()
    result = []
    for line in lines:
        key = re.sub(r"\W+", "", line.lower())
        if len(key) < 20:
            result.append(line)
            continue
        if key in seen:
            continue
        seen.add(key)
        result.append(line)
    return result


def convert_extracted_pages_to_md(pages_raw, pages_font=None, output_path="outputs/converted.md"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    all_lines = [line for page_lines in pages_raw for line in page_lines]
    repeating = detect_repeating_lines(all_lines)
    toc_entries = extract_toc_structure(pages_raw)
    toc_chapter_keys = {key for entry in toc_entries if entry["level"] == "chapter" for key in entry["keys"]}
    toc_section_keys = {key for entry in toc_entries if entry["level"] == "section" for key in entry["keys"]}

    all_line_info = [item for page_lines in (pages_font or []) for item in page_lines]
    body_size = _compute_body_font_size(all_line_info) if all_line_info else 12.0
    if all_line_info:
        print(f"Detected body font size: {body_size:.1f}pt")
    if toc_entries:
        print(f"Extracted {len(toc_entries)} TOC entries")

    md_lines = []
    seen_chapters = set()
    found_chapter = False

    for page_index, raw_lines in enumerate(pages_raw):
        if is_toc_page(raw_lines):
            print(f"Skipping TOC page {page_index + 1}")
            continue

        font_lookup = {}
        font_heading_hints = []
        if pages_font and page_index < len(pages_font):
            font_heading_hints = build_font_heading_hints(pages_font[page_index], body_size)
            for item in pages_font[page_index]:
                font_lookup[item["text"]] = (item["font_size"], item["is_bold"])
            for hint in font_heading_hints:
                font_lookup.setdefault(hint["text"], (hint["font_size"], hint["is_bold"]))

        cleaned_lines = [line for line in raw_lines if not is_noise(line, repeating)]
        inserted_heading_hints = set()
        for line in cleaned_lines:
            font_size, is_bold = font_lookup.get(line, (body_size, False))
            heading_level = classify_heading_level(line, font_size, is_bold, body_size)
            heading_keys = _heading_key_variants(line)

            for hint in font_heading_hints:
                hint_key = _normalize_heading_key(hint["text"])
                if hint_key in inserted_heading_hints:
                    continue
                if not any(key and key in hint_key for key in heading_keys):
                    continue
                if hint["text"] == line:
                    continue
                inserted_heading_hints.add(hint_key)
                prefix = "# " if hint["level"] == "chapter" else "## "
                md_lines.append(f"\n{prefix}{hint['text']}\n")

            is_chapter = False
            if heading_level == "chapter" and is_valid_heading_text(line):
                is_chapter = True
            if not is_chapter and match_chapter_pattern(line) and is_valid_heading_text(line):
                is_chapter = True
            if not is_chapter and any(key in toc_chapter_keys for key in heading_keys) and is_valid_heading_text(line):
                is_chapter = True

            if is_chapter and line not in seen_chapters:
                seen_chapters.add(line)
                found_chapter = True
                md_lines.append(f"\n# {line}\n")
                continue

            is_section = False
            section_text = line
            if heading_level == "section" and is_valid_heading_text(line):
                is_section = True
            if not is_section and is_all_caps_heading(line):
                is_section = True
                section_text = line.title()
            if not is_section and any(key in toc_section_keys for key in heading_keys) and is_valid_heading_text(line):
                is_section = True

            if not is_section:
                section_matches = extract_sections_from_line(line)
                if section_matches:
                    for section in section_matches:
                        md_lines.append(f"\n## {section.strip()}\n")
                        line = line.replace(section, "").strip()
                    if line:
                        md_lines.append(line)
                    continue

            if is_section:
                md_lines.append(f"\n## {section_text}\n")
                continue

            if line:
                md_lines.append(line)

    md_lines = merge_lines(md_lines)
    if not found_chapter:
        fallback = []
        for line in md_lines:
            if match_chapter_pattern(line) or re.match(r"^\d+\s+[A-Za-z]", line) or re.match(r"^\d+\.\s+[A-Za-z]", line):
                fallback.append(f"\n# {line}\n")
            else:
                fallback.append(line)
        md_lines = fallback

    md_lines = deduplicate(md_lines)
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(md_lines))
    return output_path


def convert_pdf_to_md(pdf_path, output_path="outputs/converted.md"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    all_line_info = []
    pages_raw = []
    pages_font = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            bbox = (0, page.height * 0.08, page.width, page.height * 0.92)
            try:
                cropped = page.crop(bbox)
            except ValueError:
                cropped = page

            font_lines = _extract_line_font_info(cropped)
            pages_font.append(font_lines)
            all_line_info.extend(font_lines)

            try:
                text = cropped.extract_text(layout=True) or ""
            except Exception:
                text = page.extract_text(layout=True) or ""

            raw_lines = []
            for line in text.split("\n"):
                line = clean_line(line)
                if line:
                    raw_lines.append(line)
            pages_raw.append(raw_lines)

    output = convert_extracted_pages_to_md(pages_raw, pages_font=pages_font, output_path=output_path)
    print(f"Font-aware PDF -> Markdown: {output}")
    return output
