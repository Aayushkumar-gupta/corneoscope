import threading

import pypdfium2 as pdfium

from corneoscope.core.config import settings
from corneoscope.core.errors import AppError
from corneoscope.schemas.document import PageText, TextBlock

# PDFium is not thread-safe, so only one thread may use it at a time.
_pdfium_lock = threading.Lock()


def unreadable_pdf() -> AppError:
    return AppError(
        422,
        "unreadable_document",
        "The PDF could not be read; it may be damaged or password protected",
    )


def read_page(page: pdfium.PdfPage, number: int) -> PageText:
    width, height = page.get_size()
    textpage = page.get_textpage()
    try:
        text = textpage.get_text_range().replace("\r\n", "\n")
        blocks = []
        for index in range(textpage.count_rects()):
            left, bottom, right, top = textpage.get_rect(index)
            block_text = textpage.get_text_bounded(left, bottom, right, top).strip()
            if block_text:
                bbox = (left, height - top, right, height - bottom)
                blocks.append(
                    TextBlock(text=block_text, bbox=tuple(round(v, 2) for v in bbox))
                )
    finally:
        textpage.close()
    return PageText(
        number=number,
        width=round(width, 2),
        height=round(height, 2),
        text=text,
        blocks=blocks,
    )


def parse_pdf(content: bytes) -> list[PageText]:
    with _pdfium_lock:
        try:
            pdf = pdfium.PdfDocument(content)
        except pdfium.PdfiumError as exc:
            raise unreadable_pdf() from exc
        try:
            page_count = len(pdf)
            if page_count == 0:
                raise unreadable_pdf()
            if page_count > settings.MAX_PAGES:
                raise AppError(
                    413,
                    "too_many_pages",
                    f"PDF has {page_count} pages; the limit is {settings.MAX_PAGES}",
                )
            pages = []
            for index in range(page_count):
                page = pdf[index]
                try:
                    pages.append(read_page(page, index + 1))
                finally:
                    page.close()
            return pages
        except pdfium.PdfiumError as exc:
            raise unreadable_pdf() from exc
        finally:
            pdf.close()
