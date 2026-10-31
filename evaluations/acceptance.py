"""Nghiệm thu HTTP có giới hạn; mặc định chỉ prepare, --live cần quyền người dùng riêng."""

import argparse
import csv
import hashlib
import io
import json
import subprocess
from decimal import Decimal
from time import perf_counter
from uuid import UUID, uuid4

from evaluations.model_live import normalized
from evaluations.oracle import EVALUATIONS, ROOT, postgres
from evaluations.persistence import TestSession, inside
from evaluations.semantic import load_scenarios


def ledger() -> dict:
    return json.loads(
        inside("""
import json
from sqlalchemy import select,func
from app.schema import provider_usage
from app.database import get_engine
with get_engine().connect() as c:
 print(json.dumps(dict(c.execute(select(provider_usage.c.provider,func.count()).group_by(provider_usage.c.provider)).all())))
get_engine().dispose()
""")
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--max-requests", type=int, default=0)
    parser.add_argument("--expected-ledger", type=int, default=12)
    parser.add_argument("--output", default="artifacts/acceptance.json")
    args = parser.parse_args()
    if args.live and args.max_requests != 3:
        parser.error(
            "Live plan cần quyền đúng tối đa 3 requests, không tự suy từ .env."
        )
    manifest = load_scenarios()
    baseline = ledger()
    if args.live and sum(baseline.values()) != args.expected_ledger:
        raise RuntimeError(
            "Ledger khác baseline được duyệt. Dừng trước network."
        )
    source_specs = {
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
        "maintenance": (
            "work_orders",
            {
                "work_order": "text",
                "asset_code": "text",
                "labor_hours": "numeric",
                "state": "text",
            },
        ),
    }
    sql = ["BEGIN;"] + [
        (EVALUATIONS / name).read_text(encoding="utf-8")
        for name in manifest["fixtures"]
    ]
    for domain, (table, _) in source_specs.items():
        sql.append(
            "SELECT json_build_object('domain','"
            + domain
            + "','rows',json_agg(row_to_json(t))) FROM oracle_fixture."
            + table
            + " t;"
        )
    sql.append("ROLLBACK;")
    rows = {
        item["domain"]: item["rows"]
        for item in [
            json.loads(line, parse_float=Decimal)
            for line in postgres("\n".join(sql)).splitlines()
            if line.strip()
        ]
    }
    report = {
        "mode": "model_live_http" if args.live else "prepare_only",
        "browser_status": "BLOCKED",
        "baseline_ledger": baseline,
        "cases": [],
        "sources": {},
        "stop_reason": None,
    }
    session = TestSession()
    histories = []
    used = 0
    try:
        workspace = session.request("/workspaces", {"name": "Synthetic acceptance"})
        for domain, (_, kinds) in source_specs.items():
            out = io.StringIO(newline="")
            writer = csv.writer(out)
            writer.writerow(kinds)
            writer.writerows([[row[name] for name in kinds] for row in rows[domain]])
            content = out.getvalue().encode("utf-8-sig")
            boundary = uuid4().hex
            upload = session.request(
                f"/workspaces/{workspace['id']}/datasets",
                (
                    f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="synthetic.csv"\r\nContent-Type: text/csv\r\n\r\n'.encode()
                    + content
                    + f"\r\n--{boundary}--\r\n".encode()
                ),
                content_type="multipart/form-data; boundary=" + boundary,
            )
            preview = session.request(f"/datasets/{upload['dataset_id']}/preview")
            assert preview["checksum"] == hashlib.sha256(content).hexdigest()
            assert preview["row_count"] == len(rows[domain])
            if domain == "hotel":
                setup_body = {
                    "revision_id": upload["revision_id"],
                    "use_ai": args.live,
                    "consent_metadata": args.live,
                    "provider": "gemini",
                }
                before = sum(ledger().values())
                setup = session.request(
                    f"/datasets/{upload['dataset_id']}/setup",
                    setup_body,
                    request_key=uuid4().hex,
                )
                if args.live:
                    added = sum(ledger().values()) - before
                    assert added in (0, 1), (
                        "Concurrent provider usage changed the approved baseline"
                    )
                    used += added
                    report["cases"].append(
                        {
                            "case_id": "hotel_ai_setup",
                            "mode": setup["mode"],
                            "error_code": setup["error_code"],
                            "validation_errors": setup["validation_errors"],
                            # validation_errors thuộc proposal local sau fallback;
                            # lý do loại proposal AI nằm trong notes, cần lưu trước cleanup.
                            "rejection_notes": setup["proposal"].get("notes", []),
                            "issues": setup.get("issues", []),
                            "proposal": setup["proposal"],
                            "checksum": setup["checksum"],
                            "pass": setup["mode"] == "ai_proposal"
                            and not setup["validation_errors"],
                        }
                    )
                    if not report["cases"][-1]["pass"]:
                        report["stop_reason"] = "setup_error_or_rejected"
                        break
            if args.live and domain == "hotel":
                proposal = setup["proposal"]
                assert [c["data_type"] for c in proposal["columns"]] == list(
                    kinds.values()
                ), "AI setup types differ from independently reviewed source"
                published = session.request(
                    f"/datasets/{upload['dataset_id']}/confirm",
                    {
                        "revision_id": upload["revision_id"],
                        "columns": proposal["columns"],
                        "description": proposal["description"],
                        "grain": proposal["grain"],
                        "data_classification": "synthetic",
                    },
                )
                source = {**upload, **published}
            else:
                source = session.publish(workspace["id"], content, kinds)
            typed = session.request(f"/datasets/{source['dataset_id']}/preview")
            assert normalized(typed["rows"], list(kinds.values())) == normalized(
                [[row[name] for name in kinds] for row in rows[domain]],
                list(kinds.values()),
            )
            report["sources"][domain] = source
            if not args.live:
                continue
            assert used < args.max_requests
            case_id = (
                "basic_hotel_sum" if domain == "hotel" else "basic_maintenance_labor"
            )
            case = next(c for c in manifest["cases"] if c["case_id"] == case_id)
            chat = session.request(
                "/conversations", {"workspace_id": workspace["id"], "title": case_id}
            )
            before = sum(ledger().values())
            started = perf_counter()
            question = case["question"] if domain == "hotel" else "Tổng thời gian lao động là bao nhiêu?"
            answer = session.request(
                f"/conversations/{chat['id']}/messages",
                {
                    "question": question,
                    "dataset_revision_id": source["revision_id"],
                    "provider": "gemini",
                },
                request_key=uuid4().hex,
            )
            http_latency = (perf_counter() - started) * 1000
            added = sum(ledger().values()) - before
            assert added in (0, 1), (
                "Concurrent provider usage changed the approved baseline"
            )
            used += added
            gold = [
                [row[name] for name in case["column_types"]]
                for row in case["expected_rows"]
            ]
            actual = answer.get("display_rows", [])
            correct = answer["status"] == "answered" and normalized(
                actual, list(case["column_types"].values())
            ) == normalized(gold, list(case["column_types"].values()))
            UUID(chat["id"])
            plan = json.loads(
                inside(
                    """
import json
from uuid import UUID
from sqlalchemy import select
from app.schema import messages
from app.database import get_engine
with get_engine().connect() as c:
 print(json.dumps(c.execute(select(messages.c.query_plan).where(messages.c.conversation_id==UUID('"""
                    + chat["id"]
                    + """'))).scalar_one()))
get_engine().dispose()
"""
                )
            )
            metric_name = "room_charge" if domain == "hotel" else "labor_hours"
            metric_id = typed["columns"][list(kinds).index(metric_name)]["id"]
            semantic_correct = bool(
                plan
                and len(plan["aggregations"]) == 1
                and plan["aggregations"][0]["operator"] == "SUM"
                and plan["aggregations"][0]["column_id"] == metric_id
                and not plan["filters"]
                and not plan["group_by"]
                and not plan["select_columns"]
            )
            report["cases"].append(
                {
                    "case_id": case_id,
                    "question": question,
                    "actual_plan": plan,
                    "status": answer["status"],
                    "error_code": answer.get("error_code"),
                    "answer_correct": correct,
                    "gold_semantics_match": semantic_correct,
                    "pass": correct and semantic_correct,
                    "expected_rows": gold,
                    "actual_rows": actual,
                    "latency_ms": http_latency,
                    "timings_ms": answer.get("timings_ms"),
                    "usage": answer.get("facts", {}).get("provider"),
                    "trace_id": answer.get("trace_id"),
                    "request_id": answer["request_id"],
                    "source_revision": source["revision_id"],
                    "checksum": source["checksum"],
                }
            )
            histories.append(
                (chat["id"], session.request(f"/conversations/{chat['id']}"))
            )
            if not report["cases"][-1]["pass"]:
                report["stop_reason"] = "provider_or_answer_failed"
                break
        if args.live and histories:
            subprocess.run(
                ["docker", "compose", "restart"], cwd=ROOT, check=True, timeout=60
            )
            subprocess.run(
                ["docker", "compose", "up", "-d", "--wait"],
                cwd=ROOT,
                check=True,
                timeout=90,
            )
            for chat_id, history in histories:
                assert session.request(f"/conversations/{chat_id}") == history
            hotel = report["sources"]["hotel"]
            restored = session.request(f"/datasets/{hotel['dataset_id']}/preview")
            assert restored["setup_proposal"]["response"] == setup
            report["history_after_restart"] = "PASS"
        report["final_ledger"] = ledger()
        assert sum(report["final_ledger"].values()) - sum(baseline.values()) == used
        report["generation_reservations"] = used
        print(json.dumps(report, ensure_ascii=False, default=str, indent=2))
    finally:
        report["generation_reservations"] = used
        (ROOT / "artifacts").mkdir(exist_ok=True)
        target = (ROOT / args.output).resolve()
        if not target.is_relative_to((ROOT / "artifacts").resolve()):
            raise RuntimeError("Evidence phải nằm trong artifacts của workspace.")
        target.write_text(
            json.dumps(report, ensure_ascii=False, default=str, indent=2),
            encoding="utf-8",
        )
        session.close()
    if args.live and any(not case["pass"] for case in report["cases"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
