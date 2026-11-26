"""Check the clause splitter against real contracts.

Each contract in tests/fixtures/contracts is a PDF plus a JSON file written by a
person from the PDF itself, never copied from the splitter's output. A check listed
under "known_failures" in the JSON is expected to fail; when a fix makes it pass,
pytest reports it as failed (XPASS strict) so the entry can be removed.

See tests/fixtures/contracts/README.md for how to add a contract.
"""

import json
from difflib import SequenceMatcher
from functools import cache
from pathlib import Path

import pytest

from corneoscope.clauses.splitter import clean_document_text, document_text, split_pages
from corneoscope.ingestion.pdf import parse_pdf

CONTRACTS = Path(__file__).parent / "fixtures" / "contracts"


@cache
def load(name: str):
    expected = json.loads((CONTRACTS / f"{name}.json").read_text())
    pages = parse_pdf((CONTRACTS / expected["pdf"]).read_bytes())
    return expected, pages, split_pages(pages)


def matched(expected: dict, clauses) -> list[tuple[dict, object]]:
    """Pair each expected clause with the found clause of the same number.

    Numbers repeat (each document in a PDF restarts at 1), so they are paired by
    the longest common sequence rather than by lookup.
    """
    want = [item["number"] for item in expected["clauses"]]
    found = [clause.number for clause in clauses]
    blocks = SequenceMatcher(None, want, found, autojunk=False).get_matching_blocks()
    return [
        (expected["clauses"][block.a + offset], clauses[block.b + offset])
        for block in blocks
        for offset in range(block.size)
    ]


def check_numbers(expected, pages, clauses):
    pairs = matched(expected, clauses)
    found = {id(item) for item, _ in pairs}
    missing = [
        f"{item['number']} (page {item['pages'][0]})"
        for item in expected["clauses"]
        if id(item) not in found
    ]
    assert not missing, f"{len(missing)} clauses not found: " + ", ".join(missing)


def check_headings(expected, pages, clauses):
    wrong = [
        f"{item['number']}: expected {item['heading']!r}, got {clause.heading!r}"
        for item, clause in matched(expected, clauses)
        if clause.heading != item["heading"]
    ]
    assert not wrong, "\n".join(wrong)


def check_pages(expected, pages, clauses):
    wrong = [
        f"{item['number']}: expected pages {item['pages']}, "
        f"got {[clause.page_start, clause.page_end]}"
        for item, clause in matched(expected, clauses)
        if [clause.page_start, clause.page_end] != item["pages"]
    ]
    assert not wrong, "\n".join(wrong)


def check_not_in_clause_text(expected, pages, clauses):
    found = [
        f"{text!r} in {clause.id}"
        for clause in clauses
        for text in expected["not_in_clause_text"]
        if text in clause.text
    ]
    assert not found, "\n".join(found)


# The keys are the names used under "known_failures" in a contract's JSON.
CHECKS = {
    "numbers": check_numbers,
    "headings": check_headings,
    "pages": check_pages,
    "not_in_clause_text": check_not_in_clause_text,
}


def cases():
    for path in sorted(CONTRACTS.glob("*.json")):
        failures = json.loads(path.read_text()).get("known_failures", {})
        for check in CHECKS:
            marks = []
            if check in failures:
                marks.append(pytest.mark.xfail(strict=True, reason=failures[check]))
            yield pytest.param(path.stem, check, marks=marks, id=f"{path.stem}-{check}")


@pytest.mark.parametrize(("name", "check"), list(cases()))
def test_contract(name, check):
    expected, pages, clauses = load(name)
    CHECKS[check](expected, pages, clauses)


@pytest.mark.parametrize(
    "name", [path.stem for path in sorted(CONTRACTS.glob("*.json"))]
)
def test_clauses_are_well_formed(name):
    """Rules every contract must follow, whatever its layout."""
    expected, pages, clauses = load(name)
    text, _ = document_text(pages)
    cleaned = clean_document_text(pages)

    assert len(pages) == expected["pages"]
    assert len(cleaned) == len(text)
    assert [clause.id for clause in clauses] == [
        f"c{n}" for n in range(1, len(clauses) + 1)
    ]
    for clause in clauses:
        assert " ".join(cleaned[clause.start : clause.end].split()) == clause.text
        assert text[clause.start] == cleaned[clause.start]
        assert text[clause.end - 1] == cleaned[clause.end - 1]
        assert 1 <= clause.page_start <= clause.page_end <= len(pages)
