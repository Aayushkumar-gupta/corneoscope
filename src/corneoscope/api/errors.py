import logging
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from corneoscope.core.errors import AppError

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"

HTTP_ERROR_CODES = {
    404: "not_found",
    405: "method_not_allowed",
}


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[dict] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = request.state.request_id
    logger.log(
        logging.ERROR if status_code >= 500 else logging.WARNING,
        "request_id=%s status=%s code=%s %s %s",
        request_id,
        status_code,
        code,
        request.method,
        request.url.path,
    )
    error = {"code": code, "message": message, "request_id": request_id}
    if details is not None:
        error["details"] = details
    return JSONResponse(
        status_code=status_code,
        content={"error": error},
        headers={**(headers or {}), REQUEST_ID_HEADER: request_id},
    )


async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return error_response(
        request,
        exc.status_code,
        exc.code,
        exc.message,
        exc.details,
        headers=exc.headers,
    )


async def handle_http_error(request: Request, exc: HTTPException) -> JSONResponse:
    code = HTTP_ERROR_CODES.get(exc.status_code, "http_error")
    return error_response(
        request, exc.status_code, code, str(exc.detail), headers=exc.headers
    )


async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {"location": list(error["loc"]), "message": error["msg"]}
        for error in exc.errors()
    ]
    return error_response(
        request, 400, "invalid_request", "Request validation failed", details
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    request_id = request.state.request_id
    logger.exception(f"Unexpected error, request_id={request_id}")
    return error_response(request, 500, "internal_error", "Internal server error")


def install_error_handling(app: FastAPI) -> None:
    @app.middleware("http")
    async def add_request_id(request: Request, call_next) -> Response:
        request_id = f"req_{uuid4().hex}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(HTTPException, handle_http_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
