import unicodedata

from corneoscope.schemas.document import PageText, ProcessingWarning

# A page is sent for review when more than this share of its characters is unreadable.
MAX_UNREADABLE_SHARE = 0.1

# Control, private-use, surrogate and unassigned characters. A PDF with a broken
# font mapping turns its text into these.
UNREADABLE_CATEGORIES = {"Cc", "Co", "Cs", "Cn"}


def unreadable_share(text: str) -> float:
    characters = [char for char in text if not char.isspace()]
    if not characters:
        return 0.0
    unreadable = sum(
        char == "\ufffd" or unicodedata.category(char) in UNREADABLE_CATEGORIES
        for char in characters
    )
    return unreadable / len(characters)


def page_warning(page: PageText) -> ProcessingWarning | None:
    """Return why a person should check this page, or None if it reads cleanly."""
    if not page.has_text:
        return ProcessingWarning(
            code="no_text_layer",
            message=f"Page {page.number} has no text layer; OCR is not available yet",
            page=page.number,
        )
    if unreadable_share(page.text) > MAX_UNREADABLE_SHARE:
        return ProcessingWarning(
            code="low_text_quality",
            message=f"Page {page.number} text looks garbled; a person should check it",
            page=page.number,
        )
    return None
