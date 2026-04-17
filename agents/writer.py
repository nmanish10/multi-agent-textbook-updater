from core.prompts import prompt_version
from utils.llm import call_mistral
import re


# -------------------------
# CLEAN TEXT
# -------------------------
def clean_text(response: str):
    response = response.strip()

    if response.startswith("```"):
        response = response.replace("```", "").strip()

    response = response.replace("**", "")
    response = response.replace("*", "")

    response = response.replace("\r", "")
    response = "\n\n".join(
        [block.strip() for block in response.split("\n\n") if block.strip()]
    )

    return response


# -------------------------
# VALIDATION (RELAXED & RESILIENT)
# -------------------------
def is_valid_output(text, section_id):
    parts = text.split("\n\n")

    # Expect title + 2 paragraphs
    if len(parts) < 3:
        return False

    title = parts[0]
    para1 = parts[1]
    para2 = parts[2]

    # Length checks relaxed from 40 to 30 to prevent dropping concise, well-written updates
    if len(para1.split()) < 30 or len(para2.split()) < 30:
        return False

    # Regex search for "Section X.X" to handle case and punctuation differences
    section_pattern = re.compile(rf"section\s+{re.escape(str(section_id))}", re.IGNORECASE)
    if not section_pattern.search(para1):
        return False

    # Avoid generic text, but only if it also missed the proper section pattern
    if "this section" in para1.lower() and not section_pattern.search(para1):
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
        subsection_title = upd.get("proposed_subsection") or upd.get("candidate_title")

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
2. Write exactly two comprehensive paragraphs.
3. Paragraph 1 (Context & Extension): MUST explicitly state "Section {section_id}". Seamlessly bridge the existing textbook concepts with the new update. Explain WHAT the new development is.
4. Paragraph 2 (Implications & Example): Explain WHY this matters to a student in this field. You MUST provide a brief, concrete example or theoretical application of this new concept.

STRICT CONSTRAINTS:
- No markdown formatting, bullet points, or bold text.
- Do not repeat the title in the body.
- Maintain an authoritative, educational tone.

FORMAT:

Subsection Title

Paragraph 1

Paragraph 2
"""

        success = False

        for attempt in range(max_retries + 1):
            response = call_mistral(
                prompt,
                prompt_name="writer_addendum",
                prompt_version=prompt_version("writer_addendum"),
            )

            try:
                cleaned = clean_text(response)

                if not is_valid_output(cleaned, section_id):
                    print(f"⚠️ Writer output invalid (attempt {attempt + 1})")
                    continue

                final_outputs.append({
                    "section_id": section_id,
                    "text": cleaned,
                    "sources": sources,
                    "source": source_url
                })

                success = True
                break

            except Exception:
                print(f"⚠️ Writer failed (attempt {attempt + 1})")

        # -------------------------
        # FALLBACK
        # -------------------------
        if not success:
            print("⚠️ Using fallback writer output")

            fallback = fallback_output(upd, section_id)

            final_outputs.append({
                "section_id": section_id,
                "text": fallback,
                "sources": sources,
                "source": source_url
            })

    print(f"\n📝 Generated {len(final_outputs)} final updates\n")

    return final_outputs
