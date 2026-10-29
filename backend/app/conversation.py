"""Chat dùng cùng pipeline, lịch sử DB và idempotency trước khi gọi provider."""

from __future__ import annotations

import hashlib
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, Query, Request
from pydantic import Field
from sqlalchemy import and_, insert, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import database as db
from app.auth import MutationDependency, Principal, PrincipalDependency
from app.datasets import owned_revision
from app.errors import AppError
from app.observability import annotate, current_trace_id, observation
from app.providers import generate_proposal
from app.query import Contract, compile_query, execute_query
from app.schema import conversations, messages, results, revisions, workspaces
from app.workspace import owned_workspace

router = APIRouter(prefix="/api")


class ConversationInput(Contract):
    workspace_id: str
    title: str = Field(default="Cuộc trò chuyện mới", min_length=1, max_length=120)


class MessageInput(Contract):
    question: str = Field(min_length=1, max_length=4000)
    dataset_revision_id: str
    provider: Literal["gemini", "knowledge"] = "gemini"


def owned_conversation(
    connection: Connection, conversation_id: UUID, principal: Principal
) -> dict[str, Any]:
    row = (
        connection.execute(
            select(conversations)
            .join(workspaces, conversations.c.workspace_id == workspaces.c.id)
            .where(
                and_(
                    conversations.c.id == conversation_id,
                    workspaces.c.owner_id == principal.user_id,
                )
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise AppError(404, "NOT_FOUND", "Không tìm thấy cuộc trò chuyện.")
    return dict(row)


@router.get("/conversations")
def list_conversations(
    principal: PrincipalDependency, workspace_id: Annotated[UUID | None, Query()] = None
) -> list[dict[str, Any]]:
    with db.get_engine().connect() as connection:
        query = (
            select(conversations)
            .join(workspaces, conversations.c.workspace_id == workspaces.c.id)
            .where(workspaces.c.owner_id == principal.user_id)
        )
        if workspace_id:
            owned_workspace(connection, workspace_id, principal)
            query = query.where(conversations.c.workspace_id == workspace_id)
        return [
            dict(row)
            for row in connection.execute(
                query.order_by(conversations.c.created_at.desc())
            ).mappings()
        ]


@router.post("/conversations", status_code=201)
def create_conversation(body: ConversationInput, principal: MutationDependency) -> dict[str, Any]:
    try:
        workspace_id = UUID(body.workspace_id)
    except ValueError:
        raise AppError(422, "INVALID_REQUEST", "Không gian làm việc chưa hợp lệ.") from None
    conversation_id = uuid4()
    with db.get_engine().begin() as connection:
        owned_workspace(connection, workspace_id, principal)
        connection.execute(
            insert(conversations).values(
                id=conversation_id,
                workspace_id=workspace_id,
                title=body.title,
            )
        )
    return {"id": conversation_id, "workspace_id": workspace_id, "title": body.title}


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: UUID, principal: PrincipalDependency) -> dict[str, Any]:
    with db.get_engine().connect() as connection:
        conversation = owned_conversation(connection, conversation_id, principal)
        history = (
            connection.execute(
                select(
                    messages.c.id,
                    messages.c.question,
                    messages.c.envelope,
                    messages.c.status,
                    messages.c.revision_id,
                    messages.c.created_at,
                )
                .where(messages.c.conversation_id == conversation_id)
                .order_by(messages.c.created_at, messages.c.id)
            )
            .mappings()
            .all()
        )
    return {**conversation, "messages": [dict(row) for row in history]}


def empty_answer(status: str, text: str, request_id: str) -> dict[str, Any]:
    return {
        "status": status,
        "facts": {},
        "display_rows": [],
        "citations": [],
        "limitations": [text],
        "display_text": text,
        "request_id": request_id,
    }


@router.post("/conversations/{conversation_id}/messages")
def send_message(
    conversation_id: UUID,
    body: MessageInput,
    request: Request,
    principal: MutationDependency,
    request_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
) -> dict[str, Any]:
    try:
        revision_id = UUID(body.dataset_revision_id)
    except ValueError:
        raise AppError(422, "INVALID_REQUEST", "Revision dữ liệu chưa hợp lệ.") from None
    request_hash = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    message_id, result_id = uuid4(), uuid4()
    try:
        with db.get_engine().begin() as connection:
            conversation = owned_conversation(connection, conversation_id, principal)
            dataset_id = connection.execute(
                select(revisions.c.dataset_id).where(revisions.c.id == revision_id)
            ).scalar_one_or_none()
            if dataset_id is None:
                raise AppError(404, "NOT_FOUND", "Không tìm thấy dữ liệu.")
            revision = owned_revision(connection, dataset_id, principal, revision_id)
            if revision["workspace_id"] != conversation["workspace_id"]:
                raise AppError(
                    404, "NOT_FOUND", "Dữ liệu không thuộc không gian của cuộc trò chuyện."
                )
            if revision["status"] != "ready":
                raise AppError(409, "SOURCE_NOT_READY", "Dữ liệu chưa được xác nhận để hỏi đáp.")
            existing = (
                connection.execute(
                    select(messages).where(
                        and_(
                            messages.c.conversation_id == conversation_id,
                            messages.c.request_key == request_key,
                        )
                    )
                )
                .mappings()
                .one_or_none()
            )
            if existing:
                if existing["request_hash"] != request_hash:
                    raise AppError(
                        409, "IDEMPOTENCY_CONFLICT", "Mã yêu cầu đã được dùng cho nội dung khác."
                    )
                if existing["envelope"]:
                    return {**existing["envelope"], "request_id": request.state.request_id}
                raise AppError(409, "REQUEST_PENDING", "Yêu cầu đang được xử lý; vui lòng đợi.")
            previous = (
                connection.execute(
                    select(messages.c.question, messages.c.query_plan, messages.c.revision_id)
                    .where(
                        and_(
                            messages.c.conversation_id == conversation_id,
                            messages.c.status == "answered",
                        )
                    )
                    .order_by(messages.c.created_at.desc())
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            if previous and previous["revision_id"] != revision_id:
                raise AppError(
                    409,
                    "STALE_CONTEXT",
                    "Nguồn dữ liệu đã thay đổi. Hãy tạo cuộc trò chuyện mới để hỏi nguồn này.",
                )
            context = (
                {"question": previous["question"], "plan": previous["query_plan"]}
                if previous and previous["revision_id"] == revision_id
                else None
            )
            connection.execute(
                insert(messages).values(
                    id=message_id,
                    conversation_id=conversation_id,
                    revision_id=revision_id,
                    question=body.question,
                    request_key=request_key,
                    request_hash=request_hash,
                    provider=body.provider,
                    status="pending",
                )
            )
    except IntegrityError:
        raise AppError(
            409, "REQUEST_PENDING", "Yêu cầu đã được tiếp nhận; vui lòng thử đọc lại."
        ) from None
    plan = None
    with observation(
        "answer_question",
        request_id=request.state.request_id,
        revision_id=str(revision_id),
        question_length=len(body.question),
    ) as span:
        try:
            proposal = generate_proposal(body.question, revision, body.provider, context)
            plan = proposal.plan
            if plan.task != "SQL" or plan.unresolved:
                status = "unsupported" if plan.task == "UNSUPPORTED" else "clarify"
                answer = empty_answer(
                    status,
                    "Vui lòng làm rõ câu hỏi hoặc chọn yêu cầu nằm trong phạm vi dữ liệu.",
                    request.state.request_id,
                )
            else:
                with observation("bind_and_compile") as validation:
                    compiled = compile_query(
                        plan, revision, body.question, context["question"] if context else ""
                    )
                    annotate(validation, output={"validation_status": "passed"})
                with observation("execute_read_only") as execution:
                    rows, latency = execute_query(compiled)
                    annotate(execution, output={"row_count": len(rows), "latency_ms": latency})
                if not rows:
                    text = "Không có dòng nào khớp điều kiện đã chọn."
                elif len(rows) == 1 and len(rows[0]) == 1:
                    value = rows[0][0]
                    unit = compiled.columns[0].get("unit")
                    text = (
                        compiled.columns[0]["name"]
                        + ": "
                        + (str(value) if value is not None else "Chưa có giá trị (NULL)")
                        + (" " + unit if unit and value is not None else "")
                    )
                else:
                    text = f"Tìm thấy {len(rows)} dòng kết quả theo dữ liệu đã chọn."
                answer = {
                    "status": "answered",
                    "facts": {
                        "columns": compiled.columns,
                        "rows": rows,
                        "filters": compiled.filters,
                        "scope": {
                            "workspace_id": str(conversation["workspace_id"]),
                            "dataset_id": str(dataset_id),
                            "source_revision": str(revision_id),
                            "checksum": revision["checksum"],
                            "timezone": revision["timezone"],
                            "grain": revision["grain"],
                        },
                        "execution_id": str(result_id),
                        "execution_latency_ms": latency,
                        "provider": {
                            "name": proposal.provider,
                            "model": proposal.model,
                            "input_tokens": proposal.input_tokens,
                            "output_tokens": proposal.output_tokens,
                            "latency_ms": proposal.latency_ms,
                            "request_id": proposal.request_id,
                        },
                        "trust": "verified_result",
                    },
                    "display_rows": rows,
                    "citations": [
                        {
                            "kind": "dataset",
                            "dataset_id": str(dataset_id),
                            "source_revision": str(revision_id),
                            "checksum": revision["checksum"],
                            "result_id": str(result_id),
                        }
                    ],
                    "limitations": [f"Kết quả được giới hạn tối đa {plan.limit} dòng."],
                    "display_text": text,
                    "request_id": request.state.request_id,
                    "result_id": str(result_id),
                }
        except AppError as error:
            status = (
                "clarify"
                if error.code == "QUERY_CLARIFY"
                else "unsupported"
                if error.code == "QUERY_UNSUPPORTED"
                else "insufficient"
                if error.code == "DATA_PERMISSION_REQUIRED"
                else "provider_unavailable"
            )
            answer = empty_answer(status, error.message, request.state.request_id)
            answer["error_code"] = error.code
        except SQLAlchemyError:
            answer = empty_answer(
                "execution_error",
                "Chưa thể lấy kết quả dữ liệu. Vui lòng thử lại.",
                request.state.request_id,
            )
        annotate(
            span,
            output={"answer_status": answer["status"], "row_count": len(answer["display_rows"])},
        )
        answer["trace_id"] = current_trace_id() if span is not None else None
    with db.get_engine().begin() as connection:
        connection.execute(
            update(messages)
            .where(messages.c.id == message_id)
            .values(
                status=answer["status"],
                envelope=answer,
                # Lưu proposal để chẩn đoán nội bộ; chỉ status answered được dùng làm context.
                query_plan=plan.model_dump(mode="json") if plan else None,
            )
        )
        connection.execute(
            insert(results).values(id=result_id, message_id=message_id, envelope=answer)
        )
    return answer


@router.get("/results/{result_id}")
def get_result(result_id: UUID, principal: PrincipalDependency) -> dict[str, Any]:
    with db.get_engine().connect() as connection:
        row = connection.execute(
            select(results.c.envelope)
            .select_from(
                results.join(messages, results.c.message_id == messages.c.id)
                .join(conversations, messages.c.conversation_id == conversations.c.id)
                .join(workspaces, conversations.c.workspace_id == workspaces.c.id)
            )
            .where(and_(results.c.id == result_id, workspaces.c.owner_id == principal.user_id))
        )
        answer = row.scalar_one_or_none()
    if answer is None:
        raise AppError(404, "NOT_FOUND", "Không tìm thấy kết quả.")
    return dict(answer)


def recover_messages() -> None:
    with db.get_engine().begin() as connection:
        connection.execute(
            update(messages)
            .where(messages.c.status == "pending")
            .values(
                status="execution_error",
                envelope=empty_answer(
                    "execution_error",
                    "Lượt hỏi bị gián đoạn. Cần gửi lại bằng một yêu cầu mới.",
                    "interrupted",
                ),
            )
        )
