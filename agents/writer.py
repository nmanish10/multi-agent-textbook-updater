import re

from core.prompts import prompt_version
from schemas.schemas import WriterOutput
from utils.llm import call_mistral_structured


# -------------------------
# CONTENT VALIDATION (post-structured-output)
# -------------------------
def is_quality_output(parsed: WriterOutput, section_id: str) -> bool:
    """Validate content quality AFTER successful structured parsing.
    Structure is guaranteed by Pydantic — this checks semantic quality."""

    # Word count check (relaxed from 40 to 30 to prevent dropping concise, well-written updates)
    if len(parsed.paragraph_1.split()) < 30 or len(parsed.paragraph_2.split()) < 30:
        return False

    # Check that paragraph 1 references the target section
    section_pattern = re.compile(rf"section\s+{re.escape(str(section_id))}", re.IGNORECASE)
    if not section_pattern.search(parsed.paragraph_1):
        return False

    return True


# -------------------------
# BETTER FALLBACK
# -------------------------
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


# -------------------------
# BUILD SECTION CONTEXT
# -------------------------
def get_section_context(chapter, section_id):
    for sec in chapter.sections:
        if sec.section_id == section_id:
            return sec.content[:500]
    return ""


# -------------------------
# MAIN FUNCTION
# -------------------------
def write_updates(chapter, mapped_updates, max_retries=2):

    final_outputs = []

    for upd in mapped_updates:

        section_id = upd.get("mapped_section_id")

        section_context = get_section_context(chapter, section_id)

        sources = upd.get("sources", [])
        if not sources and upd.get("url"):
            sources = [{
                "title": upd.get("source_title", ""),
                "url": upd.get("url"),
                "date": upd.get("date"),
                "source_type": upd.get("source_type")
            }]

        source_url = upd.get("url", "")

        # -------------------------
        # RECONSTRUCTIVE PROMPT
        # -------------------------
        prompt = f"""
You are an expert academic textbook writer and editor. Your task is to write a HIGH-QUALITY textbook addendum that updates an existing section with new research.

Chapter: {chapter.title}
Target Section: {section_id}

[EXISTING SECTION CONTEXT (May contain OCR/extraction errors)]
{section_context}

[NEW UPDATE TO INTEGRATE]
- Concept: {upd.get("summary")}
- Importance: {upd.get("why_it_matters")}

INSTRUCTIONS:
1. Ignore any fragmented sentences, merged words, or typographical errors in the Existing Section Context. Extract only the core meaning.
2. For "title": write a concise, descriptive subsection title.
3. For "paragraph_1" (Context & Extension): MUST explicitly state "Section {section_id}". Seamlessly bridge the existing textbook concepts with the new update. Explain WHAT the new development is.
4. For "paragraph_2" (Implications & Example): Explain WHY this matters to a student in this field. You MUST provide a brief, concrete example or theoretical application of this new concept.

STRICT CONSTRAINTS:
- No markdown formatting, bullet points, or bold text.
- Do not repeat the title in the paragraphs.
- Maintain an authoritative, educational tone.
- Each paragraph must be at least 30 words.
"""

        try:
            parsed_result = call_mistral_structured(
                prompt,
                WriterOutput,
                system_prompt="You are an expert academic textbook writer producing high-quality textbook addenda.",
                max_retries=max_retries,
                prompt_name="writer_addendum",
                prompt_version=prompt_version("writer_addendum"),
            )

            if not is_quality_output(parsed_result, section_id):
                print(f"⚠️ Writer output failed quality check, using fallback")
                text = fallback_output(upd, section_id)
            else:
                # Reconstruct text in the expected downstream format
                text = f"{parsed_result.title}\n\n{parsed_result.paragraph_1}\n\n{parsed_result.paragraph_2}"

            final_outputs.append({
                "section_id": section_id,
                "text": text,
                "sources": sources,
                "source": source_url,
                "why_it_matters": upd.get("why_it_matters", ""),
                "scores": upd.get("scores", {}),
                "mapping_rationale": upd.get("mapping_reason", ""),
            })

        except Exception as e:
            # -------------------------
            # FALLBACK
            # -------------------------
            print(f"⚠️ Writer failed ({e}), using fallback")

            fallback = fallback_output(upd, section_id)

            final_outputs.append({
                "section_id": section_id,
                "text": fallback,
                "sources": sources,
                "source": source_url,
                "why_it_matters": upd.get("why_it_matters", ""),
                "scores": upd.get("scores", {}),
                "mapping_rationale": upd.get("mapping_reason", ""),
            })

    print(f"\n📝 Generated {len(final_outputs)} final updates\n")

    return final_outputs
