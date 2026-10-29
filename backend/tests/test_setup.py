"""Smart setup không được sửa dữ liệu hoặc tự nâng đề xuất thành sự thật."""

from uuid import uuid4

import pytest

from app.errors import AppError
from app.setup import check_proposal, local_proposal
from app.tabular import read_table, validate_rows


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
    assert any("mơ hồ" in text for text in check_proposal(proposal, parsed, revision_id))
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
