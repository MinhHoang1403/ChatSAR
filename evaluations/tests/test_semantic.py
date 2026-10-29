"""Kiểm manifest độc lập; không import compiler hay model để tạo expected."""

import unittest
from collections import Counter

from evaluations.semantic import load_scenarios


class SemanticManifestTests(unittest.TestCase):
    def test_locked_ninety_cases_and_group_denominators(self):
        cases = load_scenarios()["cases"]
        self.assertEqual(len(cases), 90)
        self.assertEqual(len({c["case_id"] for c in cases}), 90)
        self.assertEqual(
            Counter(c["group"] for c in cases),
            {
                "basic": 30,
                "paraphrase": 20,
                "edge": 15,
                "negative": 10,
                "followup": 10,
                "metamorphic": 5,
            },
        )

    def test_new_domain_not_used_as_runtime_knowledge(self):
        cases = load_scenarios()["cases"]
        held_out = [c for c in cases if c["split"] == "held-out"]
        self.assertEqual(len(held_out), 5)
        self.assertEqual({c["domain"] for c in held_out}, {"maintenance"})
        self.assertTrue(all(c["model_status"] == "NOT_RUN" for c in cases))

    def test_gold_is_required_for_executable_cases_and_context_is_explicit(self):
        for case in load_scenarios()["cases"]:
            self.assertTrue(case["question"])
            self.assertIn("expected_qualifiers", case)
            if "oracle_sql" in case:
                self.assertIn("expected_rows", case)
                self.assertTrue(case["column_types"])
            if case["group"] == "followup":
                self.assertTrue(case["context"])
            if case["group"] == "negative":
                self.assertFalse(case["execution_allowed"])
