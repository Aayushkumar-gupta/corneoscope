import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from corneoscope.core.config import Settings, settings
from corneoscope.main import app

client = TestClient(app)

PDF = b"%PDF-1.7\nsynthetic test document"


def upload(headers: dict[str, str]):
    return client.post(
        "/api/v1/extract", files={"file": ("doc.pdf", PDF)}, headers=headers
    )


def test_valid_key_is_accepted():
    key = settings.API_KEY.get_secret_value()

    response = upload({"Authorization": f"Bearer {key}"})

    assert response.status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer wrong-key"},
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": "Bearer"},
    ],
)
def test_missing_or_wrong_key_is_rejected(headers):
    response = upload(headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert response.headers["www-authenticate"] == "Bearer"


def test_health_needs_no_key():
    assert client.get("/health").status_code == 200


def test_docs_show_bearer_security():
    schemes = client.get("/openapi.json").json()["components"]["securitySchemes"]

    assert schemes["HTTPBearer"] == {"type": "http", "scheme": "bearer"}


def test_settings_reject_a_short_key():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, API_KEY="too-short")


def test_settings_hide_the_key():
    key = settings.API_KEY.get_secret_value()

    assert key not in repr(settings)
    assert key not in str(settings.API_KEY)
