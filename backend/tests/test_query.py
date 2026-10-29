"""Giới hạn compiler và literal; expected được viết độc lập với SQL sinh ra."""

from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from app.errors import AppError
from app.query import QueryPlan, compile_query
from app.tabular import wire

CODE, AMOUNT, DAY = ["c_" + digit * 32 for digit in "abc"]


@pytest.fixture
def revision() -> dict:
    revision_id = uuid4()
    return {
        "id": revision_id,
        "dataset_id": uuid4(),
        "status": "ready",
        "physical_table": "r_" + revision_id.hex,
        "timezone": "Asia/Ho_Chi_Minh",
        "columns": [
            {"id": CODE, "name": "code", "data_type": "text"},
            {"id": AMOUNT, "name": "amount", "data_type": "numeric"},
            {"id": DAY, "name": "day", "data_type": "date"},
        ],
    }


def proposal(revision: dict, question: str = "Tổng", **fields: object) -> QueryPlan:
    return QueryPlan.model_validate(
        {
            "task": "SQL",
            "table_id": str(revision["dataset_id"]),
            "source_revision_id": str(revision["id"]),
            "raw_user_spans": [question],
            "coverage": [question],
            "aggregations": [{"operator": "SUM", "column_id": AMOUNT, "output_id": "total"}],
            **fields,
        }
    )


def leaf(raw: str, candidate: str, column: str = CODE, kind: str = "text") -> dict:
    return {
        "operator": "EQ",
        "column_id": column,
        "literal": {"raw_phrase": raw, "candidate_value": candidate, "value_type": kind},
    }


def test_untrusted_text_is_bound_parameter_and_provenance_kept(revision: dict) -> None:
    value = "0007'; DROP TABLE app.users; --"
    query = compile_query(proposal(revision, value, filters=leaf(value, value)), revision, value)
    compiled = query.statement.compile(dialect=postgresql.dialect())
    assert value not in str(compiled)
    assert value in compiled.params.values()
    assert query.filters[0]["canonical_value"] == value
    assert query.filters[0]["question_span"]["start"] == 0
    assert query.columns[0]["type"] == "numeric"


@pytest.mark.parametrize("raw,candidate", [("0007", "7"), ("quận 3", "3")])
def test_literal_cannot_be_silently_rewritten(revision: dict, raw: str, candidate: str) -> None:
    with pytest.raises(AppError) as error:
        compile_query(proposal(revision, raw, filters=leaf(raw, candidate)), revision, raw)
    assert error.value.code == "QUERY_CLARIFY"


@pytest.mark.parametrize(
    "fields",
    [
        {"table_id": str(uuid4())},
        {"select_columns": ["app.users"], "aggregations": []},
        {"aggregations": [{"operator": "SUM", "column_id": CODE, "output_id": "total"}]},
        {"group_by": [CODE]},
        {"order_by": [{"field_id": "pg_sleep(10)"}]},
        {"filters": {"operator": "IS_NULL", "column_id": "unknown"}},
    ],
)
def test_catalog_and_expression_boundaries(revision: dict, fields: dict) -> None:
    with pytest.raises(AppError):
        compile_query(proposal(revision, **fields), revision, "Tổng")


@pytest.mark.parametrize(
    "fields",
    [{"sql": "SELECT 1"}, {"limit": 501}, {"limit": "1"}, {"coverage": []}, {"table_id": ""}],
)
def test_strict_grammar_rejects_raw_sql_and_bad_caps(revision: dict, fields: dict) -> None:
    with pytest.raises(ValidationError):
        proposal(revision, **fields)


def test_missing_known_qualifier_is_clarification(revision: dict) -> None:
    question = "Tổng tại quận 3"
    for fields in [
        {"raw_user_spans": ["Tổng"], "coverage": ["Tổng"]},
        {"entities": ["quận 3"]},
    ]:
        with pytest.raises(AppError) as error:
            compile_query(proposal(revision, question, **fields), revision, question)
        assert error.value.code == "QUERY_CLARIFY"


@pytest.mark.parametrize("raw,candidate", [("tháng 9", "2026-09-01"), ("2026-09-01", "2026-09-02")])
def test_dates_cannot_be_invented_or_shifted(revision: dict, raw: str, candidate: str) -> None:
    with pytest.raises(AppError) as error:
        compile_query(
            proposal(revision, raw, filters=leaf(raw, candidate, DAY, "date")), revision, raw
        )
    assert error.value.code == "QUERY_CLARIFY"


