from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List

from core.models import AcceptedUpdate, Book, WrittenUpdate
from storage.artifact_store import ArtifactStore


def _source_summary(update: WrittenUpdate) -> str:
    if update.sources:
        return "; ".join(filter(None, [source.url or source.title for source in update.sources]))
    return update.source


def _score_summary(scores: dict) -> str:
    if not scores:
        return ""
    ordered = sorted(scores.items(), key=lambda item: item[0])
    return ", ".join(f"{key}={value}" for key, value in ordered)


def _chapter_title_map(book: Book) -> Dict[str, str]:
    return {chapter.chapter_id: chapter.title for chapter in book.chapters}


def build_review_payload(
    book: Book,
    updates: List[WrittenUpdate],
    judged_candidates: Dict[str, List[AcceptedUpdate]],
    summary: dict | None = None,
) -> dict:
    chapter_titles = _chapter_title_map(book)
    review_rows = []
    for update in updates:
        review_rows.append(
            {
                "chapter_id": update.chapter_id,
                "chapter_title": chapter_titles.get(update.chapter_id, ""),
                "section_id": update.section_id,
                "proposed_subsection_id": update.proposed_subsection_id or "",
                "title": update.title,
                "why_it_matters": update.why_it_matters,
                "mapping_rationale": update.mapping_rationale,
                "source_summary": _source_summary(update),
                "scores": update.scores,
                "review_decision": "",
                "review_notes": "",
            }
        )

    return {
        "book_title": book.book_title,
        "parse_report": book.parse_report.model_dump(mode="json") if book.parse_report else None,
        "summary": summary or {},
        "chapter_titles": chapter_titles,
        "accepted_updates": review_rows,
        "accepted_candidates_by_chapter": {
            chapter_id: [item.model_dump(mode="json") for item in items]
            for chapter_id, items in judged_candidates.items()
        },
    }


def _write_review_csv(destination: Path, updates: Iterable[WrittenUpdate], chapter_titles: Dict[str, str]) -> Path:
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "chapter_id",
                "chapter_title",
                "section_id",
                "proposed_subsection_id",
                "title",
                "source_summary",
                "score_summary",
                "review_decision",
                "review_notes",
            ],
        )
        writer.writeheader()
        for update in updates:
            writer.writerow(
                {
                    "chapter_id": update.chapter_id,
                    "chapter_title": chapter_titles.get(update.chapter_id, ""),
                    "section_id": update.section_id,
                    "proposed_subsection_id": update.proposed_subsection_id or "",
                    "title": update.title,
                    "source_summary": _source_summary(update),
                    "score_summary": _score_summary(update.scores),
                    "review_decision": "",
                    "review_notes": "",
                }
            )
    return destination


def _build_review_markdown(
    book: Book,
    updates: List[WrittenUpdate],
    judged_candidates: Dict[str, List[AcceptedUpdate]],
    summary: dict | None = None,
) -> str:
    lines = [f"# Review Pack: {book.book_title}", ""]
    if summary:
        lines.extend(
            [
                "## Run Summary",
                "",
                f"- Run ID: {summary.get('run_id', '')}",
                f"- Chapters processed: {summary.get('stats', {}).get('chapters_processed', 0)}",
                f"- Final updates written: {summary.get('stats', {}).get('final_updates', 0)}",
                "",
            ]
        )

    if book.parse_report:
        lines.extend(
            [
                "## Parse Review",
                "",
                f"- Parser strategy: {book.parse_report.strategy_used or book.parse_report.parser_name}",
                f"- Chapters detected: {book.parse_report.chapters_detected}",
                f"- Sections detected: {book.parse_report.sections_detected}",
                f"- Assets detected: {book.parse_report.assets_detected}",
                f"- Scanned pages: {book.parse_report.scanned_pages}",
                f"- OCR recommended: {'yes' if book.parse_report.ocr_recommended else 'no'}",
                "",
            ]
        )
        if book.parse_report.warnings:
            lines.extend(["### Parse Warnings", ""])
            lines.extend([f"- {warning}" for warning in book.parse_report.warnings])
            lines.append("")

    lines.extend(
        [
            "## Reviewer Instructions",
            "",
            "1. Review each proposed update against the original chapter context and source credibility.",
            "2. Record `approve`, `revise`, or `reject` in `review/review_queue.csv`.",
            "3. Use `review_notes` for factual corrections, placement concerns, or style changes.",
            "",
        ]
    )

    chapter_titles = _chapter_title_map(book)
    if not updates:
        lines.extend(["## Accepted Updates", "", "No accepted updates were produced in this run.", ""])
        return "\n".join(lines).strip() + "\n"

    lines.extend(["## Accepted Updates", ""])
    grouped_updates: Dict[str, List[WrittenUpdate]] = {}
    for update in updates:
        grouped_updates.setdefault(update.chapter_id, []).append(update)

    for chapter_id, chapter_updates in grouped_updates.items():
        lines.extend([f"### Chapter {chapter_id}: {chapter_titles.get(chapter_id, '')}", ""])
        chapter_candidates = judged_candidates.get(chapter_id, [])
        if chapter_candidates:
            lines.append(f"Accepted candidate count: {len(chapter_candidates)}")
            lines.append("")
        for update in chapter_updates:
            lines.extend(
                [
                    f"#### {update.proposed_subsection_id or update.section_id} {update.title}",
                    "",
                    f"- Section: {update.section_id}",
                    f"- Source summary: {_source_summary(update) or 'n/a'}",
                    f"- Scores: {_score_summary(update.scores) or 'n/a'}",
                    f"- Mapping rationale: {update.mapping_rationale or 'n/a'}",
                    "",
                ]
            )
            if update.why_it_matters:
                lines.extend(["Why it matters:", update.why_it_matters, ""])
            lines.extend(["Proposed text:", "", update.text.strip(), ""])

    return "\n".join(lines).strip() + "\n"


def write_review_pack(
    store: ArtifactStore,
    book: Book,
    updates: List[WrittenUpdate],
    judged_candidates: Dict[str, List[AcceptedUpdate]],
    summary: dict | None = None,
) -> dict:
    chapter_titles = _chapter_title_map(book)
    payload = build_review_payload(book, updates, judged_candidates, summary)
    json_path = store.write_json("review/review_pack.json", payload)
    markdown_path = store.write_text(
        "review/review_pack.md",
        _build_review_markdown(book, updates, judged_candidates, summary),
    )
    csv_path = _write_review_csv(store.base_path / "review" / "review_queue.csv", updates, chapter_titles)

    return {
        "json": str(json_path),
        "markdown": str(markdown_path),
        "csv": str(csv_path),
    }
