"""Ứng viên offline: hợp đồng phẳng chuyển lossless sang typed plan hiện hữu."""

from typing import Literal

from pydantic import Field

from app.query import Aggregate, Contract, Ordering, Predicate, QueryLiteral, QueryPlan


class Condition(Contract):
    operator: Literal[
        "EQ", "NE", "GT", "GTE", "LT", "LTE", "IN", "IS_NULL", "IS_NOT_NULL", "AND", "OR"
    ]
    column_id: str | None
    literal: QueryLiteral | None
    values: list[QueryLiteral] = Field(max_length=100)
    children: list[int] = Field(max_length=100)


class QueryRequest(Contract):
    task: Literal["SQL", "CLARIFY", "UNSUPPORTED"]
    table_id: str
    source_revision_id: str
    result_shape: Literal["record", "list", "list_all", "scalar", "group", "ranking"]
    required_columns: list[str] = Field(
        max_length=30,
        description="Requested direct projection columns, excluding aggregate inputs.",
    )
    raw_user_spans: list[str] = Field(max_length=100)
    select_columns: list[str] = Field(max_length=30)
    aggregations: list[Aggregate] = Field(max_length=20)
    conditions: list[Condition] = Field(max_length=100)
    group_by: list[str] = Field(max_length=10)
    order_by: list[Ordering] = Field(max_length=10)
    limit: int = Field(ge=1, le=500)
    unresolved: list[str] = Field(max_length=30)

    def to_plan(self, *, identifier_columns: set[str] | None = None) -> QueryPlan:
        nodes: list[Predicate] = []
        depths: list[int] = []
        references: list[int] = [0] * len(self.conditions)
        for index, item in enumerate(self.conditions):
            boolean = item.operator in {"AND", "OR"}
            if boolean:
                if (
                    len(item.children) < 2
                    or len(set(item.children)) != len(item.children)
                    or any(child < 0 or child >= index for child in item.children)
                    or item.column_id is not None
                    or item.literal is not None
                    or item.values
                ):
                    raise ValueError("Invalid Boolean condition")
                for child in item.children:
                    references[child] += 1
                depth = 1 + max(depths[child] for child in item.children)
            else:
                if item.children or item.column_id is None:
                    raise ValueError("Invalid leaf condition")
                if item.operator in {"IS_NULL", "IS_NOT_NULL"}:
                    valid = item.literal is None and not item.values
                elif item.operator == "IN":
                    valid = item.literal is None and bool(item.values)
                else:
                    valid = item.literal is not None and not item.values
                if not valid:
                    raise ValueError("Missing or surplus condition operands")
                depth = 1
            if depth > 8:
                raise ValueError("Condition depth exceeded")
            nodes.append(
                Predicate(
                    operator=item.operator,
                    column_id=item.column_id,
                    literal=item.literal,
                    values=item.values,
                    children=[nodes[child] for child in item.children],
                )
            )
            depths.append(depth)
        if references and references != [1] * (len(references) - 1) + [0]:
            raise ValueError("Conditions must form one tree without unused or shared nodes")
        if self.task == "SQL":
            selected = set(self.select_columns)
            if not set(self.required_columns) <= selected:
                raise ValueError("Requested output columns are missing")
            if self.result_shape in {"record", "list", "list_all"}:
                if self.aggregations or self.group_by or not self.select_columns:
                    raise ValueError("Record/list requires direct projection")
                if (
                    self.result_shape == "record"
                    and identifier_columns
                    and not identifier_columns.intersection(selected)
                ):
                    raise ValueError("Record output lacks its catalog identifier")
            elif self.result_shape == "scalar":
                if not self.aggregations or selected or self.group_by or self.order_by:
                    raise ValueError("Scalar requires aggregates without grouping or ranking")
            elif self.result_shape == "group":
                if not self.aggregations or not self.group_by or selected != set(self.group_by):
                    raise ValueError("Grouped result requires its grouping columns")
            elif not self.order_by:
                raise ValueError("Ranking requires ordering")
        return QueryPlan(
            task=self.task,
            table_id=self.table_id,
            source_revision_id=self.source_revision_id,
            raw_user_spans=self.raw_user_spans,
            coverage=self.raw_user_spans,
            select_columns=self.select_columns,
            aggregations=self.aggregations,
            filters=nodes[-1] if nodes else None,
            group_by=self.group_by,
            order_by=self.order_by,
            limit=self.limit,
            result_mode="top"
            if self.result_shape == "ranking"
            else "all"
            if self.result_shape == "list_all"
            else "bounded",
            unresolved=self.unresolved,
        )
