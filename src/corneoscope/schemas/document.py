from typing import Literal

from pydantic import BaseModel


class DocumentInfo(BaseModel):
    id: str
    filename: str | None
    media_type: str
    size_bytes: int
    sha256: str


class ExtractResponse(BaseModel):
    status: Literal["validated"]
    document: DocumentInfo
