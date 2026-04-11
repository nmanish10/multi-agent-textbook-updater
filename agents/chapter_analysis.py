from utils.llm import call_mistral
import json


def analyze_chapter(chapter):
    prompt = f"""
You are analyzing a textbook chapter.

Your task:
1. Summarize the chapter (5-6 lines, academic tone)
2. Extract 5-8 key concepts (important terms only)
3. Generate 5 high-quality research queries

IMPORTANT:
- Queries MUST be grounded in the chapter's key concepts
- Focus on theoretical, methodological, or algorithmic developments
- Avoid domain-specific applications unless central to the chapter
- Ensure queries stay aligned with the chapter's subject

Chapter Title:
{chapter.title}

Chapter Content:
{chapter.content[:3000]}

Return ONLY valid JSON:
{{
  "summary": "...",
  "key_concepts": ["...", "..."],
  "search_queries": ["...", "..."]
}}
"""

    response = call_mistral(prompt)

    # -------------------------
    # CLEAN RESPONSE (IMPORTANT FIX)
    # -------------------------
    response = response.strip()

    if response.startswith("```"):
        response = response.replace("```json", "").replace("```", "").strip()

    # -------------------------
    # PARSE JSON SAFELY
    # -------------------------
    try:
        return json.loads(response)

    except Exception as e:
        print("⚠️ JSON parsing failed.")
        print("Raw response:")
        print(response)

        return {
            "summary": "",
            "key_concepts": [],
            "search_queries": []
        }