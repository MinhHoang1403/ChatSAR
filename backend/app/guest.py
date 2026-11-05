"""Phiên khách tạm dùng cùng pipeline; không khôi phục token sau reload."""

import asyncio
import hmac
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Request, Response
from sqlalchemy import MetaData, Table, delete, insert, select, update
from sqlalchemy.exc import SQLAlchemyError

from app import database as db
from app.auth import create_session, digest
from app.config import get_settings
from app.errors import AppError
from app.query import Contract
from app.schema import (
    conversations,
    datasets,
    jobs,
    messages,
    results,
    revisions,
    sessions,
    users,
    workspaces,
)

router = APIRouter(prefix="/api/auth/guest")
logger = logging.getLogger(__name__)
GUEST_LIFETIME = timedelta(hours=2)


class GuestInput(Contract):
    pass


def purge_guest(owner: UUID) -> bool:
    """Chỉ dọn principal guest đã kết thúc; tuyệt đối không nhận owner từ body."""
    with db.get_engine().begin() as connection:
        guest = connection.execute(
            select(users.c.id)
            .where(users.c.id == owner, users.c.provider == "guest")
            .with_for_update()
        ).first()
        if guest is None:
            return True
        # Cùng thứ tự khóa workspace của send/delete. Lượt model đang bay phải
        # hoàn tất ghi usage; dữ liệu tạm được reaper dọn sau, không replay request.
        owned = list(
            connection.execute(
                select(workspaces.c.id)
                .where(workspaces.c.owner_id == owner)
                .order_by(workspaces.c.id)
                .with_for_update()
            ).scalars()
        )
        chats = select(conversations.c.id).where(conversations.c.workspace_id.in_(owned))
        if connection.execute(
            select(messages.c.id)
            .where(messages.c.conversation_id.in_(chats), messages.c.status == "pending")
            .limit(1)
        ).first():
            return False
        sources = (
            connection.execute(
                select(revisions)
                .join(datasets, revisions.c.dataset_id == datasets.c.id)
                .where(datasets.c.workspace_id.in_(owned))
                .with_for_update(of=revisions)
            )
            .mappings()
            .all()
        )
        if any(
            source["status"] in ("validating", "publishing")
            or (source["setup_proposal"] or {}).get("status") == "pending"
            for source in sources
        ):
            return False
        message_ids = select(messages.c.id).where(messages.c.conversation_id.in_(chats))
        connection.execute(delete(results).where(results.c.message_id.in_(message_ids)))
        connection.execute(delete(messages).where(messages.c.conversation_id.in_(chats)))
        connection.execute(delete(conversations).where(conversations.c.workspace_id.in_(owned)))
        storage = Path(get_settings().storage_root).resolve()
        for source in sources:
            expected = str(source["id"]) + source["suffix"]
            path = (storage / expected).resolve()
            if source["storage_name"] != expected or path.parent != storage:
                raise AppError(409, "INVALID_SOURCE", "Chưa xác minh được file của phiên khách.")
            if source["physical_table"]:
                if source["physical_table"] != "r_" + source["id"].hex:
                    raise AppError(409, "INVALID_SOURCE", "Bảng phiên khách chưa hợp lệ.")
                Table(source["physical_table"], MetaData(), schema="data").drop(
                    connection, checkfirst=True
                )
            # Đây là tài nguyên của đúng guest đã hết phiên. Nếu unlink lỗi,
            # metadata rollback để reaper còn căn cứ thử dọn lại.
            path.unlink(missing_ok=True)
            connection.execute(delete(jobs).where(jobs.c.revision_id == source["id"]))
            connection.execute(delete(revisions).where(revisions.c.id == source["id"]))
        connection.execute(delete(datasets).where(datasets.c.workspace_id.in_(owned)))
        connection.execute(delete(workspaces).where(workspaces.c.owner_id == owner))
        connection.execute(delete(users).where(users.c.id == owner, users.c.provider == "guest"))
    return True


def reap_guests() -> None:
    now = datetime.now(UTC)
    active = (
        select(sessions.c.user_id)
        .where(
            sessions.c.user_id == users.c.id,
            sessions.c.expires_at > now,
            sessions.c.revoked_at.is_(None),
        )
        .exists()
    )
    with db.get_engine().connect() as connection:
        expired = list(
            connection.execute(
                select(users.c.id).where(users.c.provider == "guest", ~active).limit(20)
            ).scalars()
        )
    for owner in expired:
        try:
            purge_guest(owner)
        except (SQLAlchemyError, AppError, OSError):
            logger.warning("Guest cleanup delayed; expired session remains inaccessible")


async def guest_maintenance() -> None:
    while True:
        await asyncio.sleep(60)
        try:
            await asyncio.to_thread(reap_guests)
        except (SQLAlchemyError, AppError, OSError):
            # Không log token, đường dẫn file hoặc nội dung dữ liệu tạm.
            continue


@router.post("", status_code=201)
def begin_guest(body: GuestInput, response: Response) -> dict[str, object]:
    owner = uuid4()
    with db.get_engine().begin() as connection:
        connection.execute(
            insert(users).values(
                id=owner, provider="guest", provider_subject=uuid4().hex, display_name="Khách"
            )
        )
        token = create_session(connection, owner, lifetime=GUEST_LIFETIME)
        connection.execute(
            insert(workspaces).values(id=uuid4(), owner_id=owner, name="Không gian tạm")
        )
    response.headers["Cache-Control"] = "no-store"
    return {
        "id": str(owner),
        "display_name": "Khách",
        "is_guest": True,
        "csrf_token": digest("csrf:" + token),
        "guest_token": token,
    }


@router.delete("", status_code=204)
def end_guest(request: Request) -> Response:
    token = request.headers.get("X-Guest-Session", "")
    if not token or len(token) > 128:
        raise AppError(401, "UNAUTHENTICATED", "Phiên khách không hợp lệ.")
    if not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), digest("csrf:" + token)):
        raise AppError(403, "CSRF_REJECTED", "Yêu cầu không hợp lệ.")
    with db.get_engine().begin() as connection:
        owner = connection.execute(
            select(users.c.id)
            .join(sessions, sessions.c.user_id == users.c.id)
            .where(users.c.provider == "guest", sessions.c.token_hash == digest(token))
        ).scalar_one_or_none()
        if owner is not None:
            connection.execute(
                update(sessions)
                .where(sessions.c.user_id == owner)
                .values(revoked_at=datetime.now(UTC), expires_at=datetime.now(UTC))
            )
    if owner is not None:
        purge_guest(owner)
    return Response(status_code=204)
