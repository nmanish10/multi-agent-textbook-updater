from __future__ import annotations

import argparse
import json

from ingestion.pipeline import load_book
from ingestion.normalization.validation import validate_book_structure


def evaluate_parser(input_file: str) -> dict:
    book = load_book(input_file)
    validation = validate_book_structure(book)
    return {
        "input_file": input_file,
        "book_title": book.book_title,
        "parse_report": book.parse_report.model_dump(mode="json") if book.parse_report else None,
        "validation": validation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate parser output quality")
    parser.add_argument("input_file")
    args = parser.parse_args()
    report = evaluate_parser(args.input_file)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
