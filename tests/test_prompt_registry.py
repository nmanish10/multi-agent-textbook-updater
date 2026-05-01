from __future__ import annotations

import unittest

from core.prompts import prompt_system, prompt_version, render_prompt


class PromptRegistryTests(unittest.TestCase):
    def test_prompt_version_is_loaded_from_yaml(self) -> None:
        self.assertEqual(prompt_version("chapter_analysis"), "1.1")
        self.assertIn("academic reviewer", prompt_system("chapter_analysis") or "")

    def test_render_prompt_formats_values_and_preserves_examples(self) -> None:
        prompt = render_prompt(
            "judge_candidate",
            chapter_summary="Foundations of neural networks.",
            key_concepts=["backpropagation", "optimization"],
            candidate_title="Adaptive Optimizer Refinement",
            candidate_summary="Introduces a more stable training update rule.",
            candidate_why="Improves convergence for practical training setups.",
            source_type="paper",
            source_date="2026-01-12",
        )

        self.assertIn("Foundations of neural networks.", prompt)
        self.assertIn("Adaptive Optimizer Refinement", prompt)
        self.assertIn('"relevance": 0.0', prompt)
        self.assertIn("backpropagation", prompt)


if __name__ == "__main__":
    unittest.main()
