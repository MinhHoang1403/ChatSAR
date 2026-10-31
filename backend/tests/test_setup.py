"""Smart setup không được sửa dữ liệu hoặc tự nâng đề xuất thành sự thật."""

from uuid import uuid4

import pytest

from app.errors import AppError
from app.setup import check_proposal, local_proposal
from app.tabular import read_table, validate_rows


def test_setup_vocabulary_requires_explicit_opt_in_and_never_sends_rows() -> None:
    from app.setup import setup_profile

    parsed = read_table(
        b"code,state,enabled,amount\n0007,ready,true,0.10\n0012,pending,false,0.20\n", ".csv"
    )
    revision = uuid4()
    private = setup_profile(parsed, revision, include_values=False)
    assert all("observed_values" not in column for column in private)
    shared = setup_profile(parsed, revision, include_values=True)
    assert shared[0]["observed_values"] == ["0007", "0012"]
    assert shared[1]["observed_values"] == ["pending", "ready"]
    assert shared[2]["observed_values"] == ["false", "true"]
    assert shared[2]["data_type"] == "boolean"
    assert "observed_values" not in shared[3]
    assert all("rows" not in column for column in shared)


@pytest.mark.parametrize("values", [[f"item-{i}" for i in range(21)], ["x" * 121]])
def test_setup_omits_incomplete_or_oversize_vocabulary(values: list[str]) -> None:
    from app.setup import setup_profile
    from app.tabular import ParsedTable

    columns = setup_profile(
        ParsedTable(["label"], [[v] for v in values], [], ""), uuid4(), include_values=True
    )
    assert "observed_values" not in columns[0]


def test_business_metadata_merges_by_id_and_never_changes_source_order() -> None:
    from app.setup import SetupSuggestion, merge_suggestion

    parsed = read_table(b"code,value\n0007,0.10\n0012,\n", ".csv")
    revision = uuid4()
    local = local_proposal(parsed, revision)
    suggestion = SetupSuggestion.model_validate(
        {
            "columns": [
                {
                    "id": local.columns[1].id,
                    "description": "Giá trị được nhập",
                    "aliases": ["giá trị"],
                },
                {"id": local.columns[0].id, "role": "identifier"},
            ]
        }
    )
    merged, issues = merge_suggestion(suggestion, parsed, revision)
    assert not issues and not check_proposal(merged, parsed, revision)
    assert [c.id for c in merged.columns] == [c.id for c in local.columns]
    assert [c.name for c in merged.columns] == parsed.headers
    assert merged.columns[1].null_values == [""]
    assert validate_rows(parsed, merged.columns, "UTC")[0][merged.columns[0].id] == "0007"


def test_composite_key_is_checked_on_full_tuple_not_individual_columns() -> None:
    parsed = read_table(b"site,item\nA,1\nA,2\nB,1\n", ".csv")
    revision = uuid4()
    proposal = local_proposal(parsed, revision)
    for column in proposal.columns:
        column.primary_key = True
    assert not check_proposal(proposal, parsed, revision)
    parsed.rows.append(["A", "1"])
    issues = check_proposal(proposal, parsed, revision)
    assert any(i.rule == "primary_key_uniqueness" and i.decision == "rejected" for i in issues)


@pytest.mark.parametrize(
    "source",
    [
        b"booking_ref,room_charge\nH01,100.05\nH02,200.10\nH03,\nH04,0.00\n",
        b"code,value\n0007,\n0012,\n",
        b"code,value\n0007,1.10\n0012,unknown\n",
        b"code,value\n0007,\n0012,hello\n",
    ],
)
def test_metadata_only_suggestion_preserves_full_local_rows(source: bytes) -> None:
    from app.setup import SetupSuggestion, merge_suggestion

    parsed = read_table(source, ".csv")
    revision = uuid4()
    original = [row[:] for row in parsed.rows]
    proposal, issues = merge_suggestion(
        SetupSuggestion(description="Chờ xác nhận"), parsed, revision
    )
    assert not issues and not check_proposal(proposal, parsed, revision)
    assert parsed.rows == original
    assert validate_rows(parsed, proposal.columns, "UTC") == validate_rows(
        parsed, local_proposal(parsed, revision).columns, "UTC"
    )


@pytest.mark.parametrize("duplicate", [True, False])
def test_unknown_or_duplicate_suggestion_id_rejected(duplicate: bool) -> None:
    from app.setup import SetupSuggestion, merge_suggestion

    parsed = read_table(b"code\n0007\n", ".csv")
    revision = uuid4()
    identifier = local_proposal(parsed, revision).columns[0].id
    columns = [{"id": identifier}, {"id": identifier if duplicate else "c_" + "f" * 32}]
    _, issues = merge_suggestion(
        SetupSuggestion.model_validate({"columns": columns}), parsed, revision
    )
    assert issues[0].code == "COLUMN_ID_INVALID" and issues[0].decision == "rejected"


