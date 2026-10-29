"""Kiểm gold PostgreSQL của 90 tình huống; không gọi model và không chấm NL giả."""

import hashlib
import json
from collections import Counter
from decimal import Decimal

from evaluations.oracle import EVALUATIONS, postgres, verify_checksums


def load_scenarios() -> dict:
    verify_checksums()
    locked = json.loads(
        (EVALUATIONS / "semantic_checksums.json").read_text(encoding="utf-8")
    )
    for name, expected in locked.items():
        if hashlib.sha256((EVALUATIONS / name).read_bytes()).hexdigest() != expected:
            raise AssertionError("Semantic fixture checksum mismatch: " + name)
    return json.loads((EVALUATIONS / "semantic.json").read_text(encoding="utf-8"))


def normalize(rows: list[dict], types: dict) -> list:
    return [
        {
            key: Decimal(str(row[key]))
            if kind in ("numeric", "integer") and row[key] is not None
            else row[key]
            for key, kind in types.items()
        }
        for row in rows
    ]


def main() -> None:
    manifest = load_scenarios()
    executable = [c for c in manifest["cases"] if "oracle_sql" in c]
    statements = ["BEGIN;"] + [
        (EVALUATIONS / n).read_text(encoding="utf-8") for n in manifest["fixtures"]
    ]
    for case in executable:
        statements.append(
            "SELECT json_build_object('case_id','"
            + case["case_id"]
            + "','rows', COALESCE(json_agg(row_to_json(t)), '[]'::json)) FROM ("
            + case["oracle_sql"]
            + ") t;"
        )
    statements.append("ROLLBACK;")
    actual = [
        json.loads(line, parse_float=Decimal)
        for line in postgres("\n".join(statements)).splitlines()
        if line.strip()
    ]
    assert len(actual) == len(executable)
    for case, result in zip(executable, actual, strict=True):
        assert result["case_id"] == case["case_id"]
        assert normalize(result["rows"], case["column_types"]) == normalize(
            case["expected_rows"], case["column_types"]
        ), case["case_id"]
    report = {
        "scenarios": len(manifest["cases"]),
        "groups": dict(Counter(c["group"] for c in manifest["cases"])),
        "gold_sql_checks": len(executable),
        "gold_sql_status": "PASS",
        "non_sql_scenarios": len(manifest["cases"]) - len(executable),
        "model_semantic_status": "NOT_RUN",
        "model_accuracy": None,
        "qualifier_coverage": None,
        "false_refusals": None,
        "silent_wrong_answers": None,
        "p50_model_latency_ms": None,
        "p95_model_latency_ms": None,
        "per_domain_model": {
            d: "NOT_RUN" for d in sorted({c["domain"] for c in manifest["cases"]})
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
