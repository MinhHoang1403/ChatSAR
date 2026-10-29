"""Upload/review/publish atomic thành bảng revision PostgreSQL có kiểu."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal, cast
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, File, Form, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    DDL,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
    and_,
    event,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.types import TypeEngine

from app import database as db
from app.auth import MutationDependency, Principal, PrincipalDependency
from app.config import get_settings
from app.errors import AppError
from app.schema import datasets, jobs, revisions, workspaces
from app.tabular import (
    MAX_BYTES,
    ColumnReview,
    invalid,
    profile,
    read_table,
    typed_value,
    validate_rows,
    wire,
)
from app.workspace import owned_workspace

router = APIRouter(prefix="/api")


class PublishInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    revision_id: str
    columns: list[ColumnReview] = Field(min_length=1, max_length=100)
    sheet_name: str | None = None
    timezone: str = "Asia/Ho_Chi_Minh"
    grain: str = Field(min_length=1, max_length=300)
    data_classification: Literal["private", "synthetic"] = "private"
    description: str = Field(default="", max_length=1000)
    sharing_providers: list[Literal["gemini", "knowledge"]] = Field(
        default_factory=list, max_length=2
    )


def owned_revision(
    connection: Connection,
    dataset_id: UUID,
    principal: Principal,
    revision_id: UUID | None = None,
    lock: bool = False,
) -> dict[str, Any]:
    query = (
        select(revisions, datasets.c.workspace_id, datasets.c.checksum, datasets.c.name)
        .select_from(
            revisions.join(datasets, revisions.c.dataset_id == datasets.c.id).join(
                workspaces, datasets.c.workspace_id == workspaces.c.id
            )
        )
        .where(and_(datasets.c.id == dataset_id, workspaces.c.owner_id == principal.user_id))
    )
    if revision_id:
        query = query.where(revisions.c.id == revision_id)
    if lock:
        query = query.with_for_update(of=revisions)
    row = connection.execute(query).mappings().one_or_none()
    if row is None:
        raise AppError(404, "NOT_FOUND", "Không tìm thấy dữ liệu trong không gian làm việc.")
    return dict(row)


def source_bytes(revision: dict[str, Any]) -> bytes:
    storage = Path(get_settings().storage_root)
    expected = str(revision["id"]) + str(revision["suffix"])
    if revision["storage_name"] != expected:
        raise AppError(409, "INVALID_SOURCE", "Thông tin nguồn dữ liệu không hợp lệ.")
    try:
        data = (storage / expected).read_bytes()
    except OSError:
        raise AppError(409, "SOURCE_UNAVAILABLE", "Chưa truy cập được file nguồn.") from None
    if hashlib.sha256(data).hexdigest() != revision["checksum"]:
        raise AppError(409, "SOURCE_CHANGED", "File nguồn đã thay đổi; cần kiểm tra lại.")
    return data


def job_state(
    connection: Connection, revision_id: UUID, status: str, error: str | None = None
) -> None:
    connection.execute(update(revisions).where(revisions.c.id == revision_id).values(status=status))
    connection.execute(
        update(jobs)
        .where(jobs.c.revision_id == revision_id)
        .values(status=status, error_code=error, updated_at=datetime.now(UTC))
    )


def recover_ingestion() -> None:
    # Khi process dừng giữa chừng, transaction DDL bị rollback; không tự báo ready.
    with db.get_engine().begin() as connection:
        ids = (
            connection.execute(
                select(revisions.c.id).where(revisions.c.status.in_(["validating", "publishing"]))
            )
            .scalars()
            .all()
        )
        for revision_id in ids:
            job_state(connection, revision_id, "failed", "INTERRUPTED")
        pending = connection.execute(
            select(revisions.c.id, revisions.c.setup_proposal).where(
                revisions.c.setup_proposal.is_not(None)
            )
        ).all()
        for revision_id, proposal in pending:
            if proposal.get("status") == "pending":
                connection.execute(
                    update(revisions)
                    .where(revisions.c.id == revision_id)
                    .values(setup_proposal={**proposal, "status": "interrupted"})
                )


@router.get("/workspaces/{workspace_id}/datasets")
def list_datasets(workspace_id: UUID, principal: PrincipalDependency) -> list[dict[str, Any]]:
    with db.get_engine().connect() as connection:
        owned_workspace(connection, workspace_id, principal)
        rows = (
            connection.execute(
                select(
                    datasets.c.id,
                    datasets.c.name,
                    revisions.c.id.label("revision_id"),
                    revisions.c.status,
                    revisions.c.row_count,
                )
                .select_from(datasets.join(revisions, datasets.c.id == revisions.c.dataset_id))
                .where(datasets.c.workspace_id == workspace_id)
                .order_by(revisions.c.created_at)
            )
            .mappings()
            .all()
        )
    return [dict(row) for row in rows]


@router.post("/workspaces/{workspace_id}/datasets", status_code=202)
async def upload_dataset(
    workspace_id: UUID,
    principal: MutationDependency,
    file: Annotated[UploadFile, File()],
    sheet_name: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    with db.get_engine().connect() as connection:
        owned_workspace(connection, workspace_id, principal)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".csv", ".xlsx"):
        raise invalid("Chỉ hỗ trợ CSV và XLSX.")
    data = await file.read(MAX_BYTES + 1)
    await file.close()
    if not data or len(data) > MAX_BYTES:
        raise AppError(413, "UPLOAD_LIMIT", "File trống hoặc vượt giới hạn 20 MiB.")
    checksum = hashlib.sha256(data).hexdigest()
    with db.get_engine().begin() as connection:
        existing = connection.execute(
            select(datasets.c.id).where(
                and_(datasets.c.workspace_id == workspace_id, datasets.c.checksum == checksum)
            )
        ).scalar_one_or_none()
        if existing:
            old = owned_revision(connection, existing, principal, lock=True)
            job_id = connection.execute(
                select(jobs.c.id).where(jobs.c.revision_id == old["id"])
            ).scalar_one()
            if old["status"] != "failed":
                return {
                    "dataset_id": existing,
                    "revision_id": old["id"],
                    "job_id": job_id,
                    "status": old["status"],
                }
            dataset_id, revision_id = existing, old["id"]
            job_state(connection, revision_id, "validating")
        else:
            dataset_id, revision_id, job_id = uuid4(), uuid4(), uuid4()
            storage = Path(get_settings().storage_root)
            storage.mkdir(parents=True, exist_ok=True)
            storage_name = str(revision_id) + suffix
            with (storage / storage_name).open("xb") as destination:
                destination.write(data)
            connection.execute(
                insert(datasets).values(
                    id=dataset_id,
                    workspace_id=workspace_id,
                    name=Path(file.filename or "Dữ liệu").name[:200],
                    checksum=checksum,
                )
            )
            connection.execute(
                insert(revisions).values(
                    id=revision_id,
                    dataset_id=dataset_id,
                    status="validating",
                    storage_name=storage_name,
                    suffix=suffix,
                )
            )
            connection.execute(
                insert(jobs).values(
                    id=job_id,
                    revision_id=revision_id,
                    status="validating",
                )
            )
    try:
        parsed = read_table(data, suffix, sheet_name)
        columns = profile(parsed, revision_id) if parsed.headers else []
        with db.get_engine().begin() as connection:
            connection.execute(
                update(revisions)
                .where(revisions.c.id == revision_id)
                .values(
                    columns=columns,
                    sheet_name=parsed.sheet_name or None,
                    row_count=len(parsed.rows) if parsed.headers else None,
                )
            )
            job_state(connection, revision_id, "needs_review")
    except AppError:
        with db.get_engine().begin() as connection:
            job_state(connection, revision_id, "failed", "INVALID_SOURCE")
        raise
    return {
        "dataset_id": dataset_id,
        "revision_id": revision_id,
        "job_id": job_id,
        "status": "needs_review",
        "sheets": parsed.sheets,
    }


@router.get("/datasets/{dataset_id}/preview")
def preview_dataset(
    dataset_id: UUID,
    principal: PrincipalDependency,
    revision_id: UUID | None = None,
    sheet_name: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    with db.get_engine().connect() as connection:
        revision = owned_revision(connection, dataset_id, principal, revision_id)
    parsed = read_table(
        source_bytes(revision), revision["suffix"], sheet_name or revision["sheet_name"]
    )
    columns = (
        revision["columns"]
        if revision["status"] == "ready"
        else profile(parsed, revision["id"])
        if parsed.headers
        else []
    )
    preview_rows = parsed.rows[offset : offset + limit]
    if revision["status"] == "ready":
        reviews = [ColumnReview.model_validate(c) for c in columns]
        preview_rows = [
            [
                typed_value(value, review, revision["timezone"])
                for value, review in zip(row, reviews, strict=True)
            ]
            for row in preview_rows
        ]
    return {
        "dataset_id": dataset_id,
        "revision_id": revision["id"],
        "status": revision["status"],
        "name": revision["name"],
        "sheets": parsed.sheets,
        "sheet_name": parsed.sheet_name,
        "columns": columns,
        "rows": [[wire(v) for v in row] for row in preview_rows],
        "row_count": len(parsed.rows),
        "checksum": revision["checksum"],
        "data_classification": revision["data_classification"],
        "relationships": [],
        "description": revision["description"],
        "grain": revision["grain"],
        "timezone": revision["timezone"],
        "sharing_providers": revision["sharing_providers"],
        "setup_proposal": revision["setup_proposal"],
        "relationship_status": "not_configured_single_table",
    }


@router.post("/datasets/{dataset_id}/confirm")
def publish_dataset(
    dataset_id: UUID, body: PublishInput, principal: MutationDependency
) -> dict[str, Any]:
    try:
        revision_id = UUID(body.revision_id)
        ZoneInfo(body.timezone)
    except (ValueError, ZoneInfoNotFoundError):
        raise invalid("Revision hoặc múi giờ không hợp lệ.") from None
    with db.get_engine().begin() as connection:
        revision = owned_revision(connection, dataset_id, principal, revision_id, lock=True)
        if revision["status"] != "needs_review":
            raise AppError(
                409, "REVISION_STATE", "Revision đã công bố hoặc chưa sẵn sàng để xác nhận."
            )
        parsed = read_table(
            source_bytes(revision), revision["suffix"], body.sheet_name or revision["sheet_name"]
        )
        expected = profile(parsed, revision_id) if parsed.headers else []
        if (
            any(not c.name.strip() for c in body.columns)
            or [c.id for c in body.columns] != [c["id"] for c in expected]
            or len({c.name.strip().casefold() for c in body.columns}) != len(body.columns)
        ):
            raise invalid("Danh sách cột hoặc tên cột không khớp; cần kiểm tra lại preview.")
        rows = validate_rows(parsed, body.columns, body.timezone)
        physical_name = "r_" + revision_id.hex
        types: dict[str, TypeEngine[Any]] = {
            "text": Text(),
            "integer": BigInteger(),
            "numeric": Numeric(asdecimal=True),
            "boolean": Boolean(),
            "date": Date(),
            "timestamp": DateTime(timezone=True),
        }
        table = Table(
            physical_name,
            MetaData(),
            Column("_source_row", Integer, nullable=False),
            *(
                Column(
                    c.id,
                    types[c.data_type],
                    nullable=c.nullable and not c.primary_key,
                    primary_key=c.primary_key,
                )
                for c in body.columns
            ),
            schema="data",
        )
        ddl = cast(Callable[..., DDL], DDL)
        event.listen(table, "after_create", ddl("GRANT SELECT ON %(fullname)s TO chatsar_reader"))
        try:
            table.create(connection)
            for start in range(0, len(rows), 1000):
                connection.execute(insert(table), rows[start : start + 1000])
            connection.execute(
                update(revisions)
                .where(revisions.c.id == revision_id)
                .values(
                    columns=[c.model_dump(mode="json") for c in body.columns],
                    physical_table=physical_name,
                    row_count=len(rows),
                    timezone=body.timezone,
                    grain=body.grain,
                    sheet_name=parsed.sheet_name or None,
                    data_classification=body.data_classification,
                    description=body.description,
                    sharing_providers=list(set(body.sharing_providers)),
                )
            )
            job_state(connection, revision_id, "ready")
        except SQLAlchemyError:
            raise AppError(
                409, "PUBLISH_FAILED", "Không thể công bố; dữ liệu chưa được thay đổi."
            ) from None
    return {
        "revision_id": revision_id,
        "status": "ready",
        "row_count": len(rows),
        "checksum": revision["checksum"],
    }


@router.get("/jobs/{job_id}")
def get_job(job_id: UUID, principal: PrincipalDependency) -> dict[str, Any]:
    with db.get_engine().connect() as connection:
        row = (
            connection.execute(
                select(jobs)
                .select_from(
                    jobs.join(revisions, jobs.c.revision_id == revisions.c.id)
                    .join(datasets, revisions.c.dataset_id == datasets.c.id)
                    .join(workspaces, datasets.c.workspace_id == workspaces.c.id)
                )
                .where(and_(jobs.c.id == job_id, workspaces.c.owner_id == principal.user_id))
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise AppError(404, "NOT_FOUND", "Không tìm thấy công việc xử lý dữ liệu.")
    return dict(row)
