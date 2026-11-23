"""Split contract text into clauses with rules, keeping exact character positions.

A clause starts at the beginning of a line with a section number ("12.", "12.3"),
"Section 5", "ARTICLE IV" or a short ALL-CAPS heading. Lettered items such as (a)
and (i) stay inside their clause. Text with no headings is split into paragraphs.
"""

import re
from bisect import bisect_right
from dataclasses import dataclass

from corneoscope.schemas.clause import Clause
from corneoscope.schemas.document import PageText

MAX_HEADING_WORDS = 8
MAX_CAPS_HEADING_WORDS = 6
SMALL_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}

ARTICLE = re.compile(
    r"(?:ARTICLE|Article)\s+(?P<number>[IVXLC]+|\d{1,3})\b(?P<rest>.*)"
)
SECTION = re.compile(
    r"(?:SECTION|Section)\s+(?P<number>\d{1,3}(?:\.\d{1,3}){0,3})\b(?P<rest>.*)"
)
NUMBERED = re.compile(
    r"(?P<number>\d{1,3}(?:\.\d{1,3}){0,3})(?P<dot>\.?)\s+(?P<rest>\S.*)"
)
INLINE_HEADING = re.compile(r"(?P<heading>[A-Z][^.:]{0,80}?)[.:]\s+\S")
NEW_NUMBERING = re.compile(r"(?:EXHIBIT|SCHEDULE|APPENDIX|ANNEX)\b")
PAGE_NUMBER = re.compile(
    r"(?:page\s+)?\d{1,4}(?:\s*(?:of|/)\s*\d{1,4})?|-\s*\d{1,4}\s*-", re.I
)
PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")
# Hyphen, en dash, em dash and other marks that can sit between a number and its heading.
LEADING_MARKS = "-\u2013\u2014:.) "


@dataclass
class Line:
    """One line of the text, with its surrounding whitespace removed.

    start and end are positions in the original text, so text[start:end] == text.
    """

    start: int
    end: int
    text: str


@dataclass
class Start:
    """The place where a clause begins, found by find_starts.

    offset is where the clause's first line begins. body_start is where the text
    after the heading begins; if nothing but whitespace lies between body_start
    and the next clause, the clause is only a heading.
    """

    offset: int
    number: str | None
    heading: str | None
    body_start: int


def lines_of(text: str) -> list[Line]:
    """Empty lines are kept (with empty text) so that positions stay in step."""
    lines = []
    offset = 0
    for raw in text.split("\n"):
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip())
        lines.append(Line(offset + indent, offset + indent + len(stripped), stripped))
        offset += len(raw) + 1
    return lines


def is_title(phrase: str) -> bool:
    """True for a short Title Case phrase such as "Termination for Convenience".

    Every word must start with a capital, a non-letter, or be a small word like
    "of". A sentence such as "The Supplier shall deliver" fails on "shall".
    """
    words = phrase.split()
    if not words or len(words) > MAX_HEADING_WORDS or not words[0][0].isupper():
        return False
    return all(
        word[0].isupper() or not word[0].isalpha() or word.lower() in SMALL_WORDS
        for word in words
    )


def is_caps(line: str) -> bool:
    letters = [char for char in line if char.isalpha()]
    return len(letters) >= 3 and line == line.upper()


def clean(rest: str) -> str:
    """Drop the marks between a number and its heading: "- PAYMENT" -> "PAYMENT"."""
    return rest.strip().lstrip(LEADING_MARKS).strip()


def is_short_caps(line: str) -> bool:
    return is_caps(line) and len(line.split()) <= MAX_CAPS_HEADING_WORDS


def starts_like_a_clause(rest: str) -> bool:
    # \u201c is a curly opening quote.
    return not rest or rest[0].isupper() or rest[0] in "\"'(\u201c"


def accept_number(parts: list[int], last_top: int | None) -> bool:
    """Guard against numbers that only happen to start a wrapped line."""
    first = parts[0]
    if len(parts) == 1:
        return first <= 3 if last_top is None else last_top < first <= last_top + 3
    return last_top is None or first in (last_top, last_top + 1)


def header(
    rest: str, line: Line, following: Line | None
) -> tuple[str | None, int, bool]:
    """Return the heading, where the body starts, and whether the next line was used."""
    rest = clean(rest)
    if not rest:
        if following and is_title(following.text.rstrip(".:")):
            return following.text.rstrip(".: "), following.end, True
        return None, line.end, False
    whole = rest.rstrip(".: ")
    # A heading on its own line has no sentence break inside, unlike "Law. England."
    if (
        not rest.endswith((",", ";"))
        and not any(c in whole for c in ".:")
        and is_title(whole)
    ):
        return whole, line.end, False
    inline = INLINE_HEADING.match(rest)
    if inline and is_title(inline["heading"]):
        return inline["heading"].strip(), line.start, False
    return None, line.start, False


