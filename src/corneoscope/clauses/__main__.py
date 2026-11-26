"""Print the clauses of a PDF: python -m corneoscope.clauses contract.pdf"""

import argparse
import sys
import textwrap
from pathlib import Path

from corneoscope.clauses.splitter import split_pages
from corneoscope.core.errors import AppError
from corneoscope.ingestion.pdf import parse_pdf
from corneoscope.ingestion.quality import page_warning


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m corneoscope.clauses",
        description="Split a PDF into clauses and print each one with its pages.",
    )
    parser.add_argument("pdf", type=Path, help="path to a PDF file")
    args = parser.parse_args(argv)

    try:
        pages = parse_pdf(args.pdf.read_bytes())
    except OSError as exc:
        print(f"error: cannot read {args.pdf}: {exc.strerror}", file=sys.stderr)
        return 1
    except AppError as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return 1

    clauses = split_pages(pages)
    for clause in clauses:
        pages_cited = (
            f"page {clause.page_start}"
            if clause.page_start == clause.page_end
            else f"pages {clause.page_start}-{clause.page_end}"
        )
        title = " ".join(part for part in (clause.number, clause.heading) if part)
        print(f"[{clause.id}] {title or '(no heading)'} ({pages_cited})")
        print(textwrap.indent(textwrap.shorten(clause.text, 300), "    "))
    for page in pages:
        if warning := page_warning(page):
            print(f"review: {warning.message}")
    print(f"{len(clauses)} clauses from {len(pages)} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
