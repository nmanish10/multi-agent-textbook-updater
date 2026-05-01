import re

from core.prompts import prompt_system, prompt_version, render_prompt
from schemas.schemas import WriterOutput
from utils.llm import call_mistral_structured


def is_quality_output(parsed: WriterOutput, section_id: str) -> bool:
    if len(parsed.paragraph_1.split()) < 30 or len(parsed.paragraph_2.split()) < 30:
        return False

    section_pattern = re.compile(rf"section\s+{re.escape(str(section_id))}", re.IGNORECASE)
    if not section_pattern.search(parsed.paragraph_1):
        return False

    return True


def fallback_output(upd, section_id):
    title = upd.get("candidate_title", "Generated Update")

    summary = upd.get("summary", "")
    why = upd.get("why_it_matters", "")

    para1 = (
        f"Building upon the concepts in Section {section_id}, this subsection introduces "
        f"{summary.lower()}, expanding the existing discussion with recent methodological developments."
    )

    para2 = (
        f"This addition is significant because {why.lower()}, helping learners understand how "
        f"modern approaches refine and extend traditional concepts within this domain."
    )

    return f"{title}\n\n{para1}\n\n{para2}"


def get_section_context(chapter, section_id):
    for sec in chapter.sections:
        if sec.section_id == section_id:
            return sec.content[:500]
    return ""


def write_updates(chapter, mapped_updates, max_retries=2):
    final_outputs = []
    prompt_name = "writer_addendum"

    for upd in mapped_updates:
        section_id = upd.get("mapped_section_id")
        section_context = get_section_context(chapter, section_id)

        sources = upd.get("sources", [])
        if not sources and upd.get("url"):
            sources = [
                {
                    "title": upd.get("source_title", ""),
                    "url": upd.get("url"),
                    "date": upd.get("date"),
                    "source_type": upd.get("source_type"),
                }
            ]

        source_url = upd.get("url", "")
        prompt = render_prompt(
            prompt_name,
            chapter_title=chapter.title,
            section_id=section_id,
            section_context=section_context,
            update_summary=upd.get("summary"),
            update_why=upd.get("why_it_matters"),
        )

        try:
            parsed_result = call_mistral_structured(
                prompt,
                WriterOutput,
                system_prompt=prompt_system(prompt_name),
                max_retries=max_retries,
                prompt_name=prompt_name,
                prompt_version=prompt_version(prompt_name),
            )

            if not is_quality_output(parsed_result, section_id):
                print("Writer output failed quality check, using fallback")
                text = fallback_output(upd, section_id)
            else:
                text = f"{parsed_result.title}\n\n{parsed_result.paragraph_1}\n\n{parsed_result.paragraph_2}"

            final_outputs.append(
                {
                    "section_id": section_id,
                    "text": text,
                    "title": parsed_result.title if is_quality_output(parsed_result, section_id) else upd.get("candidate_title", "Generated Update"),
                    "sources": sources,
                    "source": source_url,
                    "why_it_matters": upd.get("why_it_matters", ""),
                    "scores": upd.get("scores", {}),
                    "mapping_rationale": upd.get("mapping_reason", ""),
                }
            )

        except Exception as e:
            print(f"Writer failed ({e}), using fallback")
            fallback = fallback_output(upd, section_id)

            final_outputs.append(
                {
                    "section_id": section_id,
                    "text": fallback,
                    "title": upd.get("candidate_title", "Generated Update"),
                    "sources": sources,
                    "source": source_url,
                    "why_it_matters": upd.get("why_it_matters", ""),
                    "scores": upd.get("scores", {}),
                    "mapping_rationale": upd.get("mapping_reason", ""),
                }
            )

    print(f"\nGenerated {len(final_outputs)} final updates\n")
    return final_outputs
