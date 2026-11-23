import pytest
from fastapi.testclient import TestClient
from samples import SCHEMA, make_pdf

from corneoscope.core.config import settings
from corneoscope.main import app
from corneoscope.schemas.document import PageText

client = TestClient(
    app, headers={"Authorization": f"Bearer {settings.API_KEY.get_secret_value()}"}
)

PDF = make_pdf(["Invoice 1001\nTotal: 42.50"])


def upload(content: bytes, filename: str = "document.pdf", schema: str = SCHEMA):
    return client.post(
        "/api/v1/extract",
        files={"file": (filename, content)},
        data={"schema": schema},
    )


def test_parses_a_pdf():
    response = upload(PDF)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "parsed"
    assert body["document"]["media_type"] == "application/pdf"
    assert body["document"]["size_bytes"] == len(PDF)
    assert body["document"]["pages"] == 1
    assert body["warnings"] == []


def test_returns_a_result_for_every_requested_field():
    body = upload(PDF).json()

    assert body["schema_name"] is None
    assert body["schema_version"] == "1.0"
    assert list(body["fields"]) == ["invoice_number", "total_amount"]
    for key, field in body["fields"].items():
        assert field["key"] == key
        assert field["value"] is None
        assert field["status"] == "error"
        assert field["warnings"][0]["code"] == "extraction_not_available"


@pytest.mark.parametrize(
    "schema",
    [
        "not json",
        "{}",
        '{"fields": {"name": {"type": "text"}}}',
    ],
)
def test_invalid_schema(schema):
    response = upload(PDF, schema=schema)

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "invalid_schema"
    assert error["details"]
    assert all(detail["location"][0] == "schema" for detail in error["details"])


def test_schema_is_checked_before_the_file():
    response = upload(b"plain text pretending", schema="not json")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_schema"


def test_missing_schema_is_invalid_request():
    response = client.post("/api/v1/extract", files={"file": ("doc.pdf", PDF)})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_warns_about_pages_without_text():
    response = upload(make_pdf(["Cover", "", "Back"]))

    assert response.status_code == 200
    body = response.json()
    assert body["document"]["pages"] == 3
    assert [warning["page"] for warning in body["warnings"]] == [2]
    assert body["warnings"][0]["code"] == "no_text_layer"


def test_warns_about_garbled_pages(monkeypatch):
    def garbled_pages(content):
        return [
            PageText(number=1, width=612, height=792, text="Clean text", blocks=[]),
            PageText(number=2, width=612, height=792, text="\ue001\ue002", blocks=[]),
        ]

    monkeypatch.setattr("corneoscope.pipeline.extract.parse_pdf", garbled_pages)

    body = upload(PDF).json()

    assert [(w["code"], w["page"]) for w in body["warnings"]] == [
        ("low_text_quality", 2)
    ]


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
    response = client.post("/api/v1/extract", data={"schema": SCHEMA})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
