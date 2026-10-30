"""Google token verification, session DB và CSRF; không có đường đăng nhập giả."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Annotated, Any, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
from google.auth.exceptions import GoogleAuthError, TransportError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import and_, insert, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from app import database as db
from app.config import get_settings
from app.errors import AppError
from app.schema import sessions, users

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
SESSION_COOKIE = "chatsar_session"
CHALLENGE_COOKIE = "chatsar_login_challenge"
GOOGLE_CLOCK_SKEW_SECONDS = 10


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    display_name: str
    token_hash: str = field(repr=False)
    csrf_token: str = field(repr=False)


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    credential: str = Field(min_length=1, max_length=16384)
    g_csrf_token: str = Field(min_length=20, max_length=128)


class ProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    display_name: str = Field(min_length=1, max_length=200)
    phone: str = Field(max_length=40, pattern=r"^[0-9+(). \-]*$")
    interests: str = Field(max_length=1000)

    @field_validator("display_name", "phone", "interests")
    @classmethod
    def clean_profile(cls, value: str) -> str:
        if any(ord(c) < 32 and c not in "\n\t" for c in value):
            raise ValueError("Invalid profile text")
        return value.strip()

    @field_validator("display_name")
    @classmethod
    def require_name(cls, value: str) -> str:
        if not value or "\n" in value or "\t" in value:
            raise ValueError("Invalid display name")
        return value


def digest(value: str) -> str:
    secret = get_settings().session_secret.get_secret_value()
    if len(secret) < 32:
        raise AppError(503, "AUTH_NOT_CONFIGURED", "Chưa hoàn tất cấu hình đăng nhập.")
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def secure_cookie() -> bool:
    settings = get_settings()
    if settings.app_env != "development" and not settings.app_origin.startswith("https://"):
        raise AppError(503, "HTTPS_REQUIRED", "Cần kết nối HTTPS để đăng nhập.")
    return settings.app_origin.startswith("https://")


def verify_google_identity(credential: str, nonce: str) -> dict[str, Any]:
    client_id = get_settings().google_client_id
    if not client_id:
        raise AppError(503, "GOOGLE_NOT_CONFIGURED", "Đăng nhập Google đang chờ cấu hình.")
    try:
        verifier = cast(Callable[..., dict[str, Any]], id_token.verify_oauth2_token)
        claims = verifier(
            credential,
            partial(GoogleRequest(), timeout=5),
            client_id,
            clock_skew_in_seconds=GOOGLE_CLOCK_SKEW_SECONDS,
        )
    except TransportError:
        logger.warning("Google identity verification unavailable: transport")
        raise AppError(
            503, "GOOGLE_UNAVAILABLE", "Chưa kết nối được Google. Vui lòng thử lại."
        ) from None
    except (GoogleAuthError, ValueError, TypeError, KeyError) as error:
        # Chỉ log mã phân loại cố định; exception gốc có thể chứa toàn bộ token.
        text = str(error).lower()
        reason = next(
            (
                name
                for name, phrase in (
                    ("clock_early", "too early"),
                    ("expired", "expired"),
                    ("audience", "audience"),
                    ("certificate", "certificate"),
                    ("signature", "signature"),
                    ("algorithm", "algorithm"),
                    ("malformed", "segments"),
                )
                if phrase in text
            ),
            "verification",
        )
        logger.warning("Google identity rejected: %s", reason)
        raise AppError(401, "INVALID_GOOGLE_TOKEN", "Thông tin đăng nhập không hợp lệ.") from None
    subject, expiry, claim_nonce = claims.get("sub"), claims.get("exp"), claims.get("nonce")
    checks = {
        "audience": claims.get("aud") == client_id,
        "issuer": claims.get("iss") in ("https://accounts.google.com", "accounts.google.com"),
        "subject": isinstance(subject, str) and 1 <= len(subject) <= 255,
        "expiry": isinstance(expiry, (int, float)) and expiry > time.time(),
        "nonce": isinstance(claim_nonce, str)
        and hmac.compare_digest(claim_nonce.encode(), nonce.encode()),
    }
    if not all(checks.values()):
        logger.warning(
            "Google identity rejected claims: %s", ",".join(k for k, v in checks.items() if not v)
        )
        raise AppError(401, "INVALID_GOOGLE_TOKEN", "Thông tin đăng nhập không hợp lệ.")
    return claims


def create_session(connection: Connection, user_id: UUID, nonce: str | None = None) -> str:
    token = secrets.token_urlsafe(32)
    connection.execute(
        insert(sessions).values(
            token_hash=digest(token),
            user_id=user_id,
            expires_at=datetime.now(UTC) + timedelta(hours=24),
            google_nonce_hash=digest("nonce:" + nonce) if nonce else None,
        )
    )
    return token


def current_principal(request: Request) -> Principal:
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token or len(token) > 128:
        raise AppError(401, "UNAUTHENTICATED", "Vui lòng đăng nhập để tiếp tục.")
    token_hash = digest(token)
    with db.get_engine().connect() as connection:
        row = (
            connection.execute(
                select(users.c.id, users.c.display_name)
                .select_from(sessions.join(users, users.c.id == sessions.c.user_id))
                .where(
                    and_(
                        sessions.c.token_hash == token_hash,
                        sessions.c.expires_at > datetime.now(UTC),
                        sessions.c.revoked_at.is_(None),
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise AppError(401, "SESSION_EXPIRED", "Phiên đăng nhập đã hết hạn.")
    return Principal(row["id"], row["display_name"], token_hash, digest("csrf:" + token))


PrincipalDependency = Annotated[Principal, Depends(current_principal)]


def authorized_mutation(request: Request, principal: PrincipalDependency) -> Principal:
    if not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), principal.csrf_token):
        raise AppError(403, "CSRF_REJECTED", "Yêu cầu không hợp lệ. Vui lòng tải lại trang.")
    return principal


MutationDependency = Annotated[Principal, Depends(authorized_mutation)]


@router.get("/auth/config")
def login_config(response: Response) -> dict[str, Any]:
    nonce = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    payload = base64.urlsafe_b64encode(
        json.dumps({"nonce": nonce, "csrf": csrf, "created": int(time.time())}).encode()
    ).decode()
    response.set_cookie(
        CHALLENGE_COOKIE,
        payload + "." + digest(payload),
        max_age=600,
        httponly=True,
        secure=secure_cookie(),
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "google_client_id": get_settings().google_client_id,
        "app_origin": get_settings().app_origin,
        "nonce": nonce,
        "csrf_token": csrf,
    }


@router.post("/auth/google")
def google_login(body: LoginInput, request: Request, response: Response) -> dict[str, Any]:
    try:
        payload, signature = request.cookies.get(CHALLENGE_COOKIE, "").split(".", 1)
        if len(payload) > 2048 or not hmac.compare_digest(signature, digest(payload)):
            raise ValueError("Invalid challenge")
        state = json.loads(base64.urlsafe_b64decode(payload))
        age = time.time() - state["created"]
        if not 0 <= age <= 600 or not hmac.compare_digest(state["csrf"], body.g_csrf_token):
            raise ValueError("Invalid challenge")
    except (ValueError, TypeError, KeyError):
        raise AppError(
            403, "CSRF_REJECTED", "Phiên đăng nhập không hợp lệ hoặc đã hết hạn."
        ) from None
    claims = verify_google_identity(body.credential, state["nonce"])
    try:
        with db.get_engine().begin() as connection:
            row = connection.execute(
                select(users.c.id).where(
                    and_(users.c.provider == "google", users.c.provider_subject == claims["sub"])
                )
            ).one_or_none()
            user_id = row[0] if row else uuid4()
            if row is None:
                name = claims.get("name")
                connection.execute(
                    insert(users).values(
                        id=user_id,
                        provider="google",
                        provider_subject=claims["sub"],
                        display_name=name[:200]
                        if isinstance(name, str) and name.strip()
                        else "Người dùng",
                    )
                )
            token = create_session(connection, user_id, state["nonce"])
            old_token = request.cookies.get(SESSION_COOKIE)
            if old_token:
                connection.execute(
                    update(sessions)
                    .where(sessions.c.token_hash == digest(old_token))
                    .values(revoked_at=datetime.now(UTC))
                )
    except IntegrityError:
        raise AppError(409, "LOGIN_REPLAY", "Vui lòng bắt đầu lại lượt đăng nhập.") from None
    response.set_cookie(
        SESSION_COOKIE, token, max_age=86400, httponly=True, secure=secure_cookie(), samesite="lax"
    )
    response.delete_cookie(CHALLENGE_COOKIE)
    return {"id": str(user_id), "csrf_token": digest("csrf:" + token)}


@router.get("/me")
def me(principal: PrincipalDependency) -> dict[str, str]:
    return {
        "id": str(principal.user_id),
        "display_name": principal.display_name,
        "csrf_token": principal.csrf_token,
    }


@router.post("/auth/logout", status_code=204)
def logout(principal: MutationDependency, response: Response) -> None:
    with db.get_engine().begin() as connection:
        connection.execute(
            update(sessions)
            .where(sessions.c.token_hash == principal.token_hash)
            .values(revoked_at=datetime.now(UTC))
        )
    response.delete_cookie(SESSION_COOKIE)


@router.get("/profile")
def get_profile(principal: PrincipalDependency) -> dict[str, str]:
    with db.get_engine().connect() as connection:
        row = (
            connection.execute(
                select(users.c.display_name, users.c.phone, users.c.interests).where(
                    users.c.id == principal.user_id
                )
            )
            .mappings()
            .one()
        )
    return dict(row)


@router.patch("/profile")
def update_profile(body: ProfileInput, principal: MutationDependency) -> dict[str, str]:
    with db.get_engine().begin() as connection:
        connection.execute(
            update(users).where(users.c.id == principal.user_id).values(**body.model_dump())
        )
    return body.model_dump()
