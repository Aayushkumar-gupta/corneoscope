import asyncio
from functools import cache
from pathlib import Path

from corneoscope.classify.labels import LABELS
from corneoscope.classify.model import ClauseModel
from corneoscope.clauses.splitter import document_text, split_pages
from corneoscope.core.errors import AppError
from corneoscope.ingestion.intake import inspect_document
from corneoscope.ingestion.pdf import parse_pdf
from corneoscope.ingestion.quality import page_warning
from corneoscope.schemas.analysis import AnalyzeResponse, ClauseLabel, ClauseResult
from corneoscope.schemas.clause import Clause
from corneoscope.schemas.document import PageText, ProcessingWarning
from corneoscope.schemas.extraction import Evidence

# Not tuned: a score this close to its threshold, on either side, sends the clause to a
# person, because a small change in wording could flip the label.
REVIEW_MARGIN = 0.1

# 99.7% of CUAD training paragraphs are shorter. A longer clause usually means the
# splitter missed a boundary, so it holds several clauses.
LONG_CLAUSE_CHARS = 4000


@cache
def load_model(path: Path) -> ClauseModel:
    return ClauseModel.load(path)


def label_clause(
    scores: list[float], thresholds: list[float], page: int
) -> tuple[list[ClauseLabel], list[ProcessingWarning]]:
    labels, warnings = [], []
    for label, score, threshold in zip(LABELS, scores, thresholds, strict=True):
        if score >= threshold:
            labels.append(ClauseLabel(label=label, score=score, threshold=threshold))
        if abs(score - threshold) < REVIEW_MARGIN:
            warnings.append(
                ProcessingWarning(
                    code="low_confidence",
                    message=f"{label} scored {score:.2f}, close to its threshold of "
                    f"{threshold:.2f}",
                    page=page,
                )
            )
    labels.sort(key=lambda item: item.score, reverse=True)
    return labels, warnings


def evidence_of(
    clause: Clause,
    text: str,
    page_starts: list[int],
    pages: list[PageText],
    doc_id: str,
) -> list[Evidence]:
    """The clause's text on each page it covers, as the page has it."""
    evidence = []
    for page, begin in zip(pages, page_starts, strict=True):
        end = begin + len(page.text)
        part = text[max(clause.start, begin) : min(clause.end, end)].strip()
        if part:
            evidence.append(
                Evidence(
                    document_id=doc_id, page=page.number, text=part, method="text_layer"
                )
            )
    return evidence


def analyze_pages(
    pages: list[PageText], model: ClauseModel, doc_id: str
) -> tuple[list[ClauseResult], list[ProcessingWarning]]:
    page_warnings = {
        page.number: warning
        for page in pages
        if (warning := page_warning(page)) is not None
    }
    clauses = split_pages(pages)
    if not clauses:
        return [], list(page_warnings.values())

    text, page_starts = document_text(pages)
    scores = model.probabilities([clause.text for clause in clauses]).tolist()
    thresholds = model.thresholds.tolist()
    results = []
    for clause, clause_scores in zip(clauses, scores, strict=True):
        labels, warnings = label_clause(clause_scores, thresholds, clause.page_start)
        if len(clause.text) > LONG_CLAUSE_CHARS:
            warnings.append(
                ProcessingWarning(
                    code="long_clause",
                    message=f"This clause is {len(clause.text)} characters long and may "
                    "hold several clauses",
                    page=clause.page_start,
                )
            )
        warnings += [
            ProcessingWarning(
                code="page_needs_review",
                message=f"Page {number} of this clause needs a person's check: "
                f"{page_warnings[number].code}",
                page=number,
            )
            for number in range(clause.page_start, clause.page_end + 1)
            if number in page_warnings
        ]
        results.append(
            ClauseResult(
                **clause.model_dump(exclude={"page_start", "page_end"}),
                page_start=clause.page_start,
                page_end=clause.page_end,
                labels=labels,
                review_required=bool(warnings),
                evidence=evidence_of(clause, text, page_starts, pages, doc_id),
                warnings=warnings,
            )
        )
    return results, list(page_warnings.values())


async def analyze_document(
    content: bytes, filename: str | None, model: ClauseModel, model_name: str
) -> AnalyzeResponse:
    document = inspect_document(content, filename)
    if document.media_type != "application/pdf":
        raise AppError(
            415,
            "unsupported_media_type",
            "Only PDF files can be analyzed; images need OCR, which is not available yet",
        )
    pages = await asyncio.to_thread(parse_pdf, content)
    clauses, warnings = await asyncio.to_thread(
        analyze_pages, pages, model, document.id
    )
    return AnalyzeResponse(
        status="analyzed",
        document=document.model_copy(update={"pages": len(pages)}),
        model=model_name,
        clauses=clauses,
        warnings=warnings,
    )
