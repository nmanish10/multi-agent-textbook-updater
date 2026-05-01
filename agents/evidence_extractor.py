import logging
import re

from core.logging import get_logger, log_event
from core.prompts import prompt_system, prompt_version, render_prompt
from schemas.schemas import ExtractedEvidence
from utils.llm import call_mistral_structured


logger = get_logger("textbook_updater.evidence_extractor")


def tokenize(text):
    return set(re.findall(r"\b[a-z]{3,}\b", text.lower()))


def compute_alignment(concepts, text):
    concept_tokens = set()
    for concept in concepts:
        concept_tokens |= tokenize(concept)

    text_tokens = tokenize(text)
    if not concept_tokens:
        return 0
    return len(concept_tokens & text_tokens) / len(concept_tokens)


def source_signal_score(result):
    retrieval_score = float(result.get("retrieval_score", 0) or 0)
    credibility_score = float(result.get("credibility_score", 0) or 0)
    recency_score = float(result.get("recency_score", 0.5) or 0.5)
    venue_score = float(result.get("venue_score", 0.5) or 0.5)
    return 0.45 * retrieval_score + 0.30 * credibility_score + 0.15 * recency_score + 0.10 * venue_score


def is_valid_candidate(data, concepts):
    if not isinstance(data, dict):
        return False

    title = data.get("candidate_title", "").strip()
    summary = data.get("summary", "").strip()
    why = data.get("why_it_matters", "").strip()

    if not title or not summary or not why:
        return False
    if len(summary.split()) < 10 or len(why.split()) < 10:
        return False

    weak_phrases = [
        "this paper discusses",
        "this article talks about",
        "this study explores",
    ]
    if any(phrase in summary.lower() for phrase in weak_phrases):
        return False

    alignment = compute_alignment(concepts, summary)
    return alignment >= 0.15


def extract_evidence(chapter_analysis, retrieval_results, max_retries=2):
    candidates = []
    concepts = chapter_analysis.get("key_concepts", [])
    retrieval_results = sorted(retrieval_results, key=source_signal_score, reverse=True)
    prompt_name = "evidence_extraction"

    for result in retrieval_results:
        prompt = render_prompt(
            prompt_name,
            chapter_concepts=concepts,
            source_title=result.get("title"),
            source_summary=result.get("summary"),
        )

        try:
            parsed_result = call_mistral_structured(
                prompt,
                ExtractedEvidence,
                system_prompt=prompt_system(prompt_name),
                max_retries=max_retries,
                prompt_name=prompt_name,
                prompt_version=prompt_version(prompt_name),
            )
            parsed = parsed_result.model_dump()

            if not is_valid_candidate(parsed, concepts):
                log_event(logger, logging.INFO, "Weak or irrelevant candidate skipped", source_title=result.get("title", ""))
                continue

            source_obj = {
                "title": result.get("title"),
                "url": result.get("url"),
                "date": result.get("date"),
                "source_type": result.get("source_type"),
                "source_name": result.get("source_name"),
                "credibility_score": result.get("credibility_score"),
                "venue": result.get("venue", ""),
                "cited_by_count": result.get("cited_by_count"),
                "citation_velocity": result.get("citation_velocity"),
                "recency_score": result.get("recency_score"),
                "author_signal": result.get("author_signal"),
                "venue_score": result.get("venue_score"),
                "summary": result.get("summary", ""),
            }

            parsed["sources"] = [source_obj]
            parsed["source_title"] = source_obj["title"]
            parsed["source_type"] = source_obj["source_type"]
            parsed["date"] = source_obj["date"]
            parsed["url"] = source_obj["url"]
            parsed["source_name"] = source_obj["source_name"]
            parsed["retrieval_score"] = result.get("retrieval_score", 0)
            parsed["credibility_score"] = result.get("credibility_score", 0)
            parsed["semantic_score"] = result.get("semantic_score", 0)
            parsed["venue"] = result.get("venue", "")
            parsed["cited_by_count"] = result.get("cited_by_count")
            parsed["citation_velocity"] = result.get("citation_velocity")
            parsed["recency_score"] = result.get("recency_score")
            parsed["author_signal"] = result.get("author_signal")
            parsed["venue_score"] = result.get("venue_score")

            candidates.append(parsed)
        except Exception as exc:
            log_event(logger, logging.WARNING, "Evidence extraction failed", error=str(exc), source_title=result.get("title", ""))

    log_event(logger, logging.INFO, "Completed evidence extraction", extracted_candidates=len(candidates))
    return candidates
