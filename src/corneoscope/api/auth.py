import secrets
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from corneoscope.core.config import settings
from corneoscope.core.errors import AppError

bearer_scheme = HTTPBearer(auto_error=False)


def require_api_key(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> None:
    expected = settings.API_KEY.get_secret_value().encode()
    if credentials is None or not secrets.compare_digest(
        credentials.credentials.encode(), expected
    ):
        raise AppError(
            401,
            "unauthorized",
            "Missing or invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
