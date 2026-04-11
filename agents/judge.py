from utils.llm import call_mistral
import json


def judge_candidates(chapter_analysis, candidates):
    judged = []

    for cand in candidates:

        prompt = f"""
You are a STRICT but practical academic reviewer deciding whether a research update should be added to a textbook chapter.

Chapter Summary:
{chapter_analysis.get("summary")}

Key Concepts:
{chapter_analysis.get("key_concepts")}

Candidate Update:
Title: {cand.get("candidate_title")}
Summary: {cand.get("summary")}
Why it matters: {cand.get("why_it_matters")}
Source Type: {cand.get("source_type")}
Date: {cand.get("date")}

-----------------------------
EVALUATION INSTRUCTIONS
-----------------------------

Score the candidate from 0 to 1 on:

1. relevance (to core chapter concepts ONLY)
2. significance (importance of idea)
3. credibility (paper > preprint > web)
4. novelty (new vs textbook)
5. pedagogical_fit (useful for students)

-----------------------------
STRICT GUIDELINES
-----------------------------

Prefer HIGH relevance to core AI concepts:
- Algorithms
- Problem-solving
- Knowledge representation
- Data-driven models
- Computational methods

Reject or score LOW if:
- Domain-specific application (e.g., agriculture, biology, IoT)
- Weak conceptual contribution
- Only application, not theory
- Indirect connection to chapter

-----------------------------
FINAL SCORE FORMULA
-----------------------------

final_score =
0.30 * relevance +
0.25 * significance +
0.20 * credibility +
0.15 * novelty +
0.10 * pedagogical_fit

-----------------------------
OUTPUT FORMAT (JSON ONLY)
-----------------------------

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

        response = call_mistral(prompt)

        # -------------------------
        # CLEAN RESPONSE
        # -------------------------
        response = response.strip()

        if response.startswith("```"):
            response = response.replace("```json", "").replace("```", "").strip()

        # -------------------------
        # PARSE JSON
        # -------------------------
        try:
            scores = json.loads(response)

            cand["scores"] = scores
            cand["decision"] = scores.get("decision", "reject")

            judged.append(cand)

        except Exception:
            continue

    # -------------------------
    # DEBUG (VERY USEFUL)
    # -------------------------
    print("\n📊 Candidate Scores:")
    for c in judged:
        print(
            f"- {c.get('candidate_title')[:50]} | "
            f"Score: {c['scores'].get('final_score', 0):.2f} | "
            f"Relevance: {c['scores'].get('relevance', 0):.2f}"
        )

    # -------------------------
    # BALANCED FILTER (FINAL)
    # -------------------------
    filtered = [
        c for c in judged
        if c["scores"].get("final_score", 0) >= 0.70
        and c["scores"].get("relevance", 0) >= 0.65
    ]

    return filtered