"""Khách dùng API/PG thật, model mock; không đụng tài khoản hoặc usage thật."""

import unittest
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete, func, insert, select, update

from app import database as db
from app import providers
from app.auth import SESSION_COOKIE, create_session
from app.config import get_settings
from app.guest import purge_guest, reap_guests
from app.main import create_app
from app.planning import QueryRequest
from app.schema import datasets, messages, provider_usage, revisions, sessions, users, workspaces
from app.tabular import ColumnReview

ORIGIN = "http://localhost:18181"


class GuestIntegration(unittest.TestCase):
    def setUp(self):
        self.clients = []
        self.guests = []
        self.account = uuid4()
        self.subject = "test:" + uuid4().hex
        with db.get_engine().begin() as connection:
            connection.execute(
                insert(users).values(
                    id=self.account,
                    provider="google",
                    provider_subject=self.subject,
                    display_name="Controlled account",
                )
            )
            self.account_token = create_session(connection, self.account)
            self.account_workspace = uuid4()
            connection.execute(
                insert(workspaces).values(
                    id=self.account_workspace, owner_id=self.account, name="Account workspace"
                )
            )
        self.usage_before = self.usage_count()

    def usage_count(self):
        with db.get_engine().connect() as connection:
            return connection.execute(select(func.count()).select_from(provider_usage)).scalar_one()

    def guest(self):
        client = TestClient(create_app(recover_jobs=False))
        client.headers["Origin"] = ORIGIN
        response = client.post("/api/auth/guest", json={})
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("set-cookie", response.headers)
        self.assertEqual(response.headers["cache-control"], "no-store")
        state = response.json()
        client.headers.update(
            {"X-Guest-Session": state["guest_token"], "X-CSRF-Token": state["csrf_token"]}
        )
        self.clients.append(client)
        self.guests.append(state)
        return client, state

    def source(self, client):
        workspace = client.get("/api/workspaces").json()[0]["id"]
        upload = client.post(
            f"/api/workspaces/{workspace}/datasets",
            files={"file": ("guest.csv", b"code,amount\n0007,0.10\n0012,0.20\n")},
        ).json()
        preview = client.get(f"/api/datasets/{upload['dataset_id']}/preview").json()
        columns = [
            {k: v for k, v in column.items() if k in ColumnReview.model_fields}
            for column in preview["columns"]
        ]
        published = client.post(
            f"/api/datasets/{upload['dataset_id']}/confirm",
            json={
                "revision_id": upload["revision_id"],
                "columns": columns,
                "grain": "Một dòng",
                "data_classification": "private",
            },
        )
        self.assertEqual(published.status_code, 200, published.text)
        return upload, columns, workspace

    def tearDown(self):
        for client, state in zip(self.clients, self.guests, strict=True):
            client.headers.update(
                {"X-Guest-Session": state["guest_token"], "X-CSRF-Token": state["csrf_token"]}
            )
            client.delete("/api/auth/guest")
            client.close()
            # Chỉ UUID của guest do chính fixture này tạo; không dọn owner nhận từ user.
            with db.get_engine().begin() as connection:
                owned = select(workspaces.c.id).where(workspaces.c.owner_id == UUID(state["id"]))
                from app.schema import conversations

                chats = select(conversations.c.id).where(conversations.c.workspace_id.in_(owned))
                connection.execute(
                    update(messages)
                    .where(messages.c.conversation_id.in_(chats), messages.c.status == "pending")
                    .values(status="execution_error")
                )
            purge_guest(UUID(state["id"]))
        with db.get_engine().begin() as connection:
            connection.execute(delete(workspaces).where(workspaces.c.owner_id == self.account))
            connection.execute(delete(users).where(users.c.id == self.account))
        self.assertEqual(self.usage_count(), self.usage_before)

    def test_guest_scope_token_transport_and_csrf(self):
        a, state = self.guest()
        b, other = self.guest()
        self.assertTrue(a.get("/api/me").json()["is_guest"])
        workspace = a.get("/api/workspaces").json()[0]["id"]
        self.assertEqual(b.get(f"/api/workspaces/{workspace}").status_code, 404)
        self.assertEqual(a.get(f"/api/workspaces/{self.account_workspace}").status_code, 404)
        self.assertEqual(a.get("/api/profile").status_code, 403)
        self.assertEqual(
            a.post("/api/auth/guest", json={"owner_id": str(self.account)}).status_code, 422
        )
        csrf = a.headers.pop("X-CSRF-Token")
        self.assertEqual(a.post("/api/workspaces", json={"name": "No CSRF"}).status_code, 403)
        self.assertEqual(a.delete("/api/auth/guest").status_code, 403)
        a.headers["X-CSRF-Token"] = csrf
        self.assertEqual(
            a.post(
                "/api/auth/guest", json={}, headers={"Origin": "https://invalid.example"}
            ).status_code,
            403,
        )
        token = a.headers.pop("X-Guest-Session")
        a.cookies.set(SESSION_COOKIE, token)
        self.assertEqual(a.get("/api/me").status_code, 401)
        a.cookies.clear()
        a.headers["X-Guest-Session"] = self.account_token
        self.assertEqual(a.get("/api/me").status_code, 401)
        a.headers["X-Guest-Session"] = token

    def test_guest_upload_query_sql_and_cleanup_use_existing_pipeline(self):
        client, state = self.guest()
        other, _ = self.guest()
        upload, columns, workspace = self.source(client)
        dataset_path = f"/api/datasets/{upload['dataset_id']}"
        self.assertEqual(other.get(dataset_path + "/preview").status_code, 404)
        chat = client.post("/api/conversations", json={"workspace_id": workspace}).json()["id"]
        path = f"/api/conversations/{chat}/messages"
        body = {"question": "Tổng amount?", "dataset_revision_id": upload["revision_id"]}
        with patch.object(providers, "reserve_call") as reserve:
            denied = client.post(path, json=body, headers={"Idempotency-Key": uuid4().hex}).json()
            self.assertEqual(denied["error_code"], "DATA_PERMISSION_REQUIRED")
            reserve.assert_not_called()
        self.assertEqual(
            client.patch(
                dataset_path + "/sharing",
                json={"revision_id": upload["revision_id"], "sharing_providers": ["gemini"]},
            ).status_code,
            200,
        )
        request = QueryRequest(
            task="SQL",
            table_id=upload["dataset_id"],
            source_revision_id=upload["revision_id"],
            result_shape="scalar",
            required_columns=[],
            raw_user_spans=[body["question"]],
            select_columns=[],
            aggregations=[{"operator": "SUM", "column_id": columns[1]["id"], "output_id": "total"}],
            conditions=[],
            group_by=[],
            order_by=[],
            limit=100,
            unresolved=[],
        )

        def create(**kw):
            return SimpleNamespace(output_text=request.model_dump_json(), id="offline", usage=None)

        settings = get_settings().model_copy(
            update={"gemini_enabled": True, "gemini_api_key": SecretStr("offline-placeholder")}
        )
        with (
            patch.object(providers, "get_settings", return_value=settings),
            patch.object(providers, "reserve_call", return_value=None),
            patch.object(providers, "finish_call"),
            patch.object(
                providers.genai,
                "Client",
                return_value=nullcontext(
                    SimpleNamespace(interactions=SimpleNamespace(create=create))
                ),
            ),
        ):
            answered = client.post(path, json=body, headers={"Idempotency-Key": uuid4().hex}).json()
        self.assertEqual(answered["status"], "answered", answered)
        self.assertEqual(answered["display_rows"], [["0.30"]])
        self.assertIn("0,30", answered["display_text"])
        self.assertEqual(answered["processing"]["sql"]["execution_status"], "succeeded")
        self.assertEqual(other.get(f"/api/results/{answered['result_id']}").status_code, 404)
        with db.get_engine().connect() as connection:
            revision = (
                connection.execute(
                    select(revisions).where(revisions.c.id == UUID(upload["revision_id"]))
                )
                .mappings()
                .one()
            )
            source_path = Path(get_settings().storage_root) / revision["storage_name"]
            table_name = revision["physical_table"]
        self.assertEqual(client.delete("/api/auth/guest").status_code, 204)
        self.assertEqual(client.get("/api/me").status_code, 401)
        self.assertFalse(source_path.exists())
        with db.get_engine().connect() as connection:
            self.assertIsNone(
                connection.execute(
                    select(users.c.id).where(users.c.id == UUID(state["id"]))
                ).scalar_one_or_none()
            )
            self.assertFalse(connection.dialect.has_table(connection, table_name, schema="data"))

    def test_reaper_only_removes_expired_guests_and_preserves_google(self):
        expired, state = self.guest()
        active, _ = self.guest()
        self.source(expired)
        with db.get_engine().begin() as connection:
            connection.execute(
                update(sessions)
                .where(sessions.c.user_id == UUID(state["id"]))
                .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
        reap_guests()
        self.assertEqual(expired.get("/api/me").status_code, 401)
        self.assertEqual(active.get("/api/me").status_code, 200)
        with db.get_engine().connect() as connection:
            self.assertIsNotNone(
                connection.execute(select(users.c.id).where(users.c.id == self.account)).first()
            )

    def test_pending_cleanup_revokes_access_then_waits_for_usage_completion(self):
        client, state = self.guest()
        upload, _, workspace = self.source(client)
        chat = client.post("/api/conversations", json={"workspace_id": workspace}).json()["id"]
        message = uuid4()
        with db.get_engine().begin() as connection:
            connection.execute(
                insert(messages).values(
                    id=message,
                    conversation_id=UUID(chat),
                    revision_id=UUID(upload["revision_id"]),
                    question="Controlled pending",
                    request_key=uuid4().hex,
                    request_hash="controlled",
                    provider="gemini",
                    status="pending",
                )
            )
        self.assertEqual(client.delete("/api/auth/guest").status_code, 204)
        self.assertEqual(client.get("/api/me").status_code, 401)
        with db.get_engine().begin() as connection:
            self.assertIsNotNone(
                connection.execute(
                    select(revisions.c.id).where(revisions.c.id == UUID(upload["revision_id"]))
                ).first()
            )
            connection.execute(
                update(messages).where(messages.c.id == message).values(status="execution_error")
            )
        reap_guests()
        with db.get_engine().connect() as connection:
            self.assertIsNone(
                connection.execute(
                    select(users.c.id).where(users.c.id == UUID(state["id"]))
                ).first()
            )

    def test_login_opens_account_without_importing_guest_and_cleanup_preserves_account(self):
        client, guest = self.guest()
        upload, _, workspace = self.source(client)
        config = client.get("/api/auth/config").json()
        with patch("app.auth.verify_google_identity", return_value={"sub": self.subject}):
            response = client.post(
                "/api/auth/google",
                json={"credential": "offline", "g_csrf_token": config["csrf_token"]},
            )
        self.assertEqual(response.status_code, 200)
        who = client.get("/api/me").json()
        self.assertFalse(who["is_guest"])
        self.assertEqual(who["id"], str(self.account))
        self.assertEqual(
            [w["id"] for w in client.get("/api/workspaces").json()], [str(self.account_workspace)]
        )
        self.assertEqual(client.get(f"/api/workspaces/{workspace}").status_code, 404)
        self.assertEqual(client.delete("/api/auth/guest").status_code, 204)
        self.assertEqual(client.get("/api/me").json()["id"], str(self.account))
        with db.get_engine().connect() as connection:
            self.assertIsNone(
                connection.execute(
                    select(datasets.c.id).where(datasets.c.id == UUID(upload["dataset_id"]))
                ).first()
            )
            self.assertIsNone(
                connection.execute(
                    select(users.c.id).where(users.c.id == UUID(guest["id"]))
                ).first()
            )

    def test_cleanup_waits_for_ingestion_and_setup_without_removing_history(self):
        for state_kind in ("validating", "publishing", "setup"):
            with self.subTest(state=state_kind):
                client, state = self.guest()
                upload, _, workspace = self.source(client)
                chat = client.post("/api/conversations", json={"workspace_id": workspace}).json()[
                    "id"
                ]
                revision_id = UUID(upload["revision_id"])
                values = (
                    {"setup_proposal": {"status": "pending"}}
                    if state_kind == "setup"
                    else {"status": state_kind}
                )
                with db.get_engine().begin() as connection:
                    connection.execute(
                        update(revisions).where(revisions.c.id == revision_id).values(**values)
                    )
                self.assertEqual(client.delete("/api/auth/guest").status_code, 204)
                self.assertEqual(client.get("/api/me").status_code, 401)
                with db.get_engine().begin() as connection:
                    from app.schema import conversations

                    self.assertIsNotNone(
                        connection.execute(
                            select(conversations.c.id).where(conversations.c.id == UUID(chat))
                        ).first()
                    )
                    connection.execute(
                        update(revisions)
                        .where(revisions.c.id == revision_id)
                        .values(status="ready", setup_proposal={"status": "complete"})
                    )
                reap_guests()
                with db.get_engine().connect() as connection:
                    self.assertIsNone(
                        connection.execute(
                            select(users.c.id).where(users.c.id == UUID(state["id"]))
                        ).first()
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
