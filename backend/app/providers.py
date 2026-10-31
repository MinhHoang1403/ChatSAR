"""Một provider mỗi lượt; request/chi phí được giữ hạn mức trong PostgreSQL."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from time import perf_counter
from typing import Any, Generic, Literal, TypeVar
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter
from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError
from sqlalchemy import and_, func, insert, or_, select, update

from app import database as db
from app.auth import PrincipalDependency
from app.config import get_settings
from app.errors import AppError
from app.observability import annotate, observation
from app.planning import REQUEST_INSTRUCTIONS, QueryRequest
from app.query import QueryPlan, explicit_text_mentions, mentioned_phrases
from app.schema import provider_grants, provider_usage, provider_usage_reviews

Provider = Literal["gemini", "knowledge"]
INPUT_USD_PER_MILLION = Decimal("0.30")
OUTPUT_USD_PER_MILLION = Decimal("2.50")
MAX_OUTPUT_TOKENS = 4096
REQUEST_TIMEOUT_SECONDS = 60
FALLBACK_START_LIMIT_SECONDS = 20
router = APIRouter(prefix="/api")

INSTRUCTIONS = REQUEST_INSTRUCTIONS


Output = TypeVar("Output", bound=BaseModel)


@dataclass
class ModelReply(Generic[Output]):
    plan: Output
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: float
    request_id: str | None


Proposal = ModelReply[QueryPlan]


class ProviderError(AppError):
    def __init__(
        self,
        code: str,
        message: str,
        upstream_status: int | None = None,
        *,
        stage: str = "provider_preparation",
        provider_name: str | None = None,
        model: str | None = None,
        latency_ms: float | None = None,
    ) -> None:
        super().__init__(503, code, message, stage=stage)
        self.upstream_status = upstream_status
        self.provider_name = provider_name
        self.model = model
        self.latency_ms = latency_ms


def provider_error(code: str, message: str) -> AppError:
    return ProviderError(code, message)


def request_client(
    transport: httpx.BaseTransport | None = None, *, call_id: Any = None
) -> httpx.Client:
    sent = False
    last_status: int | None = None

    def remember_response(response: httpx.Response) -> None:
        nonlocal last_status
        last_status = response.status_code
        if call_id is not None:
            with db.get_engine().begin() as connection:
                connection.execute(
                    update(provider_usage)
                    .where(provider_usage.c.id == call_id)
                    .values(http_status=response.status_code)
                )

    def enforce_single_request(request: httpx.Request) -> None:
        nonlocal sent
        # SDK có thể đổi attempts=0 thành 1 rồi hiểu là một lần retry.
        # Chặn trước transport để một reservation chỉ phát tối đa một HTTP request.
        if sent:
            raise ProviderError(
                "PROVIDER_RETRY_BLOCKED", "Đã chặn tự gọi lại mô hình.", last_status
            )
        sent = True
        if call_id is not None:
            # Ghi trước transport: nếu process chết thì tính bảo thủ là có dispatch.
            with db.get_engine().begin() as connection:
                changed = connection.execute(
                    update(provider_usage)
                    .where(provider_usage.c.id == call_id, provider_usage.c.dispatch_count == 0)
                    .values(dispatch_count=1)
                ).rowcount
                if changed != 1:
                    raise provider_error(
                        "PROVIDER_RETRY_BLOCKED", "Không thể xác nhận lượt gửi duy nhất."
                    )

    options: dict[str, Any] = {
        "timeout": REQUEST_TIMEOUT_SECONDS,
        "follow_redirects": False,
        "event_hooks": {"request": [enforce_single_request], "response": [remember_response]},
    }
    if transport is not None:
        options["transport"] = transport
    return httpx.Client(**options)


def reserve_call(provider: Provider, model: str, reserve: Decimal) -> Any:
    settings = get_settings()
    if not settings.generation_allowed:
        raise provider_error("CALLS_NOT_ALLOWED", "Chưa có hạn mức gọi mô hình cho yêu cầu này.")
    with db.get_engine().begin() as connection:
        connection.execute(select(func.pg_advisory_xact_lock(193167598)))
        total = connection.execute(select(func.count()).select_from(provider_usage)).scalar_one()
        count = connection.execute(
            select(func.count())
            .select_from(provider_usage)
            .where(provider_usage.c.provider == provider)
        ).scalar_one()
        provider_cap = (
            settings.gemini_max_requests
            if provider == "gemini"
            else settings.knowledge_max_requests
        )
        if total >= settings.cloud_max_requests or count >= provider_cap:
            raise provider_error("CALL_LIMIT_REACHED", "Đã đạt hạn mức kiểm thử mô hình được cấp.")
        spent = connection.execute(
            select(
                func.coalesce(
                    func.sum(
                        func.coalesce(
                            provider_usage.c.estimated_cost_usd, provider_usage.c.reserved_cost_usd
                        )
                    ),
                    0,
                )
            )
        ).scalar_one()
        if provider == "gemini" and (
            settings.cloud_budget_usd <= 0 or spent + reserve > settings.cloud_budget_usd
        ):
            raise provider_error("BUDGET_REACHED", "Chưa đủ ngân sách đã cấp để gọi mô hình.")
        grant_id = None
        if settings.cloud_grant_id:
            try:
                grant_id = UUID(settings.cloud_grant_id)
            except ValueError:
                raise provider_error("GRANT_INVALID", "Hạn mức tác vụ chưa hợp lệ.") from None
            grant = (
                connection.execute(select(provider_grants).where(provider_grants.c.id == grant_id))
                .mappings()
                .one_or_none()
            )
            if grant is None or grant["provider"] != provider:
                raise provider_error("GRANT_INVALID", "Mô hình không thuộc quyền tác vụ đã cấp.")
            used, reserved = connection.execute(
                select(
                    func.count(),
                    func.coalesce(func.sum(provider_usage.c.reserved_cost_usd), 0),
                ).where(provider_usage.c.grant_id == grant_id)
            ).one()
            # Audit admin phải khớp đúng lượt, grant và snapshot bất biến.
            # Review chỉ hạch toán toàn reserve; không suy chi phí thật bằng 0.
            review = provider_usage_reviews.c
            reviewed = (
                select(review.usage_id)
                .where(
                    review.usage_id == provider_usage.c.id,
                    review.policy == "retain_full_reserve",
                    review.accounted_reserve_usd == provider_usage.c.reserved_cost_usd,
                    review.usage_snapshot == func.to_jsonb(provider_usage.table_valued()),
                    review.usage_snapshot["status"].as_string() == provider_usage.c.status,
                    review.usage_snapshot["error_code"].as_string() == provider_usage.c.error_code,
                    review.usage_snapshot["model"].as_string() == provider_usage.c.model,
                    review.usage_snapshot["dispatch_count"].as_integer() == 1,
                    or_(
                        and_(
                            review.evidence["http_status"].as_integer() == 400,
                            provider_usage.c.error_code == "PROVIDER_SCHEMA",
                        ),
                        and_(
                            review.evidence["http_status"].as_integer() == 503,
                            provider_usage.c.http_status == 503,
                            review.usage_snapshot["http_status"].as_integer() == 503,
                            provider_usage.c.error_code == "PROVIDER_TEMPORARY",
                            review.evidence["source"].as_string() == "httpx_response_hook",
                            review.evidence["usage"].as_string() == "UNKNOWN",
                            review.evidence["billing"].as_string() == "NOT_VERIFIED",
                        ),
                    ),
                    provider_usage.c.provider == "gemini",
                    provider_usage.c.status == "error",
                    provider_usage.c.reserved_cost_usd > 0,
                )
                .exists()
            )
            unknown = connection.execute(
                select(func.count()).where(
                    provider_usage.c.grant_id == grant_id,
                    provider_usage.c.dispatch_count == 1,
                    provider_usage.c.estimated_cost_usd.is_(None),
                    ~reviewed,
                )
            ).scalar_one()
            if unknown:
                raise provider_error(
                    "USAGE_UNKNOWN", "Lượt trước chưa xác định chi phí; dừng kiểm thử live."
                )
            if used >= grant["max_requests"]:
                raise provider_error("GRANT_LIMIT_REACHED", "Đã đạt số lượt của tác vụ được cấp.")
            if reserved + reserve > grant["budget_usd"]:
                raise provider_error(
                    "GRANT_BUDGET_REACHED", "Đã đạt ngân sách dự phòng của tác vụ."
                )
            recent = connection.execute(
                select(
                    provider_usage.c.http_status,
                    provider_usage.c.created_at,
                    provider_usage.c.latency_ms,
                )
                .where(provider_usage.c.grant_id == grant_id, provider_usage.c.dispatch_count == 1)
                .order_by(provider_usage.c.created_at.desc(), provider_usage.c.id.desc())
                .limit(2)
            ).all()
            if recent and recent[0].http_status in (429, 500, 503):
                # Không tự retry: lần gửi có chủ đích tiếp theo vẫn phải đợi.
                seconds = (
                    300 if len(recent) == 2 and all(r.http_status == 503 for r in recent) else 60
                )
                now = connection.execute(select(func.clock_timestamp())).scalar_one()
                completed_at = recent[0].created_at + timedelta(
                    milliseconds=recent[0].latency_ms or 0
                )
                if (now - completed_at).total_seconds() < seconds:
                    raise provider_error(
                        "PROVIDER_COOLDOWN",
                        "Mô hình đang quá tải. Vui lòng đợi rồi gửi yêu cầu mới.",
                    )
        request_id = uuid4()
        connection.execute(
            insert(provider_usage).values(
                id=request_id,
                provider=provider,
                model=model,
                status="reserved",
                reserved_cost_usd=reserve,
                grant_id=grant_id,
                dispatch_count=0,
            )
        )
    return request_id


def finish_call(
    call_id: Any,
    status: str,
    latency_ms: float,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    thought_tokens: int | None = None,
    cost: Decimal | None = None,
    error: str | None = None,
    http_status: int | None = None,
) -> None:
    with db.get_engine().begin() as connection:
        values: dict[str, Any] = {
            "status": status,
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "thought_tokens": thought_tokens,
            "estimated_cost_usd": cost,
            "error_code": error,
        }
        if http_status is not None:
            values["http_status"] = http_status
        connection.execute(
            update(provider_usage).where(provider_usage.c.id == call_id).values(**values)
        )


def integer_or_none(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def response_schema(
    contract: type[BaseModel] = QueryPlan,
    revision: dict[str, Any] | None = None,
    question: str | None = None,
) -> dict[str, Any]:
    schema = contract.model_json_schema()
    if contract in (QueryPlan, QueryRequest):
        for key in ("intent", "entities", "metric", "population", "coverage"):
            schema["properties"].pop(key, None)
        if question:
            # Server biết nguyên văn yêu cầu; không yêu cầu model tự chép các đoạn rời
            # rồi từ chối nhầm vì thiếu từ hỏi. Guard coverage/literal vẫn giữ nguyên.
            schema["properties"]["raw_user_spans"]["items"] = {"type": "string", "enum": [question]}
        if revision and revision["columns"]:
            # Ràng buộc bằng catalog đã kiểm quyền, không cho tên cột thay mã nội bộ.
            identifiers = [column["id"] for column in revision["columns"]]
            for field in ("select_columns", "group_by", "required_columns"):
                if field not in schema["properties"]:
                    continue
                schema["properties"][field]["items"] = {"type": "string", "enum": identifiers}
            for definition in ("Aggregate", "Predicate" if contract is QueryPlan else "Condition"):
                schema["$defs"][definition]["properties"]["column_id"] = {
                    "anyOf": [{"type": "string", "enum": identifiers}, {"type": "null"}]
                }
            schema["properties"]["table_id"]["enum"] = [str(revision["dataset_id"])]
            schema["properties"]["source_revision_id"]["enum"] = [str(revision["id"])]

    def simplify(node: Any) -> None:
        if isinstance(node, dict):
            # maxItems lồng trong cây đệ quy làm grammar provider bùng nổ trạng thái.
            # Chỉ bỏ giới hạn ở bước constrained decoding; Pydantic/server vẫn giữ cap.
            node.pop("maxItems", None)
            node.pop("default", None)
            if node.get("type") == "object" and "properties" in node:
                node["required"] = list(node["properties"])
            for child in node.values():
                simplify(child)
        elif isinstance(node, list):
            for child in node:
                simplify(child)

    simplify(schema)
    return schema


def query_payload(
    question: str,
    revision: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    catalog = {
        "table_id": str(revision["dataset_id"]),
        "source_revision_id": str(revision["id"]),
        "timezone": revision["timezone"],
        "grain": revision["grain"],
        "description": revision.get("description", ""),
        "grounding_values": revision.get("grounding_values", {}),
        "columns": [
            {
                k: c.get(k)
                for k in (
                    "id",
                    "name",
                    "data_type",
                    "nullable",
                    "unit",
                    "description",
                    "aliases",
                    "role",
                    "value_mappings",
                    "aggregation_policy",
                    "primary_key",
                    "date_format",
                    "decimal_separator",
                )
            }
            for c in revision["columns"]
        ],
    }
    return {
        "instructions": INSTRUCTIONS,
        "catalog": catalog,
        "question": question,
        "explicit_text_mentions": explicit_text_mentions(question, revision["columns"]),
        "current_value_mentions": {
            column_id: sorted(mentioned_phrases(question, values))
            for column_id, values in revision.get("grounding_values", {}).items()
            if mentioned_phrases(question, values)
        },
        "verified_context": context,
    }


def generate_proposal(
    question: str,
    revision: dict[str, Any],
    provider: Provider,
    context: dict[str, Any] | None = None,
) -> Proposal:
    reply = generate_structured(
        query_payload(question, revision, context), revision, provider, QueryRequest
    )
    identifiers = {
        column["id"]
        for column in revision["columns"]
        if column.get("primary_key") or column.get("role") == "identifier"
    }
    try:
        plan = reply.plan.to_plan(identifier_columns=identifiers)
    except ValueError:
        raise ProviderError(
            "QUERY_CLARIFY",
            "Cần làm rõ đầu ra hoặc điều kiện truy vấn.",
            stage="semantic_validation",
            provider_name=reply.provider,
            model=reply.model,
            latency_ms=reply.latency_ms,
        ) from None
    return Proposal(
        plan,
        reply.provider,
        reply.model,
        reply.input_tokens,
        reply.output_tokens,
        reply.latency_ms,
        reply.request_id,
    )


def generate_structured(
    payload: dict[str, Any],
    revision: dict[str, Any],
    provider: Provider,
    contract: type[Output],
) -> ModelReply[Output]:
    settings = get_settings()
    if revision["data_classification"] != "synthetic" and provider not in revision.get(
        "sharing_providers", []
    ):
        raise provider_error(
            "DATA_PERMISSION_REQUIRED", "Dữ liệu riêng tư chưa được phép gửi tới mô hình."
        )
    enabled = settings.gemini_enabled if provider == "gemini" else settings.knowledge_enabled
    if not enabled:
        raise provider_error("PROVIDER_DISABLED", "Mô hình đã chọn chưa được bật trong cấu hình.")
    model = settings.gemini_model if provider == "gemini" else settings.knowledge_model
    if (provider == "gemini" and model != "gemini-3.5-flash-lite") or (
        provider == "knowledge" and model != "knowledge"
    ):
        raise provider_error("MODEL_NOT_APPROVED", "Model chưa khớp cấu hình được phê duyệt.")
    if provider == "gemini" and not settings.gemini_api_key.get_secret_value():
        raise provider_error("PROVIDER_NOT_CONFIGURED", "Chưa hoàn tất cấu hình mô hình.")
    schema = response_schema(contract, revision, payload.get("question"))
    prompt = json.dumps(
        {**payload, **({"response_contract": schema} if provider == "knowledge" else {})},
        ensure_ascii=False,
    )
    size = len((prompt + json.dumps(schema)).encode())
    if size > 30000:
        raise provider_error("PROMPT_LIMIT", "Ngữ cảnh quá lớn cho phạm vi kiểm thử hiện tại.")
    # Dự trữ theo byte đầu vào và cap output; không bật tools, caching hay tự nối tiếp.
    reserve = (
        (
            Decimal(size + 2000) * INPUT_USD_PER_MILLION
            + Decimal(MAX_OUTPUT_TOKENS) * OUTPUT_USD_PER_MILLION
        )
        / Decimal(1000000)
        if provider == "gemini"
        else Decimal(0)
    )
    call_id = reserve_call(provider, model, reserve)
    started = perf_counter()
    input_tokens = output_tokens = thought_tokens = None
    request_id = None
    text: Any = None
    error_stage = "provider_call"
    response_status: int | None = None
    with observation("provider_proposal", provider=provider, model=model) as span:
        try:
            if provider == "gemini":
                with (
                    request_client(call_id=call_id) as http_client,
                    genai.Client(
                        api_key=settings.gemini_api_key.get_secret_value(),
                        http_options=types.HttpOptions(
                            timeout=REQUEST_TIMEOUT_SECONDS * 1000,
                            retry_options=types.HttpRetryOptions(attempts=0),
                            httpx_client=http_client,
                        ),
                    ) as client,
                ):
                    response: Any = client.interactions.create(
                        model=model,
                        input=prompt,
                        response_format={
                            "type": "text",
                            "mime_type": "application/json",
                            "schema": schema,
                        },
                        generation_config={"max_output_tokens": MAX_OUTPUT_TOKENS},
                        store=False,
                        stream=False,
                        automatic_continuation=False,
                        timeout=REQUEST_TIMEOUT_SECONDS,
                    )
                error_stage = "proposal_parse"
                text = response.output_text
                usage = getattr(response, "usage", None)
                if usage:
                    input_tokens = integer_or_none(usage.total_input_tokens)
                    output_tokens = integer_or_none(usage.total_output_tokens)
                    thought_tokens = integer_or_none(usage.total_thought_tokens)
                request_id = getattr(response, "id", None)
            else:
                # Endpoint Knowledge không nhận Authorization hoặc API key giả.
                with request_client(call_id=call_id) as client:
                    response_http = client.post(
                        settings.knowledge_base_url.rstrip("/") + "/chat/completions",
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": MAX_OUTPUT_TOKENS,
                            "temperature": 0,
                            "response_format": {
                                "type": "json_schema",
                                "json_schema": {
                                    "name": "query_plan",
                                    "strict": True,
                                    "schema": schema,
                                },
                            },
                        },
                    )
                    response_status = response_http.status_code
                    response_http.raise_for_status()
                    error_stage = "proposal_parse"
                    body = response_http.json()
                text = body["choices"][0]["message"]["content"]
                usage = body.get("usage") or {}
                input_tokens = integer_or_none(usage.get("prompt_tokens"))
                output_tokens = integer_or_none(usage.get("completion_tokens"))
                request_id = body.get("id")
            error_stage = "proposal_parse"
            if not isinstance(text, str) or len(text.encode()) > 65536:
                raise ValueError("Invalid provider output")
            payload = json.loads(text)
            if contract is QueryPlan and isinstance(payload, dict) and "coverage" not in payload:
                # Tương thích lịch sử nội bộ; không coi sao chép này là kiểm chứng ngữ nghĩa.
                payload["coverage"] = payload.get("raw_user_spans", [])
            plan = contract.model_validate(payload)
            latency = (perf_counter() - started) * 1000
            cost = None
            if provider == "gemini" and input_tokens is not None and output_tokens is not None:
                cost = (
                    Decimal(input_tokens) * INPUT_USD_PER_MILLION
                    + Decimal(output_tokens + (thought_tokens or 0)) * OUTPUT_USD_PER_MILLION
                ) / Decimal(1000000)
            finish_call(
                call_id,
                "success",
                latency,
                input_tokens,
                output_tokens,
                thought_tokens,
                cost,
            )
            annotate(
                span,
                output={"status": "proposal_received", "contract": contract.__name__},
                metadata={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "latency_ms": latency,
                    "request_id": request_id,
                },
            )
            return ModelReply(
                plan, provider, model, input_tokens, output_tokens, latency, request_id
            )
        except Exception as error:
            status = (
                getattr(error, "upstream_status", None)
                or getattr(error, "status_code", None)
                or getattr(error, "code", None)
            )
            if isinstance(error, httpx.HTTPStatusError):
                status = error.response.status_code
            code = (
                error.code
                if isinstance(error, AppError) and error.code != "PROVIDER_RETRY_BLOCKED"
                else "PROVIDER_TEMPORARY"
                if status == 503
                else "PROVIDER_FORBIDDEN"
                if status == 403
                else "PROVIDER_TIMEOUT"
                if isinstance(error, (httpx.TimeoutException, TimeoutError))
                or type(error).__name__ == "APITimeoutError"
                else "PROVIDER_AUTH"
                if status == 401
                else "PROVIDER_INTERNAL"
                if status == 500
                else "PROVIDER_DEADLINE"
                if status == 504
                else "PROVIDER_RATE_LIMIT"
                if status == 429
                else "PROVIDER_NETWORK"
                if isinstance(error, httpx.TransportError)
                else "PROVIDER_SCHEMA"
                if isinstance(error, (ValidationError, ValueError, KeyError, TypeError))
                or status == 400
                else "PROVIDER_UNAVAILABLE"
            )
            latency = (perf_counter() - started) * 1000
            # Usage có thể đã nhận trước lỗi JSON/Pydantic; giữ estimate có căn cứ
            # để không biến lỗi parse thành một khoản chi phí không rõ giả tạo.
            cost = None
            if provider == "gemini" and input_tokens is not None and output_tokens is not None:
                cost = (
                    Decimal(input_tokens) * INPUT_USD_PER_MILLION
                    + Decimal(output_tokens + (thought_tokens or 0)) * OUTPUT_USD_PER_MILLION
                ) / Decimal(1000000)
            finish_call(
                call_id,
                "error",
                latency,
                input_tokens,
                output_tokens,
                thought_tokens,
                cost=cost,
                error=code,
                # Chỉ response hook/direct HTTP mới chứng minh đã nhận HTTP.
                # Exception SDK có status nhưng không có response không đủ để review.
                http_status=response_status,
            )
            annotate(
                span,
                output={"status": code},
                level="WARNING",
                metadata={
                    "http_status": status if isinstance(status, int) else None,
                    "failure_type": type(error).__name__,
                    "schema_complexity": any(
                        term in str(error).lower()
                        for term in (
                            "too many states",
                            "too much branching",
                            "constraint",
                            "complexity",
                        )
                    ),
                    "output_characters": len(text) if isinstance(text, str) else None,
                    "missing_sql_fields": missing_sql_fields(text),
                    "validation_errors": [
                        {
                            "path": ".".join(
                                str(part)
                                if part
                                in (
                                    "model",
                                    "input",
                                    "response_format",
                                    "generation_config",
                                    "store",
                                    "steps",
                                    "outputs",
                                    "task",
                                    "usage",
                                    "aggregations",
                                    "column_id",
                                    "table_id",
                                    "source_revision_id",
                                    "coverage",
                                    "raw_user_spans",
                                )
                                or isinstance(part, int)
                                else "field"
                                for part in item["loc"]
                            ),
                            "type": item["type"],
                        }
                        for item in error.errors(include_input=False, include_context=False)[:8]
                    ]
                    if isinstance(error, ValidationError)
                    else None,
                },
            )
            raise ProviderError(
                code,
                "Mô hình đang quá tải. Vui lòng đợi rồi gửi yêu cầu mới."
                if code == "PROVIDER_TEMPORARY"
                else "Mô hình chưa xử lý được yêu cầu. "
                "Vui lòng kiểm tra trạng thái kết nối hoặc cấu hình.",
                upstream_status=status if isinstance(status, int) else None,
                stage=error_stage,
                provider_name=provider,
                model=model,
                latency_ms=latency,
            ) from None


def knowledge_available() -> bool:
    """Không probe mạng: 403 hoặc chưa có bằng chứng truy cập thì không tự fallback."""
    if not get_settings().knowledge_enabled:
        return False
    with db.get_engine().connect() as connection:
        last = connection.execute(
            select(provider_usage.c.status)
            .where(provider_usage.c.provider == "knowledge")
            .order_by(provider_usage.c.created_at.desc(), provider_usage.c.id.desc())
            .limit(1)
        ).scalar_one_or_none()
    return last == "success"


def can_fallback(
    error: AppError,
    revision: dict[str, Any],
    provider: Provider,
    opted_in: bool,
    elapsed_seconds: float = 0,
) -> bool:
    return (
        opted_in
        and elapsed_seconds <= FALLBACK_START_LIMIT_SECONDS
        and provider == "gemini"
        and error.code in ("PROVIDER_RATE_LIMIT", "PROVIDER_TEMPORARY")
        and (
            revision["data_classification"] == "synthetic"
            or "knowledge" in revision.get("sharing_providers", [])
        )
        and knowledge_available()
    )


@router.get("/providers")
def provider_status(_principal: PrincipalDependency) -> dict[str, Any]:
    settings = get_settings()
    available = knowledge_available()
    return {
        "default": "gemini",
        "gemini_enabled": settings.gemini_enabled,
        "knowledge_enabled": settings.knowledge_enabled,
        "knowledge_fallback_available": available,
        "knowledge_status": "previously_reachable" if available else "not_confirmed_or_unavailable",
    }


def missing_sql_fields(text: Any) -> list[str]:
    try:
        value = json.loads(text) if isinstance(text, str) else None
    except (ValueError, RecursionError):
        return []
    if not isinstance(value, dict) or value.get("task") != "SQL":
        return []
    missing = [
        key
        for key in ("table_id", "source_revision_id", "raw_user_spans", "coverage")
        if not value.get(key)
    ]
    if not value.get("select_columns") and not value.get("aggregations"):
        missing.append("output_selection")
    return missing
