"""Xác minh token claims và Origin bằng mock có giới hạn trong test."""

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth import verify_google_identity
from app.config import get_settings
from app.errors import AppError
from app.main import create_app


@pytest.mark.parametrize(
    "field,value",
    [
        ("aud", "another-client"),
        ("iss", "https://untrusted.invalid"),
        ("exp", 1),
        ("nonce", "wrong-nonce"),
        ("sub", ""),
    ],
)
def test_untrusted_google_claims_are_rejected(
    monkeypatch: pytest.MonkeyPatch, field: str, value: Any
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost/unused")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
    get_settings.cache_clear()
    claims = {
        "aud": "test-client",
        "iss": "https://accounts.google.com",
        "exp": time.time() + 300,
        "nonce": "expected-nonce",
        "sub": "test-subject",
    }
    claims[field] = value
    monkeypatch.setattr("app.auth.id_token.verify_oauth2_token", lambda *args, **kwargs: claims)
    with pytest.raises(AppError) as error:
        verify_google_identity("test-only-token", "expected-nonce")
    assert error.value.status == 401
    get_settings.cache_clear()


def test_unauthenticated_and_cross_origin_fail_before_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost/unused")
    get_settings.cache_clear()
    with TestClient(create_app(recover_jobs=False)) as client:
        assert client.get("/api/me").status_code == 401
        assert (
            client.post(
                "/api/workspaces",
                json={"name": "Test"},
                headers={"Origin": "https://untrusted.invalid"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/auth/google",
                json={"credential": "invalid", "g_csrf_token": "x" * 32},
                headers={"Origin": "http://localhost:18181"},
            ).status_code
            == 403
        )


def test_public_canonical_origin_and_loopback_alias_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost/unused")
    monkeypatch.setenv("SESSION_SECRET", "synthetic-session-key-for-test-only-123456789")
    monkeypatch.setenv("APP_ORIGIN", "http://localhost:18181")
    get_settings.cache_clear()
    try:
        with TestClient(create_app(recover_jobs=False)) as client:
            config = client.get("/api/auth/config")
            assert config.status_code == 200
            assert config.json()["app_origin"] == "http://localhost:18181"
            assert config.headers["Cache-Control"] == "no-store"
            for origin, expected in [
                ("http://127.0.0.1:18181", 403),
                ("http://localhost:18181", 422),
            ]:
                response = client.post("/api/auth/google", json={}, headers={"Origin": origin})
                assert response.status_code == expected
                if expected == 403:
                    assert response.json()["error"]["code"] == "ORIGIN_REJECTED"
    finally:
        get_settings.cache_clear()
