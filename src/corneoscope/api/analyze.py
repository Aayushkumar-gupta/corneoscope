from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from corneoscope.api.auth import require_api_key
from corneoscope.classify.model import ClauseModel
from corneoscope.core.config import settings
from corneoscope.core.errors import AppError
from corneoscope.pipeline.analyze import analyze_document, load_model
from corneoscope.schemas.analysis import AnalyzeResponse

router = APIRouter(
    prefix="/api/v1", tags=["analyze"], dependencies=[Depends(require_api_key)]
)


def get_model() -> ClauseModel:
    if not settings.MODEL_PATH.exists():
        raise AppError(
            503,
            "model_not_available",
            "The clause model is not available on this server",
        )
    return load_model(settings.MODEL_PATH)


@router.post("/analyze")
async def analyze(
    file: Annotated[UploadFile, File()],
    model: Annotated[ClauseModel, Depends(get_model)],
) -> AnalyzeResponse:
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise AppError(
            413, "file_too_large", f"File is larger than {settings.MAX_UPLOAD_MB} MB"
        )
    return await analyze_document(
        content, file.filename, model, settings.MODEL_PATH.stem
    )
