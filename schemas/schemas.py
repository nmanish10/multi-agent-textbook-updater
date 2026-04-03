from typing import List, Dict, Optional


# -------------------------
# SECTION
# -------------------------
class Section:
    def __init__(self, section_id: str, title: str, content: str):
        self.section_id = section_id
        self.title = title
        self.content = content


# -------------------------
# CHAPTER
# -------------------------
class Chapter:
    def __init__(
        self,
        chapter_id: str,
        title: str,
        content: str,
        sections: List[Section]
    ):
        self.chapter_id = chapter_id
        self.title = title
        self.content = content
        self.sections = sections


# -------------------------
# BOOK
# -------------------------
class Book:
    def __init__(
        self,
        book_title: str,
        chapters: List[Chapter]
    ):
        self.book_title = book_title
        self.chapters = chapters


# -------------------------
# CANDIDATE UPDATE (Raw from sources)
# -------------------------
class CandidateUpdate:
    def __init__(
        self,
        candidate_title: str,
        summary: str,
        source_type: str,
        source_title: str,
        date: str,
        url: str
    ):
        self.candidate_title = candidate_title
        self.summary = summary
        self.source_type = source_type
        self.source_title = source_title
        self.date = date
        self.url = url


# -------------------------
# ACCEPTED UPDATE (After scoring)
# -------------------------
class AcceptedUpdate:
    def __init__(
        self,
        chapter_id: str,
        mapped_section_id: str,
        proposed_subsection_id: Optional[str],
        title: str,
        summary: str,
        why_it_matters: str,
        sources: List[Dict],
        scores: Dict,
        mapping_rationale: str,
        status: str = "accepted"
    ):
        self.chapter_id = chapter_id
        self.mapped_section_id = mapped_section_id
        self.proposed_subsection_id = proposed_subsection_id
        self.title = title
        self.summary = summary
        self.why_it_matters = why_it_matters
        self.sources = sources
        self.scores = scores
        self.mapping_rationale = mapping_rationale
        self.status = status