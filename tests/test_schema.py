import pytest
from pydantic import ValidationError

from corneoscope.schemas.extraction import MAX_FIELDS, ExtractionSchema, FieldResult


def parse(schema: dict) -> ExtractionSchema:
    return ExtractionSchema.model_validate(schema)


def test_accepts_the_spec_example():
    schema = parse(
        {
            "schema_name": "generic_business_record",
            "schema_version": "1.0",
            "fields": {
                "organization_name": {"type": "string", "required": True},
                "reference_number": {"type": "string", "required": False},
                "issue_date": {"type": "date"},
                "total_amount": {"type": "decimal"},
            },
        }
    )

    assert list(schema.fields) == [
        "organization_name",
        "reference_number",
        "issue_date",
        "total_amount",
    ]
    assert schema.fields["organization_name"].required
    assert not schema.fields["issue_date"].required


def test_defaults():
    schema = parse({"fields": {"name": {"type": "string"}}})

    assert schema.schema_name is None
    assert schema.schema_version == "1.0"
    assert schema.fields["name"].description is None


def test_enum_fields_list_their_values():
    schema = parse(
        {"fields": {"currency": {"type": "enum", "values": ["USD", "EUR", "INR"]}}}
    )

    assert schema.fields["currency"].values == ["USD", "EUR", "INR"]


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"name": {"type": "text"}},
        {"name": {"type": "string", "requird": True}},
        {"name": {"type": "enum"}},
        {"name": {"type": "enum", "values": []}},
        {"name": {"type": "string", "values": ["a"]}},
        {"Name": {"type": "string"}},
        {"2nd_name": {"type": "string"}},
        {"first-name": {"type": "string"}},
        {"name": {"type": "string", "description": "x" * 501}},
        {f"field_{i}": {"type": "string"} for i in range(MAX_FIELDS + 1)},
    ],
)
def test_rejects_invalid_fields(fields):
    with pytest.raises(ValidationError):
        parse({"fields": fields})


def test_rejects_unknown_top_level_keys():
    with pytest.raises(ValidationError):
        parse({"fields": {"name": {"type": "string"}}, "feilds": {}})


def test_accepts_the_field_limit():
    fields = {f"field_{i}": {"type": "string"} for i in range(MAX_FIELDS)}

    assert len(parse({"fields": fields}).fields) == MAX_FIELDS


def test_field_result_defaults_match_the_spec():
    result = FieldResult(key="expiry_date", status="missing")

    assert result.model_dump() == {
        "key": "expiry_date",
        "value": None,
        "raw_value": None,
        "status": "missing",
        "review_required": False,
        "evidence": [],
        "confidence": None,
        "warnings": [],
    }


def test_field_result_rejects_unknown_status():
    with pytest.raises(ValidationError):
        FieldResult(key="name", status="maybe")
