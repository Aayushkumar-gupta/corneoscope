import pytest

from corneoscope.ingestion.quality import page_warning, unreadable_share
from corneoscope.schemas.document import PageText


def page(text: str) -> PageText:
    return PageText(number=4, width=612, height=792, text=text, blocks=[])


def test_clean_text_has_nothing_unreadable():
    assert unreadable_share("1. Term. Two years.\n") == 0
    assert unreadable_share("   \n") == 0


@pytest.mark.parametrize("bad", ["\ufffd", "\x01", "\ue000"])
def test_counts_replacement_control_and_private_characters(bad):
    assert unreadable_share(f"ab{bad}{bad}") == 0.5


def test_clean_page_needs_no_review():
    assert page_warning(page("1. Term. Two years.")) is None


def test_page_without_text_needs_review():
    warning = page_warning(page("  "))

    assert warning.code == "no_text_layer"
    assert warning.page == 4


def test_garbled_page_needs_review():
    warning = page_warning(page("1. T\ue001rm \ue002\ue003 \ue004\ue005rs"))

    assert warning.code == "low_text_quality"
    assert warning.page == 4
    assert "Page 4" in warning.message


def test_a_few_odd_characters_are_tolerated():
    assert page_warning(page("Fees are due within thirty days\ufffd")) is None
