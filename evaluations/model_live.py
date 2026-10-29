"""Đối chiếu model thật qua HTTP với gold đã khóa; không tự retry/tuning/fallback."""

import argparse
import csv
import io
import json
import subprocess
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from evaluations.oracle import EVALUATIONS, ROOT, postgres, verify_checksums
from evaluations.persistence import TestSession, inside

SOURCES = {
    "logistics": (
        "shipments",
        {
            "shipment_code": "text",
            "district": "text",
            "shipped_at": "timestamp",
            "fee": "numeric",
            "delivery_status": "text",
        },
    ),
    "hotel": (
        "stays",
        {
            "booking_ref": "text",
            "room_type": "text",
            "nights": "integer",
            "room_charge": "numeric",
            "checked_in": "date",
        },
    ),
    "library": (
        "loans",
        {"accession": "text", "category": "text", "overdue_days": "integer", "fine": "numeric"},
    ),
}


def normalized(rows: list, kinds: list[str]) -> list:
    return [
        [
            None
            if value is None
            else Decimal(str(value))
            if kind in ("numeric", "integer")
            else value
            for value, kind in zip(row, kinds, strict=True)
        ]
        for row in rows
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--providers", nargs="+", choices=["gemini", "knowledge"], required=True)
    parser.add_argument("--cases", nargs="+", required=True)
    parser.add_argument("--restart", action="store_true")
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Kiểm tra fidelity fixture qua ingestion, không gọi model",
    )
    args = parser.parse_args()
    manifest = verify_checksums()
    cases = [next(c for c in manifest["cases"] if c["case_id"] == name) for name in args.cases]
    domains = sorted({c["domain"] for c in cases})
    # Chỉ dữ liệu synthetic đã khóa checksum, fixture transaction bị rollback.
    sql = ["BEGIN;", (EVALUATIONS / manifest["fixtures"]).read_text(encoding="utf-8")]
    for domain in domains:
        table, _ = SOURCES[domain]
        sql.append(
            f"SELECT json_build_object('domain','{domain}','rows',json_agg(row_to_json(t))) FROM oracle_fixture.{table} t;"
        )
    sql.append("ROLLBACK;")
    fixtures = {
        item["domain"]: item["rows"]
        for item in [
            json.loads(line, parse_float=Decimal)
            for line in postgres("\n".join(sql)).splitlines()
            if line.strip()
        ]
    }
    session = TestSession()
    report, saved = [], []
    try:
        workspace = session.request("/workspaces", {"name": "Bounded semantic evaluation"})
        sources = {}
        for domain in domains:
            _, kinds = SOURCES[domain]
            sentinel = "__CHATSAR_BENCHMARK_NULL__"
            assert not any(value == sentinel for row in fixtures[domain] for value in row.values())
            output = io.StringIO(newline="")
            writer = csv.writer(output)
            writer.writerow(kinds)
            writer.writerows(
                [
                    [sentinel if row[name] is None else row[name] for name in kinds]
                    for row in fixtures[domain]
                ]
            )
            sources[domain] = session.publish(
                workspace["id"],
                output.getvalue().encode(),
                kinds,
                sentinel,
                {name for name in kinds if any(row[name] is None for row in fixtures[domain])},
            )
            published = session.request(f"/datasets/{sources[domain]['dataset_id']}/preview")
            original = [[row[name] for name in kinds] for row in fixtures[domain]]
            assert normalized(published["rows"], list(kinds.values())) == normalized(
                original, list(kinds.values())
            ), "Fixture fidelity mismatch"
            print(
                f"PASS fixture fidelity: {domain}; all typed rows/NULL/text IDs checked.",
                flush=True,
            )
        if args.prepare_only:
            return
        for provider in args.providers:
            for case in cases:
                source = sources[case["domain"]]
                conversation = session.request(
                    "/conversations", {"workspace_id": workspace["id"], "title": case["case_id"]}
                )
                started = perf_counter()
                envelope = session.request(
                    f"/conversations/{conversation['id']}/messages",
                    {
                        "question": case["question"],
                        "dataset_revision_id": source["revision_id"],
                        "provider": provider,
                    },
                    request_key=uuid4().hex,
                )
                answered = envelope["status"] == "answered"
                actual = envelope.get("facts", {}).get("rows", [])
                expected = [[row[k] for k in case["column_types"]] for row in case["expected_rows"]]
                try:
                    correct = answered and normalized(
                        actual, list(case["column_types"].values())
                    ) == normalized(expected, list(case["column_types"].values()))
                except (ValueError, TypeError, ArithmeticError):
                    correct = False
                item = {
                    "case_id": case["case_id"],
                    "split": case["split"],
                    "domain": case["domain"],
                    "provider": provider,
                    "answer_status": envelope["status"],
                    "error_code": envelope.get("error_code"),
                    "answer_correct": correct,
                    "validation_message": envelope["display_text"] if not answered else None,
                    "executed": answered,
                    "false_refusal": not answered
                    and envelope["status"] in ("clarify", "unsupported", "insufficient"),
                    "latency_ms": round((perf_counter() - started) * 1000, 2),
                    "source_revision": source["revision_id"],
                    "checksum": source["checksum"],
                    "request_id": envelope["request_id"],
                    "trace_id": envelope.get("trace_id"),
                    "usage": envelope.get("facts", {}).get("provider"),
                    "qualifier_coverage": "NOT_APPLICABLE"
                    if not case["expected_qualifiers"]
                    else "REQUIRES_REVIEW",
                    "expected_rows": expected,
                    "actual_rows": actual,
                }
                report.append(item)
                diagnostic = json.loads(
                    inside(
                        '''
import json
from uuid import UUID
from sqlalchemy import select
from app.database import get_engine
from app.schema import messages
with get_engine().connect() as c:
    plan=c.execute(select(messages.c.query_plan).where(messages.c.conversation_id==UUID("'''
                        + conversation["id"]
                        + """"))).scalar_one()
print(json.dumps(plan))
get_engine().dispose()
"""
                    )
                )
                item["proposal"] = diagnostic
                saved.append(
                    (conversation["id"], session.request(f"/conversations/{conversation['id']}"))
                )
                print(
                    json.dumps(
                        {k: v for k, v in item.items() if k != "proposal"},
                        ensure_ascii=False,
                        default=str,
                    ),
                    flush=True,
                )
                if envelope.get("error_code") in (
                    "PROVIDER_FORBIDDEN",
                    "PROVIDER_AUTH",
                    "CALL_LIMIT_REACHED",
                    "BUDGET_REACHED",
                    "PROVIDER_SCHEMA",
                    "PROVIDER_UNAVAILABLE",
                ):
                    break
        if args.restart:
            subprocess.run(["docker", "compose", "restart"], cwd=ROOT, check=True, timeout=60)
            subprocess.run(
                ["docker", "compose", "up", "-d", "--wait"], cwd=ROOT, check=True, timeout=90
            )
            for conversation_id, history in saved:
                assert session.request(f"/conversations/{conversation_id}") == history
            print(
                "PASS: stored chat envelopes/references/source revisions unchanged after restart; no model recalled."
            )
        ledger = json.loads(
            inside("""
import json
from sqlalchemy import select
from app.database import get_engine
from app.schema import provider_usage
with get_engine().connect() as c:
    rows=[dict(r) for r in c.execute(select(provider_usage)).mappings()]
print(json.dumps(rows,default=str))
get_engine().dispose()
""")
        )
        path = ROOT / "artifacts" / "model-live.json"
        path.parent.mkdir(exist_ok=True)
        previous = json.loads(path.read_text(encoding="utf-8"))["cases"] if path.exists() else []
        path.write_text(
            json.dumps(
                {"cases": previous + report, "ledger": ledger},
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        print(f"Calls recorded in durable ledger: {len(ledger)}. Report: artifacts/model-live.json")
    finally:
        session.close()


if __name__ == "__main__":
    main()
