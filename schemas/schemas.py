from typing import List

from pydantic import BaseModel

from core.models import AcceptedUpdate, Book, CandidateUpdate, Chapter, Section


class ChapterAnalysisScore(BaseModel):
    summary: str
    key_concepts: List[str]
    search_queries: List[str]


class JudgeScore(BaseModel):
    relevance: float
    significance: float
    credibility: float
    novelty: float
    pedagogical_fit: float
    final_score: float
    decision: str
    reason: str
