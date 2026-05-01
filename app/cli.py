from __future__ import annotations

import argparse
import json

from core.config import PipelineSettings
from storage.admin_config_store import AdminConfigStore


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
    parser.add_argument("--approved-docx", dest="approved_docx", help="Optional output path for approved DOCX export")
    parser.add_argument("--approved-pdf", dest="approved_pdf", help="Optional output path for approved PDF export")
    parser.add_argument("--skip-approved-docx", action="store_true", help="Skip approved DOCX export when applying review decisions")
    parser.add_argument("--skip-approved-pdf", action="store_true", help="Skip approved PDF export when applying review decisions")
    parser.add_argument("--show-admin-config", action="store_true", help="Print the persisted admin configuration")
    parser.add_argument("--show-schedule", action="store_true", help="Print scheduling metadata from the persisted admin configuration")
    parser.add_argument("--show-run-history", action="store_true", help="Print the persisted run history ledger")
    parser.add_argument("--run-if-due", action="store_true", help="Run the pipeline only when the persisted schedule says a run is due")
    parser.add_argument("--set-update-frequency", choices=["daily", "weekly", "monthly", "manual"])
    parser.add_argument("--set-chapter-parallelism", type=int)
    parser.add_argument("--set-max-updates-per-chapter", type=int)
    parser.add_argument("--set-max-total-updates-per-chapter", type=int)
    parser.add_argument("--set-min-accept-score", type=float)
    parser.add_argument("--set-min-relevance", type=float)
    parser.add_argument("--set-min-credibility", type=float)
    parser.add_argument("--set-min-significance", type=float)
    parser.add_argument("--set-enabled-sources", help="Comma-separated list such as openalex,arxiv,web,official")
    parser.add_argument("--disable-pdf", action="store_true", help="Disable PDF export in persisted admin configuration")
    parser.add_argument("--disable-docx", action="store_true", help="Disable DOCX export in persisted admin configuration")
    parser.add_argument("--disable-review-pack", action="store_true", help="Disable review-pack generation in persisted admin configuration")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    base_settings = PipelineSettings.from_env()
    admin_store = AdminConfigStore(
        base_settings.admin_config_path,
        base_settings.admin_audit_log_path,
        base_settings.scheduler_state_path,
    )
    from storage.run_history_store import RunHistoryStore
    run_history_store = RunHistoryStore(base_settings.run_history_path)

    config_updates = {}
    if args.set_update_frequency is not None:
        config_updates["update_frequency"] = args.set_update_frequency
    if args.set_chapter_parallelism is not None:
        config_updates["chapter_parallelism"] = args.set_chapter_parallelism
    if args.set_max_updates_per_chapter is not None:
        config_updates["max_updates_per_chapter"] = args.set_max_updates_per_chapter
    if args.set_max_total_updates_per_chapter is not None:
        config_updates["max_total_updates_per_chapter"] = args.set_max_total_updates_per_chapter
    if args.set_min_accept_score is not None:
        config_updates["min_accept_score"] = args.set_min_accept_score
    if args.set_min_relevance is not None:
        config_updates["min_relevance"] = args.set_min_relevance
    if args.set_min_credibility is not None:
        config_updates["min_credibility"] = args.set_min_credibility
    if args.set_min_significance is not None:
        config_updates["min_significance"] = args.set_min_significance
    if args.set_enabled_sources is not None:
        config_updates["enabled_sources"] = [item.strip() for item in args.set_enabled_sources.split(",") if item.strip()]
    if args.disable_pdf:
        config_updates["render_pdf"] = False
    if args.disable_docx:
        config_updates["render_docx"] = False
    if args.disable_review_pack:
        config_updates["generate_review_pack"] = False

    if config_updates:
        updated = admin_store.update(config_updates)
        print(json.dumps(updated.model_dump(mode="json"), indent=2))
        return

    if args.show_admin_config:
        print(json.dumps(admin_store.load().model_dump(mode="json"), indent=2))
        return

    if args.show_schedule:
        print(json.dumps(admin_store.scheduler_snapshot(), indent=2))
        return

    if args.show_run_history:
        print(json.dumps(run_history_store.load(), indent=2))
        return

    if args.apply_review_queue:
        if not args.review_run_dir:
            raise SystemExit("--review-run-dir is required when using --apply-review-queue")
        from review.decision_ingest import write_review_decision_outputs

        outputs = write_review_decision_outputs(
            run_dir=args.review_run_dir,
            review_queue_csv=args.apply_review_queue,
            output_markdown=args.approved_markdown,
            output_docx=args.approved_docx,
            output_pdf=args.approved_pdf,
            export_docx_enabled=not args.skip_approved_docx,
            export_pdf_enabled=not args.skip_approved_pdf,
            pandoc_command=base_settings.pandoc_command,
        )
        print("Applied review decisions")
        for name, path in outputs.items():
            print(f"{name}: {path}")
        return

    from app.run_pipeline import run_pipeline

    settings = base_settings
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

    if args.run_if_due:
        snapshot = admin_store.scheduler_snapshot()
        if not snapshot["due_now"]:
            print(json.dumps({"status": "not_due", "scheduler": snapshot}, indent=2))
            return
        print(json.dumps({"status": "running_due_job", "scheduler": snapshot}, indent=2))

    run_pipeline(settings)


if __name__ == "__main__":
    main()
