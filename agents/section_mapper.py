from __future__ import annotations

import logging
import re
from typing import Iterable

from core.logging import get_logger, log_event
from core.prompts import prompt_system, prompt_version, render_prompt
from schemas.schemas import SectionMapping
from utils.llm import call_mistral_structured

try:
    from agents.retrieval import get_embedding_model, util
except Exception:  # pragma: no cover - defensive fallback only
    get_embedding_model = None
    util = None


logger = get_logger("textbook_updater.section_mapper")


def tokenize(text):
    text = text.lower()
    words = re.findall(r"\b[a-z]{3,}\b", text)
    return set(words)


def build_sections_context(chapter):
    context = []
    for sec in chapter.sections:
        content_preview = sec.content[:400]
        context.append(
            {
                "id": sec.section_id,
                "title": sec.title,
                "text": content_preview,
            }
        )
    return context


def _semantic_similarity(update_text: str, section_text: str) -> float:
    if not get_embedding_model or not util:
        return 0.0
    if not update_text.strip() or not section_text.strip():
        return 0.0
    model = get_embedding_model()
    if model is None:
        return 0.0
    update_emb = model.encode(update_text, convert_to_tensor=True)
    section_emb = model.encode(section_text, convert_to_tensor=True)
    return float(util.cos_sim(update_emb, section_emb)[0][0].item())


def score_sections(update_text, sections):
    update_tokens = tokenize(update_text)
    scores = []

    for sec in sections:
        section_title_tokens = tokenize(sec["title"])
        section_tokens = tokenize(sec["title"] + " " + sec["text"])

        token_overlap = 0.0
        if update_tokens:
            token_overlap = len(update_tokens & section_tokens) / max(len(update_tokens), 1)

        title_overlap = 0.0
        if update_tokens:
            title_overlap = len(update_tokens & section_title_tokens) / max(len(update_tokens), 1)

        semantic_score = _semantic_similarity(update_text, f"{sec['title']}\n{sec['text']}")
        final_score = round(0.45 * semantic_score + 0.35 * token_overlap + 0.20 * title_overlap, 4)
        scores.append(
            (
                sec["id"],
                {
                    "final_score": final_score,
                    "semantic_score": round(semantic_score, 4),
                    "token_overlap": round(token_overlap, 4),
                    "title_overlap": round(title_overlap, 4),
                },
            )
        )

    scores.sort(key=lambda item: item[1]["final_score"], reverse=True)
    return scores


def is_valid_section(section_id, chapter):
    return any(sec.section_id == section_id for sec in chapter.sections)


def smart_fallback(chapter, update_text):
    sections = build_sections_context(chapter)
    scores = score_sections(update_text, sections)

    if not scores:
        return None

    return scores[0][0]


def top_section_confident(scored):
    if not scored:
        return False
    if len(scored) < 2:
        return scored[0][1]["final_score"] >= 0.18
    top = scored[0][1]["final_score"]
    second = scored[1][1]["final_score"]
    return top >= 0.24 and top >= second + 0.08


def _scored_lookup(scored: Iterable[tuple[str, dict]]) -> dict[str, dict]:
    return {section_id: score_data for section_id, score_data in scored}


def map_to_sections(chapter, updates, max_retries=2):
    mapped = []
    sections = build_sections_context(chapter)
    prompt_name = "section_mapping"

    for upd in updates:
        update_text = ((upd.get("candidate_title") or "") + " " + (upd.get("summary") or "")).strip()
        scored = score_sections(update_text, sections)
        scored_lookup = _scored_lookup(scored)
        top_sections = [sid for sid, _ in scored[:3]]

        if scored and top_section_confident(scored):
            best_id, best_score = scored[0]
            upd["mapped_section_id"] = best_id
            upd["mapping_reason"] = (
                "High-confidence hybrid match "
                f"(semantic={best_score['semantic_score']}, token={best_score['token_overlap']}, "
                f"title={best_score['title_overlap']})"
            )
            upd["mapping_score"] = best_score["final_score"]
            upd["mapping_breakdown"] = best_score
            mapped.append(upd)
            continue

        context_text = ""
        for sec in sections:
            if sec["id"] in top_sections:
                context_text += f"{sec['id']}: {sec['title']}\n{sec['text']}\n\n"

        prompt = render_prompt(
            prompt_name,
            sections_context=context_text,
            update_text=update_text,
        )

        try:
            parsed_result = call_mistral_structured(
                prompt,
                SectionMapping,
                system_prompt=prompt_system(prompt_name),
                max_retries=max_retries,
                prompt_name=prompt_name,
                prompt_version=prompt_version(prompt_name),
            )

            section_id = parsed_result.mapped_section_id

            if not is_valid_section(section_id, chapter):
                log_event(
                    logger,
                    logging.WARNING,
                    "LLM returned invalid section id; applying fallback",
                    returned_section_id=section_id,
                    chapter_id=chapter.chapter_id,
                )
                fallback_id = smart_fallback(chapter, update_text)
                if fallback_id:
                    upd["mapped_section_id"] = fallback_id
                    upd["mapping_reason"] = "Hybrid fallback (LLM returned invalid section)"
                    upd["mapping_score"] = scored_lookup.get(fallback_id, {}).get("final_score", 0.0)
                    upd["mapping_breakdown"] = scored_lookup.get(fallback_id, {})
                    mapped.append(upd)
                continue

            upd["mapped_section_id"] = section_id
            upd["mapping_reason"] = parsed_result.reason
            upd["mapping_score"] = scored_lookup.get(section_id, {}).get("final_score", 0.0)
            upd["mapping_breakdown"] = scored_lookup.get(section_id, {})
            mapped.append(upd)

        except Exception as exc:
            log_event(
                logger,
                logging.WARNING,
                "Section mapping failed; applying fallback",
                chapter_id=chapter.chapter_id,
                error=str(exc),
            )
            fallback_id = smart_fallback(chapter, update_text)

            if fallback_id:
                upd["mapped_section_id"] = fallback_id
                upd["mapping_reason"] = "Hybrid fallback"
                upd["mapping_score"] = scored_lookup.get(fallback_id, {}).get("final_score", 0.0)
                upd["mapping_breakdown"] = scored_lookup.get(fallback_id, {})
                mapped.append(upd)

    log_event(
        logger,
        logging.INFO,
        "Completed section mapping",
        chapter_id=chapter.chapter_id,
        mapped_updates=len(mapped),
        candidate_updates=len(updates),
    )
    return mapped
