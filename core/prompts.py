PROMPT_VERSIONS = {
    "chapter_analysis": "1.0",
    "evidence_extraction": "2.0",
    "judge_candidate": "1.0",
    "section_mapping": "2.0",
    "writer_addendum": "2.0",
}


def prompt_version(name: str) -> str:
    return PROMPT_VERSIONS.get(name, "unversioned")
