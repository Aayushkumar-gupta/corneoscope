from typing import Annotated

from fastapi import APIRouter, File, UploadFile

from corneoscope.core.config import settings
from corneoscope.core.errors import AppError
from corneoscope.ingestion.intake import inspect_document
from corneoscope.schemas.document import ExtractResponse

router = APIRouter(prefix="/api/v1", tags=["extract"])


@router.post("/extract")
async def extract(file: Annotated[UploadFile, File()]) -> ExtractResponse:
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise AppError(
            413, "file_too_large", f"File is larger than {settings.MAX_UPLOAD_MB} MB"
        )
    document = inspect_document(content, file.filename)
    return ExtractResponse(status="validated", document=document)
