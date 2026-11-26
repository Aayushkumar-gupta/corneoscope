from typing import Literal

from pydantic import BaseModel

from corneoscope.schemas.document import DocumentInfo, ProcessingWarning
from corneoscope.schemas.extraction import Evidence


class ClauseLabel(BaseModel):
    """score is the model's output from 0 to 1, not a calibrated probability.

    A label is given when score reaches threshold, which was tuned per label.
    """

    label: str
    score: float
    threshold: float


class ClauseResult(BaseModel):
    id: str
    number: str | None
    heading: str | None
    text: str
    start: int
    end: int
    page_start: int
    page_end: int
    labels: list[ClauseLabel]
    review_required: bool
    evidence: list[Evidence]
    warnings: list[ProcessingWarning]


class AnalyzeResponse(BaseModel):
    status: Literal["analyzed"]
    document: DocumentInfo
    model: str
    clauses: list[ClauseResult]
    warnings: list[ProcessingWarning]
