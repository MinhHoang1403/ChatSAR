"""Kiểm hợp đồng provider độc lập dữ liệu ngành; không phải model-live."""

import pytest

from app.planning import QueryRequest
from app.providers import response_schema


def request(**changes: object) -> QueryRequest:
    return QueryRequest.model_validate(
        {
            "task": "SQL",
            "table_id": "d",
            "source_revision_id": "r",
            "result_shape": "scalar",
            "required_columns": [],
            "raw_user_spans": ["question"],
            "select_columns": [],
            "aggregations": [{"operator": "MIN", "column_id": "hours", "output_id": "minimum"}],
            "conditions": [],
            "group_by": [],
            "order_by": [],
            "limit": 100,
            "unresolved": [],
            **changes,
        }
    )


def test_refinement_cannot_silently_drop_an_unrelated_filter() -> None:
    old = {
        "operator": "EQ",
        "column_id": "enabled",
        "literal": {"raw_phrase": "false", "value_type": "boolean"},
        "values": [],
        "children": [],
    }
    new = {
        "operator": "EQ",
        "column_id": "color",
        "literal": {"raw_phrase": "blue", "value_type": "text"},
        "values": [],
        "children": [],
    }
    previous = request(conditions=[old]).to_plan()
    with pytest.raises(ValueError, match="omitted"):
        request(context_scope="refine", conditions=[new]).to_plan(verified_plan=previous)
    complete = request(
        context_scope="refine",
        conditions=[
            old,
            new,
            {
                "operator": "AND",
                "column_id": None,
                "literal": None,
                "values": [],
                "children": [0, 1],
            },
        ],
    )
    assert complete.to_plan(verified_plan=previous).filters.operator == "AND"
    replacement = {**old, "literal": {"raw_phrase": "true", "value_type": "boolean"}}
    assert (
        request(context_scope="refine", conditions=[replacement])
        .to_plan(verified_plan=previous)
        .filters.literal.raw_phrase
        == "true"
    )
    for scope in ("independent", "reset"):
        assert (
            request(context_scope=scope, conditions=[new])
            .to_plan(verified_plan=previous)
            .filters.column_id
            == "color"
        )
    with pytest.raises(ValueError, match="verified context"):
        complete.to_plan()
    with pytest.raises(ValueError, match="same source"):
        complete.to_plan(verified_plan=previous.model_copy(update={"source_revision_id": "other"}))


@pytest.mark.parametrize("column", ["hours", "weight", "temperature"])
def test_scalar_min_is_not_a_ranking(column: str) -> None:
    plan = request(
        aggregations=[{"operator": "MIN", "column_id": column, "output_id": "minimum"}]
    ).to_plan()
    assert plan.result_mode == "bounded" and not plan.order_by


@pytest.mark.parametrize(
    "identifier,value", [("shipment", "fee"), ("asset", "hours"), ("book", "pages")]
)
def test_lookup_preserves_identifier_and_requested_value(identifier: str, value: str) -> None:
    data = dict(
        result_shape="record",
        required_columns=[identifier, value],
        select_columns=[identifier, value],
        aggregations=[],
    )
    assert request(**data).to_plan().select_columns == [identifier, value]
    with pytest.raises(ValueError, match="missing"):
        request(**{**data, "select_columns": [value]}).to_plan()
    with pytest.raises(ValueError, match="identifier"):
        request(**{**data, "required_columns": [value], "select_columns": [value]}).to_plan(
            identifier_columns={identifier}
        )
    with pytest.raises(ValueError, match="projection"):
        request(
            **{
                **data,
                "aggregations": [{"operator": "SUM", "column_id": value, "output_id": "total"}],
            }
        ).to_plan()


def leaf(column: str = "time") -> dict:
    return {
        "operator": "GTE",
        "column_id": column,
        "literal": {
            "raw_phrase": "2026-01-01",
            "value_type": "date",
            "candidate_value": "2026-01-01",
        },
        "values": [],
        "children": [],
    }


def test_time_and_multiple_metrics_are_preserved_without_inference() -> None:
    end = {
        **leaf(),
        "operator": "LT",
        "literal": {
            "raw_phrase": "2026-02-01",
            "value_type": "date",
            "candidate_value": "2026-02-01",
        },
    }
    plan = request(
        conditions=[
            leaf(),
            end,
            {
                "operator": "AND",
                "column_id": None,
                "literal": None,
                "values": [],
                "children": [0, 1],
            },
        ],
        aggregations=[
            {"operator": "COUNT_ROWS", "column_id": None, "output_id": "count"},
            {"operator": "SUM", "column_id": "amount", "output_id": "total"},
        ],
    ).to_plan()
    assert plan.filters and len(plan.filters.children) == 2
    assert [a.operator for a in plan.aggregations] == ["COUNT_ROWS", "SUM"]


