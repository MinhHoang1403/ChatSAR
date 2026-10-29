"""Tests API + PostgreSQL thật; identities chỉ tạo qua harness, không có endpoint bypass."""

import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, insert, select, update

from app import database as db
from app.auth import SESSION_COOKIE, create_session, digest
from app.main import create_app
from app.schema import sessions, users, workspaces

ORIGIN = "http://localhost:18181"


class AuthIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.owner_a, self.owner_b = uuid4(), uuid4()
        self.subject = "test:" + uuid4().hex
        self.client = TestClient(create_app())
        with db.get_engine().begin() as connection:
            connection.execute(
                insert(users),
                [
                    {
                        "id": self.owner_a,
                        "provider": "google",
                        "provider_subject": self.subject,
                        "display_name": "Test A",
                    },
                    {
                        "id": self.owner_b,
                        "provider": "google",
                        "provider_subject": self.subject + ":B",
                        "display_name": "Test B",
                    },
                ],
            )
            self.token_a = create_session(connection, self.owner_a)
            self.token_b = create_session(connection, self.owner_b)
        self.as_user(self.token_a)

    def as_user(self, token: str) -> None:
        self.client.cookies.clear()
        self.client.cookies.set(SESSION_COOKIE, token)
        self.client.headers.update({"Origin": ORIGIN, "X-CSRF-Token": digest("csrf:" + token)})

    def tearDown(self) -> None:
        self.client.close()
        with db.get_engine().begin() as connection:
            connection.execute(
                delete(workspaces).where(workspaces.c.owner_id.in_([self.owner_a, self.owner_b]))
            )
            connection.execute(delete(users).where(users.c.id.in_([self.owner_a, self.owner_b])))

    def test_workspace_owner_isolation_and_switch(self) -> None:
        response = self.client.post("/api/workspaces", json={"name": "Workspace A"})
        self.assertEqual(response.status_code, 201, response.text)
        workspace_id = response.json()["id"]
        self.as_user(self.token_b)
        self.assertEqual(self.client.get("/api/workspaces").json(), [])
        self.assertEqual(self.client.get(f"/api/workspaces/{workspace_id}").status_code, 404)
        self.as_user(self.token_a)
        self.assertEqual(self.client.get(f"/api/workspaces/{workspace_id}").status_code, 200)

    def test_owner_spoof_and_missing_csrf_are_rejected(self) -> None:
        response = self.client.post(
            "/api/workspaces", json={"name": "Spoof", "owner_id": str(self.owner_b)}
        )
        self.assertEqual(response.status_code, 422)
        del self.client.headers["X-CSRF-Token"]
        self.assertEqual(
            self.client.post("/api/workspaces", json={"name": "No CSRF"}).status_code, 403
        )

    def test_expired_revoked_and_unknown_sessions(self) -> None:
        with db.get_engine().begin() as connection:
            connection.execute(
                update(sessions)
                .where(sessions.c.token_hash == digest(self.token_a))
                .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
        self.assertEqual(self.client.get("/api/me").status_code, 401)
        self.as_user("not-a-real-session")
        self.assertEqual(self.client.get("/api/me").status_code, 401)
        self.client.cookies.clear()
        self.assertEqual(self.client.get("/api/me").status_code, 401)

    def test_logout_revokes_session_and_clears_cookie(self) -> None:
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 204)
        self.as_user(self.token_a)
        self.assertEqual(self.client.get("/api/me").status_code, 401)

    def test_missing_user_cannot_authenticate(self) -> None:
        with db.get_engine().begin() as connection:
            connection.execute(delete(users).where(users.c.id == self.owner_a))
        self.assertEqual(self.client.get("/api/me").status_code, 401)

    def test_google_login_mock_rotates_session_and_reuses_subject(self) -> None:
        def identity(token: str, nonce: str) -> dict[str, str]:
            return {"sub": self.subject, "name": "Test A", "nonce": nonce}

        state = self.client.get("/api/auth/config")
        self.assertEqual(state.status_code, 200)
        with patch("app.auth.verify_google_identity", side_effect=identity):
            response = self.client.post(
                "/api/auth/google",
                json={
                    "credential": "test-harness-only",
                    "g_csrf_token": state.json()["csrf_token"],
                },
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["id"], str(self.owner_a))
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertIn("SameSite=lax", response.headers["set-cookie"])
        self.assertEqual(self.client.get("/api/me").status_code, 200)
        self.as_user(self.token_a)
        self.assertEqual(self.client.get("/api/me").status_code, 401)
        with db.get_engine().connect() as connection:
            count = connection.execute(
                select(users.c.id).where(users.c.provider_subject == self.subject)
            ).all()
        self.assertEqual(len(count), 1)

    def test_login_challenge_tampering_and_replay(self) -> None:
        state = self.client.get("/api/auth/config").json()
        cookie = self.client.cookies.get("chatsar_login_challenge")
        payload = {"credential": "test-only", "g_csrf_token": state["csrf_token"]}
        with patch("app.auth.verify_google_identity", return_value={"sub": self.subject}):
            self.assertEqual(self.client.post("/api/auth/google", json=payload).status_code, 200)
            self.client.cookies.set("chatsar_login_challenge", cookie)
            self.assertEqual(self.client.post("/api/auth/google", json=payload).status_code, 409)
        self.client.cookies.clear()
        self.client.cookies.set("chatsar_login_challenge", "tampered")
        self.assertEqual(self.client.post("/api/auth/google", json=payload).status_code, 403)


if __name__ == "__main__":
    unittest.main(verbosity=2)
