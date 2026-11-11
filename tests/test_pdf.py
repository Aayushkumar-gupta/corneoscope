import pytest
from samples import make_pdf

from corneoscope.core.config import settings
from corneoscope.core.errors import AppError
from corneoscope.ingestion.pdf import parse_pdf


def test_reads_text_and_page_size():
    pages = parse_pdf(make_pdf(["Invoice 1001\nTotal: 42.50 (USD)"]))

    assert len(pages) == 1
    page = pages[0]
    assert page.number == 1
    assert (page.width, page.height) == (612, 792)
    assert page.text == "Invoice 1001\nTotal: 42.50 (USD)"
    assert page.has_text


def test_blocks_have_text_and_top_left_boxes():
    page = parse_pdf(make_pdf(["Invoice 1001\nTotal: 42.50"]))[0]

    assert [block.text for block in page.blocks] == ["Invoice 1001", "Total: 42.50"]
    first, second = (block.bbox for block in page.blocks)
    for left, top, right, bottom in (first, second):
        assert 0 <= left < right <= page.width
        assert 0 <= top < bottom <= page.height
    assert first[1] < second[1]


def test_pages_are_numbered_from_one():
    pages = parse_pdf(make_pdf(["First", "Second", "Third"]))

    assert [page.number for page in pages] == [1, 2, 3]
    assert [page.text for page in pages] == ["First", "Second", "Third"]


def test_page_without_text_is_flagged():
    pages = parse_pdf(make_pdf(["Cover", ""]))

    assert pages[0].has_text
    assert not pages[1].has_text
    assert pages[1].blocks == []


@pytest.mark.parametrize("content", [b"%PDF-1.7\nnot a real pdf", b"%PDF-"])
def test_damaged_pdf_is_unreadable(content):
    with pytest.raises(AppError) as error:
        parse_pdf(content)

    assert error.value.status_code == 422
    assert error.value.code == "unreadable_document"


def test_rejects_too_many_pages(monkeypatch):
    monkeypatch.setattr(settings, "MAX_PAGES", 2)

    with pytest.raises(AppError) as error:
        parse_pdf(make_pdf(["One", "Two", "Three"]))

    assert error.value.status_code == 413
    assert error.value.code == "too_many_pages"


def test_accepts_exactly_the_page_limit(monkeypatch):
    monkeypatch.setattr(settings, "MAX_PAGES", 2)

    assert len(parse_pdf(make_pdf(["One", "Two"]))) == 2
