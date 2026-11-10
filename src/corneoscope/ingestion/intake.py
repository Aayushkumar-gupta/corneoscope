import hashlib
from uuid import uuid4

from corneoscope.core.errors import AppError
from corneoscope.schemas.document import DocumentInfo

SIGNATURES = {
    b"%PDF-": "application/pdf",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}


def detect_media_type(content: bytes) -> str | None:
    for signature, media_type in SIGNATURES.items():
        if content.startswith(signature):
            return media_type
    return None


def inspect_document(content: bytes, filename: str | None) -> DocumentInfo:
    media_type = detect_media_type(content)
    if media_type is None:
        raise AppError(
            415, "unsupported_media_type", "Only PDF, PNG and JPEG files are supported"
        )
    return DocumentInfo(
        id=f"doc_{uuid4().hex}",
        filename=filename,
        media_type=media_type,
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
    )