def test_followup_literal_only_from_verified_previous_question(revision: dict) -> None:
    plan = proposal(revision, "Tổng?", filters=leaf("0007", "0007"), entities=["0007"])
    query = compile_query(plan, revision, "Tổng?", "Lọc 0007")
    assert query.filters[0]["mapping_source"] == "verified_context"
    with pytest.raises(AppError):
        compile_query(plan, revision, "Tổng?")


def test_boolean_tree_depth_and_null_literal_are_bounded(revision: dict) -> None:
    node = {"operator": "IS_NULL", "column_id": AMOUNT}
    for _ in range(10):
        node = {"operator": "AND", "children": [node]}
    with pytest.raises(AppError):
        compile_query(proposal(revision, filters=node), revision, "Tổng")
    with pytest.raises(AppError):
        compile_query(
            proposal(revision, filters={**leaf("NULL", "NULL"), "operator": "IS_NULL"}),
            revision,
            "Tổng",
        )


def test_large_integer_wire_preserves_javascript_precision() -> None:
    assert wire(2**63 - 1) == "9223372036854775807"
    assert wire(42) == 42


def test_approved_mapping_keeps_original_and_canonical(revision: dict) -> None:
    revision["columns"][0]["value_mappings"] = [{"phrase": "đã giao", "value": "DELIVERED"}]
    plan = proposal(revision, "đã giao", filters=leaf("đã giao", "DELIVERED"))
    compiled = compile_query(plan, revision, "đã giao")
    assert compiled.filters[0]["mapping_source"] == "owner_confirmed_mapping"
    assert compiled.filters[0]["canonical_value"] == "DELIVERED"
    with pytest.raises(AppError):
        compile_query(proposal(revision, "đã giao"), revision, "đã giao")
    with pytest.raises(AppError):
        compile_query(
            proposal(revision, "đã giao", filters=leaf("đã giao", "OTHER")), revision, "đã giao"
        )


@pytest.mark.parametrize(
    "question", ["Tổng tại quận 3", "Phí quận 3 là bao nhiêu?", "Cho xem dữ liệu quận 3"]
)
def test_qualifier_found_from_data_cannot_be_covered_by_model_claim(
    revision: dict, question: str
) -> None:
    revision["grounding_values"] = {CODE: ["quận 3", "3"]}
    with pytest.raises(AppError) as error:
        compile_query(proposal(revision, question), revision, question)
    assert error.value.code == "QUERY_CLARIFY"
    compile_query(
        proposal(revision, question, filters=leaf("quận 3", "quận 3")), revision, question
    )


@pytest.mark.parametrize(
    "fields", [{}, {"order_by": [{"field_id": "total"}]}, {"limit": 3, "result_mode": "top"}]
)
def test_top_requires_matching_order_limit_and_mode(revision: dict, fields: dict) -> None:
    with pytest.raises(AppError):
        compile_query(proposal(revision, "top 3", **fields), revision, "top 3")


def test_non_additive_metric_cannot_be_summed(revision: dict) -> None:
    revision["columns"][1]["aggregation_policy"] = "non_additive"
    with pytest.raises(AppError):
        compile_query(proposal(revision), revision, "Tổng")


def test_all_rows_uses_extra_row_probe(revision: dict) -> None:
    compiled = compile_query(proposal(revision, result_mode="all", limit=5), revision, "Tổng")
    assert compiled.statement.compile().params["param_1"] == 6
    assert compiled.limit == 5


def test_mapping_uses_reviewed_date_format_before_iso_binding(revision: dict) -> None:
    revision["columns"][2].update(
        {
            "date_format": "%d/%m/%Y",
            "value_mappings": [{"phrase": "ngày kiểm tra", "value": "01/02/2026"}],
        }
    )
    plan = proposal(
        revision, "ngày kiểm tra", filters=leaf("ngày kiểm tra", "2026-02-01", DAY, "date")
    )
    compiled = compile_query(plan, revision, "ngày kiểm tra")
    assert compiled.filters[0]["canonical_value"] == "2026-02-01"
