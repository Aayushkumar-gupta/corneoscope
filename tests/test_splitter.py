import pytest

from corneoscope.clauses.splitter import document_text, split_pages, split_text
from corneoscope.schemas.document import PageText


def page(number: int, text: str) -> PageText:
    return PageText(number=number, width=612, height=792, text=text, blocks=[])


def numbers(clauses):
    return [clause.number for clause in clauses]


def test_splits_numbered_sections_and_subsections():
    clauses = split_text(
        "1. Definitions\n"
        '1.1 "Services" means the work.\n'
        '1.2 "Fees" means the amounts in clause 4.\n'
        "2. Term. This Agreement lasts 2 years.\n"
    )

    assert numbers(clauses) == ["1.1", "1.2", "2"]
    assert [clause.id for clause in clauses] == ["c1", "c2", "c3"]
    assert clauses[2].text == "2. Term. This Agreement lasts 2 years."


def test_start_and_end_point_at_the_exact_text():
    text = (
        "Preamble text.\n\n  1. Term. It lasts\n  two years.\n2. Fees. Pay on time.\n"
    )

    for clause in split_text(text):
        assert " ".join(text[clause.start : clause.end].split()) == clause.text
        assert not text[clause.start].isspace()
        assert not text[clause.end - 1].isspace()


@pytest.mark.parametrize(
    ("line", "heading"),
    [
        ("3. Termination", "Termination"),
        ("3. TERMINATION", "TERMINATION"),
        ("3. Termination for Convenience.", "Termination for Convenience"),
        ("3. Termination. Either party may end it.", "Termination"),
        ("3. The Supplier shall deliver the goods.", None),
    ],
)
def test_reads_the_heading(line, heading):
    clauses = split_text(f"1. A\nText.\n2. B\nText.\n{line}\nMore text here.\n")

    assert clauses[-1].number == "3"
    assert clauses[-1].heading == heading


def test_subsections_inherit_the_section_heading():
    clauses = split_text(
        "1. TERMINATION\n1.1 Either party may end it.\n1.2 Acme may end it at once.\n"
    )

    assert numbers(clauses) == ["1.1", "1.2"]
    assert [clause.heading for clause in clauses] == ["TERMINATION", "TERMINATION"]


def test_lettered_items_stay_inside_their_clause():
    clauses = split_text(
        "1. Acme may terminate if Beta:\n(a) breaches clause 5; or\n(b) is insolvent.\n"
    )

    assert len(clauses) == 1
    assert clauses[0].text.endswith("(b) is insolvent.")


@pytest.mark.parametrize(
    "line",
    [
        "1.5 million per year.",  # a decimal, not a clause number
        "2024. The prices rise.",  # a year
        "30 days after notice.",  # a number without a dot
        "7. The schedule has items.",  # jumps too far from section 1
        "Section 5 of this Agreement survives.",  # a reference, not a heading
    ],
)
def test_numbers_in_wrapped_text_do_not_start_a_clause(line):
    clauses = split_text(f"1. Fees. Beta shall pay\n{line}\n")

    assert numbers(clauses) == ["1"]


def test_article_and_section_keywords():
    clauses = split_text(
        "ARTICLE I\nDEFINITIONS\nWords have meanings.\n"
        "Section 1.1 Services. The work.\n"
        "ARTICLE II - PAYMENT\nPay on time.\n"
    )

    assert numbers(clauses) == ["I", "1.1", "II"]
    assert [clause.heading for clause in clauses] == [
        "DEFINITIONS",
        "Services",
        "PAYMENT",
    ]


def test_caps_heading_starts_a_clause_even_above_caps_text():
    clauses = split_text(
        "1. Fees. Pay on time.\n"
        "LIMITATION OF LIABILITY\n"
        "IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR\n"
        "ANY INDIRECT OR CONSEQUENTIAL DAMAGES.\n"
    )

    assert numbers(clauses) == ["1", None]
    assert clauses[1].heading == "LIMITATION OF LIABILITY"
    assert clauses[1].text.endswith("CONSEQUENTIAL DAMAGES.")


def test_text_before_the_first_clause_is_kept():
    clauses = split_text("This Agreement is made today.\n1. Term. Two years.\n")

    assert numbers(clauses) == [None, "1"]
    assert clauses[0].text == "This Agreement is made today."


def test_exhibit_restarts_the_numbering():
    clauses = split_text(
        "1. Term. Two years.\n2. Fees. Pay.\n3. Law. England.\n"
        "EXHIBIT A\nThe items below.\n1. First item.\n2. Second item.\n"
    )

    assert numbers(clauses) == ["1", "2", "3", None, "1", "2"]


def test_text_without_headings_is_split_into_paragraphs():
    text = "First paragraph here.\n\nSecond one\ncontinues.\n"

    clauses = split_text(text)

    assert [clause.text for clause in clauses] == [
        "First paragraph here.",
        "Second one continues.",
    ]
    assert numbers(clauses) == [None, None]
    assert text[clauses[1].start : clauses[1].end] == "Second one\ncontinues."


@pytest.mark.parametrize("text", ["", "   \n\n  "])
def test_empty_text_has_no_clauses(text):
    assert split_text(text) == []


def test_clauses_cite_their_pages():
    pages = [
        page(1, "1. Term. Two years.\n2. Fees. Beta shall pay"),
        page(2, "within 30 days.\n3. Law. England."),
    ]

    clauses = split_pages(pages)

    assert numbers(clauses) == ["1", "2", "3"]
    assert [(c.page_start, c.page_end) for c in clauses] == [(1, 1), (1, 2), (2, 2)]
    assert clauses[1].text == "2. Fees. Beta shall pay within 30 days."


def test_page_positions_match_the_document_text():
    pages = [page(1, "1. Term. Two years."), page(2, "2. Fees. Pay on time.")]
    text, page_starts = document_text(pages)

    assert text == "1. Term. Two years.\n2. Fees. Pay on time."
    assert page_starts == [0, 20]
    for clause in split_pages(pages):
        assert " ".join(text[clause.start : clause.end].split()) == clause.text


@pytest.mark.parametrize("footer", ["3", "Page 3", "Page 3 of 10", "3/10", "- 3 -"])
def test_page_numbers_are_left_out(footer):
    pages = [
        page(1, f"1. Term. Two years and\n{footer}"),
        page(2, "two months.\n2. Fees. Pay."),
    ]

    clauses = split_pages(pages)

    assert clauses[0].text == "1. Term. Two years and two months."
    assert (clauses[0].page_start, clauses[0].page_end) == (1, 2)


def test_short_sentences_are_not_mistaken_for_a_heading():
    clauses = split_text("1. Term. Two years.\n2. Law. England.\n")

    assert numbers(clauses) == ["1", "2"]
    assert clauses[1].heading == "Law"
    assert clauses[1].text == "2. Law. England."


def test_caps_heading_alone_passes_its_heading_to_the_next_clause():
    clauses = split_text(
        "1. Term. Two years.\nGOVERNING LAW\n2. This Agreement is English.\n"
    )

    assert numbers(clauses) == ["1", "2"]
    assert clauses[1].heading == "GOVERNING LAW"


def test_article_without_a_heading():
    clauses = split_text("ARTICLE 1\nthe parties agree as follows.\n")

    assert numbers(clauses) == ["1"]
    assert clauses[0].heading is None


def test_article_reference_does_not_start_a_clause():
    clauses = split_text("1. Fees. As set out in\nArticle 5 of the Schedule.\n")

    assert numbers(clauses) == ["1"]
