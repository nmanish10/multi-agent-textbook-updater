import re
from difflib import SequenceMatcher
from collections import defaultdict


# -------------------------
# TEXT NORMALIZATION
# -------------------------
def normalize_text(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    tokens = text.split()
    return set(tokens)


# -------------------------
# JACCARD SIMILARITY
# -------------------------
def jaccard_similarity(set1, set2):
    if not set1 or not set2:
        return 0.0
    return len(set1 & set2) / len(set1 | set2)


# -------------------------
# STRING SIMILARITY
# -------------------------
def string_similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


# -------------------------
# COMBINED SIMILARITY
# -------------------------
def combined_similarity(cand, sel):
    cand_title = cand.get("candidate_title", "")
    cand_summary = cand.get("summary", "")

    sel_title = sel.get("candidate_title", "")
    sel_summary = sel.get("summary", "")

    # Token-based
    title_j = jaccard_similarity(
        normalize_text(cand_title),
        normalize_text(sel_title)
    )

    summary_j = jaccard_similarity(
        normalize_text(cand_summary),
        normalize_text(sel_summary)
    )

    # String-based
    title_s = string_similarity(cand_title, sel_title)
    summary_s = string_similarity(cand_summary, sel_summary)

    # Weighted score
    return max(
        0.4 * title_j + 0.6 * summary_j,
        0.4 * title_s + 0.6 * summary_s
    )


# -------------------------
# DUPLICATE CHECK (STRONGER)
# -------------------------
def is_duplicate(cand, selected, threshold=0.7):
    for sel in selected:
        sim = combined_similarity(cand, sel)

        if sim > threshold:
            print(f"⚠️ Duplicate filtered (sim={sim:.2f}): {cand.get('candidate_title')[:60]}")
            return True

    return False


# -------------------------
# SCORE FILTER
# -------------------------
def is_high_quality(cand, min_score=0.75):
    score = cand.get("scores", {}).get("final_score", 0)
    decision = cand.get("scores", {}).get("decision", cand.get("decision", "reject"))
    return score >= min_score and decision == "accept"


# -------------------------
# MAIN RANKING FUNCTION
# -------------------------
def rank_and_select(candidates, top_k=3):

    if not candidates:
        return []

    # -------------------------
    # FILTER LOW QUALITY
    # -------------------------
    candidates = [c for c in candidates if is_high_quality(c)]

    if not candidates:
        print("⚠️ No high-quality candidates after filtering")
        return []

    # -------------------------
    # SORT BY SCORE
    # -------------------------
    candidates = sorted(
        candidates,
        key=lambda x: (
            x.get("scores", {}).get("final_score", 0),
            x.get("mapping_score", 0),
            x.get("retrieval_score", 0),
        ),
        reverse=True
    )

    selected = []
    section_counts = defaultdict(int)

    for cand in candidates:

        # -------------------------
        # DUPLICATE FILTER
        # -------------------------
        if is_duplicate(cand, selected):
            continue

        section_id = cand.get("mapped_section_id")

        # -------------------------
        # DIVERSITY CONTROL
        # -------------------------
        if section_id:
            if section_counts[section_id] >= 2:
                # Avoid overloading same section
                continue

        selected.append(cand)

        if section_id:
            section_counts[section_id] += 1

        if len(selected) >= top_k:
            break

    print(f"\n🏆 Selected {len(selected)} final updates\n")

    return selected
