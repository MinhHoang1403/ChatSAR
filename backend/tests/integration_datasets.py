"""Workflow upload → review → PostgreSQL thật với oracle row-level độc lập."""

import io
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import MetaData, Table, create_engine, delete, insert, select, update

from app import database as db
from app.auth import SESSION_COOKIE, create_session, digest
from app.config import get_settings
from app.datasets import recover_ingestion
from app.main import create_app
from app.schema import datasets, jobs, revisions, users, workspaces


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
