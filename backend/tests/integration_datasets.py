"""Workflow upload → review → PostgreSQL thật với oracle row-level độc lập."""

import io
import unittest
from contextlib import nullcontext
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import MetaData, Table, create_engine, delete, insert, select, update

from app import database as db
from app.auth import SESSION_COOKIE, create_session, digest
from app.config import get_settings
from app.datasets import recover_ingestion
from app.main import create_app
from app.providers import Proposal
from app.query import Predicate, QueryPlan, compile_query, execute_query
from app.schema import (
    conversations,
    datasets,
    jobs,
    messages,
    results,
    revisions,
    users,
    workspaces,
)
from app.tabular import wire


class DatasetIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.owner_a, self.owner_b = uuid4(), uuid4()
        self.client = TestClient(create_app())
        with db.get_engine().begin() as connection:
            for owner in [self.owner_a, self.owner_b]:
                connection.execute(
                    insert(users).values(
                        id=owner,
                        provider="google",
                        provider_subject="test:" + uuid4().hex,
                        display_name="Dataset test",
                    )
                )
            self.token_a = create_session(connection, self.owner_a)
            self.token_b = create_session(connection, self.owner_b)
        self.as_user(self.token_a)
        result = self.client.post("/api/workspaces", json={"name": "Dataset test"})
        self.workspace_id = UUID(result.json()["id"])

    def as_user(self, token: str) -> None:
        self.client.cookies.clear()
        self.client.cookies.set(SESSION_COOKIE, token)
        self.client.headers.update(
            {"Origin": "http://localhost:18181", "X-CSRF-Token": digest("csrf:" + token)}
        )

    def tearDown(self) -> None:
        self.client.close()
        with db.get_engine().begin() as connection:
            conversation_ids = select(conversations.c.id).where(
                conversations.c.workspace_id == self.workspace_id
            )
            message_ids = select(messages.c.id).where(
                messages.c.conversation_id.in_(conversation_ids)
            )
            connection.execute(delete(results).where(results.c.message_id.in_(message_ids)))
            connection.execute(
                delete(messages).where(messages.c.conversation_id.in_(conversation_ids))
            )
            connection.execute(
                delete(conversations).where(conversations.c.workspace_id == self.workspace_id)
            )
            rows = (
                connection.execute(
                    select(revisions)
                    .join(datasets, revisions.c.dataset_id == datasets.c.id)
                    .where(datasets.c.workspace_id == self.workspace_id)
                )
                .mappings()
                .all()
            )
            for row in rows:
                if row["physical_table"]:
                    self.assertEqual(row["physical_table"], "r_" + row["id"].hex)
                    Table(row["physical_table"], MetaData(), schema="data").drop(connection)
                name = str(row["id"]) + row["suffix"]
                self.assertEqual(row["storage_name"], name)
                (Path(get_settings().storage_root) / name).unlink(missing_ok=True)
                connection.execute(delete(jobs).where(jobs.c.revision_id == row["id"]))
                connection.execute(delete(revisions).where(revisions.c.id == row["id"]))
            connection.execute(delete(datasets).where(datasets.c.workspace_id == self.workspace_id))
            connection.execute(delete(workspaces).where(workspaces.c.id == self.workspace_id))
            connection.execute(delete(users).where(users.c.id.in_([self.owner_a, self.owner_b])))

    def upload(self, content: bytes, name: str = "data.csv") -> dict:
        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/datasets", files={"file": (name, content)}
        )
        self.assertEqual(response.status_code, 202, response.text)
        return response.json()

    def preview(self, dataset_id: str, sheet: str | None = None) -> dict:
        response = self.client.get(
            f"/api/datasets/{dataset_id}/preview", params={"sheet_name": sheet} if sheet else None
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def publish_input(self, preview: dict) -> dict:
        allowed = {
            "id",
            "name",
            "data_type",
            "nullable",
            "primary_key",
            "null_values",
            "date_format",
            "decimal_separator",
            "unit",
        }
        columns = [{k: v for k, v in c.items() if k in allowed} for c in preview["columns"]]
        for column in columns:
            if column["name"] == "code":
                column["primary_key"] = True
            if column["name"] == "amount":
                column["null_values"] = [""]
        return {
            "revision_id": preview["revision_id"],
            "columns": columns,
            "sheet_name": preview["sheet_name"] or None,
            "grain": "Một dòng dữ liệu tổng hợp",
            "timezone": "Asia/Ho_Chi_Minh",
            "data_classification": "synthetic",
        }

    def test_csv_publish_typed_rows_idempotency_and_immutable_revision(self) -> None:
        content = (
            "\ufeffcode;amount;day\n0007;0.10;2026-09-01\n0012;0.20;2026-09-02\n0100;;2026-09-03\n"
        ).encode()
        uploaded = self.upload(content)
        preview = self.preview(uploaded["dataset_id"])
        body = self.publish_input(preview)
        response = self.client.post(f"/api/datasets/{uploaded['dataset_id']}/confirm", json=body)
        self.assertEqual(response.status_code, 200, response.text)
        with db.get_engine().connect() as connection:
            revision = (
                connection.execute(
                    select(revisions).where(revisions.c.id == UUID(uploaded["revision_id"]))
                )
                .mappings()
                .one()
            )
            table = Table(
                revision["physical_table"], MetaData(), schema="data", autoload_with=connection
            )
        reader = create_engine(get_settings().reader_database_url.get_secret_value())
        try:
            with reader.connect() as connection:
                result = connection.execute(
                    select(*[table.c[c["id"]] for c in body["columns"]]).order_by(
                        table.c._source_row
                    )
                ).all()
        finally:
            reader.dispose()
        self.assertEqual(
            [tuple(row) for row in result],
            [
                ("0007", Decimal("0.10"), date(2026, 9, 1)),
                ("0012", Decimal("0.20"), date(2026, 9, 2)),
                ("0100", None, date(2026, 9, 3)),
            ],
        )
        self.assertEqual(self.preview(uploaded["dataset_id"])["rows"][2][1], None)
        self.assertEqual(self.upload(content)["revision_id"], uploaded["revision_id"])
        self.assertEqual(
            self.client.post(
                f"/api/datasets/{uploaded['dataset_id']}/confirm", json=body
            ).status_code,
            409,
        )

    def test_duplicate_keys_and_invalid_dates_do_not_publish(self) -> None:
        uploaded = self.upload(b"code,day\n0007,2026-09-01\n0007,2026-09-02\n")
        preview = self.preview(uploaded["dataset_id"])
        response = self.client.post(
            f"/api/datasets/{uploaded['dataset_id']}/confirm", json=self.publish_input(preview)
        )
        self.assertEqual(response.status_code, 422)
        uploaded = self.upload(b"code,day\n0008,2026-02-30\n")
        body = self.publish_input(self.preview(uploaded["dataset_id"]))
        body["columns"][1]["data_type"] = "date"
        self.assertEqual(
            self.client.post(
                f"/api/datasets/{uploaded['dataset_id']}/confirm", json=body
            ).status_code,
            422,
        )
        with db.get_engine().connect() as connection:
            rows = (
                connection.execute(
                    select(revisions.c.physical_table)
                    .join(datasets, revisions.c.dataset_id == datasets.c.id)
                    .where(datasets.c.workspace_id == self.workspace_id)
                )
                .scalars()
                .all()
            )
        self.assertEqual(rows, [None, None])

    def test_dataset_job_and_upload_owner_isolation(self) -> None:
        uploaded = self.upload(b"code,amount\n0007,0.10\n")
        body = self.publish_input(self.preview(uploaded["dataset_id"]))
        self.as_user(self.token_b)
        for path in [
            f"/api/datasets/{uploaded['dataset_id']}/preview",
            f"/api/jobs/{uploaded['job_id']}",
            f"/api/workspaces/{self.workspace_id}/datasets",
        ]:
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(
            self.client.post(
                f"/api/datasets/{uploaded['dataset_id']}/confirm", json=body
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                f"/api/workspaces/{self.workspace_id}/datasets",
                files={"file": ("x.csv", b"a\n1\n")},
            ).status_code,
            404,
        )

    def test_excel_sheet_selection_and_formula_rejection(self) -> None:
        workbook = Workbook()
        workbook.active.title = "Other"
        workbook.active.append(["unused"])
        workbook.active.append([1])
        sheet = workbook.create_sheet("Data")
        sheet.append(["code", "amount"])
        sheet.append(["0007", 0.1])
        stream = io.BytesIO()
        workbook.save(stream)
        uploaded = self.upload(stream.getvalue(), "data.xlsx")
        self.assertEqual(self.preview(uploaded["dataset_id"])["sheets"], ["Other", "Data"])
        preview = self.preview(uploaded["dataset_id"], "Data")
        self.assertEqual(
            self.client.post(
                f"/api/datasets/{uploaded['dataset_id']}/confirm", json=self.publish_input(preview)
            ).status_code,
            200,
        )
        sheet.append(["0008", "=1+1"])
        stream = io.BytesIO()
        workbook.save(stream)
        response = self.client.post(
            f"/api/workspaces/{self.workspace_id}/datasets",
            files={"file": ("formula.xlsx", stream.getvalue())},
            data={"sheet_name": "Data"},
        )
        self.assertEqual(response.status_code, 422)

    def test_interrupted_ingestion_is_retryable_without_new_revision(self) -> None:
        content = b"code,amount\n0007,0.10\n"
        uploaded = self.upload(content)
        with db.get_engine().begin() as connection:
            connection.execute(
                update(revisions)
                .where(revisions.c.id == UUID(uploaded["revision_id"]))
                .values(status="validating")
            )
        recover_ingestion()
        self.assertEqual(
            self.client.get(f"/api/jobs/{uploaded['job_id']}").json()["error_code"], "INTERRUPTED"
        )
        self.assertEqual(self.upload(content)["revision_id"], uploaded["revision_id"])
        self.assertEqual(self.preview(uploaded["dataset_id"])["status"], "needs_review")

    def test_corrupt_file_and_upload_cap(self) -> None:
        for name, content, status in [
            ("bad.xlsx", b"broken", 422),
            ("too-big.csv", b"x" * (20 * 1024 * 1024 + 1), 413),
        ]:
            response = self.client.post(
                f"/api/workspaces/{self.workspace_id}/datasets", files={"file": (name, content)}
            )
            self.assertEqual(response.status_code, status)

    def published(self, content: bytes, kinds: dict | None = None) -> dict:
        uploaded = self.upload(content)
        preview = self.preview(uploaded["dataset_id"])
        review = self.publish_input(preview)
        for column in review["columns"]:
            if kinds and column["name"] in kinds:
                column["data_type"] = kinds[column["name"]]
            if column["data_type"] != "text":
                column["null_values"] = [""]
        response = self.client.post(f"/api/datasets/{uploaded['dataset_id']}/confirm", json=review)
        self.assertEqual(response.status_code, 200, response.text)
        with db.get_engine().connect() as connection:
            revision = dict(
                connection.execute(
                    select(revisions).where(revisions.c.id == UUID(uploaded["revision_id"]))
                )
                .mappings()
                .one()
            )
            revision["checksum"] = response.json()["checksum"]
        return revision

    def plan(self, revision: dict, question: str, **fields: object) -> QueryPlan:
        return QueryPlan.model_validate(
            {
                "task": "SQL",
                "table_id": str(revision["dataset_id"]),
                "source_revision_id": str(revision["id"]),
                "raw_user_spans": [question],
                "coverage": [question],
                **fields,
            }
        )

    def test_typed_compiler_postgres_count_null_decimal_and_metamorphic(self) -> None:
        revision = self.published(b"code,amount\n0007,0.10\n0012,0.20\n0100,\n0101,0.00\n")
        code, amount = [c["id"] for c in revision["columns"]]
        expected = {
            "COUNT_ROWS": 4,
            "COUNT_NON_NULL": 3,
            "COUNT_DISTINCT": 3,
            "SUM": Decimal("0.30"),
            "AVG": Decimal("0.10"),
            "MIN": Decimal("0.00"),
            "MAX": Decimal("0.20"),
        }
        for operator, gold in expected.items():
            aggregate = {"operator": operator, "output_id": "total"}
            if operator != "COUNT_ROWS":
                aggregate["column_id"] = amount
            plan = self.plan(revision, "Kiểm thử", aggregations=[aggregate])
            rows, _ = execute_query(compile_query(plan, revision, "Kiểm thử"))
            self.assertEqual(Decimal(str(rows[0][0])), Decimal(str(gold)))
        empty = self.plan(
            revision,
            "9999",
            aggregations=[{"operator": "SUM", "column_id": amount, "output_id": "total"}],
            filters={
                "operator": "EQ",
                "column_id": code,
                "literal": {"raw_phrase": "9999", "value_type": "text", "candidate_value": "9999"},
            },
        )
        self.assertEqual(execute_query(compile_query(empty, revision, "9999"))[0], [[None]])
        grouped = self.plan(
            revision,
            "Nhóm",
            select_columns=[code],
            group_by=[code],
            aggregations=[{"operator": "SUM", "column_id": amount, "output_id": "total"}],
            order_by=[{"field_id": code}],
        )
        self.assertEqual(
            execute_query(compile_query(grouped, revision, "Nhóm"))[0],
            [["0007", "0.10"], ["0012", "0.20"], ["0100", None], ["0101", "0.00"]],
        )
        # Thứ tự nguồn và bản ghi ngoài điều kiện không đổi phép SUM đã lọc.
        filtered = self.plan(
            revision,
            "0007",
            aggregations=[{"operator": "SUM", "column_id": amount, "output_id": "total"}],
            filters={
                "operator": "EQ",
                "column_id": code,
                "literal": {"raw_phrase": "0007", "value_type": "text", "candidate_value": "0007"},
            },
        )
        self.assertEqual(execute_query(compile_query(filtered, revision, "0007"))[0], [["0.10"]])

    def test_chat_result_history_ownership_idempotency_and_verified_followup(self) -> None:
        revision = self.published(b"code,amount\n0007,0.10\n0012,0.20\n0100,\n")
        code, amount = [c["id"] for c in revision["columns"]]
        created = self.client.post(
            "/api/conversations", json={"workspace_id": str(self.workspace_id)}
        )
        conversation_id = created.json()["id"]
        path = f"/api/conversations/{conversation_id}/messages"
        body = {"question": "Tổng 0007", "dataset_revision_id": str(revision["id"])}
        plan = self.plan(
            revision,
            body["question"],
            aggregations=[{"operator": "SUM", "column_id": amount, "output_id": "total"}],
            entities=["0007"],
            filters={
                "operator": "EQ",
                "column_id": code,
                "literal": {"raw_phrase": "0007", "candidate_value": "0007", "value_type": "text"},
            },
        )

        def propose(question: str, source: dict, provider: str, context: dict | None) -> Proposal:
            if question == "Còn trung bình?":
                self.assertEqual(context["question"], "Tổng 0007")
                self.assertNotIn("display_text", context)
                followup = plan.model_copy(
                    update={"raw_user_spans": [question], "coverage": [question]}
                )
                followup.aggregations[0] = followup.aggregations[0].model_copy(
                    update={"operator": "AVG"}
                )
                return Proposal(followup, "offline", "offline", None, None, 0, None)
            return Proposal(plan, "offline", "offline", None, None, 0, None)

        with (
            patch("app.conversation.generate_proposal", side_effect=propose) as mocked,
            patch("app.conversation.observation", side_effect=lambda *a, **k: nullcontext(None)),
        ):
            first = self.client.post(
                path, json=body, headers={"Idempotency-Key": "test-request-key"}
            )
            self.assertEqual(first.status_code, 200, first.text)
            answer = first.json()
            self.assertEqual(answer["status"], "answered", answer)
            self.assertEqual(answer["facts"]["rows"], [["0.10"]])
            self.assertEqual(answer["facts"]["scope"]["checksum"], revision["checksum"])
            again = self.client.post(
                path, json=body, headers={"Idempotency-Key": "test-request-key"}
            )
            self.assertEqual(again.json()["result_id"], answer["result_id"])
            self.assertEqual(mocked.call_count, 1)
            changed = self.client.post(
                path,
                json={**body, "question": "Khác"},
                headers={"Idempotency-Key": "test-request-key"},
            )
            self.assertEqual(changed.status_code, 409)
            followup = self.client.post(
                path,
                json={**body, "question": "Còn trung bình?"},
                headers={"Idempotency-Key": "followup-request"},
            )
            self.assertEqual(followup.json()["status"], "answered", followup.text)
            self.assertEqual(
                len(self.client.get(f"/api/conversations/{conversation_id}").json()["messages"]), 2
            )
            self.assertEqual(
                self.client.get(f"/api/results/{answer['result_id']}").json()["facts"]["rows"],
                [["0.10"]],
            )
            self.as_user(self.token_b)
            for target in [
                f"/api/conversations/{conversation_id}",
                f"/api/results/{answer['result_id']}",
            ]:
                self.assertEqual(self.client.get(target).status_code, 404)
            self.assertEqual(
                self.client.post(
                    path, json=body, headers={"Idempotency-Key": "forbidden-request"}
                ).status_code,
                404,
            )
            self.assertEqual(mocked.call_count, 2)
            self.as_user(self.token_a)
            other = self.published(b"code,amount\n0099,1.00\n")
            stale = self.client.post(
                path,
                json={**body, "dataset_revision_id": str(other["id"])},
                headers={"Idempotency-Key": "changed-source-key"},
            )
            self.assertEqual(stale.status_code, 409)
            self.assertEqual(stale.json()["error"]["code"], "STALE_CONTEXT")
            raw = self.client.post(
                path,
                json={**body, "sql": "SELECT 1"},
                headers={"Idempotency-Key": "raw-sql-request"},
            )
            self.assertEqual(raw.status_code, 422)
            self.assertEqual(mocked.call_count, 2)

    def test_second_schema_oracle_and_unpublished_source_no_provider_call(self) -> None:
        revision = self.published(
            b"room_type,nights,charge\nstandard,2,100.05\nsuite,1,200.10\nstandard,0,\nsuite,3,0.00\n"
        )
        room, nights, charge = [c["id"] for c in revision["columns"]]
        plan = self.plan(
            revision,
            "Theo phòng",
            select_columns=[room],
            group_by=[room],
            aggregations=[{"operator": "SUM", "column_id": nights, "output_id": "nights"}],
            order_by=[{"field_id": room}],
        )
        rows, _ = execute_query(compile_query(plan, revision, "Theo phòng"))
        self.assertEqual(rows, [["standard", "2"], ["suite", "4"]])
        # Oracle SQL viết tay riêng, không gọi compiler hay dùng SQL mà compiler tạo.
        with db.get_reader_engine().connect() as connection:
            gold = connection.exec_driver_sql(
                f'SELECT "{room}",SUM("{nights}") FROM data."{revision["physical_table"]}" '
                f'GROUP BY "{room}" ORDER BY "{room}"'
            ).all()
        self.assertEqual(rows, [[wire(value) for value in row] for row in gold])
        created = self.client.post(
            "/api/conversations", json={"workspace_id": str(self.workspace_id)}
        ).json()
        uploaded = self.upload(b"other,value\nx,1\n")
        with patch("app.conversation.generate_proposal") as mocked:
            response = self.client.post(
                f"/api/conversations/{created['id']}/messages",
                json={"question": "Tổng?", "dataset_revision_id": uploaded["revision_id"]},
                headers={"Idempotency-Key": "not-ready-request"},
            )
            self.assertEqual(response.status_code, 409)
            mocked.assert_not_called()

    def test_timestamp_half_open_and_boolean_tree_in_sort_limit(self) -> None:
        revision = self.published(
            b"code,at,amount\n0001,2026-08-31T17:00:00Z,0.10\n0002,2026-09-30T16:59:59Z,0.20\n0003,2026-09-30T17:00:00Z,9.99\n",
            {"at": "timestamp"},
        )
        code, at, amount = [c["id"] for c in revision["columns"]]
        start, end = "2026-09-01T00:00:00+07:00", "2026-10-01T00:00:00+07:00"
        question = f"{start} {end} 0001 0002 0"

        def leaf(operator: str, column_id: str, raw: str, kind: str) -> dict:
            return {
                "operator": operator,
                "column_id": column_id,
                "literal": {"raw_phrase": raw, "candidate_value": raw, "value_type": kind},
            }

        plan = self.plan(
            revision,
            question,
            select_columns=[code, amount],
            limit=1,
            filters={
                "operator": "AND",
                "children": [
                    leaf("GTE", at, start, "timestamp"),
                    leaf("LT", at, end, "timestamp"),
                    {
                        "operator": "OR",
                        "children": [
                            leaf("EQ", code, "0001", "text"),
                            leaf("EQ", code, "0002", "text"),
                        ],
                    },
                    leaf("GT", amount, "0", "numeric"),
                ],
            },
            order_by=[{"field_id": code, "direction": "desc"}],
        )
        self.assertEqual(
            execute_query(compile_query(plan, revision, question))[0], [["0002", "0.20"]]
        )
        plan = plan.model_copy(
            update={
                "filters": Predicate.model_validate(
                    {
                        "operator": "IN",
                        "column_id": code,
                        "values": [
                            {"raw_phrase": v, "candidate_value": v, "value_type": "text"}
                            for v in ["0001", "0002"]
                        ],
                    }
                )
            }
        )
        self.assertEqual(
            execute_query(compile_query(plan, revision, question))[0], [["0002", "0.20"]]
        )

    def test_row_reordering_and_irrelevant_records_preserve_filtered_sum(self) -> None:
        for content in [
            b"code,amount\n0007,0.10\n0012,0.20\n",
            b"code,amount\n0999,999.99\n0012,0.20\n0007,0.10\n",
        ]:
            revision = self.published(content)
            code, amount = [c["id"] for c in revision["columns"]]
            plan = self.plan(
                revision,
                "0007",
                aggregations=[{"operator": "SUM", "column_id": amount, "output_id": "total"}],
                filters={
                    "operator": "EQ",
                    "column_id": code,
                    "literal": {
                        "raw_phrase": "0007",
                        "candidate_value": "0007",
                        "value_type": "text",
                    },
                },
            )
            self.assertEqual(execute_query(compile_query(plan, revision, "0007"))[0], [["0.10"]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
