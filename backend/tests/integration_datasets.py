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
    dataset_sharing_events,
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
    def test_missing_explicit_unknown_filter_stops_before_sql_and_empty_sum_remains_null(
        self,
    ) -> None:
        revision = self.published(b"code,amount\n0007,0.10\n0012,0.20\n")
        code, amount = [c["id"] for c in revision["columns"]]
        question = "Tổng amount khi code ghi đúng là missing?"
        aggregate = [{"operator": "SUM", "column_id": amount, "output_id": "total"}]
        plan = self.plan(revision, question, aggregations=aggregate)
        chat = self.client.post(
            "/api/conversations", json={"workspace_id": str(self.workspace_id)}
        ).json()["id"]
        path = f"/api/conversations/{chat}/messages"
        body = {"question": question, "dataset_revision_id": str(revision["id"])}
        with (
            patch(
                "app.conversation.generate_proposal",
                return_value=Proposal(plan, "gemini", "offline", None, None, 0, None),
            ),
            patch("app.conversation.execute_query") as execute,
        ):
            blocked = self.client.post(
                path, json=body, headers={"Idempotency-Key": uuid4().hex}
            ).json()
            self.assertEqual(blocked["status"], "clarify")
            self.assertFalse(blocked["processing"]["sql"]["compiled"])
            execute.assert_not_called()
        plan.filters = Predicate.model_validate(
            {
                "operator": "EQ",
                "column_id": code,
                "literal": {
                    "raw_phrase": "missing",
                    "candidate_value": "missing",
                    "value_type": "text",
                },
            }
        )
        with patch(
            "app.conversation.generate_proposal",
            return_value=Proposal(plan, "gemini", "offline", None, None, 0, None),
        ):
            empty = self.client.post(
                path, json=body, headers={"Idempotency-Key": uuid4().hex}
            ).json()
        self.assertEqual(empty["status"], "answered")
        self.assertEqual(empty["display_rows"], [[None]])
        self.assertEqual(empty["facts"]["filters"][0]["source_match"], "no_match")

    def test_ready_private_permission_can_be_granted_and_revoked_without_republish(self) -> None:
        revision = self.published(b"code,amount\n0007,0.10\n")
        with db.get_engine().begin() as connection:
            connection.execute(
                update(revisions)
                .where(revisions.c.id == revision["id"])
                .values(data_classification="private", sharing_providers=[])
            )
        dataset_id = str(revision["dataset_id"])
        before = self.preview(dataset_id)
        path = f"/api/datasets/{dataset_id}/sharing"
        body = {"revision_id": str(revision["id"]), "sharing_providers": ["gemini"]}
        self.as_user(self.token_b)
        self.assertEqual(self.client.patch(path, json=body).status_code, 404)
        self.as_user(self.token_a)
        csrf = self.client.headers.pop("X-CSRF-Token")
        self.assertEqual(self.client.patch(path, json=body).status_code, 403)
        self.client.headers["X-CSRF-Token"] = csrf
        self.assertEqual(
            self.client.patch(path, json={**body, "sharing_providers": ["unknown"]}).status_code,
            422,
        )
        self.assertEqual(
            self.client.patch(path, json={**body, "data_classification": "synthetic"}).status_code,
            422,
        )
        self.assertEqual(self.client.patch(path, json=body).status_code, 200)
        self.assertEqual(self.client.patch(path, json=body).status_code, 200)
        allowed = self.preview(dataset_id)
        self.assertEqual(allowed, {**before, "sharing_providers": ["gemini"]})
        # Adapter thật, transport mock; kiểm quyền mới được đọc từ catalog ở HTTP.
        from app import providers
        from app.planning import QueryRequest

        plan = QueryRequest(
            task="SQL",
            table_id=str(revision["dataset_id"]),
            source_revision_id=str(revision["id"]),
            result_shape="scalar",
            required_columns=[],
            raw_user_spans=["Tổng"],
            select_columns=[],
            aggregations=[
                {"operator": "SUM", "column_id": revision["columns"][1]["id"], "output_id": "total"}
            ],
            conditions=[],
            group_by=[],
            order_by=[],
            limit=100,
            unresolved=[],
        )
        chat = self.client.post(
            "/api/conversations", json={"workspace_id": str(self.workspace_id)}
        ).json()["id"]
        query = {
            "question": "Tổng",
            "dataset_revision_id": str(revision["id"]),
            "provider": "knowledge",
        }
        with patch.object(providers, "reserve_call", return_value=None) as reserve:
            denied = self.client.post(
                f"/api/conversations/{chat}/messages",
                json=query,
                headers={"Idempotency-Key": uuid4().hex},
            ).json()
            self.assertEqual(denied["error_code"], "DATA_PERMISSION_REQUIRED")
            reserve.assert_not_called()
        # Không sửa provider/key/config runtime để test đường được phép.
        from types import SimpleNamespace

        from pydantic import SecretStr

        settings = get_settings().model_copy(
            update={"gemini_enabled": True, "gemini_api_key": SecretStr("offline-placeholder")}
        )
        with (
            patch.object(providers, "get_settings", return_value=settings),
            patch.object(providers, "reserve_call", return_value=None) as reserve,
            patch.object(providers, "finish_call"),
            patch.object(
                providers.genai,
                "Client",
                return_value=nullcontext(
                    SimpleNamespace(
                        interactions=SimpleNamespace(
                            create=lambda **kw: SimpleNamespace(
                                output_text=plan.model_dump_json(), id="offline", usage=None
                            )
                        )
                    )
                ),
            ),
        ):
            reply = self.client.post(
                f"/api/conversations/{chat}/messages",
                json={**query, "provider": "gemini"},
                headers={"Idempotency-Key": uuid4().hex},
            ).json()
            self.assertEqual(reply["status"], "answered", reply)
            self.assertEqual(reply["display_rows"], [["0.10"]])
            self.assertEqual(reserve.call_count, 1)
        self.assertEqual(
            self.client.patch(path, json={**body, "sharing_providers": []}).status_code, 200
        )
        self.assertEqual(self.preview(dataset_id), before)
        with patch.object(providers, "reserve_call") as reserve:
            denied = self.client.post(
                f"/api/conversations/{chat}/messages",
                json={**query, "provider": "gemini"},
                headers={"Idempotency-Key": uuid4().hex},
            ).json()
            self.assertEqual(denied["error_code"], "DATA_PERMISSION_REQUIRED")
            reserve.assert_not_called()
        with db.get_engine().connect() as connection:
            events = (
                connection.execute(
                    select(dataset_sharing_events)
                    .where(dataset_sharing_events.c.revision_id == revision["id"])
                    .order_by(dataset_sharing_events.c.created_at)
                )
                .mappings()
                .all()
            )
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["previous_providers"], [])
        self.assertEqual(events[1]["sharing_providers"], [])

    def test_chat_management_preserves_sources_and_other_owners(self) -> None:
        revision = self.published("code,Tổng\n0007,0.10\n".encode(), aliases={"Tổng": ["Phí"]})
        chat = self.client.post(
            "/api/conversations", json={"workspace_id": str(self.workspace_id), "title": "Before"}
        ).json()["id"]
        plan = self.plan(
            revision,
            "Tổng",
            aggregations=[
                {"operator": "SUM", "column_id": revision["columns"][1]["id"], "output_id": "total"}
            ],
        )
        with patch(
            "app.conversation.generate_proposal",
            return_value=Proposal(plan, "offline", "offline", None, None, 0, None),
        ):
            response = self.client.post(
                f"/api/conversations/{chat}/messages",
                json={"question": "Tổng", "dataset_revision_id": str(revision["id"])},
                headers={"Idempotency-Key": "management-request"},
            )
        self.assertEqual(response.json()["status"], "answered", response.text)
        self.assertEqual(response.json()["facts"]["columns"][0]["label"], "Tổng Phí")
        self.assertEqual(response.json()["facts"]["rows"], [["0.10"]])
        result_id = response.json()["result_id"]
        self.assertEqual(
            self.client.patch(f"/api/conversations/{chat}", json={"title": "After"}).status_code,
            200,
        )
        listed = self.client.get(f"/api/conversations?workspace_id={self.workspace_id}").json()[0]
        self.assertEqual(listed["revision_id"], str(revision["id"]))
        self.assertTrue(listed["dataset_name"])
        self.assertEqual(len(self.client.get(f"/api/conversations/{chat}").json()["messages"]), 1)
        self.as_user(self.token_b)
        self.assertEqual(self.client.delete(f"/api/conversations/{chat}").status_code, 404)
        self.assertEqual(
            self.client.patch(f"/api/conversations/{chat}", json={"title": "Spoof"}).status_code,
            404,
        )
        self.assertEqual(
            self.client.delete(f"/api/workspaces/{self.workspace_id}/conversations").status_code,
            404,
        )
        self.as_user(self.token_a)
        for title in [" ", "x" * 121, "bad\nname"]:
            self.assertEqual(
                self.client.patch(f"/api/conversations/{chat}", json={"title": title}).status_code,
                422,
            )
        self.assertEqual(self.client.delete(f"/api/conversations/{chat}").status_code, 204)
        self.assertEqual(self.client.delete(f"/api/conversations/{chat}").status_code, 204)
        self.assertEqual(self.client.get(f"/api/results/{result_id}").status_code, 404)
        self.assertEqual(self.client.get(f"/api/conversations/{chat}").status_code, 404)
        self.assertEqual(self.preview(str(revision["dataset_id"]))["status"], "ready")

    def test_bulk_delete_scope_and_csrf(self) -> None:
        other = self.client.post("/api/workspaces", json={"name": "Other"}).json()["id"]
        other_chat = self.client.post("/api/conversations", json={"workspace_id": other}).json()[
            "id"
        ]
        try:
            for _ in range(2):
                self.client.post(
                    "/api/conversations", json={"workspace_id": str(self.workspace_id)}
                )
            path = f"/api/workspaces/{self.workspace_id}/conversations"
            csrf = self.client.headers.pop("X-CSRF-Token")
            self.assertEqual(self.client.delete(path).status_code, 403)
            self.client.headers["X-CSRF-Token"] = csrf
            self.assertEqual(self.client.delete(path).status_code, 204)
            self.assertEqual(self.client.delete(path).status_code, 204)
            self.assertEqual(
                self.client.get(f"/api/conversations?workspace_id={self.workspace_id}").json(), []
            )
            self.assertEqual(self.client.get(f"/api/conversations/{other_chat}").status_code, 200)
        finally:
            self.client.delete(f"/api/workspaces/{other}/conversations")
            with db.get_engine().begin() as connection:
                connection.execute(delete(workspaces).where(workspaces.c.id == UUID(other)))

    def test_pending_send_blocks_delete_and_duplicate_dispatch(self) -> None:
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event

        started, release = Event(), Event()
        revision = self.published(b"code,amount\n0007,0.10\n")
        chat = self.client.post(
            "/api/conversations", json={"workspace_id": str(self.workspace_id)}
        ).json()["id"]
        plan = self.plan(
            revision,
            "Tổng",
            aggregations=[
                {"operator": "SUM", "column_id": revision["columns"][1]["id"], "output_id": "total"}
            ],
        )

        def blocked(*args):
            started.set()
            if not release.wait(10):
                raise AssertionError("Test release timed out")
            return Proposal(plan, "offline", "offline", None, None, 0, None)

        body = {"question": "Tổng", "dataset_revision_id": str(revision["id"])}
        with (
            patch("app.conversation.generate_proposal", side_effect=blocked) as calls,
            ThreadPoolExecutor(max_workers=1) as pool,
        ):
            future = pool.submit(
                self.client.post,
                f"/api/conversations/{chat}/messages",
                json=body,
                headers={"Idempotency-Key": "pending-request-key"},
            )
            try:
                self.assertTrue(started.wait(5))
                self.assertEqual(self.client.delete(f"/api/conversations/{chat}").status_code, 409)
                self.assertEqual(
                    self.client.patch(
                        f"/api/datasets/{revision['dataset_id']}/sharing",
                        json={"revision_id": str(revision["id"]), "sharing_providers": []},
                    ).status_code,
                    409,
                )
                self.assertEqual(
                    self.client.delete(
                        f"/api/workspaces/{self.workspace_id}/conversations"
                    ).status_code,
                    409,
                )
                duplicate = self.client.post(
                    f"/api/conversations/{chat}/messages",
                    json=body,
                    headers={"Idempotency-Key": "another-request-key"},
                )
                self.assertEqual(duplicate.status_code, 409)
            finally:
                release.set()
            self.assertEqual(future.result(timeout=10).json()["status"], "answered")
            self.assertEqual(calls.call_count, 1)
        self.assertEqual(self.client.delete(f"/api/conversations/{chat}").status_code, 204)

    def test_sql_evidence_is_parameterized_per_message_and_owner_scoped(self) -> None:
        revision = self.published(b"code,amount\n0007,0.10\n0012,0.20\n")
        code, amount = [c["id"] for c in revision["columns"]]
        chat = self.client.post(
            "/api/conversations", json={"workspace_id": str(self.workspace_id)}
        ).json()["id"]
        plan = self.plan(
            revision,
            "0007",
            select_columns=[code, amount],
            filters={
                "operator": "EQ",
                "column_id": code,
                "literal": {"raw_phrase": "0007", "candidate_value": "0007", "value_type": "text"},
            },
        )
        captured = []

        def execute(compiled, **kwargs):
            captured.append(
                str(
                    compiled.statement.compile(
                        dialect=db.get_reader_engine().dialect,
                        compile_kwargs={"render_postcompile": True},
                    )
                )
            )
            return execute_query(compiled, **kwargs)

        with (
            patch(
                "app.conversation.generate_proposal",
                return_value=Proposal(plan, "gemini", "offline-model", 11, 7, 12.5, "offline"),
            ) as provider,
            patch("app.conversation.execute_query", side_effect=execute),
        ):
            path = f"/api/conversations/{chat}/messages"
            body = {"question": "0007", "dataset_revision_id": str(revision["id"])}
            first = self.client.post(
                path, json=body, headers={"Idempotency-Key": "evidence-request-key"}
            ).json()
            evidence = first["processing"]
            self.assertEqual(evidence["sql"]["statement"], captured[0])
            self.assertNotIn("0007", evidence["sql"]["statement"])
            self.assertIn("%(", evidence["sql"]["statement"])
            self.assertTrue(evidence["sql"]["compiled"])
            self.assertEqual(evidence["sql"]["execution_status"], "succeeded")
            self.assertEqual(first["display_rows"], [["0007", "0.10"]])
            self.assertIn("0,10", first["display_text"])
            self.assertEqual(evidence["source"]["revision_id"], str(revision["id"]))
            self.assertEqual(evidence["provider"]["model"], "offline-model")
            self.assertEqual(evidence["provider"]["latency_ms"], 12.5)
            second = self.client.post(
                path, json=body, headers={"Idempotency-Key": "evidence-request-key"}
            ).json()
            self.assertEqual(second["processing"], evidence)
            result_path = f"/api/results/{first['result_id']}"
            for _ in range(2):
                self.assertEqual(self.client.get(result_path).json()["processing"], evidence)
                self.assertEqual(
                    self.client.get(f"/api/conversations/{chat}").json()["messages"][0]["envelope"][
                        "processing"
                    ],
                    evidence,
                )
            self.assertEqual(provider.call_count, 1)
            self.assertEqual(len(captured), 1)
        self.as_user(self.token_b)
        self.assertEqual(self.client.get(result_path).status_code, 404)
        self.assertEqual(self.client.get(f"/api/conversations/{chat}").status_code, 404)

    def test_error_stages_do_not_borrow_or_invent_sql(self) -> None:
        from sqlalchemy.exc import CompileError, OperationalError

        from app.errors import AppError
        from app.providers import ProviderError

        revision = self.published(b"code,amount\n0007,0.10\n")
        plan = self.plan(
            revision,
            "Tổng",
            aggregations=[
                {"operator": "SUM", "column_id": revision["columns"][1]["id"], "output_id": "total"}
            ],
        )
        cases = [
            (
                "generate_proposal",
                ProviderError("PROVIDER_DISABLED", "disabled"),
                "provider_preparation",
                False,
                "not_started",
            ),
            (
                "generate_proposal",
                ProviderError(
                    "PROVIDER_TIMEOUT",
                    "timeout",
                    stage="provider_call",
                    provider_name="gemini",
                    model="offline",
                    latency_ms=12,
                ),
                "provider_call",
                False,
                "not_started",
            ),
            (
                "generate_proposal",
                ProviderError("PROVIDER_SCHEMA", "400", stage="provider_call"),
                "provider_call",
                False,
                "not_started",
            ),
            (
                "generate_proposal",
                ProviderError("PROVIDER_SCHEMA", "invalid", stage="proposal_parse"),
                "proposal_parse",
                False,
                "not_started",
            ),
            (
                "generate_proposal",
                AppError(503, "USAGE_UNKNOWN", "unknown"),
                "provider_preparation",
                False,
                "not_started",
            ),
            (
                "generate_proposal",
                AppError(503, "CALL_LIMIT_REACHED", "quota"),
                "provider_preparation",
                False,
                "not_started",
            ),
            (
                "generate_proposal",
                AppError(503, "DATA_PERMISSION_REQUIRED", "private"),
                "provider_preparation",
                False,
                "not_started",
            ),
            (
                "compile_query",
                AppError(422, "QUERY_CLARIFY", "Thiếu điều kiện."),
                "semantic_validation",
                False,
                "not_started",
            ),
            (
                "ground_catalog",
                OperationalError("secret db", {}, Exception("secret password")),
                "catalog",
                False,
                "not_started",
            ),
            (
                "capture_sql",
                CompileError("secret compile"),
                "sql_compilation",
                False,
                "not_started",
            ),
            ("compose_answer", ValueError("secret compose"), "composition", True, "succeeded"),
        ]
        for target, error, stage, compiled, execution in cases:
            with self.subTest(target=target, stage=stage):
                chat = self.client.post(
                    "/api/conversations", json={"workspace_id": str(self.workspace_id)}
                ).json()["id"]
                path = (
                    "app.conversation." + target
                    if target != "capture_sql"
                    else "app.evidence.Processing.capture_sql"
                )
                with (
                    patch(
                        "app.conversation.generate_proposal",
                        return_value=Proposal(plan, "gemini", "offline", 1, 1, 2, None),
                    ),
                    patch(path, side_effect=error),
                ):
                    response = self.client.post(
                        f"/api/conversations/{chat}/messages",
                        json={"question": "Tổng", "dataset_revision_id": str(revision["id"])},
                        headers={"Idempotency-Key": uuid4().hex},
                    )
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                e = body["processing"]
                self.assertEqual(e["failed_stage"], stage, body)
                self.assertEqual(e["sql"]["compiled"], compiled)
                self.assertEqual(e["sql"]["execution_status"], execution)
                self.assertEqual(body["display_rows"], [])
                self.assertNotIn("secret", response.text)

    def test_clarify_unsupported_and_missing_source_have_no_sql(self) -> None:
        from app.query import QueryPlan

        revision = self.published(b"code,amount\n0007,0.10\n")
        chat = self.client.post(
            "/api/conversations", json={"workspace_id": str(self.workspace_id)}
        ).json()["id"]
        for task, status in [("CLARIFY", "clarify"), ("UNSUPPORTED", "unsupported")]:
            proposal = Proposal(QueryPlan(task=task), "gemini", "offline", 1, 1, 2, None)
            with (
                patch("app.conversation.generate_proposal", return_value=proposal),
                patch("app.conversation.execute_query") as execute,
            ):
                response = self.client.post(
                    f"/api/conversations/{chat}/messages",
                    json={"question": "Cần giải thích", "dataset_revision_id": str(revision["id"])},
                    headers={"Idempotency-Key": uuid4().hex},
                ).json()
            self.assertEqual(response["status"], status)
            self.assertEqual(response["processing"]["failed_stage"], "semantic_validation")
            self.assertFalse(response["processing"]["sql"]["compiled"])
            execute.assert_not_called()
        uploaded = self.upload(b"unconfirmed\n1\n")
        response = self.client.post(
            f"/api/conversations/{chat}/messages",
            json={"question": "?", "dataset_revision_id": uploaded["revision_id"]},
            headers={"Idempotency-Key": uuid4().hex},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["diagnostics"]["failed_stage"], "authorization")
        self.assertFalse(response.json()["diagnostics"]["sql"]["compiled"])

    def test_persistence_failure_keeps_checkpoint_without_repeating_generation(self) -> None:
        from sqlalchemy import event
        from sqlalchemy.exc import OperationalError

        from app.conversation import recover_messages

        revision = self.published(b"code,amount\n0007,0.10\n")
        plan = self.plan(
            revision,
            "Tổng",
            aggregations=[
                {"operator": "SUM", "column_id": revision["columns"][1]["id"], "output_id": "total"}
            ],
        )
        chat = self.client.post(
            "/api/conversations", json={"workspace_id": str(self.workspace_id)}
        ).json()["id"]
        engine = db.get_engine()

        def reject_final_save(conn, cursor, statement, parameters, context, executemany):
            if (
                statement.startswith("UPDATE app.messages SET")
                and isinstance(parameters, dict)
                and parameters.get("status") == "answered"
            ):
                raise OperationalError("secret storage", {}, Exception("secret"))

        event.listen(engine, "before_cursor_execute", reject_final_save)
        try:
            with patch(
                "app.conversation.generate_proposal",
                return_value=Proposal(plan, "gemini", "offline", 1, 1, 2, None),
            ) as provider:
                path = f"/api/conversations/{chat}/messages"
                body = {"question": "Tổng", "dataset_revision_id": str(revision["id"])}
                first = self.client.post(
                    path, json=body, headers={"Idempotency-Key": "persistence-request-key"}
                )
                self.assertEqual(first.status_code, 503, first.text)
                self.assertEqual(first.json()["diagnostics"]["failed_stage"], "persistence")
                self.assertEqual(
                    first.json()["diagnostics"]["sql"]["execution_status"], "succeeded"
                )
                self.assertNotIn("secret", first.text)
                repeated = self.client.post(
                    path, json=body, headers={"Idempotency-Key": "persistence-request-key"}
                )
                self.assertEqual(repeated.json()["status"], "pending")
                self.assertEqual(provider.call_count, 1)
        finally:
            event.remove(engine, "before_cursor_execute", reject_final_save)
        recover_messages()
        saved = self.client.get(f"/api/conversations/{chat}").json()["messages"][0]["envelope"]
        self.assertEqual(saved["processing"]["sql"]["execution_status"], "unknown")
        self.assertEqual(
            saved["processing"]["sql"]["statement"], first.json()["diagnostics"]["sql"]["statement"]
        )

    def test_execution_failure_keeps_statement_and_recovery_keeps_unknown(self) -> None:
        from sqlalchemy.exc import OperationalError

        from app.conversation import recover_messages

        revision = self.published(b"code,amount\n0007,0.10\n")
        plan = self.plan(
            revision,
            "Tổng",
            aggregations=[
                {"operator": "SUM", "column_id": revision["columns"][1]["id"], "output_id": "total"}
            ],
        )
        chat = self.client.post(
            "/api/conversations", json={"workspace_id": str(self.workspace_id)}
        ).json()["id"]

        def fail_execute(compiled, *, on_execute):
            on_execute()
            raise OperationalError("secret sql", {}, Exception("secret password"))

        with (
            patch(
                "app.conversation.generate_proposal",
                return_value=Proposal(plan, "gemini", "offline", 1, 1, 2, None),
            ),
            patch("app.conversation.execute_query", side_effect=fail_execute),
        ):
            response = self.client.post(
                f"/api/conversations/{chat}/messages",
                json={"question": "Tổng", "dataset_revision_id": str(revision["id"])},
                headers={"Idempotency-Key": uuid4().hex},
            )
        body = response.json()
        self.assertEqual(body["processing"]["failed_stage"], "execution")
        self.assertEqual(body["processing"]["sql"]["execution_status"], "failed")
        self.assertTrue(body["processing"]["sql"]["statement"].startswith("SELECT"))
        self.assertNotIn("secret", response.text)
        with db.get_engine().begin() as connection:
            row = (
                connection.execute(select(messages).where(messages.c.conversation_id == UUID(chat)))
                .mappings()
                .one()
            )
            saved = {**body, "status": "pending"}
            saved["processing"]["sql"]["execution_status"] = "in_progress"
            connection.execute(
                update(messages)
                .where(messages.c.id == row["id"])
                .values(status="pending", envelope=saved)
            )
        recover_messages()
        restored = self.client.get(f"/api/conversations/{chat}").json()["messages"][0]["envelope"]
        self.assertEqual(restored["processing"]["failed_stage"], "interrupted")
        self.assertEqual(restored["processing"]["sql"]["execution_status"], "unknown")
        self.assertEqual(
            restored["processing"]["sql"]["statement"], body["processing"]["sql"]["statement"]
        )

    def test_provider_fallback_and_timing_do_not_bypass_semantic_refusals(self) -> None:
        from app.errors import AppError

        revision = self.published(b"code,amount\n0007,0.10\n0012,0.20\n")
        amount = revision["columns"][1]["id"]
        plan = self.plan(
            revision,
            "Tổng",
            aggregations=[{"operator": "SUM", "column_id": amount, "output_id": "total"}],
        )
        for code, opt_in, expected_calls, status in [
            ("PROVIDER_TEMPORARY", True, 2, "answered"),
            ("PROVIDER_TEMPORARY", False, 1, "provider_unavailable"),
            ("PROVIDER_TIMEOUT", True, 1, "provider_unavailable"),
            ("PROVIDER_SCHEMA", True, 1, "provider_unavailable"),
        ]:
            chat = self.client.post(
                "/api/conversations", json={"workspace_id": str(self.workspace_id)}
            ).json()["id"]

            def generate(question, source, provider, context, failure_code=code):
                if provider == "gemini":
                    raise AppError(503, failure_code, "safe failure")
                return Proposal(plan, "knowledge", "knowledge", None, None, 1, None)

            with (
                patch("app.conversation.generate_proposal", side_effect=generate) as calls,
                patch("app.providers.knowledge_available", return_value=True),
            ):
                result = self.client.post(
                    f"/api/conversations/{chat}/messages",
                    json={
                        "question": "Tổng",
                        "dataset_revision_id": str(revision["id"]),
                        "allow_fallback": opt_in,
                    },
                    headers={"Idempotency-Key": uuid4().hex},
                ).json()
            self.assertEqual(calls.call_count, expected_calls)
            self.assertEqual(result["status"], status)
            self.assertIn("server_processing", result["timings_ms"])
            if status == "answered":
                self.assertEqual(result["display_rows"], [["0.30"]])
                self.assertEqual(result["facts"]["provider"]["name"], "knowledge")

    def test_setup_local_permission_owner_and_publish(self) -> None:
        uploaded = self.upload(b"code,amount\n0007,0.10\n0012,\n")
        url = f"/api/datasets/{uploaded['dataset_id']}/setup"
        body = {"revision_id": uploaded["revision_id"]}
        with patch("app.setup.generate_structured") as generate:
            local = self.client.post(url, json=body).json()
            self.assertEqual(local["mode"], "local")
            self.assertEqual(self.client.post(url, json={**body, "use_ai": True}).status_code, 422)
            generate.assert_not_called()
            self.as_user(self.token_b)
            self.assertEqual(self.client.post(url, json=body).status_code, 404)
            generate.assert_not_called()
        self.as_user(self.token_a)
        confirm = {**self.publish_input(self.preview(uploaded["dataset_id"])), **local["proposal"]}
        confirm.pop("notes")
        self.assertEqual(
            self.client.post(
                f"/api/datasets/{uploaded['dataset_id']}/confirm", json=confirm
            ).status_code,
            200,
        )
        self.assertEqual(
            self.preview(uploaded["dataset_id"])["rows"], [["0007", "0.10"], ["0012", None]]
        )

    def test_setup_ai_idempotency_no_raw_rows_and_provider_failure(self) -> None:
        from app.errors import AppError

        uploaded = self.upload(b"code,amount\n0007,0.10\n0012,0.20\n")
        url = f"/api/datasets/{uploaded['dataset_id']}/setup"
        body = {"revision_id": uploaded["revision_id"], "use_ai": True, "consent_metadata": True}
        headers = {"Idempotency-Key": uuid4().hex}
        with patch(
            "app.setup.generate_structured",
            side_effect=AppError(503, "PROVIDER_TIMEOUT", "unavailable"),
        ) as generate:
            first = self.client.post(url, json=body, headers=headers).json()
            self.assertEqual(first["error_code"], "PROVIDER_TIMEOUT")
            self.assertEqual(first["mode"], "local")
            self.assertEqual(self.client.post(url, json=body, headers=headers).json(), first)
            self.assertEqual(generate.call_count, 1)
            payload = generate.call_args.args[0]
            import json

            self.assertNotIn("0007", json.dumps(payload))
            self.assertNotIn("rows", payload)
            self.assertEqual(
                self.client.post(
                    url, json={**body, "provider": "knowledge"}, headers=headers
                ).status_code,
                409,
            )
        self.assertEqual(self.preview(uploaded["dataset_id"])["status"], "needs_review")
        self.assertEqual(
            self.preview(uploaded["dataset_id"])["setup_proposal"]["status"], "complete"
        )

    def test_setup_invalid_proposal_falls_back_and_restart_is_explicit(self) -> None:
        from app.setup import ColumnSuggestion, SetupSuggestion, local_proposal
        from app.tabular import read_table

        content = b"code,amount\n0007,0.10\n0007,0.20\n"
        uploaded = self.upload(content)
        local = local_proposal(read_table(content, ".csv"), UUID(uploaded["revision_id"]))
        proposal = SetupSuggestion(columns=[ColumnSuggestion(id=c.id) for c in local.columns])
        proposal.columns[0].primary_key = True
        url = f"/api/datasets/{uploaded['dataset_id']}/setup"
        body = {"revision_id": uploaded["revision_id"], "use_ai": True, "consent_metadata": True}
        with patch(
            "app.setup.generate_structured",
            return_value=Proposal(proposal, "gemini", "offline", None, None, 0, None),
        ):
            result = self.client.post(
                url, json=body, headers={"Idempotency-Key": uuid4().hex}
            ).json()
        self.assertEqual(result["error_code"], "SETUP_PROPOSAL_REJECTED")
        self.assertFalse(result["proposal"]["columns"][0]["primary_key"])
        proposal.columns[0].primary_key = False
        proposal.description = "Metadata do AI đề xuất, chờ người dùng xác nhận"
        with patch(
            "app.setup.generate_structured",
            return_value=Proposal(proposal, "gemini", "offline", None, None, 0, None),
        ):
            accepted = self.client.post(
                url, json=body, headers={"Idempotency-Key": uuid4().hex}
            ).json()
        self.assertEqual(accepted["mode"], "ai_proposal")
        self.assertEqual(accepted["validation_errors"], [])
        self.assertEqual(self.preview(uploaded["dataset_id"])["status"], "needs_review")
        key = uuid4().hex
        with db.get_engine().begin() as connection:
            connection.execute(
                update(revisions)
                .where(revisions.c.id == UUID(uploaded["revision_id"]))
                .values(setup_proposal={"status": "pending", "request_key": key})
            )
        recover_ingestion()
        with patch("app.setup.generate_structured") as generate:
            self.assertEqual(
                self.client.post(url, json=body, headers={"Idempotency-Key": key}).status_code, 409
            )
            generate.assert_not_called()

    def test_setup_value_consent_is_separate_and_never_auto_publishes_mappings(self) -> None:
        from app.setup import SetupSuggestion

        uploaded = self.upload(b"code,state\n0007,ready\n0012,pending\n")
        url = f"/api/datasets/{uploaded['dataset_id']}/setup"
        body = {"revision_id": uploaded["revision_id"], "use_ai": True, "consent_values": True}
        with patch(
            "app.setup.generate_structured",
            return_value=Proposal(SetupSuggestion(), "gemini", "offline", None, None, 0, None),
        ) as generate:
            self.assertEqual(
                self.client.post(
                    url, json=body, headers={"Idempotency-Key": uuid4().hex}
                ).status_code,
                422,
            )
            generate.assert_not_called()
            response = self.client.post(
                url,
                json={**body, "consent_metadata": True},
                headers={"Idempotency-Key": uuid4().hex},
            )
            self.assertEqual(response.status_code, 200)
            payload = generate.call_args.args[0]
            self.assertEqual(payload["profile"][1]["observed_values"], ["pending", "ready"])
            self.assertNotIn("rows", payload)
        self.assertEqual(self.preview(uploaded["dataset_id"])["status"], "needs_review")

    def test_limit_probe_partial_and_exact_values(self) -> None:
        uploaded = self.upload(b"code,amount\n0007,0.10\n0008,0.20\n0009,0.30\n")
        preview = self.preview(uploaded["dataset_id"])
        body = self.publish_input(preview)
        self.assertEqual(
            self.client.post(
                f"/api/datasets/{uploaded['dataset_id']}/confirm", json=body
            ).status_code,
            200,
        )
        with db.get_engine().connect() as connection:
            revision = dict(
                connection.execute(
                    select(revisions).where(revisions.c.id == UUID(uploaded["revision_id"]))
                )
                .mappings()
                .one()
            )
        code = body["columns"][0]["id"]
        payload = {
            "task": "SQL",
            "table_id": uploaded["dataset_id"],
            "source_revision_id": uploaded["revision_id"],
            "raw_user_spans": ["Danh sách"],
            "coverage": ["Danh sách"],
            "select_columns": [code],
            "limit": 2,
            "result_mode": "all",
        }
        compiled = compile_query(QueryPlan.model_validate(payload), revision, "Danh sách")
        rows, _ = execute_query(compiled)
        self.assertTrue(compiled.truncated)
        self.assertEqual(len(rows), 2)
        chat = self.client.post(
            "/api/conversations", json={"workspace_id": str(self.workspace_id)}
        ).json()["id"]
        with patch(
            "app.conversation.generate_proposal",
            return_value=Proposal(
                QueryPlan.model_validate(payload), "gemini", "offline", None, None, 0, None
            ),
        ):
            answer = self.client.post(
                f"/api/conversations/{chat}/messages",
                json={"question": "Danh sách", "dataset_revision_id": uploaded["revision_id"]},
                headers={"Idempotency-Key": uuid4().hex},
            ).json()
        self.assertEqual(answer["status"], "partial")
        self.assertEqual(answer["facts"]["trust"], "reference_only")
        self.assertTrue(answer["facts"]["truncated"])
        payload["filters"] = {
            "operator": "EQ",
            "column_id": code,
            "literal": {"raw_phrase": "9999", "candidate_value": "9999", "value_type": "text"},
        }
        payload["raw_user_spans"] = payload["coverage"] = ["9999"]
        from app.query import ground_catalog

        query = compile_query(QueryPlan.model_validate(payload), ground_catalog(revision), "9999")
        self.assertEqual(execute_query(query)[0], [])
        self.assertEqual(query.filters[0]["source_match"], "no_match")
        payload.update(
            select_columns=[],
            aggregations=[
                {"operator": "SUM", "column_id": body["columns"][1]["id"], "output_id": "total"}
            ],
        )
        with patch(
            "app.conversation.generate_proposal",
            return_value=Proposal(
                QueryPlan.model_validate(payload), "gemini", "offline", None, None, 0, None
            ),
        ):
            empty = self.client.post(
                f"/api/conversations/{chat}/messages",
                json={"question": "9999", "dataset_revision_id": uploaded["revision_id"]},
                headers={"Idempotency-Key": uuid4().hex},
            ).json()
        self.assertEqual(empty["display_rows"], [[None]])
        self.assertEqual(empty["status"], "answered")
        self.assertEqual(empty["facts"]["filters"][0]["source_match"], "no_match")
        self.assertTrue(empty["limitations"])

    def test_catalog_mappings_must_exist_and_metadata_persists(self) -> None:
        uploaded = self.upload(b"code,amount\n0007,0.10\n0008,0.20\n")
        body = self.publish_input(self.preview(uploaded["dataset_id"]))
        body["description"] = "Bảng kiểm thử metadata"
        body["columns"][0].update(
            {
                "description": "Mã đối tượng",
                "role": "identifier",
                "aliases": ["mã"],
                "value_mappings": [{"phrase": "đầu tiên", "value": "missing"}],
            }
        )
        url = f"/api/datasets/{uploaded['dataset_id']}/confirm"
        self.assertEqual(self.client.post(url, json=body).status_code, 422)
        self.assertEqual(self.preview(uploaded["dataset_id"])["status"], "needs_review")
        body["columns"][0]["value_mappings"][0]["value"] = "0007"
        self.assertEqual(self.client.post(url, json=body).status_code, 200)
        preview = self.preview(uploaded["dataset_id"])
        self.assertEqual(preview["description"], body["description"])
        self.assertEqual(preview["columns"][0]["value_mappings"][0]["value"], "0007")

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

    def published(
        self, content: bytes, kinds: dict | None = None, aliases: dict | None = None
    ) -> dict:
        uploaded = self.upload(content)
        preview = self.preview(uploaded["dataset_id"])
        review = self.publish_input(preview)
        for column in review["columns"]:
            if aliases and column["name"] in aliases:
                column["aliases"] = aliases[column["name"]]
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

    def test_calendar_month_uses_confirmed_timezone_and_keeps_boundaries(self) -> None:
        revision = self.published(
            b"code,amount,at\n0001,100,2026-08-31T23:59:59+07:00\n0002,0.10,2026-09-01T00:00:00+07:00\n0003,0.20,2026-09-30T23:59:59+07:00\n0004,100,2026-10-01T00:00:00+07:00\n",
            {"code": "text", "amount": "numeric", "at": "timestamp"},
        )
        code, amount, at = [c["id"] for c in revision["columns"]]
        phrase = "tháng 9 năm 2026"
        plan = self.plan(
            revision,
            phrase,
            aggregations=[{"operator": "SUM", "column_id": amount, "output_id": "total"}],
            filters={
                "operator": "AND",
                "children": [
                    {
                        "operator": operator,
                        "column_id": at,
                        "literal": {
                            "raw_phrase": phrase,
                            "candidate_value": value,
                            "value_type": "timestamp",
                        },
                    }
                    for operator, value in (
                        ("GTE", "2026-09-01T00:00:00+07:00"),
                        ("LT", "2026-10-01T00:00:00+07:00"),
                    )
                ],
            },
        )
        self.assertEqual(execute_query(compile_query(plan, revision, phrase))[0], [["0.30"]])

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
