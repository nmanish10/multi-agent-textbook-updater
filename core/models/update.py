from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SourceRecord(BaseModel):
    title: str = ""
    url: str = ""
    date: str | int | None = ""
    source_type: str = ""
    source_name: str = ""
    credibility_score: Optional[float] = None
    summary: str = ""


class ChapterAnalysis(BaseModel):
    summary: str
    key_concepts: List[str] = Field(default_factory=list)
    search_queries: List[str] = Field(default_factory=list)
    likely_outdated_topics: List[str] = Field(default_factory=list)
    section_concept_map: Dict[str, List[str]] = Field(default_factory=dict)


class SearchQueryPlan(BaseModel):
    chapter_id: str
    base_queries: List[str] = Field(default_factory=list)
    refined_queries: List[str] = Field(default_factory=list)
    reasoning_summary: str = ""


class CandidateUpdate(BaseModel):
    candidate_title: str
    summary: str
    why_it_matters: str
    source_type: str = ""
    source_title: str = ""
    date: str | int | None = ""
    url: str = ""
    sources: List[SourceRecord] = Field(default_factory=list)


class JudgedCandidate(CandidateUpdate):
    scores: Dict[str, Any] = Field(default_factory=dict)
    decision: str = "reject"
    reason: str = ""


class AcceptedUpdate(JudgedCandidate):
    chapter_id: str = ""
    mapped_section_id: str = ""
    proposed_subsection_id: Optional[str] = None
    mapping_rationale: str = ""
    status: str = "accepted"


class WrittenUpdate(BaseModel):
    chapter_id: str
    section_id: str
    proposed_subsection_id: Optional[str] = None
    title: str
    text: str
    why_it_matters: str = ""
    sources: List[SourceRecord] = Field(default_factory=list)
    source: str = ""
    scores: Dict[str, Any] = Field(default_factory=dict)
    mapping_rationale: str = ""


class RunStats(BaseModel):
    chapters_processed: int = 0
    candidates_generated: int = 0
    accepted_candidates: int = 0
    final_updates: int = 0


class PromptTrace(BaseModel):
    prompt_name: str
    prompt_version: str
    model_chain: List[str] = Field(default_factory=list)
    structured: bool = False
    temperature: float = 0.0
    used_system_prompt: bool = False
    cache_hit: bool = False


class RunArtifacts(BaseModel):
    run_id: str
    input_file: str
    started_at: datetime
    output_directory: str
    analysis_by_chapter: Dict[str, ChapterAnalysis] = Field(default_factory=dict)
    query_plans: Dict[str, SearchQueryPlan] = Field(default_factory=dict)
    retrieval_results: Dict[str, List[Dict]] = Field(default_factory=dict)
    judged_candidates: Dict[str, List[AcceptedUpdate]] = Field(default_factory=dict)
    written_updates: List[WrittenUpdate] = Field(default_factory=list)
    prompt_traces: List[PromptTrace] = Field(default_factory=list)
