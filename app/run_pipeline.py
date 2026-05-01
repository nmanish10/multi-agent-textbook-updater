from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List

from agents.chapter_analysis import analyze_chapter
from agents.evidence_extractor import extract_evidence
from agents.judge import judge_candidates
from agents.ranker import competitive_replacement, rank_and_select
from agents.retrieval import retrieve_all
from agents.section_mapper import map_to_sections
from agents.writer import write_updates
from core.config import PipelineSettings
from core.console import ensure_utf8_console
from core.logging import configure_logging, get_logger, log_event
from core.models import (
    AcceptedUpdate,
    Book,
    ChapterAnalysis,
    PromptTrace,
    RunArtifacts,
    RunStats,
    SourceRecord,
    WrittenUpdate,
)
from core.run_context import create_run_artifacts, create_run_stats
from ingestion.pipeline import load_book
from rendering.docx_exporter import export_docx
from rendering.markdown_renderer import write_markdown
from rendering.pdf_exporter import export_pdf
from research.query_planner import build_query_plan
from review.review_pack import write_review_pack
from storage.admin_config_store import AdminConfigStore
from storage.artifact_store import ArtifactStore
from storage.run_history_store import RunHistoryStore, file_fingerprint
from storage.update_store import PersistentUpdateStore
from utils.llm import get_prompt_traces, reset_prompt_traces
from utils.storage import save_results

logger = get_logger("textbook_updater.pipeline")


def dedupe_retrieval_results(results: List[Dict]) -> List[Dict]:
    seen = set()
    deduped = []
    for item in results:
        title = item.get("title", "").lower()
        if title in seen:
            continue
        seen.add(title)
        deduped.append(item)
    return deduped


def _to_source_records(raw_sources: List[Dict]) -> List[SourceRecord]:
    return [SourceRecord(**source) for source in raw_sources]


def _to_written_update(chapter_id: str, raw_update: Dict) -> WrittenUpdate:
    text = raw_update.get("text", "").strip()
    title = raw_update.get("title") or (text.split("\n\n")[0].strip() if text else raw_update.get("section_id", "Generated Update"))
    return WrittenUpdate(
        chapter_id=chapter_id,
        section_id=raw_update.get("section_id", ""),
        title=title,
        text=text,
        sources=_to_source_records(raw_update.get("sources", [])),
        source=raw_update.get("source", ""),
        why_it_matters=raw_update.get("why_it_matters", ""),
        scores=raw_update.get("scores", {}),
        mapping_rationale=raw_update.get("mapping_rationale", ""),
    )


def _save_book_artifacts(store: ArtifactStore, book: Book) -> None:
    store.write_json("book/parsed_book.json", book.model_dump(mode="json"))
    if book.parse_report:
        store.write_json("book/parse_report.json", book.parse_report.model_dump(mode="json"))


def _written_update_to_rankable(update: WrittenUpdate) -> Dict:
    primary_source = update.sources[0].model_dump(mode="json") if update.sources else {}
    return {
        "candidate_title": update.title,
        "summary": update.text,
        "why_it_matters": update.why_it_matters,
        "source_title": primary_source.get("title", ""),
        "source_type": primary_source.get("source_type", ""),
        "source_name": primary_source.get("source_name", ""),
        "date": primary_source.get("date", ""),
        "url": primary_source.get("url", "") or update.source,
        "sources": [source.model_dump(mode="json") for source in update.sources],
        "retrieval_score": update.scores.get("final_score", 0),
        "credibility_score": primary_source.get("credibility_score", 0),
        "mapped_section_id": update.section_id,
        "mapping_score": update.scores.get("final_score", 0),
        "mapping_reason": update.mapping_rationale,
        "scores": update.scores,
        "decision": update.scores.get("decision", "accept"),
        "text": update.text,
    }


