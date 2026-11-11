from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from corneoscope.schemas.document import DocumentInfo, ProcessingWarning

MAX_FIELDS = 50

FieldKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
FieldType = Literal["string", "integer", "decimal", "date", "boolean", "enum"]
FieldStatus = Literal["found", "missing", "ambiguous", "unsupported", "error"]


class FieldSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: FieldType
    required: bool = False
    description: str | None = Field(default=None, max_length=500)
    values: list[Annotated[str, Field(min_length=1, max_length=100)]] | None = Field(
        default=None, min_length=1, max_length=50
    )

    @model_validator(mode="after")
    def check_enum_values(self) -> Self:
        if self.type == "enum" and self.values is None:
            raise ValueError("an enum field needs a list of values")
        if self.type != "enum" and self.values is not None:
            raise ValueError("values are only allowed on enum fields")
        return self


class ExtractionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_name: str | None = Field(default=None, max_length=100)
    schema_version: str = Field(default="1.0", min_length=1, max_length=32)
    fields: dict[FieldKey, FieldSpec] = Field(min_length=1, max_length=MAX_FIELDS)


class Evidence(BaseModel):
    document_id: str
    page: int
    text: str
    bbox: tuple[float, float, float, float] | None = None
    method: Literal["text_layer", "ocr"]


class FieldResult(BaseModel):
    key: str
    value: str | int | bool | None = None
    raw_value: str | None = None
    status: FieldStatus
    review_required: bool = False
    evidence: list[Evidence] = []
    confidence: float | None = None
    warnings: list[ProcessingWarning] = []


class ExtractResponse(BaseModel):
    status: Literal["parsed"]
    document: DocumentInfo
    schema_name: str | None
    schema_version: str
    fields: dict[str, FieldResult]
    warnings: list[ProcessingWarning]
