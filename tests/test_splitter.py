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
        (
            "3. Grant-back license to Common Technology",
            "Grant-back license to Common Technology",
        ),
        (
            "3. Warranties in relation to the Patents",
            "Warranties in relation to the Patents",
        ),
        ("3. Each party may assign its rights", None),
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


@pytest.mark.parametrize(
    "footer", ["3", "Page 3", "Page 3 of 10", "3/10", "- 3 -", "3(10)", "(10)"]
)
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


def test_a_sentence_case_line_that_runs_on_is_not_a_heading():
    clauses = split_text("1. Fees. Pay.\n2. Payment of the fees\nis due each month.\n")

    assert clauses[1].heading is None
    assert clauses[1].text == "2. Payment of the fees is due each month."


@pytest.mark.parametrize(
    "contents",
    [
        "TABLE OF CONTENTS\n1. DEFINITIONS 1\n2. TERM 2\n3. FEES 3\n",
        "Contents\n1. Definitions .......... 1\n2. Term .......... 2\n3. Fees ..... 3\n",
    ],
)
def test_table_of_contents_is_not_taken_for_sections(contents):
    clauses = split_text(
        contents + "1. DEFINITIONS\n1.1 Words mean things.\n"
        "2. TERM\n2.1 Two years.\n3. FEES\n3.1 Pay on time.\n"
    )

    assert numbers(clauses) == [None, "1.1", "2.1", "3.1"]
    assert clauses[0].heading == contents.split("\n")[0]
    assert [clause.heading for clause in clauses[1:]] == ["DEFINITIONS", "TERM", "FEES"]


def test_a_heading_that_ends_in_a_number_is_still_a_section():
    clauses = split_text("1. PHASE 2\nThe second phase.\n2. Fees. Pay.\n")

    assert numbers(clauses) == ["1", "2"]


def test_table_of_contents_ends_with_its_page():
    pages = [
        page(1, "CONTENTS\n1. TERM 2\n2. FEES 2\n3. LAW 2"),
        page(2, "This Agreement is made today.\n1. TERM\nTwo years.\n2. FEES\nPay."),
    ]

    clauses = split_pages(pages)

    assert [(c.number, c.heading) for c in clauses[:2]] == [
        (None, "CONTENTS"),
        (None, None),
    ]
    assert clauses[1].text == "This Agreement is made today."
    assert (clauses[0].page_end, clauses[1].page_start) == (1, 2)


@pytest.mark.parametrize(
    "marker",
    [
        "[Signature page follows]",
        "[SIGNATURE PAGE FOLLOWS]",
        "(Signature pages to follow)",
        "[Remainder of page intentionally left blank]",
        "IN WITNESS WHEREOF, the parties have signed this Agreement.",
    ],
)
def test_signature_marker_ends_the_last_clause(marker):
    clauses = split_text(
        f"1. Term. Two years.\n2. Law. England.\n{marker}\nAcme Inc.\n"
    )

    assert numbers(clauses) == ["1", "2", None]
    assert clauses[1].text == "2. Law. England."
    assert clauses[2].text.startswith(marker)


def test_numbering_restarts_after_the_signatures():
    clauses = split_text(
        "1. Term. Two years.\n3. Law. England.\n[Signature page follows]\nAcme Inc.\n"
        "1. Scope. This amendment changes clause 5.\n2. Effect. It starts today.\n"
    )

    assert numbers(clauses) == ["1", "3", None, "1", "2"]


@pytest.mark.parametrize("title", ["SIDE LETTER", "AMENDMENT AGREEMENT", "ADDENDUM"])
def test_a_new_document_restarts_the_numbering(title):
    clauses = split_text(
        f"1. Term. Two years.\n3. Law. England.\n{title}\nThe parties agree.\n"
        "1. Scope. It changes clause 5.\n"
    )

    assert numbers(clauses) == ["1", "3", None, "1"]


def test_an_excerpt_can_start_at_a_high_number():
    clauses = split_text("12. GOVERNING LAW\nNew York law.\n13. NOTICES\nBy post.\n")

    assert numbers(clauses) == ["12", "13"]
    assert [clause.heading for clause in clauses] == ["GOVERNING LAW", "NOTICES"]


def test_a_high_number_without_a_heading_does_not_start_a_clause():
    clauses = split_text("The term is\n12. the parties agree to it.\n")

    assert numbers(clauses) == [None]


def test_running_headers_are_left_out():
    pages = [
        page(n, f"Acme Supply Agreement {n}(3)\n{body}")
        for n, body in enumerate(
            ["1. Term. Two years and", "two months.\n2. Fees. Pay", "on time."], start=1
        )
    ]

    clauses = split_pages(pages)

    assert [clause.text for clause in clauses] == [
        "1. Term. Two years and two months.",
        "2. Fees. Pay on time.",
    ]
    assert (clauses[0].page_start, clauses[0].page_end) == (1, 2)


def test_a_line_on_only_two_pages_is_not_a_header():
    pages = [
        page(1, "Draft for review\n1. Term. Two years."),
        page(2, "Draft for review\n2. Fees. Pay."),
    ]

    clauses = split_pages(pages)

    assert clauses[0].text == "Draft for review"
