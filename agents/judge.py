import re
import logging

from core.logging import get_logger, log_event
from core.prompts import prompt_system, prompt_version, render_prompt
from schemas.schemas import JudgeScore
from utils.llm import call_mistral_structured

logger = get_logger("textbook_updater.judge")

def tokenize(text):
    text = text.lower()
    return set(re.findall(r"\b[a-z]{3,}\b", text))


def compute_concept_overlap(chapter_analysis, cand):
    concepts = chapter_analysis.get("key_concepts", [])
    concept_tokens = set()
    for concept in concepts:
        concept_tokens |= tokenize(concept)

    cand_text = f"{cand.get('candidate_title') or ''} {cand.get('summary') or ''}"
    cand_tokens = tokenize(cand_text)
    if not concept_tokens:
        return 0
    return len(concept_tokens & cand_tokens) / len(concept_tokens)


def extract_source_credibility(cand):
    if cand.get("credibility_score") is not None:
        return float(cand["credibility_score"])

    sources = cand.get("sources", [])
    if sources:
        score = sources[0].get("credibility_score")
        if score is not None:
            return float(score)
    return 0.5


def adjust_scores(cand, scores, chapter_analysis):
    source_type = cand.get("source_type", "")
    source_credibility = extract_source_credibility(cand)
    retrieval_score = float(cand.get("retrieval_score", 0) or 0)
    semantic_score = float(cand.get("semantic_score", 0) or 0)
    recency_score = float(cand.get("recency_score", 0.5) or 0.5)
    citation_velocity = float(cand.get("citation_velocity", 0.5) or 0.5)

    if source_type == "web":
        scores["credibility"] *= 0.95
    elif source_type == "paper":
        scores["credibility"] = min(scores["credibility"] * 1.08, 1.0)
    elif source_type == "preprint":
        scores["credibility"] *= 0.94
    elif source_type == "official_source":
        scores["credibility"] = min(scores["credibility"] * 1.12, 1.0)
        scores["significance"] = min(scores["significance"] + 0.08, 1.0)

    scores["credibility"] = min(
        1.0,
        0.30 * scores["credibility"]
        + 0.70 * source_credibility,
    )

    overlap = compute_concept_overlap(chapter_analysis, cand)
    scores["relevance"] = min(scores["relevance"] + 0.18 * overlap + 0.08 * semantic_score + 0.04 * recency_score, 1.0)
    scores["significance"] = min(scores["significance"] + 0.05 * retrieval_score + 0.05 * citation_velocity, 1.0)
    scores["novelty"] = min(scores["novelty"] + 0.06 * recency_score, 1.0)

    if overlap < 0.15:
        scores["relevance"] *= 0.68
        scores["significance"] *= 0.78

    if source_credibility < 0.45:
        scores["credibility"] *= 0.82
        scores["final_score"] = min(scores.get("final_score", 0), 0.72)

    scores["final_score"] = (
        0.30 * scores["relevance"]
        + 0.25 * scores["significance"]
        + 0.20 * scores["credibility"]
        + 0.15 * scores["novelty"]
        + 0.10 * scores["pedagogical_fit"]
    )

    if scores["final_score"] >= 0.78 and scores["relevance"] >= 0.75 and scores["credibility"] >= 0.70:
        scores["decision"] = "accept"
    else:
        scores["decision"] = "reject"

    return scores


def judge_candidates(
    chapter_analysis,
    candidates,
    max_retries=2,
    min_accept_score=0.78,
    min_relevance=0.75,
    min_credibility=0.70,
    min_significance=0.65,
):
    judged = []
    prompt_name = "judge_candidate"

    for cand in candidates:
        prompt = render_prompt(
            prompt_name,
            chapter_summary=chapter_analysis.get("summary"),
            key_concepts=chapter_analysis.get("key_concepts"),
            candidate_title=cand.get("candidate_title"),
            candidate_summary=cand.get("summary"),
            candidate_why=cand.get("why_it_matters"),
            source_type=cand.get("source_type"),
            source_date=cand.get("date"),
        )

        try:
            parsed_result = call_mistral_structured(
                prompt,
                JudgeScore,
                system_prompt=prompt_system(prompt_name),
                max_retries=max_retries,
                prompt_name=prompt_name,
                prompt_version=prompt_version(prompt_name),
            )
            scores = parsed_result.model_dump()
            scores = adjust_scores(cand, scores, chapter_analysis)
            cand["scores"] = scores
            cand["decision"] = scores.get("decision", "reject")
            cand["judge_reason"] = scores.get("reason", "")
            judged.append(cand)
        except Exception as e:
            log_event(logger, logging.WARNING, "Judge failed for candidate", error=str(e), candidate_title=cand.get("candidate_title", ""))

    filtered = filter_judged_candidates(
        judged,
        min_accept_score=min_accept_score,
        min_relevance=min_relevance,
        min_credibility=min_credibility,
        min_significance=min_significance,
    )

    log_event(
        logger,
        logging.INFO,
        "Completed candidate judging",
        judged_candidates=len(judged),
        accepted_candidates=len(filtered),
    )
    return filtered


def filter_judged_candidates(
    judged,
    *,
    min_accept_score=0.78,
    min_relevance=0.75,
    min_credibility=0.70,
    min_significance=0.65,
):
    return [
        cand
        for cand in judged
        if cand["scores"].get("decision") == "accept"
        and cand["scores"].get("final_score", 0) >= min_accept_score
        and cand["scores"].get("relevance", 0) >= min_relevance
        and cand["scores"].get("credibility", 0) >= min_credibility
        and cand["scores"].get("significance", 0) >= min_significance
    ]
