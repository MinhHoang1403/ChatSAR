"""Oracle trình bày từ facts cố định; không gọi model hoặc dùng composer tạo expected."""

from copy import deepcopy
from decimal import Decimal

import pytest
from sqlalchemy import literal, select

from app.answers import compose_answer, display_value, failure_text
from app.query import CompiledQuery, QueryPlan


def source() -> dict:
    return {
        "columns": [
            {"id": "code", "name": "shipment_code", "aliases": ["Mã vận đơn"]},
            {"id": "fee", "name": "fee", "aliases": ["phí"], "unit": "VND"},
        ]
    }


def result(operator: str = "SUM", value: object = "10.10", **changes) -> tuple:
    plan = QueryPlan(
        task="SQL",
        table_id="d",
        source_revision_id="r",
        raw_user_spans=["?"],
        coverage=["?"],
        aggregations=[
            {
                "operator": operator,
                "column_id": None if operator == "COUNT_ROWS" else "fee",
                "output_id": "metric",
            }
        ],
        **changes,
    )
    count = operator.startswith("COUNT")
    compiled = CompiledQuery(
        select(literal(1)),
        [
            {
                "id": "metric",
                "name": "legacy",
                "type": "integer" if count else "numeric",
                "unit": None if count else "VND",
            }
        ],
        [],
    )
    rows = [[value]]
    return plan, compiled, rows


@pytest.mark.parametrize(
    "operator,label",
    [("SUM", "Tổng phí"), ("AVG", "trung bình"), ("MIN", "nhỏ nhất"), ("MAX", "lớn nhất")],
)
def test_aggregate_meaning_units_and_exact_decimal(operator: str, label: str) -> None:
    plan, compiled, rows = result(operator)
    before = deepcopy(rows)
    text, columns = compose_answer(plan, compiled, source(), rows)
    assert label in text and "10,10 VND" in text
    assert rows == before and columns[0]["id"] == "metric"


@pytest.mark.parametrize(
    "operator,required,forbidden",
    [
        ("COUNT_ROWS", "Có 0 bản ghi", "vận đơn"),
        ("COUNT_NON_NULL", "không trống", "VND"),
        ("COUNT_DISTINCT", "khác nhau", "VND"),
    ],
)
def test_counts_do_not_invent_entity_grain_or_currency(
    operator: str, required: str, forbidden: str
) -> None:
    text, _ = compose_answer(*result(operator, 0)[:2], source(), result(operator, 0)[2])
    assert required in text and forbidden not in text


def test_null_aggregate_is_not_zero_and_empty_rows_differ() -> None:
    plan, compiled, rows = result(value=None)
    text, _ = compose_answer(plan, compiled, source(), rows)
    assert "Chưa có giá trị" in text and "không được xem là 0" in text
    empty, _ = compose_answer(plan, compiled, source(), [])
    assert "Không tìm thấy bản ghi" in empty and empty != text


def test_missing_unit_description_and_technical_names_are_not_invented() -> None:
    plan, compiled, rows = result()
    compiled.columns[0]["unit"] = None
    revision = source()
    revision["columns"][1].update(aliases=[], name="room_charge", description="Tiền phòng USD")
    text, _ = compose_answer(plan, compiled, revision, rows)
    assert "room charge" in text and "room_charge" not in text
    assert "USD" not in text and "Tiền phòng" not in text


def test_lookup_keeps_code_zeroes_and_multicolumn_output() -> None:
    plan = QueryPlan(
        task="SQL",
        table_id="d",
        source_revision_id="r",
        raw_user_spans=["?"],
        coverage=["?"],
        select_columns=["code", "fee"],
    )
    compiled = CompiledQuery(
        select(literal(1)),
        [
            {"id": "code", "name": "shipment_code", "type": "text", "unit": None},
            {"id": "fee", "name": "fee", "type": "numeric", "unit": "VND"},
        ],
        [],
    )
    text, columns = compose_answer(plan, compiled, source(), [["0007", "10.10"]])
    assert "0007" in text and "10,10" in text and len(columns) == 2
    assert "SUM" not in text


def test_internal_column_name_is_hidden_but_confirmed_alias_is_used() -> None:
    plan, compiled, rows = result()
    revision = source()
    internal_name = "c_" + "a" * 32
    revision["columns"][1].update(name=internal_name, aliases=[])
    text, columns = compose_answer(plan, compiled, revision, rows)
    assert "Tổng giá trị đã chọn" in text
    assert internal_name not in text and "a" * 32 not in text
    assert columns[0]["id"] == "metric" and rows == [["10.10"]]
    revision["columns"][1]["aliases"] = ["phí"]
    aliased, _ = compose_answer(plan, compiled, revision, rows)
    assert "Tổng phí" in aliased


def test_partial_group_ranking_are_not_a_full_result_or_invented_winner() -> None:
    plan, compiled, rows = result()
    compiled.truncated = True
    text, _ = compose_answer(plan, compiled, source(), rows)
    assert "chưa đầy đủ" in text
    compiled.truncated = False
    plan.group_by = ["code"]
    text, _ = compose_answer(plan, compiled, source(), rows)
    assert "theo từng nhóm Mã vận đơn" in text and "cao nhất" not in text
    plan.result_mode = "top"
    plan.limit = 3
    text, _ = compose_answer(plan, compiled, source(), rows)
    assert "1 kết quả" in text and "tối đa 3" in text and "thứ tự đã yêu cầu" in text


@pytest.mark.parametrize(
    "value,expected",
    [
        ("9007199254740993.123456789012345678", "9007199254740993,123456789012345678"),
        (Decimal("0.00"), "0,00"),
        ("-0.10", "-0,10"),
    ],
)
def test_decimal_format_never_rounds_or_uses_float(value, expected: str) -> None:
    assert display_value(value, "numeric") == expected
    assert display_value("A_0007", "text") == "A_0007"


@pytest.mark.parametrize(
    "status,code,meaning",
    [
        ("clarify", None, "làm rõ"),
        ("unsupported", None, "vượt phạm vi"),
        ("provider_unavailable", "USAGE_UNKNOWN", "đối soát"),
        ("provider_unavailable", "PROVIDER_TEMPORARY", "không tự gửi lại"),
        ("execution_error", None, "chưa có kết quả"),
        ("insufficient", "DATA_PERMISSION_REQUIRED", "cấp quyền"),
    ],
)
def test_failure_prose_matches_status_without_fake_facts(status: str, code, meaning: str) -> None:
    text = failure_text(status, code)
    assert meaning in text and "300" not in text and "SELECT" not in text
