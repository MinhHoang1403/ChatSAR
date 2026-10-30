"""Một đường bind/compile/execute SELECT; model không cung cấp SQL hay quyền."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from time import perf_counter
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

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
    result_mode: Literal["bounded", "all", "top"] = "bounded"
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
    limit: int = 100
    result_mode: str = "bounded"
    truncated: bool = False
    grounding_required: bool = False
    execution_latency_ms: float | None = None


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

    def literal(
        value: QueryLiteral, column_id: str, period_bound: date | datetime | None = None
    ) -> Any:
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
            # Tháng có đủ năm chỉ nhận cặp [đầu tháng, đầu tháng sau) đã đối chiếu.
            # Không lấy năm hiện tại, năm từ dữ liệu hoặc một mốc model tự chọn.
            original_review = review.model_copy(update={"null_values": []})
            mapped = [
                m
                for m in review.value_mappings
                if m.phrase.casefold() == value.raw_phrase.casefold()
            ]
            if mapped:
                if len(mapped) != 1:
                    raise ValueError("Ambiguous mapping")
                original = typed_value(mapped[0].value, original_review, revision["timezone"])
                origin = "owner_confirmed_mapping"
            elif period_bound is not None:
                original = period_bound
                origin = "explicit_calendar_period"
            else:
                original = None
            try:
                if not mapped and period_bound is None:
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
                "operator": current_operator,
                "question_span": {
                    "start": (
                        question if value.raw_phrase in question else previous_question
                    ).index(value.raw_phrase),
                    "length": len(value.raw_phrase),
                    "source": "user_phrase" if value.raw_phrase in question else "verified_context",
                },
            }
        )
        return bound

    nodes = 0
    current_operator = "EQ"

    def predicate(
        node: Predicate, depth: int = 0, period_bound: date | datetime | None = None
    ) -> ColumnElement[bool]:
        nonlocal nodes, current_operator
        nodes += 1
        if nodes > 100 or depth > 8:
            raise fail("Điều kiện truy vấn vượt giới hạn cho phép.")
        if node.operator in ("AND", "OR"):
            if not node.children or node.column_id or node.literal or node.values:
                raise fail("Cấu trúc nhóm điều kiện không hợp lệ.")
            bounds: dict[int, date | datetime] = {}
            if node.operator == "AND":
                pairs: dict[tuple[str, str], list[tuple[int, Predicate]]] = {}
                for index, child in enumerate(node.children):
                    if child.column_id and child.literal:
                        pairs.setdefault((child.column_id, child.literal.raw_phrase), []).append(
                            (index, child)
                        )
                for (column_id, phrase), items in pairs.items():
                    review = catalog.get(column_id)
                    if (
                        len(items) != 2
                        or {c.operator for _, c in items} != {"GTE", "LT"}
                        or review is None
                    ):
                        continue
                    period = calendar_month(phrase, review.data_type, revision["timezone"])
                    if period is not None:
                        for index, child in items:
                            bounds[index] = period[0 if child.operator == "GTE" else 1]
            expressions = [
                predicate(child, depth + 1, bounds.get(index))
                for index, child in enumerate(node.children)
            ]
            return and_(*expressions) if node.operator == "AND" else or_(*expressions)
        target = column(node.column_id)
        if node.children:
            raise fail("Điều kiện đơn không được chứa nhóm con.")
        column_id = str(node.column_id)
        current_operator = node.operator
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
        value = literal(node.literal, column_id, period_bound)
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
        "COUNT_NON_NULL": "Số giá trị đã có",
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
        if (
            aggregate.operator in ("SUM", "AVG")
            and aggregate_review
            and aggregate_review.aggregation_policy == "non_additive"
        ):
            raise fail(
                "Cột này không cho phép cộng hoặc lấy trung bình theo metadata đã xác nhận.",
                "QUERY_CLARIFY",
            )
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
    validate_structure(plan, revision, question, literal_evidence)
    return CompiledQuery(
        statement.limit(plan.limit + 1),
        output,
        literal_evidence,
        plan.limit,
        plan.result_mode,
        grounding_required="grounding_values" in revision,
    )


def calendar_month(
    phrase: str, kind: str, timezone: str
) -> tuple[date | datetime, date | datetime] | None:
    """Chỉ ngữ pháp tháng/năm tường minh; không đoán phần ngày/năm thiếu."""
    matched = re.fullmatch(
        r"(?:tháng|month)\s+(\d{1,2})\s+(?:năm|year)\s+(\d{4})", phrase, re.IGNORECASE
    )
    if matched is None or kind not in ("date", "timestamp"):
        return None
    month, year = map(int, matched.groups())
    try:
        start = date(year, month, 1)
        end = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
        if kind == "date":
            return start, end
        zone = ZoneInfo(timezone)
        return datetime(year, month, 1, tzinfo=zone), datetime(end.year, end.month, 1, tzinfo=zone)
    except ValueError:
        raise fail("Tháng hoặc năm chưa hợp lệ; vui lòng làm rõ.", "QUERY_CLARIFY") from None


def contains_phrase(question: str, phrase: str) -> bool:
    # Ranh giới từ Unicode, không bỏ dấu hoặc fuzzy match để tự đổi nghĩa.
    return (
        bool(phrase)
        and re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", question, re.IGNORECASE)
        is not None
    )


def mentioned_phrases(question: str, phrases: list[str]) -> set[str]:
    """Cùng một vị trí dùng tên gọi đầy đủ, tránh bắt cả phần khẳng định trong phủ định."""
    matches = [
        (match.start(), match.end(), phrase)
        for phrase in phrases
        if phrase
        for match in re.finditer(
            r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", question, re.IGNORECASE
        )
    ]
    return {
        phrase
        for start, end, phrase in matches
        if not any(a <= start and end <= b and b - a > end - start for a, b, _ in matches)
    }


def validate_structure(
    plan: QueryPlan, revision: dict[str, Any], question: str, evidence: list[dict[str, Any]]
) -> None:
    for item in revision["columns"]:
        review = ColumnReview.model_validate(item)
        for phrase in mentioned_phrases(question, [m.phrase for m in review.value_mappings]):
            if not any(
                e["column_id"] == review.id and e["raw_phrase"].casefold() == phrase.casefold()
                for e in evidence
            ):
                raise fail(
                    "Một tên gọi đã xác nhận chưa được đưa vào điều kiện lọc.", "QUERY_CLARIFY"
                )
    ranking = re.search(r"\btop\s+(\d+)\b", question, re.IGNORECASE)
    if ranking and (
        not plan.order_by or plan.limit != int(ranking[1]) or plan.result_mode != "top"
    ):
        raise fail("Yêu cầu xếp hạng cần thứ tự và số lượng kết quả khớp câu hỏi.", "QUERY_CLARIFY")
    if plan.result_mode == "top" and not plan.order_by:
        raise fail("Cần chọn tiêu chí xếp hạng.", "QUERY_CLARIFY")
    if (
        any(
            contains_phrase(question, phrase)
            for phrase in ("toàn bộ danh sách", "tất cả các dòng", "đầy đủ danh sách")
        )
        and plan.result_mode != "all"
    ):
        raise fail("Yêu cầu danh sách đầy đủ chưa được biểu diễn.", "QUERY_CLARIFY")
    # Giá trị lấy từ DB, không phải danh sách qualifier do model tự khai.
    for column_id, values in revision.get("grounding_values", {}).items():
        for value in mentioned_phrases(question, values):
            if len(value) >= 2 and not any(
                e["column_id"] == column_id and e["canonical_value"] == value for e in evidence
            ):
                raise fail(
                    "Một giá trị được nhắc trong câu hỏi chưa có điều kiện lọc tương ứng.",
                    "QUERY_CLARIFY",
                )


def ground_catalog(revision: dict[str, Any]) -> dict[str, Any]:
    """Chỉ đọc tối đa 21 giá trị/cột TEXT; bảng nhiều giá trị không giả là enum đầy đủ."""
    if (
        revision["status"] != "ready"
        or revision["physical_table"] != "r_" + UUID(str(revision["id"])).hex
    ):
        raise fail("Nguồn dữ liệu chưa sẵn sàng.")
    values: dict[str, list[str]] = {}
    with db.get_reader_engine().connect().execution_options(postgresql_readonly=True) as connection:
        with connection.begin():
            connection.exec_driver_sql("SET LOCAL statement_timeout = '5s'")
            for item in revision["columns"]:
                column = ColumnReview.model_validate(item)
                if column.data_type != "text":
                    continue
                table = Table(
                    revision["physical_table"], MetaData(), Column(column.id, Text()), schema="data"
                )
                found = (
                    connection.execute(select(table.c[column.id]).distinct().limit(21))
                    .scalars()
                    .all()
                )
                if len(found) <= 20:
                    values[column.id] = [
                        v for v in found if isinstance(v, str) and 0 < len(v) <= 120
                    ]
    return {**revision, "grounding_values": values}


def execute_query(
    compiled: CompiledQuery, *, on_execute: Callable[[], None] | None = None
) -> tuple[list[list[Any]], float]:
    started = perf_counter()
    with db.get_reader_engine().connect().execution_options(postgresql_readonly=True) as connection:
        with connection.begin():
            connection.exec_driver_sql("SET LOCAL statement_timeout = '5s'")
            for item in compiled.filters:
                if isinstance(item["canonical_value"], str) and item["operator"] in (
                    "EQ",
                    "NE",
                    "IN",
                ):
                    table = next(iter(compiled.statement.get_final_froms()))
                    target = table.c[item["column_id"]]
                    if compiled.grounding_required and isinstance(target.type, Text):
                        exists = (
                            connection.execute(
                                select(target).where(target == item["canonical_value"]).limit(1)
                            ).first()
                            is not None
                        )
                        item["source_match"] = "exact" if exists else "no_match"
                        # Literal nguyên văn không khớp có thể mô tả tập rỗng hợp lệ.
                        # Không bịa canonical value/mapping hoặc đổi SUM(empty) thành 0.
                        if not exists and item["mapping_source"] == "owner_confirmed_mapping":
                            raise fail("Mapping không còn khớp giá trị nguồn.", "QUERY_CLARIFY")
            if on_execute:
                on_execute()
            execution_started = perf_counter()
            try:
                rows = connection.execute(compiled.statement).fetchmany(501)
            finally:
                compiled.execution_latency_ms = (perf_counter() - execution_started) * 1000
    compiled.truncated = len(rows) > compiled.limit
    return [[wire(value) for value in row] for row in rows[: compiled.limit]], (
        perf_counter() - started
    ) * 1000
