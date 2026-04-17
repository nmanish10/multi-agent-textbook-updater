from __future__ import annotations

import time
from typing import Dict, List

from agents.chapter_analysis import analyze_chapter
from agents.evidence_extractor import extract_evidence
from agents.judge import judge_candidates
from agents.ranker import rank_and_select
from agents.retrieval import retrieve_all
from agents.section_mapper import map_to_sections
from agents.writer import write_updates
from core.config import PipelineSettings
from core.console import ensure_utf8_console
from core.models import (
    AcceptedUpdate,
    Book,
    ChapterAnalysis,
    PromptTrace,
    RunArtifacts,
    RunStats,
    SearchQueryPlan,
    SourceRecord,
    WrittenUpdate,
)
from core.run_context import create_run_artifacts, create_run_stats
from ingestion.pipeline import load_book
from rendering.docx_exporter import export_docx
from rendering.markdown_renderer import write_markdown
from rendering.pdf_exporter import export_pdf
from review.review_pack import write_review_pack
from research.query_planner import build_query_plan
from storage.artifact_store import ArtifactStore
from utils.llm import get_prompt_traces, reset_prompt_traces
from utils.storage import save_results


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
    title = text.split("\n\n")[0].strip() if text else raw_update.get("section_id", "Generated Update")
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


def run_pipeline(settings: PipelineSettings | None = None) -> Dict:
    ensure_utf8_console()
    settings = settings or PipelineSettings.from_env()
    settings.ensure_directories()
    reset_prompt_traces()

    start_time = time.time()
    artifacts: RunArtifacts = create_run_artifacts(settings)
    stats: RunStats = create_run_stats()
    store = ArtifactStore(settings.artifact_dir, artifacts.run_id)

    print("\nStarting hardened Multi-Agent Textbook Update System\n")

    book = load_book(settings.input_file)
    _save_book_artifacts(store, book)

    chapters = book.chapters
    if settings.chapter_limit:
        chapters = chapters[: settings.chapter_limit]

    final_updates: List[WrittenUpdate] = []

    for chapter in chapters:
        print("\n" + "=" * 60)
        print(f"Processing Chapter: {chapter.title}")
        print("=" * 60)

        if not chapter.content or len(chapter.content.split()) < 100:
            print("Skipping weak chapter")
            continue

        stats.chapters_processed += 1

        analysis_raw = analyze_chapter(chapter)
        analysis = ChapterAnalysis(**analysis_raw)
        artifacts.analysis_by_chapter[chapter.chapter_id] = analysis
        store.write_json(
            f"chapters/{chapter.chapter_id}/analysis.json",
            analysis.model_dump(mode="json"),
        )

        plan = build_query_plan(chapter.chapter_id, analysis, demo_mode=settings.demo_mode)
        all_results_raw: List[Dict] = []

        for refined in plan.refined_queries:
            print(f"\nQuery: {refined}")
            results = retrieve_all(refined)
            if settings.demo_mode:
                results = results[: settings.retrieval_preview_limit]
            print(f"Retrieved: {len(results)}")
            all_results_raw.extend(results)

        artifacts.query_plans[chapter.chapter_id] = plan
        store.write_json(
            f"chapters/{chapter.chapter_id}/query_plan.json",
            plan.model_dump(mode="json"),
        )

        if not all_results_raw:
            print("No retrieval results")
            continue

        deduped = dedupe_retrieval_results(all_results_raw)
        artifacts.retrieval_results[chapter.chapter_id] = deduped
        store.write_json(
            f"chapters/{chapter.chapter_id}/retrieval_results.json",
            deduped,
        )

        candidates = extract_evidence(analysis.model_dump(), deduped)
        stats.candidates_generated += len(candidates)
        store.write_json(
            f"chapters/{chapter.chapter_id}/candidates.json",
            candidates,
        )
        if not candidates:
            continue

        judged = judge_candidates(analysis.model_dump(), candidates)
        mapped = map_to_sections(chapter, judged)
        ranked = rank_and_select(mapped, top_k=settings.max_updates_per_chapter)
        stats.accepted_candidates += len(ranked)
        store.write_json(
            f"chapters/{chapter.chapter_id}/accepted_updates.json",
            ranked,
        )

        artifacts.judged_candidates[chapter.chapter_id] = [
            AcceptedUpdate(
                chapter_id=chapter.chapter_id,
                mapped_section_id=item.get("mapped_section_id", ""),
                proposed_subsection_id=item.get("proposed_subsection_id"),
                mapping_rationale=item.get("mapping_reason", ""),
                **{
                    key: value
                    for key, value in item.items()
                    if key not in {"mapped_section_id", "proposed_subsection_id", "mapping_reason"}
                },
            )
            for item in ranked
        ]

        if not ranked:
            continue

        written_raw = write_updates(chapter, ranked)
        chapter_written = [_to_written_update(chapter.chapter_id, item) for item in written_raw]
        final_updates.extend(chapter_written)
        store.write_json(
            f"chapters/{chapter.chapter_id}/written_updates.json",
            [item.model_dump(mode="json") for item in chapter_written],
        )
        stats.final_updates += len(chapter_written)

    artifacts.written_updates = final_updates
    artifacts.prompt_traces = [PromptTrace(**trace) for trace in get_prompt_traces()]
    store.write_json(
        "llm/prompt_traces.json",
        [trace.model_dump(mode="json") for trace in artifacts.prompt_traces],
    )

    markdown_path = write_markdown(book, final_updates, settings.canonical_markdown)
    store.write_text("outputs/updated_book.md", markdown_path.read_text(encoding="utf-8"))

    if settings.render_docx:
        ok, engine, manifest_path = export_docx(book, final_updates, settings.output_docx)
        store.write_text("outputs/docx_export_manifest_path.txt", str(manifest_path))
        if ok:
            print(f"DOCX generated via {engine}: {settings.output_docx}")
        else:
            print(f"DOCX export skipped: {engine}")

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
        store.write_text(
            "outputs/export_manifest_path.txt",
            str(export_manifest_path),
        )
        if ok:
            print(f"PDF generated via {engine}: {settings.output_pdf}")
        else:
            print(f"PDF export skipped: {engine}")

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
        "prompt_traces_recorded": len(artifacts.prompt_traces),
    }

    if settings.generate_review_pack:
        review_paths = write_review_pack(store, book, final_updates, artifacts.judged_candidates, summary)
        summary["outputs"]["review_pack"] = review_paths

    store.write_json("run_summary.json", summary)

    print("\n" + "=" * 60)
    print("RUN SUMMARY")
    print("=" * 60)
    print(f"Run ID: {artifacts.run_id}")
    print(f"Chapters processed: {stats.chapters_processed}")
    print(f"Candidates generated: {stats.candidates_generated}")
    print(f"Accepted candidates: {stats.accepted_candidates}")
    print(f"Final updates written: {stats.final_updates}")
    print(f"Total time: {elapsed}s")
    print("=" * 60)

    return summary
