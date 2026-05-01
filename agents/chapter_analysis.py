from core.prompts import prompt_system, prompt_version, render_prompt
from schemas.schemas import ChapterAnalysisScore
from utils.llm import call_mistral_structured


def fallback_output(chapter):
    title = chapter.title

    return {
        "summary": f"This chapter discusses {title} and its core theoretical foundations.",
        "key_concepts": [title],
        "search_queries": [
            f"recent advances in {title}",
            f"{title} machine learning methods",
            f"modern techniques in {title}",
        ],
    }


def analyze_chapter(chapter, max_retries=2):
    content = chapter.content[:3000]
    content = content.rsplit(" ", 1)[0]
    prompt_name = "chapter_analysis"
    prompt = render_prompt(
        prompt_name,
        chapter_title=chapter.title,
        chapter_content=content,
    )

    try:
        parsed_result = call_mistral_structured(
            prompt,
            ChapterAnalysisScore,
            system_prompt=prompt_system(prompt_name),
            max_retries=max_retries,
            prompt_name=prompt_name,
            prompt_version=prompt_version(prompt_name),
        )
        return parsed_result.model_dump()
    except Exception as e:
        print(f"Falling back to default chapter analysis: {str(e)}")
        return fallback_output(chapter)
