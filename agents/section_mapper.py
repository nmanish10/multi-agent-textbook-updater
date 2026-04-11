from utils.llm import call_mistral
import json


def map_to_sections(chapter, updates):
    mapped = []

    # Prepare section info
    sections_text = ""
    for sec in chapter.sections:
        sections_text += f"{sec.section_id}: {sec.title}\n"

    for upd in updates:

        prompt = f"""
You are assigning a textbook update to the most relevant section.

Available Sections:
{sections_text}

Update:
Title: {upd.get("candidate_title")}
Summary: {upd.get("summary")}

Task:
- Choose the BEST matching section_id
- If no section fits well, suggest a new subsection under a relevant section

Return ONLY JSON:
{{
  "mapped_section_id": "...",
  "proposed_subsection": "... or null",
  "reason": "short explanation"
}}
"""

        response = call_mistral(prompt)

        # clean
        response = response.strip()
        if response.startswith("```"):
            response = response.replace("```json", "").replace("```", "").strip()

        try:
            mapping = json.loads(response)

            upd["mapped_section_id"] = mapping.get("mapped_section_id")
            upd["proposed_subsection"] = mapping.get("proposed_subsection")
            upd["mapping_reason"] = mapping.get("reason")

            mapped.append(upd)

        except:
            continue

    return mapped