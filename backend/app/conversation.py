"""Chat dùng cùng pipeline, lịch sử DB và idempotency trước khi gọi provider."""

from __future__ import annotations

import hashlib
from time import perf_counter
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, Query, Request, Response
from pydantic import Field, field_validator
from sqlalchemy import and_, delete, insert, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import database as db
from app.answers import compose_answer, failure_text
from app.auth import MutationDependency, Principal, PrincipalDependency
from app.datasets import owned_revision
from app.errors import AppError
from app.evidence import Processing
from app.observability import annotate, current_trace_id, observation
from app.providers import ProviderError, can_fallback, generate_proposal
from app.query import Contract, compile_query, execute_query, ground_catalog
from app.schema import conversations, datasets, messages, results, revisions, workspaces
from app.workspace import owned_workspace

router = APIRouter(prefix="/api")


class ConversationInput(Contract):
    workspace_id: str
    title: str = Field(default="Cuộc trò chuyện mới", min_length=1, max_length=120)


class MessageInput(Contract):
    question: str = Field(min_length=1, max_length=4000)
    dataset_revision_id: str
    provider: Literal["gemini", "knowledge"] = "gemini"
    allow_fallback: bool = False


class ConversationTitle(Contract):
    title: str = Field(min_length=1, max_length=120)

    @field_validator("title")
    @classmethod
    def valid_title(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("Invalid title")
        return value


def lock_workspace(connection: Connection, workspace_id: UUID, principal: Principal) -> None:
    # Cùng thứ tự khóa cho send/create/rename/delete, kể cả bulk trong workspace.
    found = connection.execute(
        select(workspaces.c.id)
        .where(and_(workspaces.c.id == workspace_id, workspaces.c.owner_id == principal.user_id))
        .with_for_update()
    ).scalar_one_or_none()
    if found is None:
        raise AppError(404, "NOT_FOUND", "Không tìm thấy không gian làm việc.")


def delete_chats(connection: Connection, ids: list[UUID]) -> None:
    if not ids:
        return
    pending = connection.execute(
        select(messages.c.id)
        .where(and_(messages.c.conversation_id.in_(ids), messages.c.status == "pending"))
        .limit(1)
    ).first()
    if pending:
        raise AppError(409, "REQUEST_PENDING", "Hãy đợi lượt hỏi hoàn tất trước khi xóa.")
    message_ids = select(messages.c.id).where(messages.c.conversation_id.in_(ids))
    connection.execute(delete(results).where(results.c.message_id.in_(message_ids)))
    connection.execute(delete(messages).where(messages.c.conversation_id.in_(ids)))
    connection.execute(delete(conversations).where(conversations.c.id.in_(ids)))


@router.delete("/workspaces/{workspace_id}/conversations", status_code=204)
def delete_workspace_chats(workspace_id: UUID, principal: MutationDependency) -> Response:
    with db.get_engine().begin() as connection:
        lock_workspace(connection, workspace_id, principal)
        ids = list(
            connection.execute(
                select(conversations.c.id)
                .where(conversations.c.workspace_id == workspace_id)
                .with_for_update()
            ).scalars()
        )
        delete_chats(connection, ids)
    return Response(status_code=204)


@router.patch("/conversations/{conversation_id}")
def rename_conversation(
    conversation_id: UUID, body: ConversationTitle, principal: MutationDependency
) -> dict[str, Any]:
    with db.get_engine().begin() as connection:
        row = owned_conversation(connection, conversation_id, principal)
        lock_workspace(connection, row["workspace_id"], principal)
        row = owned_conversation(connection, conversation_id, principal)
        connection.execute(
            update(conversations)
            .where(conversations.c.id == conversation_id)
            .values(title=body.title)
        )
    return {**row, "title": body.title}


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: UUID, principal: MutationDependency) -> Response:
    with db.get_engine().begin() as connection:
        row = connection.execute(
            select(conversations.c.workspace_id).where(conversations.c.id == conversation_id)
        ).first()
        if row:
            lock_workspace(connection, row.workspace_id, principal)
            delete_chats(connection, [conversation_id])
    return Response(status_code=204)


