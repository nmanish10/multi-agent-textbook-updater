from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from agents.evidence_extractor import source_signal_score
from agents.judge import adjust_scores
from agents.retrieval import (
    canonicalize_url,
    compute_credibility,
    evaluate_domain_authority,
    infer_credibility,
    normalize_result,
    retrieve_all_async,
)
from agents.section_mapper import score_sections, top_section_confident


class DecisionQualityTests(unittest.TestCase):
    def test_duckduckgo_urls_are_canonicalized(self) -> None:
        url = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.nist.gov%2Fai"
        self.assertEqual(canonicalize_url(url), "https://nist.gov/ai")

    def test_domain_authority_uses_dynamic_evaluator_and_anchors(self) -> None:
        with patch("agents.retrieval.evaluate_domain_authority", return_value=0.97):
            self.assertGreaterEqual(infer_credibility("web", "https://www.nist.gov/ai"), 0.95)
        with patch("agents.retrieval.evaluate_domain_authority", return_value=0.22):
            self.assertLessEqual(infer_credibility("web", "https://medium.com/some-post"), 0.3)
        with patch("agents.retrieval.evaluate_domain_authority", return_value=0.96):
            self.assertGreaterEqual(infer_credibility("official_source", "https://openai.com/index/hello"), 0.95)

    def test_gov_and_edu_have_non_manual_heuristic_floors(self) -> None:
        with patch("agents.retrieval._cached_domain_score", return_value=0.2):
            self.assertGreaterEqual(evaluate_domain_authority("nist.gov"), 0.88)
            self.assertGreaterEqual(evaluate_domain_authority("mit.edu"), 0.85)

    def test_normalize_result_adds_credibility_and_domain(self) -> None:
        with patch("agents.retrieval.evaluate_domain_authority", return_value=0.96):
            result = normalize_result(
                {
                    "title": "NIST AI Guidance",
                    "summary": "Detailed technical guidance for robust and trustworthy AI systems.",
                    "source": "Web",
                    "source_type": "web",
                    "url": "https://www.nist.gov/ai",
                }
            )
        self.assertEqual(result["domain"], "nist.gov")
        self.assertGreaterEqual(result["credibility_score"], 0.95)

    def test_source_signal_score_prefers_strong_retrieval_and_credibility(self) -> None:
        strong = {"retrieval_score": 0.9, "credibility_score": 0.95, "recency_score": 0.85, "venue_score": 0.9}
        weak = {"retrieval_score": 0.8, "credibility_score": 0.3, "recency_score": 0.4, "venue_score": 0.5}
        self.assertGreater(source_signal_score(strong), source_signal_score(weak))

    def test_multi_signal_credibility_rewards_recent_strong_venue(self) -> None:
        with patch("agents.retrieval.evaluate_domain_authority", side_effect=[0.6, 0.25]):
            recent = compute_credibility(
                {
                    "source_type": "paper",
                    "url": "https://example.com/paper",
                    "date": "2026-03-01",
                    "venue": "Any Venue",
                    "cited_by_count": 140,
                    "influential_citation_count": 24,
                    "author_works_count": 120,
                    "author_cited_by_count": 2400,
                }
            )
            weak = compute_credibility(
                {
                    "source_type": "web",
                    "url": "https://medium.com/post",
                    "date": "2024-01-01",
                    "venue": "",
                    "cited_by_count": 0,
                    "author_works_count": 0,
                    "author_cited_by_count": 0,
                }
            )
        self.assertGreater(recent["credibility_score"], weak["credibility_score"])
        self.assertGreaterEqual(recent["venue_score"], 0.9)

    def test_adjust_scores_uses_source_credibility(self) -> None:
        candidate = {
            "candidate_title": "Robust AI Benchmarking",
            "summary": "A strong benchmark improves trustworthy evaluation of AI systems.",
            "source_type": "web",
            "credibility_score": 0.98,
            "retrieval_score": 0.88,
            "semantic_score": 0.84,
        }
        scores = {
            "relevance": 0.78,
            "significance": 0.76,
            "credibility": 0.75,
            "novelty": 0.8,
            "pedagogical_fit": 0.79,
            "final_score": 0.0,
            "decision": "accept",
            "reason": "strong source",
        }
        chapter_analysis = {"key_concepts": ["benchmarking", "evaluation", "trustworthy AI"]}
        adjusted = adjust_scores(candidate, scores, chapter_analysis)
        self.assertGreaterEqual(adjusted["credibility"], 0.8)
        self.assertIn(adjusted["decision"], {"accept", "reject"})

    def test_adjust_scores_avoids_double_counting_retrieval_credibility(self) -> None:
        candidate = {
            "candidate_title": "Recent Methods",
            "summary": "A highly relevant update for modern model evaluation and benchmarks.",
            "source_type": "paper",
            "credibility_score": 0.9,
            "retrieval_score": 0.6,
            "semantic_score": 0.6,
            "citation_velocity": 1.0,
            "author_signal": 1.0,
            "venue_score": 1.0,
        }
        scores = {
            "relevance": 0.8,
            "significance": 0.8,
            "credibility": 0.4,
            "novelty": 0.7,
            "pedagogical_fit": 0.8,
            "final_score": 0.0,
            "decision": "reject",
            "reason": "test",
        }
        adjusted = adjust_scores(candidate, scores, {"key_concepts": ["evaluation", "benchmarks"]})
        self.assertLessEqual(adjusted["credibility"], 0.8)
        self.assertAlmostEqual(adjusted["credibility"], 0.30 * 0.432 + 0.70 * 0.9, delta=0.03)

    def test_explicit_author_h_index_strengthens_credibility(self) -> None:
        with patch("agents.retrieval.evaluate_domain_authority", return_value=0.6):
            enriched = compute_credibility(
                {
                    "source_type": "paper",
                    "url": "https://example.com/semantic-scholar-paper",
                    "date": "2026-02-01",
                    "venue": "Any Venue",
                    "cited_by_count": 120,
                    "influential_citation_count": 20,
                    "author_h_index": 42,
                }
            )
        self.assertGreaterEqual(enriched["author_signal"], 0.8)
        self.assertGreaterEqual(enriched["credibility_score"], 0.8)

    def test_retrieve_all_async_respects_enabled_sources(self) -> None:
        results = asyncio.run(retrieve_all_async("graph neural networks", enabled_sources=[]))
        self.assertEqual(results, [])

    def test_section_scoring_detects_clear_top_match(self) -> None:
        sections = [
            {"id": "1.1", "title": "Sampling Theory", "text": "Discrete signal sampling and Nyquist analysis."},
            {"id": "1.2", "title": "Transforms", "text": "Fourier, wavelet, and spectral representations."},
            {"id": "1.3", "title": "Control", "text": "Feedback loops and stability."},
        ]
        scored = score_sections("wavelet transforms for spectral analysis", sections)
        self.assertEqual(scored[0][0], "1.2")
        self.assertGreater(scored[0][1]["final_score"], scored[1][1]["final_score"])
        self.assertGreater(scored[0][1]["token_overlap"], 0)
        self.assertTrue(top_section_confident(scored))


if __name__ == "__main__":
    unittest.main()
