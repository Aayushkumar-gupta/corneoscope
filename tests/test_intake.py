import hashlib

import pytest

from corneoscope.core.errors import AppError
from corneoscope.ingestion.intake import detect_media_type, inspect_document


@pytest.mark.parametrize(
    ("content", "media_type"),
    [
        (b"%PDF-1.7\n", "application/pdf"),
        (b"\x89PNG\r\n\x1a\n\x00", "image/png"),
        (b"\xff\xd8\xff\xe0\x00", "image/jpeg"),
        (b"hello", None),
        (b"", None),
    ],
)
def test_detect_media_type_reads_file_signature(content, media_type):
    assert detect_media_type(content) == media_type


def test_inspect_document_returns_metadata():
    content = b"%PDF-1.7\nsynthetic"

    document = inspect_document(content, "invoice.pdf")

    assert document.id.startswith("doc_")
    assert document.filename == "invoice.pdf"
    assert document.media_type == "application/pdf"
    assert document.size_bytes == len(content)
    assert document.sha256 == hashlib.sha256(content).hexdigest()


def test_inspect_document_rejects_unknown_type():
    with pytest.raises(AppError) as error:
        inspect_document(b"MZ fake executable", "invoice.pdf")

    assert error.value.status_code == 415
    assert error.value.code == "unsupported_media_type"
