"""Split contract text into clauses with rules, keeping exact character positions.

A clause starts at the beginning of a line with a section number ("12.", "12.3"),
"Section 5", "ARTICLE IV", a short ALL-CAPS heading or a signature marker. Lettered
items such as (a) and (i) stay inside their clause. Table of contents lines, page
numbers and running headers are left out. Text with no headings is split into
paragraphs.
"""

import re
from bisect import bisect_right
from dataclasses import dataclass

from corneoscope.schemas.clause import Clause
from corneoscope.schemas.document import PageText

MAX_HEADING_WORDS = 8
MAX_CAPS_HEADING_WORDS = 6
# A heading in sentence case ("Grant-back license to Common Technology") can be longer
# than a Title Case one, because its small words are not capitalised.
MAX_SENTENCE_HEADING_WORDS = 12
# Words that make a line a sentence rather than a heading.
SENTENCE_WORDS = {
    "agree",
    "agrees",
    "are",
    "be",
    "been",
    "has",
    "have",
    "hereby",
    "is",
    "may",
    "mean",
    "means",
    "must",
    "shall",
    "that",
    "was",
    "were",
    "which",
    "will",
}
# A table of contents is a run of at least this many entries ending in page numbers.
MIN_CONTENTS_RUN = 3
# A line at the top or bottom of this many pages is a running header or footer.
MIN_HEADER_PAGES = 3
MAX_HEADER_CHARS = 80
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
NEW_NUMBERING = re.compile(
    r"(?:EXHIBIT|SCHEDULE|APPENDIX|ANNEX|ADDENDUM|AMENDMENT AGREEMENT|SIDE LETTER)\b"
)
# "Page 3", "3 of 10", "3/10", "- 3 -", and "3(6)" or "(6)" for page 3 of 6.
PAGE_NUMBER = re.compile(
    r"(?:page\s+)?\d{1,4}(?:\s*(?:of|/)\s*\d{1,4})?|-\s*\d{1,4}\s*-|\d{0,4}\s*\(\d{1,4}\)",
    re.I,
)
# "TERM AND TERMINATION 5" or "Payment .......... 12": a heading and its page.
CONTENTS_ENTRY = re.compile(r"(?P<title>.*?[^\s.])(?:\s*\.{2,}\s*|\s+)\d{1,3}")
CONTENTS_TITLE = re.compile(r"(?:table of )?contents|index", re.I)
SIGNATURE_MARKER = re.compile(
    r"[\[(]?\s*(?:signature pages?\s+(?:follows?|to follow)"
    r"|remainder of (?:this )?page (?:is )?(?:intentionally )?left blank)\b.*"
    r"|IN WITNESS WHEREOF\b.*",
    re.I,
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


def is_sentence_heading(phrase: str, following: Line | None) -> bool:
    """True for a heading in sentence case, such as "Grant-back license to Technology".

    It has no sentence words such as "shall", and the next line starts afresh.
    """
    words = phrase.split()
    if (
        not words
        or len(words) > MAX_SENTENCE_HEADING_WORDS
        or not words[0][0].isupper()
        or any(char in phrase for char in ",;")
        or any(word.lower() in SENTENCE_WORDS for word in words)
    ):
        return False
    return following is None or not following.text[0].islower()


def is_contents_entry(rest: str) -> bool:
    entry = CONTENTS_ENTRY.fullmatch(clean(rest))
    return bool(entry) and (is_caps(entry["title"]) or is_title(entry["title"]))


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


def accept_number(parts: list[int], last_top: int | None, heading: bool) -> bool:
    """Guard against numbers that only happen to start a wrapped line.

    Before any section is seen, a number above 3 needs a heading, so an excerpt that
    starts at "12. GOVERNING LAW" is still split.
    """
    first = parts[0]
    if len(parts) == 1:
        if last_top is None:
            return first <= 3 or heading
        return last_top < first <= last_top + 3
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
        and (
            is_title(whole)
            or (not rest.endswith(".") and is_sentence_heading(whole, following))
        )
    ):
        return whole, line.end, False
    inline = INLINE_HEADING.match(rest)
    if inline and is_title(inline["heading"]):
        return inline["heading"].strip(), line.start, False
    return None, line.start, False


def contents_runs(lines: list[Line]) -> list[list[int]]:
    """Table of contents entries: runs of numbered headings that end in a page number."""
    entries = []
    for index, line in enumerate(lines):
        match = NUMBERED.fullmatch(line.text) or SECTION.fullmatch(line.text)
        match = match or ARTICLE.fullmatch(line.text)
        if match and is_contents_entry(match["rest"]):
            entries.append(index)
    runs: list[list[int]] = []
    for index in entries:
        between = lines[runs[-1][-1] + 1 : index] if runs else []
        if runs and all(not line.text for line in between):
            runs[-1].append(index)
        else:
            runs.append([index])
    return [run for run in runs if len(run) >= MIN_CONTENTS_RUN]


def contents_starts(lines: list[Line], runs: list[list[int]]) -> dict[int, str | None]:
    """Where each table of contents begins: its title line if it has one, else its first entry.

    The table becomes a clause of its own, so its entries are not taken for sections.
    """
    found: dict[int, str | None] = {}
    for run in runs:
        title = next(
            (index for index in range(run[0] - 1, -1, -1) if lines[index].text), None
        )
        if title is not None and CONTENTS_TITLE.fullmatch(lines[title].text):
            found[title] = lines[title].text
        else:
            found[run[0]] = None
    return found