def _process_chapter(
    chapter_index: int,
    chapter,
    settings: PipelineSettings,
    artifacts: RunArtifacts,
    store: ArtifactStore,
    update_store: PersistentUpdateStore,
) -> Dict:
    chapter_start = time.time()
    existing_written = update_store.chapter_updates(chapter.chapter_id)
    log_event(
        logger,
        logging.INFO,
        "Processing chapter",
        chapter_id=chapter.chapter_id,
        chapter_title=chapter.title,
        chapter_index=chapter_index,
    )

    if not chapter.content or len(chapter.content.split()) < 100:
        log_event(
            logger,
            logging.INFO,
            "Skipping weak chapter",
            chapter_id=chapter.chapter_id,
            word_count=len(chapter.content.split()) if chapter.content else 0,
        )
        return {
            "index": chapter_index,
            "chapter_id": chapter.chapter_id,
            "analysis": None,
            "query_plan": None,
            "retrieval_results": [],
            "accepted_updates": [],
            "final_updates": existing_written,
            "candidates_generated": 0,
            "accepted_candidates": 0,
            "chapters_processed": 0,
        }

    analysis_raw = analyze_chapter(chapter)
    analysis = ChapterAnalysis(**analysis_raw)
    store.write_json(f"chapters/{chapter.chapter_id}/analysis.json", analysis.model_dump(mode="json"))

    plan = build_query_plan(chapter.chapter_id, analysis, demo_mode=settings.demo_mode)
    store.write_json(f"chapters/{chapter.chapter_id}/query_plan.json", plan.model_dump(mode="json"))

    all_results_raw: List[Dict] = []
    for refined in plan.refined_queries:
        log_event(
            logger,
            logging.INFO,
            "Running retrieval query",
            chapter_id=chapter.chapter_id,
            query=refined,
        )
        results = retrieve_all(refined, enabled_sources=settings.enabled_sources)
        if settings.demo_mode:
            results = results[: settings.retrieval_preview_limit]
        log_event(
            logger,
            logging.INFO,
            "Retrieved results for query",
            chapter_id=chapter.chapter_id,
            query=refined,
            retrieved=len(results),
        )
        all_results_raw.extend(results)

    if not all_results_raw:
        log_event(logger, logging.INFO, "No retrieval results for chapter", chapter_id=chapter.chapter_id)
        return {
            "index": chapter_index,
            "chapter_id": chapter.chapter_id,
            "analysis": analysis,
            "query_plan": plan,
            "retrieval_results": [],
            "accepted_updates": [],
            "final_updates": existing_written,
            "candidates_generated": 0,
            "accepted_candidates": 0,
            "chapters_processed": 1,
        }

    deduped = dedupe_retrieval_results(all_results_raw)
    store.write_json(f"chapters/{chapter.chapter_id}/retrieval_results.json", deduped)

    candidates = extract_evidence(analysis.model_dump(), deduped)
    store.write_json(f"chapters/{chapter.chapter_id}/candidates.json", candidates)
    if not candidates:
        return {
            "index": chapter_index,
            "chapter_id": chapter.chapter_id,
            "analysis": analysis,
            "query_plan": plan,
            "retrieval_results": deduped,
            "accepted_updates": [],
            "final_updates": existing_written,
            "candidates_generated": 0,
            "accepted_candidates": 0,
            "chapters_processed": 1,
        }

    judged = judge_candidates(
        analysis.model_dump(),
        candidates,
        min_accept_score=settings.min_accept_score,
        min_relevance=settings.min_relevance,
        min_credibility=settings.min_credibility,
        min_significance=settings.min_significance,
    )
    mapped = map_to_sections(chapter, judged)
    ranked = rank_and_select(mapped, top_k=settings.max_updates_per_chapter, min_score=settings.min_accept_score)
    store.write_json(f"chapters/{chapter.chapter_id}/accepted_updates.json", ranked)

    accepted_models = [
        AcceptedUpdate(
            chapter_id=chapter.chapter_id,
            mapped_section_id=item.get("mapped_section_id", ""),
            proposed_subsection_id=item.get("proposed_subsection_id"),
            mapping_rationale=item.get("mapping_reason", ""),
            **{key: value for key, value in item.items() if key not in {"mapped_section_id", "proposed_subsection_id", "mapping_reason"}},
        )
        for item in ranked
    ]

    if not ranked and not existing_written:
        return {
            "index": chapter_index,
            "chapter_id": chapter.chapter_id,
            "analysis": analysis,
            "query_plan": plan,
            "retrieval_results": deduped,
            "accepted_updates": accepted_models,
            "final_updates": [],
            "candidates_generated": len(candidates),
            "accepted_candidates": 0,
            "chapters_processed": 1,
        }

    chapter_written = []
    if ranked:
        written_raw = write_updates(chapter, ranked)
        chapter_written = [_to_written_update(chapter.chapter_id, item) for item in written_raw]

    existing_rankable = [_written_update_to_rankable(item) for item in existing_written]
    new_rankable = [_written_update_to_rankable(item) for item in chapter_written]
    survivor_rankables, removed_rankables = competitive_replacement(
        existing_rankable,
        new_rankable,
        threshold=settings.max_total_updates_per_chapter,
        min_score=settings.min_accept_score,
    )

    survivor_lookup = {
        (
            item.title if hasattr(item, "title") else item.get("candidate_title", ""),
            item.section_id if hasattr(item, "section_id") else item.get("mapped_section_id", ""),
        ): item
        for item in existing_written + chapter_written
    }
    survivor_written = []
    removed_written = []
    for item in survivor_rankables:
        key = (item.get("candidate_title", ""), item.get("mapped_section_id", ""))
        if key in survivor_lookup:
            survivor_written.append(survivor_lookup[key])
    for item in removed_rankables:
        key = (item.get("candidate_title", ""), item.get("mapped_section_id", ""))
        if key in survivor_lookup:
            removed_written.append(survivor_lookup[key])

    update_store.save_chapter_state(chapter.chapter_id, survivor_written, removed_written, artifacts.run_id)
    store.write_json(
        f"chapters/{chapter.chapter_id}/written_updates.json",
        [item.model_dump(mode="json") for item in survivor_written],
    )
    store.write_json(
        f"chapters/{chapter.chapter_id}/replacement_audit.json",
        {
            "survivors": [item.model_dump(mode="json") for item in survivor_written],
            "removed": [item.model_dump(mode="json") for item in removed_written],
        },
    )

    log_event(
        logger,
        logging.INFO,
        "Completed chapter processing",
        chapter_id=chapter.chapter_id,
        elapsed_seconds=round(time.time() - chapter_start, 2),
        accepted_candidates=len(ranked),
        written_updates=len(survivor_written),
        replaced_updates=len(removed_written),
    )

    return {
        "index": chapter_index,
        "chapter_id": chapter.chapter_id,
        "analysis": analysis,
        "query_plan": plan,
        "retrieval_results": deduped,
        "accepted_updates": accepted_models,
        "final_updates": survivor_written,
        "candidates_generated": len(candidates),
        "accepted_candidates": len(ranked),
        "chapters_processed": 1,
    }


