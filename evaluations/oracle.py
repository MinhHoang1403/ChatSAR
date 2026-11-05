"""Chạy gold SQL trên PostgreSQL; tuyệt đối không import compiler ứng dụng."""

from __future__ import annotations

import hashlib
import json
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVALUATIONS = ROOT / "evaluations"


def verify_checksums() -> dict[str, Any]:
    checksums = json.loads((EVALUATIONS / "checksums.json").read_text(encoding="utf-8"))
    for name, expected in checksums.items():
        actual = hashlib.sha256((EVALUATIONS / name).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Checksum không khớp: {name}")
    return json.loads((EVALUATIONS / "manifest.json").read_text(encoding="utf-8"))


def postgres(sql: str) -> str:
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "db", "psql", "-X", "-qAt",
         "-U", "chatsar_admin", "-d", "chatsar", "-v", "ON_ERROR_STOP=1"],
        input=sql, text=True, encoding="utf-8", capture_output=True,
        cwd=ROOT, timeout=60, check=False,
    )
    if result.returncode:
        raise RuntimeError("Oracle PostgreSQL không chạy được: " + result.stderr.strip())
    return result.stdout


def normalize(rows: list[dict[str, Any]], types: dict[str, str]) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        if set(row) != set(types):
            raise AssertionError("Cột trả về khác hợp đồng oracle")
        values: dict[str, Any] = {}
        for key, kind in types.items():
            value = row[key]
            if value is None:
                values[key] = None
            elif kind == "numeric":
                values[key] = Decimal(str(value))
            elif kind == "integer" and type(value) is int:
                values[key] = value
            elif kind == "text" and type(value) is str:
                values[key] = value
            else:
                raise AssertionError(f"Sai kiểu oracle: {key}/{kind}")
        normalized.append(values)
    return normalized


def main() -> None:
    manifest = verify_checksums()
    statements = ["BEGIN;", (EVALUATIONS / manifest["fixtures"]).read_text(encoding="utf-8")]
    # Chỉ đọc SQL tin cậy đã khóa checksum; không nhận SQL qua API ứng dụng.
    for case in manifest["cases"]:
        query = case["oracle_sql"]
        case_id = case["case_id"]
        statements.append(
            f"SELECT json_build_object('case_id', '{case_id}', 'rows', "
            f"COALESCE(json_agg(row_to_json(result)), '[]'::json)) FROM ({query}) AS result;"
        )
    statements.append("ROLLBACK;")
    output = postgres("\n".join(statements))
    results = [json.loads(line, parse_float=Decimal) for line in output.splitlines() if line.strip()]
    if len(results) != len(manifest["cases"]):
        raise AssertionError("Thiếu kết quả oracle")
    for case, result in zip(manifest["cases"], results, strict=True):
        if result["case_id"] != case["case_id"]:
            raise AssertionError("Sai thứ tự case oracle")
        types = case["column_types"]
        if normalize(result["rows"], types) != normalize(case["expected_rows"], types):
            raise AssertionError(f"Oracle không khớp expected: {case['case_id']}")
        print(f"PASS PostgreSQL oracle: {case['case_id']}")
    print(f"PASS {len(results)} SQL oracle cases; natural-language/model/negative API checks: NOT_RUN")


if __name__ == "__main__":
    main()
