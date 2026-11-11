from pydantic import BaseModel


class DocumentInfo(BaseModel):
    id: str
    filename: str | None
    media_type: str
    size_bytes: int
    sha256: str
    pages: int | None = None


class TextBlock(BaseModel):
    text: str
    bbox: tuple[float, float, float, float]


class PageText(BaseModel):
    number: int
    width: float
    height: float
    text: str
    blocks: list[TextBlock]

    @property
    def has_text(self) -> bool:
        return bool(self.text.strip())


class ProcessingWarning(BaseModel):
    code: str
    message: str
    page: int | None = None
