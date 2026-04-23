from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from core.models import Book, WrittenUpdate
from rendering.markdown_renderer import write_markdown


DecisionMap = Dict[Tuple[str, str, str], dict]


def _decision_key(chapter_id: str, section_id: str, title: str) -> Tuple[str, str, str]:
    return (chapter_id.strip(), section_id.strip(), title.strip().lower())


def load_review_decisions(review_queue_csv: str) -> DecisionMap:
    decisions: DecisionMap = {}
    with open(review_queue_csv, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            key = _decision_key(row.get("chapter_id", ""), row.get("section_id", ""), row.get("title", ""))
            decisions[key] = {
                "review_decision": (row.get("review_decision", "") or "").strip().lower(),
                "review_notes": (row.get("review_notes", "") or "").strip(),
                "proposed_subsection_id": (row.get("proposed_subsection_id", "") or "").strip(),
                "chapter_title": (row.get("chapter_title", "") or "").strip(),
            }
    return decisions


def load_written_updates(run_dir: str) -> List[WrittenUpdate]:
    base = Path(run_dir)
    updates: List[WrittenUpdate] = []
    for path in sorted(base.glob("chapters/*/written_updates.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        updates.extend(WrittenUpdate(**item) for item in payload)
    return updates


def load_parsed_book(run_dir: str) -> Book:
    payload = json.loads((Path(run_dir) / "book" / "parsed_book.json").read_text(encoding="utf-8"))
    return Book(**payload)


def apply_review_decisions(updates: Iterable[WrittenUpdate], decisions: DecisionMap) -> dict:
    approved: List[WrittenUpdate] = []
    revise: List[dict] = []
    rejected: List[dict] = []
    unreviewed: List[dict] = []

    for update in updates:
        key = _decision_key(update.chapter_id, update.section_id, update.title)
        decision = decisions.get(key, {})
        label = decision.get("review_decision", "")
        notes = decision.get("review_notes", "")
        row = {
            "chapter_id": update.chapter_id,
            "section_id": update.section_id,
            "title": update.title,
            "proposed_subsection_id": update.proposed_subsection_id,
            "review_notes": notes,
        }
        if label == "approve":
            approved.append(update)
        elif label == "revise":
            revise.append(row)
        elif label == "reject":
            rejected.append(row)
        else:
            unreviewed.append(row)

    return {
        "approved_updates": approved,
        "revise_updates": revise,
        "rejected_updates": rejected,
        "unreviewed_updates": unreviewed,
    }


def write_review_decision_outputs(run_dir: str, review_queue_csv: str, output_markdown: str | None = None) -> dict:
    run_path = Path(run_dir)
    decisions = load_review_decisions(review_queue_csv)
    updates = load_written_updates(run_dir)
    book = load_parsed_book(run_dir)
    outcome = apply_review_decisions(updates, decisions)

    approved_updates: List[WrittenUpdate] = outcome["approved_updates"]
    review_dir = run_path / "review"
    review_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "review_queue_csv": str(Path(review_queue_csv)),
        "approved_count": len(approved_updates),
        "revise_count": len(outcome["revise_updates"]),
        "rejected_count": len(outcome["rejected_updates"]),
        "unreviewed_count": len(outcome["unreviewed_updates"]),
    }
    summary_path = review_dir / "review_decision_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    approved_path = review_dir / "approved_updates.json"
    approved_path.write_text(
        json.dumps([item.model_dump(mode="json") for item in approved_updates], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    pending_path = review_dir / "pending_review_updates.json"
    pending_path.write_text(
        json.dumps(
            {
                "revise_updates": outcome["revise_updates"],
                "rejected_updates": outcome["rejected_updates"],
                "unreviewed_updates": outcome["unreviewed_updates"],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    markdown_target = output_markdown or str(review_dir / "approved_book.md")
    approved_book_path = write_markdown(book, approved_updates, markdown_target)

    return {
        "summary": str(summary_path),
        "approved_updates": str(approved_path),
        "pending_updates": str(pending_path),
        "approved_book_markdown": str(approved_book_path),
    }