async def _run_chapter_jobs(
    chapters,
    settings: PipelineSettings,
    artifacts: RunArtifacts,
    store: ArtifactStore,
    update_store: PersistentUpdateStore,
) -> List[Dict]:
    semaphore = asyncio.Semaphore(max(1, settings.chapter_parallelism))

    async def _bounded_process(index, chapter):
        async with semaphore:
            return await asyncio.to_thread(_process_chapter, index, chapter, settings, artifacts, store, update_store)

    tasks = [_bounded_process(index, chapter) for index, chapter in enumerate(chapters)]
    return await asyncio.gather(*tasks)


def run_pipeline(settings: PipelineSettings | None = None) -> Dict:
    ensure_utf8_console()
    configure_logging()
    settings = settings or PipelineSettings.from_env()
    settings.ensure_directories()
    reset_prompt_traces()

    admin_store = AdminConfigStore(
        settings.admin_config_path,
        settings.admin_audit_log_path,
        settings.scheduler_state_path,
    )
    run_history_store = RunHistoryStore(settings.run_history_path)
    admin_config = admin_store.load()
    settings.apply_admin_config(admin_config)

    start_time = time.time()
    artifacts: RunArtifacts = create_run_artifacts(settings)
    stats: RunStats = create_run_stats()
    store = ArtifactStore(settings.artifact_dir, artifacts.run_id)

    log_event(
        logger,
        logging.INFO,
        "Starting hardened Multi-Agent Textbook Update System",
        input_file=settings.input_file,
        demo_mode=settings.demo_mode,
        chapter_limit=settings.chapter_limit,
        update_frequency=admin_config.update_frequency,
        chapter_parallelism=settings.chapter_parallelism,
    )

    book = load_book(settings.input_file)
    _save_book_artifacts(store, book)
    update_store = PersistentUpdateStore(settings.update_store_dir, settings.input_file, book.book_title)

    chapters = book.chapters
    if settings.chapter_limit:
        chapters = chapters[: settings.chapter_limit]

    chapter_results = asyncio.run(_run_chapter_jobs(chapters, settings, artifacts, store, update_store))

    final_updates: List[WrittenUpdate] = []
    for result in chapter_results:
        chapter_id = result["chapter_id"]
        if result["analysis"] is not None:
            artifacts.analysis_by_chapter[chapter_id] = result["analysis"]
        if result["query_plan"] is not None:
            artifacts.query_plans[chapter_id] = result["query_plan"]
        if result["retrieval_results"]:
            artifacts.retrieval_results[chapter_id] = result["retrieval_results"]
        if result["accepted_updates"]:
            artifacts.judged_candidates[chapter_id] = result["accepted_updates"]

        stats.chapters_processed += result["chapters_processed"]
        stats.candidates_generated += result["candidates_generated"]
        stats.accepted_candidates += result["accepted_candidates"]
        stats.final_updates += len(result["final_updates"])
        final_updates.extend(result["final_updates"])

    artifacts.written_updates = final_updates
    artifacts.prompt_traces = [PromptTrace(**trace) for trace in get_prompt_traces()]
    store.write_json("llm/prompt_traces.json", [trace.model_dump(mode="json") for trace in artifacts.prompt_traces])

    markdown_path = write_markdown(book, final_updates, settings.canonical_markdown)
    store.write_text("outputs/updated_book.md", markdown_path.read_text(encoding="utf-8"))

    if settings.render_docx:
        ok, engine, manifest_path = export_docx(book, final_updates, settings.output_docx)
        store.write_text("outputs/docx_export_manifest_path.txt", str(manifest_path))
        if ok:
            log_event(logger, logging.INFO, "DOCX generated", engine=engine, output=settings.output_docx)
        else:
            log_event(logger, logging.WARNING, "DOCX export skipped", reason=engine)

    save_results(
        {
            "run_id": artifacts.run_id,
            "book": book.model_dump(mode="json"),
            "updates": [item.model_dump(mode="json") for item in final_updates],
            "stats": stats.model_dump(mode="json"),
            "parse_report": book.parse_report.model_dump(mode="json") if book.parse_report else None,
        }
    )

    if settings.render_pdf:
        ok, engine, export_manifest_path = export_pdf(str(markdown_path), settings.output_pdf, settings.pandoc_command)
        store.write_text("outputs/export_manifest_path.txt", str(export_manifest_path))
        if ok:
            log_event(logger, logging.INFO, "PDF generated", engine=engine, output=settings.output_pdf)
        else:
            log_event(logger, logging.WARNING, "PDF export skipped", reason=engine)

    elapsed = round(time.time() - start_time, 2)
    summary = {
        "run_id": artifacts.run_id,
        "elapsed_seconds": elapsed,
        "stats": stats.model_dump(mode="json"),
        "outputs": {
            "markdown": settings.canonical_markdown,
            "pdf": settings.output_pdf if settings.render_pdf else None,
            "docx": settings.output_docx if settings.render_docx else None,
            "artifact_dir": str(store.base_path),
        },
        "admin_config": admin_config.model_dump(mode="json"),
        "scheduler": admin_store.scheduler_snapshot(),
        "prompt_traces_recorded": len(artifacts.prompt_traces),
    }

    if settings.generate_review_pack:
        review_paths = write_review_pack(store, book, final_updates, artifacts.judged_candidates, summary)
        summary["outputs"]["review_pack"] = review_paths

    history_entry = run_history_store.append_run(
        {
            "run_id": artifacts.run_id,
            "book_key": update_store.store_key,
            "book_title": book.book_title,
            "input_file": settings.input_file,
            "input_fingerprint": file_fingerprint(settings.input_file),
            "artifact_dir": str(store.base_path),
            "outputs": summary["outputs"],
            "stats": stats.model_dump(mode="json"),
            "admin_config": admin_config.model_dump(mode="json"),
        }
    )
    summary["history"] = history_entry
    summary["scheduler"] = admin_store.mark_run_completed(run_id=artifacts.run_id)

    store.write_json("run_summary.json", summary)

    log_event(
        logger,
        logging.INFO,
        "Run summary",
        run_id=artifacts.run_id,
        chapters_processed=stats.chapters_processed,
        candidates_generated=stats.candidates_generated,
        accepted_candidates=stats.accepted_candidates,
        final_updates=stats.final_updates,
        elapsed_seconds=elapsed,
    )
    return summary
