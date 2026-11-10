import pytest
from fastapi.testclient import TestClient

from corneoscope.core.config import settings
from corneoscope.main import app

client = TestClient(app)

PDF = b"%PDF-1.7\nsynthetic test document"


def upload(content: bytes, filename: str = "document.pdf"):
    return client.post("/api/v1/extract", files={"file": (filename, content)})


@pytest.mark.parametrize(
    ("content", "media_type"),
    [
        (PDF, "application/pdf"),
        (b"\x89PNG\r\n\x1a\nsynthetic", "image/png"),
        (b"\xff\xd8\xffsynthetic", "image/jpeg"),
    ],
)
def test_accepts_supported_files(content, media_type):
    response = upload(content)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "validated"
    assert body["document"]["media_type"] == media_type
    assert body["document"]["size_bytes"] == len(content)


def test_type_comes_from_content_not_filename():
    response = upload(b"plain text pretending", filename="invoice.pdf")

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"


def test_rejects_file_over_the_limit(monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)

    response = upload(PDF + b"0" * (1024 * 1024))

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_accepts_file_exactly_at_the_limit(monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)
    content = PDF + b"0" * (1024 * 1024 - len(PDF))

    response = upload(content)

    assert response.status_code == 200
    assert response.json()["document"]["size_bytes"] == 1024 * 1024


def test_missing_file_is_invalid_request():
    response = client.post("/api/v1/extract")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