def contents_ends(
    lines: list[Line], runs: list[list[int]], page_starts: list[int]
) -> set[int]:
    """The first line on the page after each table of contents, where the next clause starts."""
    ends = set()
    for run in runs:
        last = lines[run[-1]].start
        next_page = next((start for start in page_starts if start > last), None)
        if next_page is None:
            continue
        first = next(
            (i for i, ln in enumerate(lines) if ln.text and ln.start >= next_page), None
        )
        if first is not None:
            ends.add(first)
    return ends


def find_starts(text: str, page_starts: list[int] | None = None) -> list[Start]:
    """last_top is the latest top-level number, so out-of-order numbers are rejected.

    page_starts, the positions where pages begin, let a table of contents end with
    its page.
    """
    lines = lines_of(text)
    runs = contents_runs(lines)
    contents = {index for run in runs for index in run}
    contents_begin = contents_starts(lines, runs)
    contents_end = contents_ends(lines, runs, page_starts or [])
    starts: list[Start] = []
    last_top: int | None = None
    skip = -1
    for index, line in enumerate(lines):
        if index in contents_begin:
            heading = contents_begin[index]
            body = line.end if heading else line.start
            starts.append(Start(line.start, None, heading, body))
            continue
        if index == skip or not line.text or index in contents:
            continue
        if index in contents_end and not (
            is_short_caps(line.text)
            or NUMBERED.fullmatch(line.text)
            or SECTION.fullmatch(line.text)
            or ARTICLE.fullmatch(line.text)
        ):
            starts.append(Start(line.start, None, None, line.start))
            continue
        following = next((ln for ln in lines[index + 1 :] if ln.text), None)
        previous = lines[index - 1].text if index else ""
        found = None

        if SIGNATURE_MARKER.fullmatch(line.text):
            # The signatures end a document, so the next one numbers from 1 again.
            last_top = None
            starts.append(Start(line.start, None, None, line.start))
            continue
        if match := ARTICLE.fullmatch(line.text):
            if starts_like_a_clause(clean(match["rest"])):
                found = (match["number"], match["rest"])
        elif match := SECTION.fullmatch(line.text):
            if starts_like_a_clause(clean(match["rest"])):
                found = (match["number"], match["rest"])
                last_top = int(match["number"].split(".")[0])
        elif match := NUMBERED.fullmatch(line.text):
            parts = [int(part) for part in match["number"].split(".")]
            has_heading = header(match["rest"], line, following)[0] is not None
            if (
                (match["dot"] or len(parts) > 1)
                and starts_like_a_clause(match["rest"])
                and accept_number(parts, last_top, has_heading)
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


def split_text(text: str, page_starts: list[int] | None = None) -> list[Clause]:
    """Split plain text into clauses; start and end are positions in text."""
    starts = find_starts(text, page_starts)
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


def header_key(line: str) -> str:
    """The letters of a line, so "Agreement 1(6)" and "Agreement 2(6)" match."""
    return "".join(char for char in line.lower() if char.isalpha())


def edge_lines(text: str) -> list[Line]:
    """The non-empty lines at the top and bottom of a page, up to 3 at each end."""
    lines = [line for line in lines_of(text) if line.text]
    return list({id(ln): ln for ln in lines[:3] + lines[-3:]}.values())


def could_be_header(line: str) -> bool:
    return (
        len(line) <= MAX_HEADER_CHARS
        and len(header_key(line)) >= 6
        and not SIGNATURE_MARKER.fullmatch(line)
        and not (
            NUMBERED.fullmatch(line)
            or SECTION.fullmatch(line)
            or ARTICLE.fullmatch(line)
        )
    )


def running_headers(pages: list[PageText]) -> set[str]:
    """Keys of lines at the top or bottom of at least MIN_HEADER_PAGES pages."""
    seen: dict[str, int] = {}
    for page in pages:
        keys = {
            header_key(line.text)
            for line in edge_lines(page.text)
            if could_be_header(line.text)
        }
        for key in keys:
            seen[key] = seen.get(key, 0) + 1
    return {key for key, count in seen.items() if count >= MIN_HEADER_PAGES}


def blank_page_numbers(text: str, headers: set[str] | None = None) -> str:
    """Replace page numbers and running headers at the top or bottom of a page with spaces.

    Spaces keep every other character at the same position. Only lines next to the
    edge are blanked: the first non-matching line from each end stops the search.
    """
    headers = headers or set()
    lines = [line for line in lines_of(text) if line.text]

    def is_noise(line: Line) -> bool:
        return bool(PAGE_NUMBER.fullmatch(line.text)) or (
            could_be_header(line.text) and header_key(line.text) in headers
        )

    noise = []
    for edge in (lines[:3], lines[::-1][:3]):
        for line in edge:
            if not is_noise(line):
                break
            noise.append(line)
    for line in noise:
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


def clean_document_text(pages: list[PageText]) -> str:
    """document_text with page numbers and running headers blanked to spaces.

    It has the same length, so a position in one is the same position in the other.
    """
    headers = running_headers(pages)
    return "\n".join(blank_page_numbers(page.text, headers) for page in pages)


def split_pages(pages: list[PageText]) -> list[Clause]:
    """Split PDF pages into clauses that cite their pages.

    start and end are positions in document_text(pages), the page texts joined
    with a newline. A clause's text leaves out page numbers and running headers.
    """
    _, page_starts = document_text(pages)
    cleaned = clean_document_text(pages)
    numbers = [page.number for page in pages]
    return [
        clause.model_copy(
            update={
                "page_start": numbers[bisect_right(page_starts, clause.start) - 1],
                "page_end": numbers[bisect_right(page_starts, clause.end - 1) - 1],
            }
        )
        for clause in split_text(cleaned, page_starts)
    ]
