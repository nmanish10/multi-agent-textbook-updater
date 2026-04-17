from __future__ import annotations

from typing import List

from core.models import ChapterAnalysis, SearchQueryPlan


def refine_query(query: str, concepts: List[str]) -> str:
    concept_str = ", ".join(concepts[:3])
    return f"{query} focusing on {concept_str}" if concept_str else query


def build_query_plan(chapter_id: str, analysis: ChapterAnalysis, demo_mode: bool = True) -> SearchQueryPlan:
    queries = analysis.search_queries[:1] if demo_mode else list(analysis.search_queries)
    refined = [refine_query(query, analysis.key_concepts) for query in queries]
    return SearchQueryPlan(
        chapter_id=chapter_id,
        base_queries=queries,
        refined_queries=refined,
        reasoning_summary=(
            f"Derived {len(refined)} retrieval queries from chapter concepts: "
            + ", ".join(analysis.key_concepts[:5])
        ).strip(),
    )