def find_starts(text: str) -> list[Start]:
    """last_top is the latest top-level number, so out-of-order numbers are rejected."""
    lines = lines_of(text)
    starts: list[Start] = []
    last_top: int | None = None
    skip = -1
    for index, line in enumerate(lines):
        if index == skip or not line.text:
            continue
        following = next((ln for ln in lines[index + 1 :] if ln.text), None)
        previous = lines[index - 1].text if index else ""
        found = None

        if match := ARTICLE.fullmatch(line.text):
            if starts_like_a_clause(clean(match["rest"])):
                found = (match["number"], match["rest"])
        elif match := SECTION.fullmatch(line.text):
            if starts_like_a_clause(clean(match["rest"])):
                found = (match["number"], match["rest"])
                last_top = int(match["number"].split(".")[0])
        elif match := NUMBERED.fullmatch(line.text):
            parts = [int(part) for part in match["number"].split(".")]
            if (
                (match["dot"] or len(parts) > 1)
                and starts_like_a_clause(match["rest"])
                and accept_number(parts, last_top)
            ):
                found = (match["number"], match["rest"])
                last_top = parts[0]
        elif (
            is_short_caps(line.text)
            and not line.text.endswith((",", ";"))
            and not is_caps(previous)
            and not (following and is_short_caps(following.text))
        ):
            if NEW_NUMBERING.match(line.text):
                last_top = None
            starts.append(Start(line.start, None, line.text.rstrip(".: "), line.end))
            continue

        if found:
            number, rest = found
            heading, body_start, used_next = header(rest, line, following)
            if used_next and following:
                skip = lines.index(following)
            starts.append(Start(line.start, number, heading, body_start))
    return starts


def normalise(text: str) -> str:
    return " ".join(text.split())


def paragraphs(text: str) -> list[Clause]:
    """Fallback when no headings are found: one clause per blank-line paragraph."""
    edges = [0]
    for match in PARAGRAPH_BREAK.finditer(text):
        edges += [match.start(), match.end()]
    edges.append(len(text))
    clauses = []
    for begin, end in zip(edges[::2], edges[1::2], strict=True):
        piece = text[begin:end]
        if piece.strip():
            begin += len(piece) - len(piece.lstrip())
            end = begin + len(piece.strip())
            clauses.append(
                Clause(
                    id=f"c{len(clauses) + 1}",
                    number=None,
                    heading=None,
                    text=normalise(text[begin:end]),
                    start=begin,
                    end=end,
                )
            )
    return clauses


def split_text(text: str) -> list[Clause]:
    """Split plain text into clauses; start and end are positions in text."""
    starts = find_starts(text)
    if not starts:
        return paragraphs(text)

    first = starts[0].offset
    if text[:first].strip():
        begin = len(text) - len(text.lstrip())
        starts.insert(0, Start(begin, None, None, begin))

    clauses: list[Clause] = []
    headings: dict[str, str] = {}
    carried: str | None = None
    for index, start in enumerate(starts):
        limit = starts[index + 1].offset if index + 1 < len(starts) else len(text)
        end = start.offset + len(text[start.offset : limit].rstrip())

        heading = start.heading
        number = start.number
        parent = number
        while heading is None and parent and "." in parent:
            parent = parent.rsplit(".", 1)[0]
            heading = headings.get(parent)
        if heading is None:
            heading = carried
        carried = None
        if number and heading:
            headings[number] = heading

        if not text[start.body_start : end].strip():
            if number is None:
                carried = heading
            continue
        clauses.append(
            Clause(
                id=f"c{len(clauses) + 1}",
                number=number,
                heading=heading,
                text=normalise(text[start.offset : end]),
                start=start.offset,
                end=end,
            )
        )
    return clauses


def blank_page_numbers(text: str) -> str:
    """Replace a page-number line at the top or bottom of a page with spaces.

    Spaces keep every other character at the same position.
    """
    lines = [line for line in lines_of(text) if line.text]
    for line in {id(ln): ln for ln in (lines[:1] + lines[-1:])}.values():
        if PAGE_NUMBER.fullmatch(line.text):
            text = text[: line.start] + " " * (line.end - line.start) + text[line.end :]
    return text


def document_text(pages: list[PageText]) -> tuple[str, list[int]]:
    page_starts = []
    parts = []
    offset = 0
    for page in pages:
        page_starts.append(offset)
        parts.append(page.text)
        offset += len(page.text) + 1
    return "\n".join(parts), page_starts


def split_pages(pages: list[PageText]) -> list[Clause]:
    """Split PDF pages into clauses that cite their pages.

    start and end are positions in document_text(pages), the page texts joined
    with a newline.
    """
    _, page_starts = document_text(pages)
    cleaned = "\n".join(blank_page_numbers(page.text) for page in pages)
    numbers = [page.number for page in pages]
    return [
        clause.model_copy(
            update={
                "page_start": numbers[bisect_right(page_starts, clause.start) - 1],
                "page_end": numbers[bisect_right(page_starts, clause.end - 1) - 1],
            }
        )
        for clause in split_text(cleaned)
    ]