def test_unknown_units_need_owner_review_and_source_names_cannot_be_replaced() -> None:
    from pydantic import ValidationError

    from app.setup import SetupSuggestion, merge_suggestion

    parsed = read_table(b"code,value\n0007,1.10\n", ".csv")
    revision = uuid4()
    identifier = local_proposal(parsed, revision).columns[1].id
    proposal, issues = merge_suggestion(
        SetupSuggestion.model_validate(
            {"columns": [{"id": identifier, "unit": "Đơn vị chưa được xác nhận"}]}
        ),
        parsed,
        revision,
    )
    assert any(i.code == "UNIT_UNCONFIRMED" and i.decision == "needs_review" for i in issues)
    assert proposal.columns[1].unit is None
    assert not check_proposal(proposal, parsed, revision)
    for forbidden in ({"name": "new"}, {"null_values": ["0"]}, {"rows": [[0]]}):
        with pytest.raises(ValidationError):
            SetupSuggestion.model_validate({"columns": [{"id": identifier, **forbidden}]})


def test_invalid_mapping_and_mixed_numeric_report_column_and_rule() -> None:
    from app.tabular import ValueMapping

    parsed = read_table(b"code,value\n0007,1.10\n0012,other\n", ".csv")
    revision = uuid4()
    proposal = local_proposal(parsed, revision)
    proposal.columns[1].data_type = "numeric"
    issue = check_proposal(proposal, parsed, revision)[0]
    assert issue.column_id == proposal.columns[1].id and issue.position == 2
    assert issue.rule == "lossless_type_conversion" and issue.decision == "rejected"
    proposal = local_proposal(parsed, revision)
    proposal.columns[0].value_mappings = [ValueMapping(phrase="mã đầu", value="0007")]
    assert not check_proposal(proposal, parsed, revision)
    proposal.columns[0].value_mappings[0].value = "absent"
    assert check_proposal(proposal, parsed, revision)[0].rule == "mapping_source_exists"


def test_reordered_review_and_duplicate_names_cannot_publish_as_valid_proposal() -> None:
    parsed = read_table(b"code,amount\n0007,0.10\n", ".csv")
    revision = uuid4()
    proposal = local_proposal(parsed, revision)
    proposal.columns.reverse()
    assert check_proposal(proposal, parsed, revision)[0].code == "COLUMN_ORDER_INVALID"
    proposal.columns.reverse()
    proposal.columns[1].name = proposal.columns[0].name
    assert check_proposal(proposal, parsed, revision)[0].code == "COLUMN_NAME_INVALID"


@pytest.mark.parametrize(
    "source",
    [
        b"code,amount\n0007,0.10\n0012,0.20\n",
        b"code,amount\n0007,\n0012,0.20\n",
        b"code,amount\n0007,0.10\n0007,0.00\n",
    ],
)
def test_local_profile_preserves_codes_decimal_empty_and_duplicates(source: bytes) -> None:
    parsed = read_table(source, ".csv")
    revision_id = uuid4()
    proposal = local_proposal(parsed, revision_id)
    assert proposal.columns[0].data_type == "text"
    assert proposal.columns[0].primary_key is False
    assert proposal.columns[1].unit is None
    assert check_proposal(proposal, parsed, revision_id) == []
    rows = validate_rows(parsed, proposal.columns, "UTC")
    assert rows[0][proposal.columns[0].id] == "0007"


@pytest.mark.parametrize(
    "change",
    [
        {"data_type": "integer"},
        {"primary_key": True},
        {"value_mappings": [{"phrase": "mã", "value": "absent"}]},
    ],
)
def test_invalid_ai_type_key_or_mapping_is_rejected(change: dict) -> None:
    parsed = read_table(b"code,amount\n0007,0.10\n0007,0.20\n", ".csv")
    revision_id = uuid4()
    proposal = local_proposal(parsed, revision_id)
    proposal.columns[0] = type(proposal.columns[0]).model_validate(
        {**proposal.columns[0].model_dump(), **change}
    )
    assert check_proposal(proposal, parsed, revision_id)


def test_date_ambiguity_requires_confirmation_and_bad_column_ids_rejected() -> None:
    parsed = read_table(b"day\n01/02/2026\n02/03/2026\n", ".csv")
    revision_id = uuid4()
    proposal = local_proposal(parsed, revision_id)
    proposal.columns[0].data_type = "date"
    proposal.columns[0].date_format = "%d/%m/%Y"
    assert any(
        issue.code == "DATE_FORMAT_AMBIGUOUS" and issue.decision == "needs_review"
        for issue in check_proposal(proposal, parsed, revision_id)
    )
    proposal.columns[0].id = "c_" + "a" * 32
    assert check_proposal(proposal, parsed, revision_id)


def test_text_empty_not_null_and_leading_zero_cannot_be_erased() -> None:
    parsed = read_table(b"code,name\n0007,\n0012,hello\n", ".csv")
    proposal = local_proposal(parsed, uuid4())
    rows = validate_rows(parsed, proposal.columns, "UTC")
    assert rows[0][proposal.columns[1].id] == ""
    proposal.columns[0].data_type = "integer"
    with pytest.raises(AppError):
        validate_rows(parsed, proposal.columns, "UTC")


def test_mapping_cannot_override_an_existing_exact_value() -> None:
    from app.tabular import ValueMapping

    parsed = read_table("district\nquận 3\n3\n".encode(), ".csv")
    revision_id = uuid4()
    proposal = local_proposal(parsed, revision_id)
    proposal.columns[0].value_mappings = [ValueMapping(phrase="quận 3", value="3")]
    assert check_proposal(proposal, parsed, revision_id)
