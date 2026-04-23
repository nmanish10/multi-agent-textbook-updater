from __future__ import annotations

import argparse

from core.config import PipelineSettings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Multi-Agent Textbook Update System")
    parser.add_argument("--input-file", dest="input_file")
    parser.add_argument("--output-dir", dest="output_dir")
    parser.add_argument("--chapter-limit", dest="chapter_limit", type=int)
    parser.add_argument("--full-run", action="store_true", help="Disable demo chapter limits")
    parser.add_argument("--skip-pdf", action="store_true", help="Skip PDF export")
    parser.add_argument("--skip-docx", action="store_true", help="Skip DOCX export")
    parser.add_argument("--skip-review-pack", action="store_true", help="Skip human review pack generation")
    parser.add_argument("--apply-review-queue", dest="apply_review_queue", help="Apply reviewer decisions from review_queue.csv")
    parser.add_argument("--review-run-dir", dest="review_run_dir", help="Artifact run directory containing parsed book and written updates")
    parser.add_argument("--approved-markdown", dest="approved_markdown", help="Optional output path for approved markdown export")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.apply_review_queue:
        if not args.review_run_dir:
            raise SystemExit("--review-run-dir is required when using --apply-review-queue")
        from review.decision_ingest import write_review_decision_outputs

        outputs = write_review_decision_outputs(
            run_dir=args.review_run_dir,
            review_queue_csv=args.apply_review_queue,
            output_markdown=args.approved_markdown,
        )
        print("Applied review decisions")
        for name, path in outputs.items():
            print(f"{name}: {path}")
        return

    from app.run_pipeline import run_pipeline

    settings = PipelineSettings.from_env()
    if args.input_file:
        settings.input_file = args.input_file
    if args.output_dir:
        settings.output_dir = args.output_dir
    if args.chapter_limit is not None:
        settings.chapter_limit = args.chapter_limit
    if args.full_run:
        settings.demo_mode = False
        settings.chapter_limit = args.chapter_limit
    if args.skip_pdf:
        settings.render_pdf = False
    if args.skip_docx:
        settings.render_docx = False
    if args.skip_review_pack:
        settings.generate_review_pack = False

    run_pipeline(settings)


if __name__ == "__main__":
    main()
