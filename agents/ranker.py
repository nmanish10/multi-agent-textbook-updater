import logging
import re
from collections import defaultdict
from difflib import SequenceMatcher

from core.logging import get_logger, log_event


logger = get_logger("textbook_updater.ranker")


def normalize_text(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return set(text.split())


def jaccard_similarity(set1, set2):
    if not set1 or not set2:
        return 0.0
    return len(set1 & set2) / len(set1 | set2)


def string_similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def combined_similarity(cand, sel):
    cand_title = cand.get("candidate_title", "")
    cand_summary = cand.get("summary", "")
    sel_title = sel.get("candidate_title", "")
    sel_summary = sel.get("summary", "")

    title_j = jaccard_similarity(normalize_text(cand_title), normalize_text(sel_title))
    summary_j = jaccard_similarity(normalize_text(cand_summary), normalize_text(sel_summary))
    title_s = string_similarity(cand_title, sel_title)
    summary_s = string_similarity(cand_summary, sel_summary)

    return max(0.4 * title_j + 0.6 * summary_j, 0.4 * title_s + 0.6 * summary_s)


def is_duplicate(cand, selected, threshold=0.7):
    for sel in selected:
        sim = combined_similarity(cand, sel)
        if sim > threshold:
            log_event(logger, logging.INFO, "Duplicate candidate filtered", similarity=round(sim, 2), candidate_title=cand.get("candidate_title", "")[:60])
            return True
    return False


def is_high_quality(cand, min_score=0.75):
    score = cand.get("scores", {}).get("final_score", 0)
    decision = cand.get("scores", {}).get("decision", cand.get("decision", "reject"))
    return score >= min_score and decision == "accept"


def _candidate_sort_key(candidate):
    return (
        candidate.get("scores", {}).get("final_score", 0),
        candidate.get("mapping_score", 0),
        candidate.get("retrieval_score", 0),
    )


def rank_and_select(candidates, top_k=3, min_score=0.75):
    if not candidates:
        return []

    candidates = [candidate for candidate in candidates if is_high_quality(candidate, min_score=min_score)]
    if not candidates:
        log_event(logger, logging.INFO, "No high-quality candidates after filtering")
        return []

    candidates = sorted(candidates, key=_candidate_sort_key, reverse=True)
    selected = []
    section_counts = defaultdict(int)

    for cand in candidates:
        if is_duplicate(cand, selected):
            continue

        section_id = cand.get("mapped_section_id")
        if section_id and section_counts[section_id] >= 2:
            continue

        selected.append(cand)
        if section_id:
            section_counts[section_id] += 1
        if len(selected) >= top_k:
            break

    log_event(logger, logging.INFO, "Selected final updates", selected_updates=len(selected), requested_top_k=top_k)
    return selected


def competitive_replacement(existing_updates, new_updates, threshold=5, min_score=0.75):
    combined = list(existing_updates) + list(new_updates)
    if not combined:
        return [], []

    survivors = rank_and_select(combined, top_k=threshold, min_score=min_score)
    survivor_keys = {
        (
            item.get("candidate_title", ""),
            item.get("mapped_section_id", ""),
            item.get("source_title", ""),
            item.get("url", ""),
        )
        for item in survivors
    }
    removed = []
    for item in combined:
        key = (
            item.get("candidate_title", ""),
            item.get("mapped_section_id", ""),
            item.get("source_title", ""),
            item.get("url", ""),
        )
        if key not in survivor_keys:
            removed.append(item)

    log_event(
        logger,
        logging.INFO,
        "Competitive replacement completed",
        existing_updates=len(existing_updates),
        new_updates=len(new_updates),
        threshold=threshold,
        survivors=len(survivors),
        removed=len(removed),
    )
    return survivors, removed
