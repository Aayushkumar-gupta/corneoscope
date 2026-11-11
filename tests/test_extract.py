import pytest
from fastapi.testclient import TestClient
from samples import make_pdf

from corneoscope.core.config import settings
from corneoscope.main import app

client = TestClient(
    app, headers={"Authorization": f"Bearer {settings.API_KEY.get_secret_value()}"}
)

PDF = make_pdf(["Invoice 1001\nTotal: 42.50"])


def upload(content: bytes, filename: str = "document.pdf"):
    return client.post("/api/v1/extract", files={"file": (filename, content)})


def test_parses_a_pdf():
    response = upload(PDF)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "parsed"
    assert body["document"]["media_type"] == "application/pdf"
    assert body["document"]["size_bytes"] == len(PDF)
    assert body["document"]["pages"] == 1
    assert body["warnings"] == []


def test_warns_about_pages_without_text():
    response = upload(make_pdf(["Cover", "", "Back"]))

    assert response.status_code == 200
    body = response.json()
    assert body["document"]["pages"] == 3
    assert [warning["page"] for warning in body["warnings"]] == [2]
    assert body["warnings"][0]["code"] == "no_text_layer"


@pytest.mark.parametrize(
    ("content", "media_type"),
    [
        (b"\x89PNG\r\n\x1a\nsynthetic", "image/png"),
        (b"\xff\xd8\xffsynthetic", "image/jpeg"),
    ],
)
def test_images_are_accepted_with_an_ocr_warning(content, media_type):
    response = upload(content, filename="scan.png")

    assert response.status_code == 200
    body = response.json()
    assert body["document"]["media_type"] == media_type
    assert body["document"]["pages"] == 1
    assert body["warnings"][0]["code"] == "no_text_layer"


def test_type_comes_from_content_not_filename():
    response = upload(b"plain text pretending", filename="invoice.pdf")

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"


def test_damaged_pdf_is_unreadable():
    response = upload(b"%PDF-1.7\nnot a real pdf")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unreadable_document"


def test_too_many_pages(monkeypatch):
    monkeypatch.setattr(settings, "MAX_PAGES", 1)

    response = upload(make_pdf(["One", "Two"]))

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "too_many_pages"


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