@pytest.mark.parametrize(
    "kind,phrase", [("date", "tháng 2 năm 2024"), ("timestamp", "month 12 year 2026")]
)
def test_calendar_membership_lowers_to_existing_half_open_pair(kind: str, phrase: str) -> None:
    item = {**leaf(), "operator": "IN_MONTH", "literal": {"raw_phrase": phrase, "value_type": kind}}
    plan = request(conditions=[item]).to_plan()
    assert plan.filters and plan.filters.operator == "AND"
    assert [c.operator for c in plan.filters.children] == ["GTE", "LT"]
    assert all(
        c.literal.raw_phrase == phrase and c.literal.candidate_value is None
        for c in plan.filters.children
    )
    assert all(c.column_id == "time" for c in plan.filters.children)


@pytest.mark.parametrize(
    "conditions",
    [
        [{"operator": "AND", "column_id": None, "literal": None, "values": [], "children": []}],
        [leaf(), leaf()],
        [
            leaf(),
            {
                "operator": "OR",
                "column_id": None,
                "literal": None,
                "values": [],
                "children": [0, 0],
            },
        ],
        [{**leaf(), "children": [0]}],
        [{**leaf(), "literal": None}],
    ],
)
def test_incomplete_or_non_tree_filters_are_rejected(conditions: list) -> None:
    with pytest.raises(ValueError):
        request(conditions=conditions).to_plan()


def test_provider_schema_is_non_recursive_and_catalog_bound() -> None:
    schema = response_schema(
        QueryRequest, {"id": "r", "dataset_id": "d", "columns": [{"id": "c"}]}, "question"
    )
    assert "Predicate" not in schema["$defs"]
    assert "filters" not in schema["properties"] and "result_mode" not in schema["properties"]
    assert schema["properties"]["required_columns"]["items"]["enum"] == ["c"]
    assert schema["$defs"]["Condition"]["properties"]["children"]["items"]["type"] == "integer"
    assert set(schema["$defs"]["QueryLiteral"]["properties"]) == {"raw_phrase", "value_type"}


def test_missing_conversion_context_remains_clarify_not_fake_sql() -> None:
    plan = request(task="CLARIFY", aggregations=[], unresolved=["Missing exchange rate"]).to_plan()
    assert plan.task == "CLARIFY" and not plan.aggregations


def test_full_list_keeps_all_mode_for_existing_truncation_guard() -> None:
    plan = request(result_shape="list_all", select_columns=["code"], aggregations=[]).to_plan()
    assert plan.result_mode == "all"


@pytest.mark.parametrize("identifier,value", [("serial", "cost"), ("accession", "days")])
@pytest.mark.parametrize("shape", ["record", "list", "list_all"])
def test_direct_output_has_catalog_identifier_order_only_when_order_is_absent(
    identifier: str, value: str, shape: str
) -> None:
    data = dict(result_shape=shape, select_columns=[identifier, value], aggregations=[])
    plan = request(**data).to_plan(identifier_columns={identifier})
    assert [(o.field_id, o.direction) for o in plan.order_by] == [(identifier, "asc")]
    explicit = request(**data, order_by=[{"field_id": value, "direction": "desc"}]).to_plan(
        identifier_columns={identifier}
    )
    assert [(o.field_id, o.direction) for o in explicit.order_by] == [(value, "desc")]
    assert not request(**data).to_plan(identifier_columns=set()).order_by
    if shape != "record":
        assert not request(**data).to_plan(identifier_columns={"unselected"}).order_by


@pytest.mark.parametrize("identifier,value", [("serial", "cost"), ("reference", "weight")])
def test_record_keeps_lookup_column_even_without_catalog_role(identifier: str, value: str) -> None:
    condition = {**leaf(identifier), "operator": "EQ"}
    with pytest.raises(ValueError, match="lookup column"):
        request(
            result_shape="record",
            select_columns=[value],
            required_columns=[value],
            aggregations=[],
            conditions=[condition],
        ).to_plan()
    plan = request(
        result_shape="record",
        select_columns=[identifier, value],
        required_columns=[identifier, value],
        aggregations=[],
        conditions=[condition],
    ).to_plan()
    assert plan.select_columns == [identifier, value]
