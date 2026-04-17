import re
import json
from core.prompts import prompt_version
from utils.llm import call_mistral


# -------------------------
# CLEAN JSON
# -------------------------
def clean_json_response(response: str):
    response = response.strip()

    if response.startswith("```"):
        response = response.replace("```json", "").replace("```", "").strip()

    match = re.search(r"\{.*\}", response, re.DOTALL)
    if match:
        return match.group(0)

    return response


# -------------------------
# TEXT NORMALIZATION
# -------------------------
def tokenize(text):
    text = text.lower()
    words = re.findall(r"\b[a-z]{3,}\b", text)
    return set(words)


# -------------------------
# BUILD SECTION CONTEXT
# -------------------------
def build_sections_context(chapter):
    context = []
    for sec in chapter.sections:
        content_preview = sec.content[:300]
        context.append({
            "id": sec.section_id,
            "title": sec.title,
            "text": content_preview
        })
    return context


# -------------------------
# HEURISTIC SCORING
# -------------------------
def score_sections(update_text, sections):
    update_tokens = tokenize(update_text)
    scores = []

    for sec in sections:
        section_tokens = tokenize(sec["title"] + " " + sec["text"])

        overlap = len(update_tokens & section_tokens)

        title_overlap = len(update_tokens & tokenize(sec["title"]))
        weighted_score = overlap + 1.5 * title_overlap
        scores.append((sec["id"], weighted_score))

    # sort descending
    scores.sort(key=lambda x: x[1], reverse=True)

    return scores


# -------------------------
# VALIDATION
# -------------------------
def is_valid_section(section_id, chapter):
    return any(sec.section_id == section_id for sec in chapter.sections)


# -------------------------
# SMART FALLBACK
# -------------------------
def smart_fallback(chapter, update_text):
    """
    Instead of first section → pick best heuristic match
    """
    sections = build_sections_context(chapter)
    scores = score_sections(update_text, sections)

    if not scores:
        return None

    best_id = scores[0][0]

    return best_id


def top_section_confident(scored):
    if len(scored) < 2:
        return True
    return scored[0][1] >= max(2, scored[1][1] + 2)


# -------------------------
# MAIN FUNCTION
# -------------------------
def map_to_sections(chapter, updates, max_retries=2):

    mapped = []

    sections = build_sections_context(chapter)

    for upd in updates:

        update_text = (
            (upd.get("candidate_title") or "") + " " +
            (upd.get("summary") or "")
        )

        # -------------------------
        # HEURISTIC SHORTLIST
        # -------------------------
        scored = score_sections(update_text, sections)

        top_sections = [sid for sid, _ in scored[:3]]

        if scored and top_section_confident(scored):
            best_id, best_score = scored[0]
            upd["mapped_section_id"] = best_id
            upd["mapping_reason"] = f"Heuristic high-confidence match (score={best_score})"
            upd["mapping_score"] = best_score
            mapped.append(upd)
            continue

        # Build context only for top sections
        context_text = ""
        for sec in sections:
            if sec["id"] in top_sections:
                context_text += (
                    f"{sec['id']}: {sec['title']}\n"
                    f"{sec['text']}\n\n"
                )

        prompt = f"""
You are mapping an update to the best textbook section.

Sections:
{context_text}

Update:
{update_text}

Rules:
- Choose the MOST relevant section_id
- Only choose from the given section_ids
- Prefer deeper conceptual match, not keyword match
- Do NOT guess randomly

Return ONLY JSON:
{{
  "mapped_section_id": "...",
  "reason": "short explanation"
}}
"""

        success = False

        for attempt in range(max_retries + 1):
            response = call_mistral(
                prompt,
                prompt_name="section_mapping",
                prompt_version=prompt_version("section_mapping"),
            )

            try:
                cleaned = clean_json_response(response)
                mapping = json.loads(cleaned)

                section_id = mapping.get("mapped_section_id")

                if not is_valid_section(section_id, chapter):
                    print(f"⚠️ Invalid section_id (attempt {attempt+1})")
                    continue

                upd["mapped_section_id"] = section_id
                upd["mapping_reason"] = mapping.get("reason")
                upd["mapping_score"] = dict(scored).get(section_id, 0)

                mapped.append(upd)
                success = True
                break

            except Exception:
                print(f"⚠️ Mapping failed (attempt {attempt+1})")

        # -------------------------
        # FALLBACK (SMART)
        # -------------------------
        if not success:
            print("⚠️ Using SMART fallback")

            fallback_id = smart_fallback(chapter, update_text)

            if fallback_id:
                upd["mapped_section_id"] = fallback_id
                upd["mapping_reason"] = "Heuristic fallback"
                upd["mapping_score"] = dict(scored).get(fallback_id, 0)

                mapped.append(upd)

    print(f"\n🧭 Mapped {len(mapped)} updates to sections\n")

    return mapped