def owned_conversation(
    connection: Connection, conversation_id: UUID, principal: Principal
) -> dict[str, Any]:
    row = (
        connection.execute(
            select(conversations, datasets.c.name.label("dataset_name"))
            .join(workspaces, conversations.c.workspace_id == workspaces.c.id)
            .outerjoin(revisions, conversations.c.revision_id == revisions.c.id)
            .outerjoin(datasets, revisions.c.dataset_id == datasets.c.id)
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
            select(conversations, datasets.c.name.label("dataset_name"))
            .join(workspaces, conversations.c.workspace_id == workspaces.c.id)
            .outerjoin(revisions, conversations.c.revision_id == revisions.c.id)
            .outerjoin(datasets, revisions.c.dataset_id == datasets.c.id)
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
        lock_workspace(connection, workspace_id, principal)
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
            lock_workspace(connection, conversation["workspace_id"], principal)
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
            if connection.execute(
                select(messages.c.id)
                .where(
                    and_(
                        messages.c.conversation_id == conversation_id,
                        messages.c.status == "pending",
                    )
                )
                .limit(1)
            ).first():
                raise AppError(409, "REQUEST_PENDING", "Cuộc trò chuyện đang xử lý một lượt hỏi.")
            if conversation["revision_id"] and conversation["revision_id"] != revision_id:
                raise AppError(409, "STALE_CONTEXT", "Nguồn đã đổi. Hãy tạo đoạn chat mới.")
            if not conversation["revision_id"]:
                old_sources = set(
                    connection.execute(
                        select(messages.c.revision_id).where(
                            messages.c.conversation_id == conversation_id
                        )
                    ).scalars()
                )
                if old_sources and old_sources != {revision_id}:
                    raise AppError(
                        409, "STALE_CONTEXT", "Lịch sử dùng nguồn khác. Hãy tạo chat mới."
                    )
                connection.execute(
                    update(conversations)
                    .where(conversations.c.id == conversation_id)
                    .values(revision_id=revision_id)
                )
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
            409,
            "REQUEST_PENDING",
            "Yêu cầu đã được tiếp nhận; vui lòng thử đọc lại.",
            stage="authorization",
        ) from None
    except AppError as error:
        error.stage = "authorization"
        raise
    plan = None
    started = perf_counter()
    timings: dict[str, float] = {}
    processing = Processing(
        body.provider,
        {
            "name": revision["name"],
            "dataset_id": str(dataset_id),
            "revision_id": str(revision_id),
            "workspace_id": str(conversation["workspace_id"]),
            "checksum": revision["checksum"],
            "timezone": revision["timezone"],
            "grain": revision["grain"],
        },
    )
    processing.stages["authorization"] = {"status": "succeeded"}

    def checkpoint() -> None:
        progress = empty_answer("pending", "Đang xử lý yêu cầu…", request.state.request_id)
        progress["processing"] = processing.snapshot()
        try:
            with db.get_engine().begin() as connection:
                connection.execute(
                    update(messages)
                    .where(messages.c.id == message_id)
                    .values(
                        envelope=progress, query_plan=plan.model_dump(mode="json") if plan else None
                    )
                )
        except SQLAlchemyError:
            raise AppError(
                503,
                "PERSISTENCE_UNAVAILABLE",
                "Chưa thể lưu bằng chứng xử lý. Chưa tiếp tục truy vấn.",
                stage="persistence",
            ) from None

    def execution_started() -> None:
        processing.sql["execution_status"] = "in_progress"
        try:
            checkpoint()
        except AppError:
            processing.sql["execution_status"] = "not_started"
            raise

    with observation(
        "answer_question",
        request_id=request.state.request_id,
        revision_id=str(revision_id),
        question_length=len(body.question),
    ) as span:
        try:
            with processing.step("catalog"), observation("ground_catalog"):
                revision = ground_catalog(revision)
            timings["catalog"] = processing.stages["catalog"]["duration_ms"]
            active_provider = body.provider
            with processing.step("provider"):
                try:
                    proposal = generate_proposal(body.question, revision, active_provider, context)
                except AppError as error:
                    if not can_fallback(
                        error,
                        revision,
                        body.provider,
                        body.allow_fallback,
                        perf_counter() - started,
                    ):
                        raise
                    active_provider = "knowledge"
                    proposal = generate_proposal(body.question, revision, active_provider, context)
            timings["provider"] = processing.stages["provider"]["duration_ms"]
            processing.provider = {
                "name": proposal.provider,
                "model": proposal.model,
                "latency_ms": proposal.latency_ms,
                "proposal_received": True,
            }
            processing.stages["proposal_parse"] = {"status": "succeeded"}
            plan = proposal.plan
            if plan.task != "SQL" or plan.unresolved:
                status = "unsupported" if plan.task == "UNSUPPORTED" else "clarify"
                processing.failed_stage = "semantic_validation"
                processing.error_code = (
                    "QUERY_UNSUPPORTED" if status == "unsupported" else "QUERY_CLARIFY"
                )
                processing.stages["semantic_validation"] = {
                    "status": "needs_clarification" if status == "clarify" else "unsupported"
                }
                answer = empty_answer(status, failure_text(status), request.state.request_id)
            else:
                with (
                    processing.step("semantic_validation"),
                    observation("bind_and_compile") as validation,
                ):
                    compiled = compile_query(
                        plan, revision, body.question, context["question"] if context else ""
                    )
                    annotate(validation, output={"validation_status": "passed"})
                timings["validation"] = processing.stages["semantic_validation"]["duration_ms"]
                with processing.step("sql_compilation"):
                    processing.capture_sql(compiled, db.get_reader_engine().dialect)
                timings["compilation"] = processing.stages["sql_compilation"]["duration_ms"]
                # Checkpoint ngay trước execute: crash sau đây giữ statement thật,
                # không dựng lại SQL cũ hoặc coi execution bị gián đoạn là thành công.
                with processing.step("execution"), observation("execute_read_only") as execution:
                    try:
                        rows, latency = execute_query(compiled, on_execute=execution_started)
                    finally:
                        if compiled.execution_latency_ms is not None:
                            processing.sql["duration_ms"] = compiled.execution_latency_ms
                    processing.sql["execution_status"] = "succeeded"
                    annotate(execution, output={"row_count": len(rows), "latency_ms": latency})
                timings["execution"] = latency
                if compiled.execution_latency_ms is not None:
                    timings["sql"] = compiled.execution_latency_ms
                with processing.step("composition"):
                    text, output_columns = compose_answer(plan, compiled, revision, rows)
                    partial = compiled.truncated and compiled.result_mode != "top"
                    answer = {
                        "status": "partial" if partial else "answered",
                        "facts": {
                            "columns": output_columns,
                            "rows": rows,
                            "filters": compiled.filters,
                            "scope": {
                                "workspace_id": str(conversation["workspace_id"]),
                                "dataset_id": str(dataset_id),
                                "dataset_name": revision["name"],
                                "source_revision": str(revision_id),
                                "checksum": revision["checksum"],
                                "timezone": revision["timezone"],
                                "grain": revision["grain"],
                            },
                            "execution_id": str(result_id),
                            "execution_latency_ms": latency,
                            "truncated": compiled.truncated,
                            "limit": compiled.limit,
                            "result_mode": compiled.result_mode,
                            "provider": {
                                "name": proposal.provider,
                                "model": proposal.model,
                                "input_tokens": proposal.input_tokens,
                                "output_tokens": proposal.output_tokens,
                                "latency_ms": proposal.latency_ms,
                                "request_id": proposal.request_id,
                            },
                            "trust": "reference_only" if partial else "verified_result",
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
                        "limitations": (
                            [f"Chỉ hiển thị {plan.limit} dòng; hãy thu hẹp điều kiện để xem thêm."]
                            if partial
                            else []
                        )
                        + (
                            ["Có giá trị lọc không khớp nguồn; không tự chọn giá trị gần giống."]
                            if any(f.get("source_match") == "no_match" for f in compiled.filters)
                            else []
                        ),
                        "display_text": text,
                        "request_id": request.state.request_id,
                        "result_id": str(result_id),
                    }
                timings["composition"] = processing.stages["composition"]["duration_ms"]
        except AppError as error:
            if isinstance(error, ProviderError) and error.provider_name:
                processing.provider = {
                    "name": error.provider_name,
                    "model": error.model,
                    "latency_ms": error.latency_ms,
                    "proposal_received": False,
                }
            status = (
                "clarify"
                if error.code == "QUERY_CLARIFY"
                else "unsupported"
                if error.code == "QUERY_UNSUPPORTED"
                else "insufficient"
                if error.code == "DATA_PERMISSION_REQUIRED"
                else "execution_error"
                if error.code == "PERSISTENCE_UNAVAILABLE"
                else "provider_unavailable"
            )
            if error.stage:
                processing.failed_stage = error.stage
            elif processing.failed_stage == "provider" and error.code in {
                "USAGE_UNKNOWN",
                "CALL_LIMIT_REACHED",
                "BUDGET_REACHED",
                "GRANT_LIMIT_REACHED",
                "GRANT_BUDGET_REACHED",
                "CLOUD_DISABLED",
                "DATA_PERMISSION_REQUIRED",
            }:
                processing.failed_stage = "provider_preparation"
            processing.error_code = error.code
            answer = empty_answer(
                status, failure_text(status, error.code, error.message), request.state.request_id
            )
            answer["error_code"] = error.code
        except (SQLAlchemyError, ValueError, TypeError):
            processing.error_code = {
                "execution": "SQL_EXECUTION_FAILED",
                "sql_compilation": "SQL_COMPILATION_FAILED",
                "composition": "ANSWER_COMPOSITION_FAILED",
                "catalog": "CATALOG_UNAVAILABLE",
                "semantic_validation": "QUERY_VALIDATION_FAILED",
            }.get(processing.failed_stage or "", "PROCESSING_FAILED")
            answer = empty_answer(
                "execution_error", failure_text("execution_error"), request.state.request_id
            )
            answer["error_code"] = processing.error_code
        if processing.sql["execution_status"] == "in_progress":
            processing.sql["execution_status"] = "failed"
            answer["display_text"] = (
                "Chưa thể lấy kết quả từ dữ liệu. "
                "Truy vấn đã được tạo nhưng thực hiện không thành công."
            )
            answer["limitations"] = [answer["display_text"]]
        elif processing.failed_stage == "composition":
            answer["display_text"] = "Đã lấy dữ liệu nhưng chưa thể diễn đạt câu trả lời."
            answer["limitations"] = [answer["display_text"]]
        if processing.failed_stage and processing.failed_stage not in processing.stages:
            processing.stages[processing.failed_stage] = {"status": "failed"}
        answer["timings_ms"] = {**timings, "server_processing": (perf_counter() - started) * 1000}
        answer["processing"] = processing.snapshot()
        answer["result_id"] = str(result_id)
        annotate(
            span,
            output={
                "answer_status": answer["status"],
                "row_count": len(answer["display_rows"]),
                "timings_ms": answer["timings_ms"],
            },
        )
        answer["trace_id"] = current_trace_id() if span is not None else None
    # Nội dung này chỉ quan sát được khi transaction commit thành công. Không bịa
    # duration persistence hoặc trả success khi không ghi được kết quả.
    processing.stages["persistence"] = {"status": "succeeded"}
    answer["processing"] = processing.snapshot()
    try:
        with db.get_engine().begin() as connection:
            connection.execute(
                update(messages)
                .where(messages.c.id == message_id)
                .values(
                    status=answer["status"],
                    envelope=answer,
                    query_plan=plan.model_dump(mode="json") if plan else None,
                )
            )
            connection.execute(
                insert(results).values(id=result_id, message_id=message_id, envelope=answer)
            )
    except SQLAlchemyError:
        processing.failed_stage = "persistence"
        processing.stages["persistence"] = {"status": "failed"}
        raise AppError(
            503,
            "PERSISTENCE_UNAVAILABLE",
            "Chưa lưu được kết quả. Hãy đọc lại lịch sử trước khi gửi yêu cầu mới.",
            stage="persistence",
            diagnostics=processing.snapshot(),
        ) from None
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
        pending = (
            connection.execute(
                select(messages).where(messages.c.status == "pending").with_for_update()
            )
            .mappings()
            .all()
        )
        for message in pending:
            answer = empty_answer(
                "execution_error",
                "Lượt hỏi bị gián đoạn. Hãy kiểm tra lịch sử trước khi gửi yêu cầu mới.",
                "interrupted",
            )
            old = message["envelope"] or {}
            if isinstance(old.get("processing"), dict):
                evidence = old["processing"]
                if evidence.get("sql", {}).get("execution_status") == "in_progress":
                    evidence["sql"]["execution_status"] = "unknown"
                evidence.update(failed_stage="interrupted", error_code="REQUEST_INTERRUPTED")
                for detail in evidence.get("stages", {}).values():
                    if detail.get("status") == "in_progress":
                        detail["status"] = "unknown"
                evidence.setdefault("stages", {})["interrupted"] = {"status": "unknown"}
                answer["processing"] = evidence
            answer["error_code"] = "REQUEST_INTERRUPTED"
            connection.execute(
                update(messages)
                .where(messages.c.id == message["id"])
                .values(status="execution_error", envelope=answer)
            )
