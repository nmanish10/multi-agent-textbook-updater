import re
import logging

from core.logging import get_logger, log_event
from core.prompts import prompt_version
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
    author_signal = float(cand.get("author_signal", 0.5) or 0.5)
    venue_score = float(cand.get("venue_score", 0.5) or 0.5)

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
        0.13 * scores["credibility"]
        + 0.57 * source_credibility
        + 0.10 * venue_score
        + 0.10 * author_signal
        + 0.10 * citation_velocity,
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


def judge_candidates(chapter_analysis, candidates, max_retries=2):
    judged = []

    for cand in candidates:
        prompt = f"""
You are a STRICT academic reviewer.

Chapter Summary:
{chapter_analysis.get("summary")}

Key Concepts:
{chapter_analysis.get("key_concepts")}

Candidate:
Title: {cand.get("candidate_title")}
Summary: {cand.get("summary")}
Why it matters: {cand.get("why_it_matters")}
Source: {cand.get("source_type")}
Date: {cand.get("date")}

Score STRICTLY (0-1):

- relevance
- significance
- credibility
- novelty
- pedagogical_fit

Rules:
- Penalize domain-specific or unrelated work
- Reward core algorithmic or theoretical contributions
- Prefer generalizable ideas

Return JSON ONLY:
{{
  "relevance": 0.0,
  "significance": 0.0,
  "credibility": 0.0,
  "novelty": 0.0,
  "pedagogical_fit": 0.0,
  "final_score": 0.0,
  "decision": "accept" or "reject",
  "reason": "short explanation"
}}
"""

        try:
            parsed_result = call_mistral_structured(
                prompt,
                JudgeScore,
                system_prompt="You are a STRICT academic reviewer evaluating new additions for a textbook.",
                max_retries=max_retries,
                prompt_name="judge_candidate",
                prompt_version=prompt_version("judge_candidate"),
            )
            scores = parsed_result.model_dump()
            scores = adjust_scores(cand, scores, chapter_analysis)
            cand["scores"] = scores
            cand["decision"] = scores.get("decision", "reject")
            cand["judge_reason"] = scores.get("reason", "")
            judged.append(cand)
        except Exception as e:
            log_event(logger, logging.WARNING, "Judge failed for candidate", error=str(e), candidate_title=cand.get("candidate_title", ""))

    filtered = [
        cand
        for cand in judged
        if cand["scores"].get("decision") == "accept"
        and cand["scores"].get("final_score", 0) >= 0.78
        and cand["scores"].get("relevance", 0) >= 0.75
        and cand["scores"].get("credibility", 0) >= 0.70
        and cand["scores"].get("significance", 0) >= 0.65
    ]

    log_event(
        logger,
        logging.INFO,
        "Completed candidate judging",
        judged_candidates=len(judged),
        accepted_candidates=len(filtered),
    )
    return filtered
