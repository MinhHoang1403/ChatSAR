"""Workspace một owner; mọi truy cập được scope theo principal đã xác thực."""

from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, insert, select
from sqlalchemy.engine import Connection

from app import database as db
from app.auth import MutationDependency, Principal, PrincipalDependency
from app.errors import AppError
from app.schema import workspaces

router = APIRouter(prefix="/api/workspaces")


class WorkspaceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1, max_length=120, pattern=r"\S")


def owned_workspace(connection: Connection, workspace_id: UUID, principal: Principal) -> None:
    found = connection.execute(
        select(workspaces.c.id).where(
            and_(workspaces.c.id == workspace_id, workspaces.c.owner_id == principal.user_id)
        )
    ).one_or_none()
    if found is None:
        raise AppError(404, "NOT_FOUND", "Không tìm thấy không gian làm việc.")


@router.get("")
def list_workspaces(principal: PrincipalDependency) -> list[dict[str, Any]]:
    with db.get_engine().connect() as connection:
        rows = (
            connection.execute(
                select(workspaces.c.id, workspaces.c.name)
                .where(workspaces.c.owner_id == principal.user_id)
                .order_by(workspaces.c.created_at, workspaces.c.id)
            )
            .mappings()
            .all()
        )
    return [dict(row) for row in rows]


@router.post("", status_code=201)
def create_workspace(body: WorkspaceInput, principal: MutationDependency) -> dict[str, Any]:
    workspace_id = uuid4()
    with db.get_engine().begin() as connection:
        connection.execute(
            insert(workspaces).values(
                id=workspace_id, owner_id=principal.user_id, name=body.name.strip()
            )
        )
    return {"id": workspace_id, "name": body.name.strip()}


@router.get("/{workspace_id}")
def get_workspace(workspace_id: UUID, principal: PrincipalDependency) -> dict[str, Any]:
    with db.get_engine().connect() as connection:
        owned_workspace(connection, workspace_id, principal)
        row = (
            connection.execute(
                select(workspaces.c.id, workspaces.c.name).where(workspaces.c.id == workspace_id)
            )
            .mappings()
            .one()
        )
    return dict(row)
