from pydantic import BaseModel


class Clause(BaseModel):
    """One clause of a document.

    text is the clause with wrapped lines joined. start and end are its positions
    in the source text, so the exact original can always be found again. The page
    fields are filled in by split_pages; split_text leaves them empty.
    """

    id: str
    number: str | None
    heading: str | None
    text: str
    start: int
    end: int
    page_start: int | None = None
    page_end: int | None = None
