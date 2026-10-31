"""Xác minh token claims và Origin bằng mock có giới hạn trong test."""

import time
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from google.auth import crypt, jwt
from google.auth.exceptions import TransportError

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


def test_google_rejection_log_does_not_include_token(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost/unused")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
    get_settings.cache_clear()
    token = "synthetic-sensitive-token-do-not-log"

    def rejected(*args: object, **kwargs: object) -> dict:
        raise ValueError("Token has wrong audience " + token)

    monkeypatch.setattr("app.auth.id_token.verify_oauth2_token", rejected)
    try:
        with pytest.raises(AppError):
            verify_google_identity(token, "test-nonce")
        assert "audience" in caplog.text
        assert token not in caplog.text
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize(
    "issued_offset,expires_offset,accepted", [(5, 300, True), (60, 300, False), (-300, -1, False)]
)
def test_signed_google_token_clock_window_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
    issued_offset: int,
    expires_offset: int,
    accepted: bool,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost/unused")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
    get_settings.cache_clear()
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    public = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    # Chỉ thay nguồn certificate trong test; verifier vẫn kiểm chữ ký RSA và claims thật.
    monkeypatch.setattr("app.auth.id_token._fetch_certs", lambda *a, **k: {"synthetic-key": public})
    now = int(time.time())
    credential = jwt.encode(
        crypt.RSASigner.from_string(private, key_id="synthetic-key"),
        {
            "aud": "test-client",
            "iss": "https://accounts.google.com",
            "sub": "synthetic-user",
            "nonce": "test-nonce",
            "iat": now + issued_offset,
            "exp": now + expires_offset,
        },
    ).decode()
    try:
        if accepted:
            assert verify_google_identity(credential, "test-nonce")["sub"] == "synthetic-user"
            parts = credential.split(".")
            parts[2] = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
            with pytest.raises(AppError):
                verify_google_identity(".".join(parts), "test-nonce")
            with pytest.raises(AppError):
                verify_google_identity(credential, "different-nonce")
        else:
            with pytest.raises(AppError) as error:
                verify_google_identity(credential, "test-nonce")
            assert error.value.status == 401
    finally:
        get_settings.cache_clear()


def test_google_certificate_transport_failure_is_safe_503(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused:unused@localhost/unused")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
    get_settings.cache_clear()
    sensitive = "synthetic-sensitive-transport-input"

    def unavailable(*args: object, **kwargs: object) -> dict:
        raise TransportError(sensitive)

    monkeypatch.setattr("app.auth.id_token.verify_oauth2_token", unavailable)
    try:
        with pytest.raises(AppError) as error:
            verify_google_identity(sensitive, "nonce")
        assert error.value.status == 503 and error.value.code == "GOOGLE_UNAVAILABLE"
        assert sensitive not in caplog.text
    finally:
        get_settings.cache_clear()
