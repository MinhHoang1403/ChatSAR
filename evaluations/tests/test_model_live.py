"""Chấm nghĩa độc lập theo annotations đã khóa, không chỉ so con số tình cờ trùng."""

import unittest

from evaluations.model_live import semantic_shape, semantics_match


class SemanticScoringTests(unittest.TestCase):
    def test_span_only_actual_requires_bound_evidence_and_keeps_text_and_period_bounds(self):
        columns = [{"id":"c", "name":"region", "data_type":"text"}]
        node = {"operator":"EQ", "column_id":"c", "literal":{"raw_phrase":"3", "value_type":"text"}}
        actual = {"column_id":"c", "raw_phrase":"3", "canonical_value":"3", "operator":"EQ"}
        expected = {"filters":{"operator":"EQ", "column":"region", "value":"3"}}
        self.assertFalse(semantics_match(semantic_shape({"filters":node}, columns), expected))
        self.assertTrue(semantics_match(semantic_shape({"filters":node}, columns, [actual]), expected))
        changed = {**actual, "canonical_value":"quận 3"}
        self.assertFalse(semantics_match(semantic_shape({"filters":node}, columns, [changed]), expected))
        period = {"filters":{"operator":"AND", "children":[{**node,"operator":"GTE"},{**node,"operator":"LT"}]}}
        bindings = [{**actual,"operator":"GTE","canonical_value":"2026-02-01"},{**actual,"operator":"LT","canonical_value":"2026-03-01"}]
        result = semantic_shape(period, columns, bindings)
        self.assertEqual([child['value'] for child in result['filters']['children']], ['2026-02-01','2026-03-01'])

    def test_semantic_prepare_only_cannot_dispatch(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from evaluations.model_live import run_semantic

        with patch("evaluations.model_live.TestSession") as session:
            with self.assertRaises(RuntimeError):
                run_semantic(SimpleNamespace(prepare_only=True, max_requests=95))
            session.assert_not_called()

    def test_same_column_or_equality_is_in_but_other_predicates_are_not(self):
        expected = {"filters": {"operator": "OR", "children": [
            {"operator": "EQ", "column": "x", "value": "a"},
            {"operator": "EQ", "column": "x", "value": "b"}]}}
        actual = {"filters": {"operator": "IN", "column": "x", "values": ["a", "b"]}}
        self.assertTrue(semantics_match(actual, expected))
        for change in ({"column": "y"}, {"operator": "NE"}, {"value": None}):
            different = {"filters": {"operator": "OR", "children": [
                {"operator": "EQ", "column": "x", "value": "a"},
                {"operator": "EQ", "column": "x", "value": "b", **change}]}}
            self.assertFalse(semantics_match(actual, different))

    def test_scalar_filtered_count_rows_equals_only_the_same_nonnull_count(self):
        actual = {"metrics": [{"operator": "COUNT_ROWS", "column": None}], "filters": {"operator": "IS_NOT_NULL", "column": "fee"}}
        expected = {"metrics": [{"operator": "COUNT_NON_NULL", "column": "fee"}]}
        self.assertTrue(semantics_match(actual, expected))
        self.assertFalse(semantics_match(actual, {"metrics": [{"operator": "COUNT_ROWS", "column": None}]}))
        self.assertFalse(semantics_match(actual, {"metrics": [{"operator": "COUNT_NON_NULL", "column": "other"}]}))
        for change in ({"group_by": ["code"], "selection": ["code"]}, {"metrics": actual["metrics"] + [{"operator": "SUM", "column": "amount"}]}, {"filters": {"operator": "OR", "children": [actual["filters"], {"operator": "IS_NULL", "column": "amount"}]}}):
            self.assertFalse(semantics_match({**actual, **change}, expected))

    def test_boolean_spelling_equivalence_requires_both_catalog_and_literal_boolean(self):
        for kind in ("boolean", "text"):
            columns = [{"id": "a", "name": "enabled", "data_type": kind}]
            for value_kind in ("boolean", "text"):
                plan = {"filters": {"operator": "EQ", "column_id": "a", "literal": {"candidate_value": "False", "value_type": value_kind}}}
                shape = semantic_shape(plan, columns)
                expected = {"filters": {"operator": "EQ", "column": "enabled", "value": "false"}}
                self.assertEqual(semantics_match(shape, expected), kind == value_kind == "boolean")
                self.assertFalse(semantics_match(shape, {"filters": {"operator": "EQ", "column": "enabled", "value": "true"}}))

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
