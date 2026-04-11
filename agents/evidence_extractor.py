from utils.llm import call_mistral
import json


def extract_evidence(chapter_analysis, retrieval_results):
    candidates = []

    for result in retrieval_results:
        prompt = f"""
You are an academic assistant converting research into textbook updates.

Chapter Summary:
{chapter_analysis.get("summary")}

Key Concepts:
{chapter_analysis.get("key_concepts")}

Source Title:
{result.get("title")}

Source Summary:
{result.get("summary")}

Your task:
1. Identify what NEW development or idea this source introduces
2. Explain it clearly in 2-3 lines
3. Explain why it matters to students

Return ONLY JSON:
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

        response = call_mistral(prompt)

        # clean JSON
        response = response.strip()
        if response.startswith("```"):
            response = response.replace("```json", "").replace("```", "").strip()

        try:
            parsed = json.loads(response)
            candidates.append(parsed)
        except:
            continue

    return candidates