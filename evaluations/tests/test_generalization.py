"""Kiểm bộ mới và adjudication độc lập; không dùng compiler hoặc model."""

import hashlib
import json
import os
import unittest

from evaluations.oracle import EVALUATIONS, postgres
from evaluations.semantic import load_scenarios, normalize


class GeneralizationTests(unittest.TestCase):
    def test_annotation_review_covers_original_90_and_locks_new_labels(self):
        original = load_scenarios()
        audit = json.loads(
            (EVALUATIONS / "annotation_review.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            {c["case_id"] for c in original["cases"]},
            {c["case_id"] for c in audit["cases"]},
        )
        self.assertEqual(len(audit["cases"]), 90)
        for name, digest in json.loads(
            (EVALUATIONS / "generalization_checksums.json").read_text()
        ).items():
            self.assertEqual(
                hashlib.sha256((EVALUATIONS / name).read_bytes()).hexdigest(), digest
            )
        for case, reviewed in zip(original["cases"], audit["cases"], strict=True):
            self.assertEqual(
                hashlib.sha256(
                    json.dumps(case, sort_keys=True, ensure_ascii=False).encode()
                ).hexdigest(),
                reviewed["annotation_sha256"],
            )
        self.assertEqual(set(audit["overrides"]), {"basic_logistics_month_boundary"})

    @unittest.skipUnless(
        os.getenv("CHATSAR_POSTGRES_TESTS") == "1", "Cần PostgreSQL thật"
    )
    def test_new_sql_oracles_and_adjudication(self):
        manifest = json.loads(
            (EVALUATIONS / "generalization.json").read_text(encoding="utf-8")
        )
        audit = json.loads(
            (EVALUATIONS / "annotation_review.json").read_text(encoding="utf-8")
        )
        cases = [c for c in manifest["cases"] if c["oracle_sql"]] + list(
            audit["overrides"].values()
        )
        sql = [
            "BEGIN;",
            (EVALUATIONS / "datasets/fixtures.sql").read_text(encoding="utf-8"),
            (EVALUATIONS / "datasets/generalization.sql").read_text(encoding="utf-8"),
        ]
        sql += [
            "SELECT coalesce(jsonb_agg(t),'[]'::jsonb) FROM ("
            + c["oracle_sql"]
            + ") t;"
            for c in cases
        ]
        actual = [
            json.loads(line)
            for line in postgres("\n".join(sql + ["ROLLBACK;"])).splitlines()
            if line.strip()
        ]
        self.assertEqual(len(actual), len(cases))
        for rows, case in zip(actual, cases, strict=True):
            self.assertEqual(
                normalize(rows, case["column_types"]),
                normalize(case["expected_rows"], case["column_types"]),
            )

    @unittest.skipUnless(
        os.getenv("CHATSAR_POSTGRES_TESTS") == "1", "Cần PostgreSQL thật"
    )
    def test_or_equality_and_in_have_identical_pg_null_semantics(self):
        output = postgres("""WITH sample(x,y) AS (
        VALUES ('a'::text,'b'),('b','c'),('c','b'),(NULL,'b'))
        SELECT bool_and(((x='a' OR x='b') IS NOT DISTINCT FROM (x IN ('a','b')))),
        bool_or(((x='a' OR y='b') IS DISTINCT FROM (x IN ('a','b')))),
        bool_or(((x='a' OR x<>'b') IS DISTINCT FROM (x IN ('a','b')))) FROM sample;""")
        self.assertEqual(output.strip(), "t|t|t")
