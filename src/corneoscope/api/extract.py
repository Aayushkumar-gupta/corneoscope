from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import ValidationError

from corneoscope.api.auth import require_api_key
from corneoscope.core.config import settings
from corneoscope.core.errors import AppError
from corneoscope.pipeline.extract import process_document
from corneoscope.schemas.extraction import ExtractionSchema, ExtractResponse

router = APIRouter(
    prefix="/api/v1", tags=["extract"], dependencies=[Depends(require_api_key)]
)


def parse_schema(raw: str) -> ExtractionSchema:
    try:
        return ExtractionSchema.model_validate_json(raw)
    except ValidationError as exc:
        details = [
            {"location": ["schema", *error["loc"]], "message": error["msg"]}
            for error in exc.errors()
        ]
        raise AppError(
            400, "invalid_schema", "The extraction schema is not valid", details
        ) from exc


@router.post("/extract")
async def extract(
    file: Annotated[UploadFile, File()],
    schema_text: Annotated[str, Form(alias="schema")],
) -> ExtractResponse:
    extraction_schema = parse_schema(schema_text)
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise AppError(
            413, "file_too_large", f"File is larger than {settings.MAX_UPLOAD_MB} MB"
        )
    return await process_document(content, file.filename, extraction_schema)
