"""Cut a paragraph or clause into sentences for the sentence half of the clause model."""

import re
from itertools import pairwise

# Contracts list conditions as "(a) ...; (b) ...;", so a semicolon or colon also
# ends a sentence. Whitespace of any kind counts, so a text cuts the same way
# before and after its line breaks are joined.
SENTENCE_END = re.compile(r"(?<=[.;:])\s+(?=[A-Z(\"0-9])")
MIN_SENTENCE_CHARS = 3


def sentence_bounds(text: str) -> list[tuple[int, int]]:
    cuts = [0, *(match.end() for match in SENTENCE_END.finditer(text)), len(text)]
    return [
        (start, end)
        for start, end in pairwise(cuts)
        if len(text[start:end].strip()) >= MIN_SENTENCE_CHARS
    ]


def split_sentences(text: str) -> list[str]:
    """Never empty: a text too short to cut is its own sentence."""
    sentences = [
        " ".join(text[start:end].split()) for start, end in sentence_bounds(text)
    ]
    return sentences or [" ".join(text.split())]
