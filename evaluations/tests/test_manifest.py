"""Đối chứng oracle không phụ thuộc code ứng dụng hay output PostgreSQL."""

import unittest
from decimal import Decimal

from evaluations.oracle import normalize, verify_checksums


class ManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = verify_checksums()
        self.cases = {case["case_id"]: case for case in self.manifest["cases"]}

    def test_cases_have_unique_ids_permissions_and_evidence(self) -> None:
        cases = self.manifest["cases"] + self.manifest["negative_cases"]
        self.assertEqual(len({case["case_id"] for case in cases}), len(cases))
        self.assertGreaterEqual(len({case["domain"] for case in self.cases.values()}), 4)
        for case in self.cases.values():
            self.assertIn("permissions", case)
            self.assertEqual(case["source_revision"], case["expected_evidence"]["source_revision"])
            self.assertNotIn("?", case["oracle_sql"])
            self.assertNotIn("?", case["question"].rstrip("?"))
            normalize(case["expected_rows"], case["column_types"])

    def test_held_out_domain_is_disjoint(self) -> None:
        held = {case["domain"] for case in self.cases.values() if case["split"] == "held-out"}
        other = {case["domain"] for case in self.cases.values() if case["split"] != "held-out"}
        self.assertTrue(held)
        self.assertFalse(held & other)

    def test_decimal_gold_has_independent_arithmetic(self) -> None:
        examples = {
            "logistics_sum": sum(map(Decimal, ["10.10", "20.20", "0.00", "-0.10"])),
            "logistics_exact_district": Decimal("10.10") - Decimal("0.10"),
            "hotel_sum": Decimal("100.05") + Decimal("200.10") + Decimal("0.00"),
            "energy_decimal": Decimal("0.100") + Decimal("0.200"),
        }
        for case_id, expected in examples.items():
            self.assertEqual(Decimal(self.cases[case_id]["expected_rows"][0]["total"]), expected)
        self.assertEqual(
            Decimal(self.cases["hotel_avg"]["expected_rows"][0]["average"]),
            (Decimal("100.05") + Decimal("200.10")) / Decimal(3),
        )

    def test_negative_cases_never_authorize_execution(self) -> None:
        for case in self.manifest["negative_cases"]:
            self.assertFalse(case["execution_allowed"])
            self.assertNotEqual(case["expected_status"], "answered")

    def test_null_and_text_ids_remain_distinct(self) -> None:
        self.assertIsNone(self.cases["logistics_empty_sum"]["expected_rows"][0]["total"])
        self.assertEqual(self.cases["logistics_text_id"]["expected_rows"][0]["shipment_code"], "0007")


if __name__ == "__main__":
    unittest.main()
