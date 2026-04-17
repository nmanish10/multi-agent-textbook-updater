PROMPT_VERSIONS = {
    "chapter_analysis": "1.0",
    "evidence_extraction": "1.0",
    "judge_candidate": "1.0",
    "section_mapping": "1.0",
    "writer_addendum": "1.0",
}


def prompt_version(name: str) -> str:
    return PROMPT_VERSIONS.get(name, "unversioned")
