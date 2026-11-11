import asyncio

from corneoscope.ingestion.intake import inspect_document
from corneoscope.ingestion.pdf import parse_pdf
from corneoscope.schemas.document import ExtractResponse, ProcessingWarning


async def process_document(content: bytes, filename: str | None) -> ExtractResponse:
    document = inspect_document(content, filename)

    if document.media_type == "application/pdf":
        pages = await asyncio.to_thread(parse_pdf, content)
        page_count = len(pages)
        warnings = [
            ProcessingWarning(
                code="no_text_layer",
                message=f"Page {page.number} has no text layer; OCR is not available yet",
                page=page.number,
            )
            for page in pages
            if not page.has_text
        ]
    else:
        page_count = 1
        warnings = [
            ProcessingWarning(
                code="no_text_layer",
                message="Images have no text layer; OCR is not available yet",
                page=1,
            )
        ]

    return ExtractResponse(
        status="parsed",
        document=document.model_copy(update={"pages": page_count}),
        warnings=warnings,
    )
