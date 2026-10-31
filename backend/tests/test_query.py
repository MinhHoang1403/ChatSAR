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


@pytest.mark.parametrize(
    "name,aliases,question,raw",
    [
        (
            "zone_tag",
            [],
            "Tổng amount nơi zone_tag ghi đúng là không tồn tại, giữ NULL.",
            "không tồn tại",
        ),
        ("brand", [], 'Tổng amount với brand = "ACME, Inc."?', "ACME, Inc."),
        ("batch", ["mã lô"], "Tổng amount khi mã lô bằng văn bản 0047?", "0047"),
        ("state", [], "Tổng amount khi state equals pending.", "pending"),
        ("route", [], "Tổng amount khi route ghi chính xác là north west?", "north west"),
        ("tag", [], 'Tổng amount khi tag bằng "a."?', "a."),
    ],
)
def test_explicit_unknown_text_filter_cannot_disappear(
    revision: dict, name: str, aliases: list[str], question: str, raw: str
) -> None:
    revision["columns"][0].update(name=name, aliases=aliases)
    revision["grounding_values"] = {CODE: ["existing"]}
    for filters in (None, leaf(raw, raw, AMOUNT, "numeric"), {**leaf(raw, raw), "operator": "NE"}):
        with pytest.raises(AppError):
            compile_query(proposal(revision, question, filters=filters), revision, question)
    compiled = compile_query(
        proposal(revision, question, filters=leaf(raw, raw)), revision, question
    )
    assert compiled.filters[0]["canonical_value"] == raw
    assert raw in compiled.statement.compile(dialect=postgresql.dialect()).params.values()


def test_explicit_text_guard_does_not_guess_implicit_or_negated_comparison(revision: dict) -> None:
    from app.query import explicit_text_mentions

    assert explicit_text_mentions("Tổng amount?", revision["columns"]) == {}
    assert explicit_text_mentions("code không bằng missing", revision["columns"]) == {}
    # Tên cột gần giống không được nhận; không áp regex theo tên schema/domain.
    assert explicit_text_mentions("zipcode bằng missing", revision["columns"]) == {}


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


def test_longer_approved_phrase_does_not_require_its_nested_opposite(revision: dict) -> None:
    revision["columns"][0]["value_mappings"] = [
        {"phrase": "còn hàng", "value": "AVAILABLE"},
        {"phrase": "không còn hàng", "value": "EMPTY"},
    ]
    question = "Tổng không còn hàng"
    compiled = compile_query(
        proposal(revision, question, filters=leaf("không còn hàng", "EMPTY")), revision, question
    )
    assert compiled.filters[0]["canonical_value"] == "EMPTY"
    with pytest.raises(AppError):
        compile_query(
            proposal(revision, question, filters=leaf("còn hàng", "AVAILABLE")), revision, question
        )
    with pytest.raises(AppError):
        question = "Tổng còn hàng và không còn hàng"
        compile_query(
            proposal(revision, question, filters=leaf("không còn hàng", "EMPTY")),
            revision,
            question,
        )


def test_mapping_case_preserves_exact_canonical_value(revision: dict) -> None:
    revision["columns"][0]["value_mappings"] = [{"phrase": "sẵn sàng", "value": "Ready"}]
    compiled = compile_query(
        proposal(revision, "SẴN SÀNG", filters=leaf("SẴN SÀNG", "Ready")), revision, "SẴN SÀNG"
    )
    assert compiled.filters[0]["canonical_value"] == "Ready"


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


@pytest.mark.parametrize(
    "kind,phrase,start,end",
    [
        ("date", "tháng 2 năm 2024", "2024-02-01", "2024-03-01"),
        (
            "timestamp",
            "tháng 12 năm 2026",
            "2026-12-01T00:00:00+07:00",
            "2027-01-01T00:00:00+07:00",
        ),
    ],
)
def test_explicit_calendar_month_requires_exact_half_open_pair(
    revision: dict, kind: str, phrase: str, start: str, end: str
) -> None:
    revision["columns"][2]["data_type"] = kind
    first = {**leaf(phrase, start, DAY, kind), "operator": "GTE"}
    last = {**leaf(phrase, end, DAY, kind), "operator": "LT"}
    plan = proposal(revision, phrase, filters={"operator": "AND", "children": [first, last]})
    compiled = compile_query(plan, revision, phrase)
    assert all(item["mapping_source"] == "explicit_calendar_period" for item in compiled.filters)
    for filters in (
        first,
        {"operator": "OR", "children": [first, last]},
        {
            "operator": "AND",
            "children": [first, {**last, "literal": {**last["literal"], "candidate_value": start}}],
        },
    ):
        with pytest.raises(AppError):
            compile_query(proposal(revision, phrase, filters=filters), revision, phrase)


def test_calendar_month_never_guesses_year_and_checks_dst() -> None:
    from app.query import calendar_month

    assert calendar_month("tháng 9", "timestamp", "UTC") is None
    start, end = calendar_month("month 3 year 2026", "timestamp", "Europe/Berlin")
    assert start.isoformat() == "2026-03-01T00:00:00+01:00"
    assert end.isoformat() == "2026-04-01T00:00:00+02:00"
    with pytest.raises(AppError):
        calendar_month("tháng 13 năm 2026", "date", "UTC")
