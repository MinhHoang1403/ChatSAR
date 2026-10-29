"""Một đường bind/compile/execute SELECT; model không cung cấp SQL hay quyền."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    MetaData,
    Numeric,
    Table,
    Text,
    and_,
    asc,
    desc,
    distinct,
    func,
    or_,
    select,
)
from sqlalchemy.sql import ColumnElement, Select
from sqlalchemy.types import TypeEngine

from app import database as db
from app.errors import AppError
from app.tabular import ColumnReview, typed_value, wire


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


class QueryLiteral(Contract):
    raw_phrase: str = Field(min_length=1, max_length=500)
    value_type: Literal["text", "integer", "numeric", "boolean", "date", "timestamp"]
    candidate_value: str = Field(max_length=500)


class Predicate(Contract):
    operator: Literal[
        "EQ", "NE", "GT", "GTE", "LT", "LTE", "IN", "IS_NULL", "IS_NOT_NULL", "AND", "OR"
    ]
    column_id: str | None = None
    literal: QueryLiteral | None = None
    values: list[QueryLiteral] = Field(default_factory=list, max_length=100)
    children: list[Predicate] = Field(default_factory=list, max_length=100)


class Aggregate(Contract):
    operator: Literal["COUNT_ROWS", "COUNT_NON_NULL", "COUNT_DISTINCT", "SUM", "AVG", "MIN", "MAX"]
    column_id: str | None = None
    output_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,40}$")


class Ordering(Contract):
    field_id: str
    direction: Literal["asc", "desc"] = "asc"


class QueryPlan(Contract):
    task: Literal["SQL", "CLARIFY", "UNSUPPORTED"]
    table_id: str = ""
    source_revision_id: str = ""
    intent: str = ""
    entities: list[str] = Field(default_factory=list, max_length=30)
    metric: str = ""
    population: str = ""
    raw_user_spans: list[str] = Field(
        default_factory=list,
        max_length=100,
        description="Exact substrings covering the entire current question, including qualifiers.",
    )
    coverage: list[str] = Field(
        default_factory=list,
        max_length=100,
        description="Copy raw_user_spans exactly if every span is represented; otherwise CLARIFY.",
    )
    select_columns: list[str] = Field(default_factory=list, max_length=30)
    aggregations: list[Aggregate] = Field(default_factory=list, max_length=20)
    filters: Predicate | None = None
    group_by: list[str] = Field(default_factory=list, max_length=10)
    order_by: list[Ordering] = Field(default_factory=list, max_length=10)
    limit: int = Field(default=100, ge=1, le=500)
    unresolved: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def require_sql_payload(self) -> QueryPlan:
        if self.task == "SQL" and not (
            self.table_id
            and self.source_revision_id
            and self.raw_user_spans
            and self.coverage
            and (self.select_columns or self.aggregations)
        ):
            raise ValueError("SQL proposal missing required catalog or query fields")
        return self


@dataclass
class CompiledQuery:
    statement: Select[Any]
    columns: list[dict[str, Any]]
    filters: list[dict[str, Any]]


def fail(message: str, code: str = "QUERY_UNSUPPORTED") -> AppError:
    return AppError(422, code, message)


def compile_query(
    plan: QueryPlan, revision: dict[str, Any], question: str, previous_question: str = ""
) -> CompiledQuery:
    if plan.task != "SQL" or plan.unresolved:
        raise fail("Cần làm rõ câu hỏi trước khi lấy số liệu.", "QUERY_CLARIFY")
    if plan.table_id != str(revision["dataset_id"]) or plan.source_revision_id != str(
        revision["id"]
    ):
        raise fail("Nguồn dữ liệu không khớp phạm vi được chọn.")
    if (
        revision["status"] != "ready"
        or revision["physical_table"] != "r_" + UUID(str(revision["id"])).hex
    ):
        raise fail("Nguồn dữ liệu chưa sẵn sàng.")
    if not plan.raw_user_spans or any(span not in question for span in plan.raw_user_spans):
        raise fail("Chưa đối chiếu được các phần trong câu hỏi.", "QUERY_CLARIFY")
    if set(plan.coverage) != set(plan.raw_user_spans):
        raise fail("Còn điều kiện trong câu hỏi chưa được đối chiếu.", "QUERY_CLARIFY")
    covered = [False] * len(question)
    for span in plan.raw_user_spans:
        if not span:
            raise fail("Phạm vi câu hỏi chưa hợp lệ.", "QUERY_CLARIFY")
        start = 0
        while (start := question.find(span, start)) >= 0:
            covered[start : start + len(span)] = [True] * len(span)
            start += len(span)
    if any(character.isalnum() and not covered[i] for i, character in enumerate(question)):
        raise fail("Một phần câu hỏi chưa được biểu diễn; vui lòng làm rõ.", "QUERY_CLARIFY")
    reviews = [ColumnReview.model_validate(c) for c in revision["columns"]]
    catalog = {c.id: c for c in reviews}
    types: dict[str, TypeEngine[Any]] = {
        "text": Text(),
        "integer": BigInteger(),
        "numeric": Numeric(asdecimal=True),
        "boolean": Boolean(),
        "date": Date(),
        "timestamp": DateTime(timezone=True),
    }
    table = Table(
        revision["physical_table"],
        MetaData(),
        *(Column(c.id, types[c.data_type]) for c in reviews),
        schema="data",
    )

    def column(column_id: str | None) -> Column[Any]:
        if column_id is None or column_id not in catalog:
            raise fail("Cột không thuộc danh mục dữ liệu đã xác nhận.")
        return table.c[column_id]

    literal_evidence: list[dict[str, Any]] = []

    def literal(value: QueryLiteral, column_id: str) -> Any:
        review = catalog[column_id]
        if value.value_type != review.data_type:
            raise fail("Kiểu giá trị không khớp cột đã xác nhận.", "QUERY_CLARIFY")
        origin = "user_phrase" if value.raw_phrase in question else "verified_context"
        if value.raw_phrase not in question and value.raw_phrase not in previous_question:
            raise fail("Giá trị lọc chưa có căn cứ từ câu hỏi.", "QUERY_CLARIFY")
        try:
            query_review = review.model_copy(
                update={
                    "null_values": [],
                    "date_format": "%Y-%m-%d",
                    "decimal_separator": ".",
                    "nullable": False,
                }
            )
            bound = typed_value(value.candidate_value, query_review, revision["timezone"])
            # Chỉ chấp nhận chuyển kiểu chính xác theo format đã duyệt hoặc ISO.
            # Mốc tháng/thiếu năm chưa có mapping đã duyệt thì hỏi lại, không đoán.
            original_review = review.model_copy(update={"null_values": []})
            try:
                original = typed_value(value.raw_phrase, original_review, revision["timezone"])
            except ValueError:
                if review.data_type != "date":
                    raise
                original = typed_value(value.raw_phrase, query_review, revision["timezone"])
            if original != bound:
                raise ValueError("Literal changed")
        except (ValueError, TypeError, ArithmeticError):
            raise fail(
                "Giá trị hoặc mốc thời gian còn mơ hồ; vui lòng làm rõ.", "QUERY_CLARIFY"
            ) from None
        literal_evidence.append(
            {
                "column_id": column_id,
                "raw_phrase": value.raw_phrase,
                "candidate_value": value.candidate_value,
                "canonical_value": wire(bound),
                "mapping_source": origin,
                "question_span": {
                    "start": (question if origin == "user_phrase" else previous_question).index(
                        value.raw_phrase
                    ),
                    "length": len(value.raw_phrase),
                    "source": origin,
                },
            }
        )
        return bound

    nodes = 0

    def predicate(node: Predicate, depth: int = 0) -> ColumnElement[bool]:
        nonlocal nodes
        nodes += 1
        if nodes > 100 or depth > 8:
            raise fail("Điều kiện truy vấn vượt giới hạn cho phép.")
        if node.operator in ("AND", "OR"):
            if not node.children or node.column_id or node.literal or node.values:
                raise fail("Cấu trúc nhóm điều kiện không hợp lệ.")
            expressions = [predicate(child, depth + 1) for child in node.children]
            return and_(*expressions) if node.operator == "AND" else or_(*expressions)
        target = column(node.column_id)
        if node.children:
            raise fail("Điều kiện đơn không được chứa nhóm con.")
        column_id = str(node.column_id)
        if node.operator in ("IS_NULL", "IS_NOT_NULL"):
            if node.literal or node.values:
                raise fail("Kiểm tra NULL không nhận giá trị thay thế.")
            return target.is_(None) if node.operator == "IS_NULL" else target.is_not(None)
        if node.operator == "IN":
            if node.literal or not node.values:
                raise fail("Danh sách lọc chưa hợp lệ.")
            return target.in_([literal(v, column_id) for v in node.values])
        if not node.literal or node.values:
            raise fail("Điều kiện thiếu giá trị có kiểu.")
        if catalog[column_id].data_type in ("text", "boolean") and node.operator not in (
            "EQ",
            "NE",
        ):
            raise fail("Phép so sánh chưa được hỗ trợ cho kiểu này.")
        value = literal(node.literal, column_id)
        operations = {
            "EQ": target.__eq__,
            "NE": target.__ne__,
            "GT": target.__gt__,
            "GTE": target.__ge__,
            "LT": target.__lt__,
            "LTE": target.__le__,
        }
        return operations[node.operator](value)

    selected: list[Any] = []
    output: list[dict[str, Any]] = []
    order_fields: dict[str, Any] = {}
    if len(set(plan.select_columns)) != len(plan.select_columns) or len(set(plan.group_by)) != len(
        plan.group_by
    ):
        raise fail("Cột truy vấn bị lặp.")
    for column_id in plan.select_columns:
        selected.append(column(column_id))
        order_fields[column_id] = table.c[column_id]
        review = catalog[column_id]
        output.append(
            {"id": column_id, "name": review.name, "type": review.data_type, "unit": review.unit}
        )
    if plan.aggregations and set(plan.select_columns) != set(plan.group_by):
        raise fail("Cột hiển thị phải khớp mức nhóm của phép tổng hợp.")
    if plan.group_by and not plan.aggregations:
        raise fail("Nhóm dữ liệu cần có phép tổng hợp rõ ràng.")
    aliases = set(order_fields)
    names = {
        "COUNT_ROWS": "Số dòng",
        "COUNT_NON_NULL": "Số giá trị không NULL",
        "COUNT_DISTINCT": "Số giá trị khác nhau",
        "SUM": "Tổng",
        "AVG": "Trung bình",
        "MIN": "Nhỏ nhất",
        "MAX": "Lớn nhất",
    }
    for aggregate in plan.aggregations:
        if aggregate.output_id in aliases:
            raise fail("Tên kết quả bị lặp.")
        aliases.add(aggregate.output_id)
        aggregate_review = catalog.get(aggregate.column_id or "")
        expression: ColumnElement[Any]
        if aggregate.operator == "COUNT_ROWS":
            if aggregate.column_id is not None:
                raise fail("COUNT_ROWS không nhận cột.")
            expression = func.count()
        else:
            target = column(aggregate.column_id)
            if (
                aggregate.operator in ("SUM", "AVG")
                and aggregate_review
                and aggregate_review.data_type not in ("numeric", "integer")
            ):
                raise fail("Phép tính cần cột có kiểu số.")
            aggregate_functions: dict[str, Callable[..., Any]] = {
                "COUNT_NON_NULL": func.count,
                "SUM": func.sum,
                "AVG": func.avg,
                "MIN": func.min,
                "MAX": func.max,
            }
            expression = (
                func.count(distinct(target))
                if aggregate.operator == "COUNT_DISTINCT"
                else aggregate_functions[aggregate.operator](target)
            )
        expression = expression.label(aggregate.output_id)
        selected.append(expression)
        order_fields[aggregate.output_id] = expression
        kind = (
            "integer"
            if aggregate.operator.startswith("COUNT")
            else "numeric"
            if aggregate.operator in ("SUM", "AVG")
            else aggregate_review.data_type
            if aggregate_review
            else "numeric"
        )
        output.append(
            {
                "id": aggregate.output_id,
                "name": names[aggregate.operator]
                + (" · " + aggregate_review.name if aggregate_review else ""),
                "type": kind,
                "unit": aggregate_review.unit
                if aggregate_review and not aggregate.operator.startswith("COUNT")
                else None,
            }
        )
    if not selected:
        raise fail("Câu hỏi chưa xác định dữ liệu hoặc phép tính cần lấy.", "QUERY_CLARIFY")
    statement = select(*selected).select_from(table)
    if plan.filters:
        statement = statement.where(predicate(plan.filters))
    if any(
        not entity or not any(e["raw_phrase"] == entity for e in literal_evidence)
        for entity in plan.entities
    ):
        raise fail("Điều kiện đối tượng chưa được đưa vào phép lọc.", "QUERY_CLARIFY")
    if plan.group_by:
        statement = statement.group_by(*(column(c) for c in plan.group_by))
    for order in plan.order_by:
        if order.field_id not in order_fields:
            raise fail("Thứ tự sắp xếp phải tham chiếu cột kết quả hợp lệ.")
        expression = order_fields[order.field_id]
        statement = statement.order_by(
            asc(expression).nulls_last()
            if order.direction == "asc"
            else desc(expression).nulls_last()
        )
    return CompiledQuery(statement.limit(plan.limit), output, literal_evidence)


def execute_query(compiled: CompiledQuery) -> tuple[list[list[Any]], float]:
    started = perf_counter()
    with db.get_reader_engine().connect().execution_options(postgresql_readonly=True) as connection:
        with connection.begin():
            connection.exec_driver_sql("SET LOCAL statement_timeout = '5s'")
            rows = connection.execute(compiled.statement).fetchmany(501)
            if len(rows) > 500:
                raise fail("Kết quả vượt giới hạn cho phép.")
    return [[wire(value) for value in row] for row in rows], (perf_counter() - started) * 1000
