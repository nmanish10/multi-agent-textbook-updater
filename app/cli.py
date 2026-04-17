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
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
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
