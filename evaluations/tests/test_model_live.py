"""Chấm nghĩa độc lập theo annotations đã khóa, không chỉ so con số tình cờ trùng."""

import unittest

from evaluations.model_live import semantic_shape, semantics_match


class SemanticScoringTests(unittest.TestCase):
    def test_only_redundant_scalar_null_filters_are_equivalent(self):
        metric = {"operator": "COUNT_DISTINCT", "column": "value"}
        actual = {
            "metrics": [metric],
            "filters": {"operator": "IS_NOT_NULL", "column": "value"},
        }
        self.assertTrue(semantics_match(actual, {"metrics": [metric]}))
        self.assertFalse(
            semantics_match(
                actual, {"metrics": [{"operator": "COUNT_ROWS", "column": None}]}
            )
        )
        self.assertFalse(
            semantics_match(
                {**actual, "group_by": ["code"]},
                {"metrics": [metric], "group_by": ["code"]},
            )
        )
        actual["filters"]["column"] = "other"
        self.assertFalse(semantics_match(actual, {"metrics": [metric]}))

    def test_matching_result_cannot_hide_missing_or_extra_qualifier(self):
        expected = {
            "metrics": [{"operator": "SUM", "column": "value"}],
            "filters": {"operator": "EQ", "column": "district", "value": "quận 3"},
        }
        actual = {
            "metrics": expected["metrics"],
            "selection": [],
            "group_by": [],
            "filters": None,
        }
        self.assertFalse(semantics_match(actual, expected))
        actual["filters"] = expected["filters"]
        self.assertTrue(semantics_match(actual, expected))
        self.assertFalse(semantics_match(actual, {"metrics": expected["metrics"]}))
        actual["metrics"] = [{"operator": "AVG", "column": "value"}]
        self.assertFalse(semantics_match(actual, expected))

    def test_boolean_tree_order_is_commutative_but_and_is_not_or(self):
        leaves = [
            {"operator": "EQ", "column": "code", "value": "0007"},
            {"operator": "GT", "column": "value", "value": "0"},
        ]
        expected = {"filters": {"operator": "AND", "children": leaves}}
        actual = {"filters": {"operator": "AND", "children": list(reversed(leaves))}}
        self.assertTrue(semantics_match(actual, expected))
        actual["filters"]["operator"] = "OR"
        self.assertFalse(semantics_match(actual, expected))

    def test_column_binding_and_timezone_equivalence_keep_text_zeroes(self):
        columns = [{"id": "a", "name": "code"}, {"id": "b", "name": "at"}]
        plan = {
            "select_columns": ["a"],
            "filters": {
                "operator": "GTE",
                "column_id": "b",
                "literal": {"candidate_value": "2026-09-01T00:00:00+07:00"},
            },
        }
        shape = semantic_shape(plan, columns)
        expected = {
            "selection": ["code"],
            "filters": {
                "operator": "GTE",
                "column": "at",
                "value": "2026-08-31T17:00:00Z",
            },
        }
        self.assertTrue(semantics_match(shape, expected))
        expected["filters"]["value"] = "2026-09-01T17:00:00Z"
        self.assertFalse(semantics_match(shape, expected))
        expected = {"filters": {"operator": "EQ", "column": "code", "value": "0007"}}
        self.assertFalse(
            semantics_match(
                {"filters": {"operator": "EQ", "column": "code", "value": "7"}},
                expected,
            )
        )
