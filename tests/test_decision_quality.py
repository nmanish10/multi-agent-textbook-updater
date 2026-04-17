from __future__ import annotations

import unittest

from agents.evidence_extractor import source_signal_score
from agents.judge import adjust_scores
from agents.retrieval import canonicalize_url, infer_credibility, normalize_result
from agents.section_mapper import score_sections, top_section_confident


class DecisionQualityTests(unittest.TestCase):
    def test_duckduckgo_urls_are_canonicalized(self) -> None:
        url = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.nist.gov%2Fai"
        self.assertEqual(canonicalize_url(url), "https://nist.gov/ai")

    def test_trusted_domain_gets_high_web_credibility(self) -> None:
        self.assertGreaterEqual(infer_credibility("web", "https://www.nist.gov/ai"), 0.95)
        self.assertLessEqual(infer_credibility("web", "https://medium.com/some-post"), 0.3)

    def test_normalize_result_adds_credibility_and_domain(self) -> None:
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
        strong = {"retrieval_score": 0.9, "credibility_score": 0.95}
        weak = {"retrieval_score": 0.8, "credibility_score": 0.3}
        self.assertGreater(source_signal_score(strong), source_signal_score(weak))

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

    def test_section_scoring_detects_clear_top_match(self) -> None:
        sections = [
            {"id": "1.1", "title": "Sampling Theory", "text": "Discrete signal sampling and Nyquist analysis."},
            {"id": "1.2", "title": "Transforms", "text": "Fourier, wavelet, and spectral representations."},
            {"id": "1.3", "title": "Control", "text": "Feedback loops and stability."},
        ]
        scored = score_sections("wavelet transforms for spectral analysis", sections)
        self.assertEqual(scored[0][0], "1.2")
        self.assertTrue(top_section_confident(scored))


if __name__ == "__main__":
    unittest.main()
