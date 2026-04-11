from utils.llm import call_mistral


def write_updates(chapter, mapped_updates):
    final_outputs = []

    for upd in mapped_updates:

        section_id = upd.get("mapped_section_id")

        prompt = f"""
You are an expert academic textbook writer.

Your task:
Write a subsection that blends seamlessly into an existing textbook.

Chapter Title:
{chapter.title}

Section:
{section_id}

Subsection Title:
{upd.get("proposed_subsection") or upd.get("candidate_title")}

Content to use:
- Summary: {upd.get("summary")}
- Importance: {upd.get("why_it_matters")}

Instructions:
- Write EXACTLY 2 paragraphs
- Each paragraph should be 3–4 sentences
- Academic tone (like a real textbook)
- Flow naturally from existing content
- Clearly highlight what is NEW compared to traditional approaches
- Do NOT mention "research paper", "study", or sources explicitly
- Do NOT output JSON
- Do NOT include labels like "content", "summary", etc.
- Do NOT repeat the subsection title inside paragraphs

Format EXACTLY like this:

Subsection Title

Paragraph 1...

Paragraph 2...

References:
- reference 1
- reference 2
"""

        response = call_mistral(prompt)

        # -------------------------
        # CLEAN RESPONSE
        # -------------------------
        response = response.strip()

        if response.startswith("```"):
            response = response.replace("```", "").strip()

        # 🔥 Normalize spacing (important for textbook look)
        response = response.replace("\r", "")
        response = "\n".join([line.strip() for line in response.split("\n") if line.strip()])

        final_outputs.append({
            "section_id": section_id,
            "text": response
        })

    return final_outputs