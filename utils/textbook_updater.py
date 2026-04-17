from __future__ import annotations

from typing import Iterable, List

from core.models import SourceRecord, WrittenUpdate
from rendering.markdown_renderer import write_markdown


def _convert_updates(updates: Iterable[dict]) -> List[WrittenUpdate]:
    converted = []
    for update in updates:
        text = update.get("text", "").strip()
        title = text.split("\n\n")[0].strip() if text else update.get("section_id", "Generated Update")
        converted.append(
            WrittenUpdate(
                chapter_id=update.get("chapter_id", update.get("section_id", "").split(".")[0]),
                section_id=update.get("section_id", ""),
                proposed_subsection_id=update.get("proposed_subsection_id"),
                title=title,
                text=text,
                why_it_matters=update.get("why_it_matters", ""),
                sources=[SourceRecord(**source) for source in update.get("sources", [])],
                source=update.get("source", ""),
                scores=update.get("scores", {}),
                mapping_rationale=update.get("mapping_rationale", update.get("mapping_reason", "")),
            )
        )
    return converted


def update_textbook_md(book, updates, output_file="outputs/updated_book.md"):
    rendered = write_markdown(book, _convert_updates(updates), output_file)
    print(f"Updated textbook saved to {rendered}")
