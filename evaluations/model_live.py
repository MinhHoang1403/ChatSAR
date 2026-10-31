"""Đối chiếu model thật qua HTTP với gold đã khóa; không tự retry/tuning/fallback."""

import argparse
import csv
import hashlib
import io
import json
import subprocess
from datetime import datetime
from decimal import Decimal
from time import perf_counter
from uuid import uuid4

from evaluations.oracle import EVALUATIONS, ROOT, postgres, verify_checksums
from evaluations.persistence import TestSession, inside
from evaluations.semantic import load_scenarios

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
        {
            "accession": "text",
            "category": "text",
            "overdue_days": "integer",
            "fine": "numeric",
        },
    ),
}
SOURCES.update(
    {
        "energy": (
            "meters",
            {
                "meter_code": "text",
                "zone": "text",
                "consumption": "numeric",
                "reading_day": "date",
            },
        ),
        "agriculture": (
            "harvests",
            {
                "plot_code": "text",
                "crop": "text",
                "yield_kg": "numeric",
                "harvested": "boolean",
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
        "printing": ("print_jobs", {"job_code": "text", "sheets": "integer",
                                   "minutes": "numeric", "fee": "numeric", "completed_on": "date"}),
    }
)


def semantic_shape(plan: dict, columns: list[dict], bindings: list[dict] | None = None) -> dict:
    """Đọc plan đã lưu, không import binder/compiler hoặc dùng chúng tạo expected."""
    names = {c["id"]: c["name"] for c in columns}
    types = {c["id"]: c.get("data_type") for c in columns}
    outputs = {
        a["output_id"]: a["operator"] + ":" + str(names.get(a.get("column_id")))
        for a in plan.get("aggregations", [])
    }

    def literal_value(value, column_id):
        candidate = value.get("candidate_value")
        if candidate is None:
            actual = {
                str(item["canonical_value"])
                for item in (bindings or [])
                if item["column_id"] == column_id and item["raw_phrase"] == value["raw_phrase"]
            }
            # Không đoán actual từ gold hoặc chạy lại binder trong evaluator.
            # Tháng dùng cùng span cho hai bound: chọn theo operator ở predicate.
            candidate = next(iter(actual)) if len(actual) == 1 else None
        # Cột BOOLEAN được PostgreSQL bind theo kiểu; khác hoa/thường ở biểu diễn
        # không đổi nghĩa. TEXT luôn so nguyên văn, kể cả chữ True/False/0/1.
        if types.get(column_id) == "boolean" and value.get("value_type") == "boolean":
            canonical = str(candidate).casefold()
            if canonical in ("true", "1"):
                return "true"
            if canonical in ("false", "0"):
                return "false"
        return candidate

    def predicate(node):
        if not node:
            return None
        result = {"operator": node["operator"]}
        if node["operator"] in ("AND", "OR"):
            result["children"] = sorted(
                [predicate(c) for c in node["children"]],
                key=lambda x: json.dumps(x, sort_keys=True),
            )
        else:
            result["column"] = names.get(
                node.get("column_id"), "UNBOUND:" + str(node.get("column_id"))
            )
            if node.get("literal"):
                matches = [
                    b for b in (bindings or [])
                    if b["column_id"] == node.get("column_id")
                    and b["raw_phrase"] == node["literal"].get("raw_phrase")
                    and b["operator"] == node["operator"]
                ]
                result["value"] = literal_value(node["literal"], node.get("column_id"))
                if node["literal"].get("candidate_value") is None and len(matches) == 1:
                    value = matches[0]["canonical_value"]
                    result["value"] = str(value).lower() if isinstance(value, bool) else str(value)
            if node.get("values"):
                result["values"] = sorted(literal_value(v, node.get("column_id")) for v in node["values"])
        return result

    return {
        "metrics": [
            {"operator": a["operator"], "column": names.get(a.get("column_id"))}
            for a in plan.get("aggregations", [])
        ],
        "selection": [
            names.get(c, "UNBOUND:" + c) for c in plan.get("select_columns", [])
        ],
        "filters": predicate(plan.get("filters")),
        "group_by": [names.get(c, "UNBOUND:" + c) for c in plan.get("group_by", [])],
        "order": [
            {
                "field": names.get(
                    o["field_id"], outputs.get(o["field_id"], o["field_id"])
                ),
                "direction": o["direction"],
            }
            for o in plan.get("order_by", [])
        ],
        "limit": plan.get("limit"),
    }


def semantics_match(actual: dict, expected: dict) -> bool:
    def scalar_nonnull_count(shape):
        shape = dict(shape)
        predicate = shape.get("filters")
        if (
            shape.get("metrics") == [{"operator": "COUNT_ROWS", "column": None}]
            and not shape.get("selection") and not shape.get("group_by")
            and isinstance(predicate, dict) and predicate.get("operator") == "IS_NOT_NULL"
            and set(predicate) == {"operator", "column"}
        ):
            # COUNT(*) WHERE c IS NOT NULL = COUNT(c) cho một scalar duy nhất.
            # Không áp dụng GROUP BY (có thể làm mất nhóm chỉ NULL), OR, nhiều metric
            # hoặc filter cột khác. Gold không đổi; đối chiếu PG độc lập có regression.
            shape["metrics"] = [{"operator": "COUNT_NON_NULL", "column": predicate["column"]}]
            shape["filters"] = None
        return shape

    actual, expected = scalar_nonnull_count(actual), scalar_nonnull_count(expected)

    def remove_redundant_null_filter(shape):
        shape = dict(shape)
        metrics = shape.get("metrics", [])
        columns = {m.get("column") for m in metrics}
        if (
            not metrics
            or len(columns) != 1
            or None in columns
            or shape.get("selection")
            or shape.get("group_by")
            or any(
                m["operator"]
                not in ("COUNT_NON_NULL", "COUNT_DISTINCT", "SUM", "AVG", "MIN", "MAX")
                for m in metrics
            )
        ):
            return shape

        def prune(node):
            if not node:
                return None
            if node["operator"] == "IS_NOT_NULL" and node.get("column") in columns:
                return None
            if node["operator"] == "AND":
                children = [
                    item for child in node["children"] if (item := prune(child))
                ]
                return (
                    {"operator": "AND", "children": children}
                    if len(children) > 1
                    else children[0]
                    if children
                    else None
                )
            return node

        shape["filters"] = prune(shape.get("filters"))
        return shape

    # PostgreSQL scalar aggregates bỏ NULL; chỉ bỏ guard cùng một cột, không GROUP/OR.
    # Không sửa gold, không áp dụng COUNT_ROWS hoặc phép tính ở một cột khác.
    actual, expected = (
        remove_redundant_null_filter(actual),
        remove_redundant_null_filter(expected),
    )

    def canonical(value):
        if isinstance(value, dict):
            result = {k: canonical(v) for k, v in value.items()}
            if result.get("operator") == "OR":
                children = result["children"]
                if (len(children) >= 2 and all(set(c) == {"operator", "column", "value"}
                    and c["operator"] == "EQ" and c["value"] is not None for c in children)
                    and len({c["column"] for c in children}) == 1):
                    return {"operator": "IN", "column": children[0]["column"],
                            "values": sorted({c["value"] for c in children})}
            if result.get("operator") in ("AND", "OR"):
                result["children"] = sorted(
                    result["children"], key=lambda x: json.dumps(x, sort_keys=True)
                )
            return result
        if isinstance(value, list):
            return [canonical(v) for v in value]
        if isinstance(value, str) and "T" in value:
            try:
                return datetime.fromisoformat(value).timestamp()
            except ValueError:
                pass
        return value

    # Chặn extra filters/metrics/projections/group; limit/order chỉ khi gold quy định.
    for key, default in (
        ("metrics", []),
        ("selection", []),
        ("filters", None),
        ("group_by", []),
    ):
        if canonical(actual.get(key, default)) != canonical(expected.get(key, default)):
            return False
    return all(
        canonical(actual.get(k)) == canonical(expected[k])
        for k in ("order", "limit")
        if k in expected
    )


def run_semantic(args) -> None:
    if getattr(args, "prepare_only", False):
        raise RuntimeError("Semantic prepare-only chưa hỗ trợ; không được gọi model.")
    manifest = load_scenarios()
    if getattr(args, "generalization", False):
        locked = json.loads((EVALUATIONS / "generalization_checksums.json").read_text(encoding="utf-8"))
        for name, digest in locked.items():
            assert hashlib.sha256((EVALUATIONS / name).read_bytes()).hexdigest() == digest, name
        manifest = json.loads((EVALUATIONS / "generalization.json").read_text(encoding="utf-8"))
        SOURCES.update({name: (source["table"], source["columns"])
                        for name, source in manifest["sources"].items()})
    original_cases = {c["case_id"]: c for c in manifest["cases"]}
    if getattr(args, "adjudicated", False):
        locked = json.loads((EVALUATIONS / "generalization_checksums.json").read_text(encoding="utf-8"))
        assert hashlib.sha256((EVALUATIONS / "annotation_review.json").read_bytes()).hexdigest() == locked["annotation_review.json"]
        audit = json.loads((EVALUATIONS / "annotation_review.json").read_text(encoding="utf-8"))
        assert audit["semantic_sha256"] == hashlib.sha256((EVALUATIONS / "semantic.json").read_bytes()).hexdigest()
        manifest = {**manifest, "cases": [{**c, **audit["overrides"].get(c["case_id"], {})}
                                          for c in manifest["cases"]]}
    catalog_review = None
    if args.catalog_review:
        review_path = (ROOT / args.catalog_review).resolve()
        if not review_path.is_relative_to((ROOT / "artifacts").resolve()):
            raise ValueError("Catalog review must stay in local artifacts")
        catalog_review = json.loads(review_path.read_text(encoding="utf-8"))
        if catalog_review.get("status") != "reviewed":
            raise ValueError("Catalog review has not been confirmed")
    if args.replacement:
        # Chỉ dùng cho chấm held-out sau khi candidate đã khóa; không đưa gold
        # vào payload model hoặc đổi fixture/checksum khi nhận kết quả.
        locked = json.loads((EVALUATIONS / "holdout_checksums.json").read_text(encoding="utf-8"))
        for name, expected in locked.items():
            assert hashlib.sha256((EVALUATIONS / name).read_bytes()).hexdigest() == expected
        manifest = json.loads((EVALUATIONS / "holdout.json").read_text(encoding="utf-8"))
        expectations = [
            {"selection": ["job_code", "fee"], "filters": {"operator": "EQ", "column": "job_code", "value": "0004"}},
            {"metrics": [{"operator": "MIN", "column": "minutes"}]},
            {"metrics": [{"operator": "COUNT_ROWS", "column": None}, {"operator": "SUM", "column": "fee"}],
             "filters": {"operator": "AND", "children": [
                 {"operator": "GTE", "column": "completed_on", "value": "2026-04-01"},
                 {"operator": "LT", "column": "completed_on", "value": "2026-05-01"}]}},
            {"metrics": [{"operator": "COUNT_NON_NULL", "column": "sheets"}]},
            {"metrics": [{"operator": "SUM", "column": "fee"}], "filters": {"operator": "EQ", "column": "job_code", "value": "0999"}},
            {"execution_allowed": False},
        ]
        manifest["cases"] = [{**c, "domain": "printing", "group": "replacement", "split": "held-out",
                              "expected_status": c.get("expected_status", "answered"),
                              "expected_semantics": expectation}
                             for c, expectation in zip(manifest["cases"], expectations, strict=True)]
    selected = [
        next(c for c in manifest["cases"] if c["case_id"] == name)
        for name in args.cases
    ]
    if args.providers != ["gemini"] or not 1 <= args.max_requests <= 495:
        raise RuntimeError("Semantic live chỉ Gemini và cap rõ ràng <=495; grant thực tế vẫn quyết định.")
    if any(
        c["domain"] not in SOURCES
        or "metrics" not in c["expected_semantics"]
        and "selection" not in c["expected_semantics"]
        for c in selected
        if c["expected_status"] == "answered"
    ):
        raise RuntimeError(
            "Case quan hệ/hệ thống cần harness riêng có oracle; không giả lập thành NL PASS."
        )
    domains = sorted(
        {c["domain"] if c["domain"] in SOURCES else "logistics" for c in selected}
    )
    statements = ["BEGIN;"] + [
        (EVALUATIONS / n).read_text(encoding="utf-8") for n in manifest["fixtures"]
    ]
    for domain in domains:
        table_name = SOURCES[domain][0] if domain == "printing" or getattr(args, "generalization", False) else "oracle_fixture." + SOURCES[domain][0]
        statements.append(
            f"SELECT json_build_object('domain','{domain}','rows',json_agg(row_to_json(t))) FROM {table_name} t;"
        )
    statements.append("ROLLBACK;")
    fixtures = {
        r["domain"]: r["rows"]
        for r in [
            json.loads(line, parse_float=Decimal)
            for line in postgres("\n".join(statements)).splitlines()
            if line.strip()
        ]
    }
    session = TestSession()
    report = {
        "mode": "semantic_model_live",
        "provider_contract": "QueryRequest -> QueryPlan",
        "transport": "HTTP proxy",
        "code_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "working_tree_dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, text=True
            ).strip()
        ),
        "app_source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((ROOT / "backend" / "app").glob("*.py"))
        },
        "cases": [],
        "sources": {},
        "stop_reason": None,
        "max_requests": args.max_requests,
        "catalog_review": args.catalog_review,
        "continue_after_refusal": getattr(args, "continue_after_refusal", False),
    }
    used = 0
    try:
        workspace = session.request(
            "/workspaces", {"name": "Locked semantic benchmark"}
        )
        for domain in domains:
            kinds = SOURCES[domain][1]
            sentinel = "__CHATSAR_BENCHMARK_NULL__"
            out = io.StringIO(newline="")
            writer = csv.writer(out)
            writer.writerow(kinds)
            writer.writerows(
                [
                    [sentinel if row[name] is None else row[name] for name in kinds]
                    for row in fixtures[domain]
                ]
            )
            content = out.getvalue().encode()
            reviewed = catalog_review["sources"].get(domain) if catalog_review else None
            if reviewed and reviewed["data_sha256"] != hashlib.sha256(content).hexdigest():
                raise ValueError("Reviewed catalog does not match exact source CSV")
            source = session.publish(
                workspace["id"],
                content,
                kinds,
                sentinel,
                {
                    name
                    for name in kinds
                    if any(r[name] is None for r in fixtures[domain])
                },
                reviewed_metadata=reviewed["columns"] if reviewed else manifest.get("sources", {}).get(domain, {}).get("metadata"),
            )
            source["preview"] = session.request(
                f"/datasets/{source['dataset_id']}/preview"
            )
            assert normalized(
                source["preview"]["rows"], list(kinds.values())
            ) == normalized(
                [[r[n] for n in kinds] for r in fixtures[domain]], list(kinds.values())
            )
            report["sources"][domain] = source
        chats = {}
        baseline = json.loads(
            inside("""
import json
from app.database import get_engine
from app.schema import provider_usage
from sqlalchemy import select
with get_engine().connect() as c:
 print(json.dumps([str(x) for x in c.execute(select(provider_usage.c.id)).scalars()]))
get_engine().dispose()
""")
        )
        report["baseline_usage_ids"] = baseline[:]
        for case in selected:
            if used >= args.max_requests:
                report["stop_reason"] = "request_cap"
                break
            domain = case["domain"] if case["domain"] in SOURCES else "logistics"
            source = report["sources"][domain]
            context = case.get("context", {})
            previous = context.get("previous_case")
            if previous and previous not in chats:
                report["stop_reason"] = "missing_verified_context:" + previous
                break
            if previous:
                chat = chats[previous]
            else:
                chat = session.request(
                    "/conversations",
                    {"workspace_id": workspace["id"], "title": case["case_id"]},
                )["id"]
            started = perf_counter()
            envelope = session.request(
                f"/conversations/{chat}/messages",
                {
                    "question": case["question"],
                    "dataset_revision_id": source["revision_id"],
                    "provider": "gemini",
                },
                request_key=uuid4().hex,
            )
            latency = (perf_counter() - started) * 1000
            diagnostic = json.loads(
                inside(
                    """
import json
from app.database import get_engine
from app.schema import messages,provider_usage
from app.config import get_settings
from sqlalchemy import select
from uuid import UUID
with get_engine().connect() as c:
 plan=c.execute(select(messages.c.query_plan).where(messages.c.conversation_id==UUID('"""
                    + chat
                    + """')).order_by(messages.c.created_at.desc()).limit(1)).scalar_one()
 grant=UUID(get_settings().cloud_grant_id)
 usage=[dict(r) for r in c.execute(select(provider_usage).where(provider_usage.c.grant_id==grant).order_by(provider_usage.c.created_at.desc()).limit(1)).mappings()]
print(json.dumps({'plan':plan,'usage':usage},default=str))
get_engine().dispose()
"""
                )
            )
            usage = diagnostic["usage"][0]
            used += int(usage["id"] not in baseline)
            baseline.append(usage["id"])
            shape = (
                semantic_shape(diagnostic["plan"], source["preview"]["columns"], envelope.get("facts", {}).get("filters", []))
                if diagnostic["plan"]
                else None
            )
            actual = envelope.get("display_rows", [])
            expected = [
                [r[k] for k in case.get("column_types", {})]
                for r in case.get("expected_rows", [])
            ]
            status_ok = envelope["status"] == case["expected_status"]
            result_ok = None
            semantics_ok = None
            if case["expected_status"] == "answered":
                try:
                    result_ok = status_ok and normalized(
                        actual, list(case["column_types"].values())
                    ) == normalized(expected, list(case["column_types"].values()))
                except (ValueError, TypeError, ArithmeticError):
                    result_ok = False
                semantics_ok = bool(
                    shape and semantics_match(shape, case["expected_semantics"])
                )
            passed = (
                status_ok and (result_ok is not False) and (semantics_ok is not False)
            )
            item = {
                "case_id": case["case_id"],
                "domain": domain,
                "group": case["group"],
                "split": case["split"],
                "question": case["question"],
                "expected_status": case["expected_status"],
                "actual_status": envelope["status"],
                "expected_semantics": case["expected_semantics"],
                "actual_semantics": shape,
                "actual_plan": diagnostic["plan"],
                "expected_rows": expected,
                "actual_rows": actual,
                "answer_correct": result_ok,
                "semantics_correct": semantics_ok,
                "pass": passed,
                "failure_layer": None
                if passed
                else "provider"
                if envelope["status"] == "provider_unavailable"
                else "semantic_validation"
                if envelope["status"] != "answered"
                else "planning_or_oracle",
                "error_code": envelope.get("error_code"),
                "message": envelope["display_text"],
                "usage": usage,
                "http_latency_ms": latency,
                "timings_ms": envelope.get("timings_ms"),
                "request_id": envelope["request_id"],
                "trace_id": envelope.get("trace_id"),
                "source_revision": source["revision_id"],
                "checksum": source["checksum"],
                "false_refusal": case["expected_status"] == "answered"
                and envelope["status"] in ("clarify", "unsupported", "insufficient"),
                "silent_wrong_answer": envelope["status"] == "answered"
                and (result_ok is False or semantics_ok is False),
            }
            if getattr(args, "adjudicated", False):
                original = original_cases[case["case_id"]]
                original_expected = [[r[k] for k in original.get("column_types", {})]
                                     for r in original.get("expected_rows", [])]
                item["original_reference_pass"] = bool(
                    status_ok and shape and semantics_match(shape, original["expected_semantics"])
                    and normalized(actual, list(original.get("column_types", {}).values()))
                    == normalized(original_expected, list(original.get("column_types", {}).values()))
                ) if original["expected_status"] == "answered" else passed
                item["adjudicated"] = original != case
            report["cases"].append(item)
            print(
                json.dumps(
                    {
                        k: item[k]
                        for k in (
                            "case_id",
                            "actual_status",
                            "pass",
                            "failure_layer",
                            "message",
                        )
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            continue_refusal = (
                getattr(args, "continue_after_refusal", False) and item["false_refusal"]
            )
            if (not passed and not continue_refusal) or usage["estimated_cost_usd"] is None:
                report["stop_reason"] = "case_failed" if not passed else "usage_unknown"
                break
            if case.get("baseline_ref"):
                chats[case["baseline_ref"]] = chat
    finally:
        report["requests_used"] = used
        target = (ROOT / args.output).resolve()
        if not target.is_relative_to((ROOT / "artifacts").resolve()):
            raise RuntimeError("Evidence ngoài workspace artifacts.")
        target.parent.mkdir(exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, default=str, indent=2),
            encoding="utf-8",
        )
        session.close()
    if report["stop_reason"]:
        raise SystemExit(1)


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
    parser.add_argument(
        "--providers", nargs="+", choices=["gemini", "knowledge"], required=True
    )
    parser.add_argument("--cases", nargs="+", required=True)
    parser.add_argument("--semantic", action="store_true")
    suite = parser.add_mutually_exclusive_group()
    suite.add_argument("--replacement", action="store_true", help="Bộ held-out thay thế đã khóa")
    suite.add_argument("--generalization", action="store_true", help="Schema mới khóa độc lập")
    suite.add_argument("--adjudicated", action="store_true", help="Chấm riêng adjudication, giữ điểm gốc")
    parser.add_argument("--max-requests", type=int, default=0)
    parser.add_argument("--output", default="artifacts/semantic-live.json")
    parser.add_argument("--catalog-review", help="Local source-checksummed metadata reviewed before evaluation")
    parser.add_argument("--continue-after-refusal", action="store_true", help="Giữ FAIL và đo tiếp ca độc lập sau false refusal; không retry hoặc bỏ qua đáp án sai.")
    parser.add_argument("--restart", action="store_true")
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Kiểm tra fidelity fixture qua ingestion, không gọi model",
    )
    args = parser.parse_args()
    if (args.replacement or args.generalization or args.adjudicated) and not args.semantic:
        parser.error("Bộ semantic cần --semantic; không gọi provider.")
    if args.semantic:
        run_semantic(args)
        return
    manifest = verify_checksums()
    cases = [
        next(c for c in manifest["cases"] if c["case_id"] == name)
        for name in args.cases
    ]
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
        workspace = session.request(
            "/workspaces", {"name": "Bounded semantic evaluation"}
        )
        sources = {}
        for domain in domains:
            _, kinds = SOURCES[domain]
            sentinel = "__CHATSAR_BENCHMARK_NULL__"
            assert not any(
                value == sentinel for row in fixtures[domain] for value in row.values()
            )
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
                {
                    name
                    for name in kinds
                    if any(row[name] is None for row in fixtures[domain])
                },
            )
            published = session.request(
                f"/datasets/{sources[domain]['dataset_id']}/preview"
            )
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
                    "/conversations",
                    {"workspace_id": workspace["id"], "title": case["case_id"]},
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
                expected = [
                    [row[k] for k in case["column_types"]]
                    for row in case["expected_rows"]
                ]
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
                    "validation_message": envelope["display_text"]
                    if not answered
                    else None,
                    "executed": answered,
                    "false_refusal": not answered
                    and envelope["status"]
                    in ("clarify", "unsupported", "insufficient"),
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
                    (
                        conversation["id"],
                        session.request(f"/conversations/{conversation['id']}"),
                    )
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
            subprocess.run(
                ["docker", "compose", "restart"], cwd=ROOT, check=True, timeout=60
            )
            subprocess.run(
                ["docker", "compose", "up", "-d", "--wait"],
                cwd=ROOT,
                check=True,
                timeout=90,
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
        previous = (
            json.loads(path.read_text(encoding="utf-8"))["cases"]
            if path.exists()
            else []
        )
        path.write_text(
            json.dumps(
                {"cases": previous + report, "ledger": ledger},
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        print(
            f"Calls recorded in durable ledger: {len(ledger)}. Report: artifacts/model-live.json"
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
