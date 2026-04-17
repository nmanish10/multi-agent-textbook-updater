from core.prompts import prompt_version
from utils.llm import call_mistral_structured
from schemas.schemas import ChapterAnalysisScore
import json


# -------------------------
# FALLBACK
# -------------------------
def fallback_output(chapter):
    title = chapter.title

    return {
        "summary": f"This chapter discusses {title} and its core theoretical foundations.",
        "key_concepts": [title],
        "search_queries": [
            f"recent advances in {title}",
            f"{title} machine learning methods",
            f"modern techniques in {title}"
        ]
    }


# -------------------------
# MAIN FUNCTION
# -------------------------
def analyze_chapter(chapter, max_retries=2):

    content = chapter.content[:3000]
    content = content.rsplit(" ", 1)[0]

    prompt = f"""
You are analyzing a textbook chapter for research integration.

Tasks:
1. Write a concise academic summary (5–6 lines)
2. Extract 6–10 key concepts (technical terms only)
3. Generate 5 HIGH-QUALITY research queries

IMPORTANT:
- Queries must be diverse:
  • theoretical advancements
  • algorithmic improvements
  • modern techniques
  • limitations and improvements
- Avoid overly narrow or overly broad queries
- Focus on concepts central to the chapter

Chapter Title:
{chapter.title}

Chapter Content:
{content}

Return JSON ONLY:
{{
  "summary": "...",
  "key_concepts": ["...", "..."],
  "search_queries": ["...", "..."]
}}
"""

    try:
        parsed_result = call_mistral_structured(
            prompt,
            ChapterAnalysisScore,
            system_prompt="You are an expert academic reviewer analyzing a textbook chapter.",
            max_retries=max_retries,
            prompt_name="chapter_analysis",
            prompt_version=prompt_version("chapter_analysis"),
        )
        return parsed_result.model_dump()
        
    except Exception as e:
        print(f"🚨 Falling back to default chapter analysis: {str(e)}")
        return fallback_output(chapter)
