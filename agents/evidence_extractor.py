from core.prompts import prompt_version
from utils.llm import call_mistral
import json
import re


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
# TOKENIZE
# -------------------------
def tokenize(text):
    return set(re.findall(r"\b[a-z]{3,}\b", text.lower()))


# -------------------------
# CONCEPT ALIGNMENT
# -------------------------
def compute_alignment(concepts, text):
    concept_tokens = set()
    for c in concepts:
        concept_tokens |= tokenize(c)

    text_tokens = tokenize(text)

    if not concept_tokens:
        return 0

    return len(concept_tokens & text_tokens) / len(concept_tokens)


def source_signal_score(result):
    retrieval_score = float(result.get("retrieval_score", 0) or 0)
    credibility_score = float(result.get("credibility_score", 0) or 0)
    return 0.65 * retrieval_score + 0.35 * credibility_score


# -------------------------
# VALIDATION
# -------------------------
def is_valid_candidate(data, concepts):

    if not isinstance(data, dict):
        return False

    title = data.get("candidate_title", "").strip()
    summary = data.get("summary", "").strip()
    why = data.get("why_it_matters", "").strip()

    if not title or not summary or not why:
        return False

    if len(summary.split()) < 10:
        return False

    if len(why.split()) < 10:
        return False

    # 🚨 Reject generic phrasing
    weak_phrases = [
        "this paper discusses",
        "this article talks about",
        "this study explores"
    ]

    if any(p in summary.lower() for p in weak_phrases):
        return False

    # -------------------------
    # ALIGNMENT CHECK
    # -------------------------
    alignment = compute_alignment(concepts, summary)

    if alignment < 0.15:
        return False

    return True


# -------------------------
# MAIN FUNCTION
# -------------------------
def extract_evidence(chapter_analysis, retrieval_results, max_retries=2):

    candidates = []
    concepts = chapter_analysis.get("key_concepts", [])
    retrieval_results = sorted(retrieval_results, key=source_signal_score, reverse=True)

    for result in retrieval_results:

        prompt = f"""
Convert this research into a textbook update.

Chapter Concepts:
{concepts}

Source Title:
{result.get("title")}

Source Summary:
{result.get("summary")}

Tasks:
1. Identify the NEW contribution (not generic)
2. Explain clearly in 2–3 lines
3. Explain why it matters for students

IMPORTANT:
- Focus on methods, models, or theory
- Avoid generic descriptions
- Be specific

Return JSON ONLY:
{{
  "candidate_title": "...",
  "summary": "...",
  "why_it_matters": "...",
  "source_title": "{result.get("title")}",
  "source_type": "{result.get("source_type")}",
  "date": "{result.get("date")}",
  "url": "{result.get("url")}"
}}
"""

        for attempt in range(max_retries + 1):
            response = call_mistral(
                prompt,
                prompt_name="evidence_extraction",
                prompt_version=prompt_version("evidence_extraction"),
            )

            try:
                cleaned = clean_json_response(response)
                parsed = json.loads(cleaned)

                if not is_valid_candidate(parsed, concepts):
                    print(f"⚠️ Weak/irrelevant candidate skipped")
                    continue

                # -------------------------
                # STRUCTURED SOURCE
                # -------------------------
                source_obj = {
                    "title": result.get("title"),
                    "url": result.get("url"),
                    "date": result.get("date"),
                    "source_type": result.get("source_type"),
                    "source_name": result.get("source_name"),
                    "credibility_score": result.get("credibility_score"),
                    "summary": result.get("summary", "")
                }

                parsed["sources"] = [source_obj]

                # Compatibility
                parsed["source_title"] = source_obj["title"]
                parsed["source_type"] = source_obj["source_type"]
                parsed["date"] = source_obj["date"]
                parsed["url"] = source_obj["url"]
                parsed["source_name"] = source_obj["source_name"]
                parsed["retrieval_score"] = result.get("retrieval_score", 0)
                parsed["credibility_score"] = result.get("credibility_score", 0)
                parsed["semantic_score"] = result.get("semantic_score", 0)

                candidates.append(parsed)
                break

            except:
                print("⚠️ Extraction failed")

    print(f"\n📦 Extracted {len(candidates)} valid candidates\n")
    return candidates
