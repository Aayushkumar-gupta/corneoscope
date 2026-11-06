import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from corneoscope.api.errors import REQUEST_ID_HEADER, install_error_handling
from corneoscope.core.errors import AppError
from corneoscope.main import app


@pytest.fixture
def client() -> TestClient:
    test_app = FastAPI()
    install_error_handling(test_app)

    @test_app.get("/app-error")
    def raise_app_error():
        raise AppError(413, "file_too_large", "File is larger than 15 MB")

    @test_app.get("/crash")
    def raise_unexpected_error():
        raise RuntimeError("secret internal detail")

    @test_app.get("/items/{item_id}")
    def read_item(item_id: int):
        return {"item_id": item_id}

    return TestClient(test_app, raise_server_exceptions=False)


def test_app_error_uses_standard_format(client):
    response = client.get("/app-error")

    assert response.status_code == 413
    assert response.json() == {
        "error": {
            "code": "file_too_large",
            "message": "File is larger than 15 MB",
            "request_id": response.headers[REQUEST_ID_HEADER],
        }
    }


def test_validation_error_returns_400_with_details(client):
    response = client.get("/items/not-a-number")

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "invalid_request"
    assert error["details"][0]["location"] == ["path", "item_id"]
    assert error["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_unexpected_error_hides_details_and_logs_request_id(client, caplog):
    with caplog.at_level(logging.ERROR, logger="corneoscope.api.errors"):
        response = client.get("/crash")

    request_id = response.headers[REQUEST_ID_HEADER]
    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "Internal server error",
            "request_id": request_id,
        }
    }
    assert "secret internal detail" not in response.text
    assert request_id in caplog.text


def test_unknown_route_returns_not_found():
    response = TestClient(app).get("/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_wrong_method_returns_method_not_allowed():
    response = TestClient(app).post("/health")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"
    assert response.headers["allow"] == "GET"


def test_every_response_gets_a_unique_request_id():
    client = TestClient(app)

    first = client.get("/health").headers[REQUEST_ID_HEADER]
    second = client.get("/health").headers[REQUEST_ID_HEADER]

    assert first.startswith("req_")
    assert first != second
