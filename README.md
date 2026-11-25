# Corneoscope

[![CI](https://github.com/Aayushkumar-gupta/corneoscope/actions/workflows/ci.yml/badge.svg)](https://github.com/Aayushkumar-gupta/corneoscope/actions/workflows/ci.yml)
![Python 3.13](https://img.shields.io/badge/python-3.13-blue)
![FastAPI](https://img.shields.io/badge/api-FastAPI-009688)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://pre-commit.com)

A document intelligence API for structured extraction, validation and comparison,
with evidence for every extracted value.

**Status:** early development. The upload endpoint checks files, reads PDF text and
accepts an extraction schema; no fields are extracted yet. Contracts can be split
into clauses that cite their pages, with a [dev command](#split-a-contract-into-clauses)
to try it.

## Setup

Requires Python 3.13.

```bash
git clone https://github.com/Aayushkumar-gupta/corneoscope.git
cd corneoscope
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .
cp .env.example .env
pre-commit install
```

Then set `API_KEY` in `.env` to a random value of at least 32 characters. This
command prints one:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Configuration

Settings are read from `.env`, and environment variables override it.

| Setting | Default | What it does |
| --- | --- | --- |
| `API_KEY` | None, required | Key every `/api/v1` request must send; at least 32 characters |
| `MAX_UPLOAD_MB` | `15` | Largest upload accepted |
| `MAX_PAGES` | `100` | Most pages a PDF may have |
| `APP_NAME` | `Corneoscope` | Name shown in the API docs |

## Run

```bash
uvicorn corneoscope.main:app --reload
```

API docs are at http://localhost:8000/docs.

## Authentication

Every `/api/v1` route needs the key from `API_KEY` in an `Authorization: Bearer`
header. `/health` and the API docs stay open. In the docs, click **Authorize** and
paste the key to try the routes.

## Upload a document

`POST /api/v1/extract` takes two form parts:

- `file`: one PDF, PNG or JPEG file up to 15 MB (`MAX_UPLOAD_MB`). A PDF can have up
  to 100 pages (`MAX_PAGES`). The type is read from the file's content, not its name.
- `schema`: a JSON string listing the fields to extract, described in
  [Extraction schema](#extraction-schema).

The text of every PDF page is read, and pages a person should check get a warning
with the page number:

- `no_text_layer`: the page has no text, such as a scan. Images always get it,
  because OCR is not available yet.
- `low_text_quality`: more than 10% of the page's characters are unreadable, which
  happens when a PDF's fonts do not map to real letters.

Field extraction is not available yet, so every field comes back with status
`error` and an `extraction_not_available` warning.

```bash
export API_KEY=$(grep '^API_KEY=' .env | cut -d= -f2)
curl -H "Authorization: Bearer $API_KEY" -F "file=@invoice.pdf" \
  -F 'schema={"fields": {"invoice_number": {"type": "string", "required": true}}}' \
  http://localhost:8000/api/v1/extract
```

```json
{
  "status": "parsed",
  "document": {
    "id": "doc_5114269d513347c8a90895570138f67b",
    "filename": "invoice.pdf",
    "media_type": "application/pdf",
    "size_bytes": 48213,
    "sha256": "5aea7a7a5e33d66d021fd52802ceb64ac5b8f377b2be55fddca8607f093ce3ce",
    "pages": 2
  },
  "schema_name": null,
  "schema_version": "1.0",
  "fields": {
    "invoice_number": {
      "key": "invoice_number",
      "value": null,
      "raw_value": null,
      "status": "error",
      "review_required": false,
      "evidence": [],
      "confidence": null,
      "warnings": [
        {
          "code": "extraction_not_available",
          "message": "Field extraction is not available yet",
          "page": null
        }
      ]
    }
  },
  "warnings": [
    {
      "code": "no_text_layer",
      "message": "Page 2 has no text layer; OCR is not available yet",
      "page": 2
    }
  ]
}
```

## Split a contract into clauses

```bash
python -m corneoscope.clauses contract.pdf
```

It takes a PDF. Run it from the project folder, since reading a PDF loads the
settings from `.env`.
It prints every clause with its number, heading and pages, then lists the pages that
need a person's review:

```text
[c1] MASTER SERVICES AGREEMENT (page 1)
    MASTER SERVICES AGREEMENT This Agreement is made between Acme and Beta.
[c2] 1.1 Definitions (page 1)
    1.1 "Services" means the work.
[c3] 2.1 TERMINATION (pages 1-2)
    2.1 Either party may end it on 30 days notice.
review: Page 3 has no text layer; OCR is not available yet
3 clauses from 3 pages
```

A clause starts at the beginning of a line with a section number (`12.`, `12.3`),
`Section 5`, `ARTICLE IV` or a short ALL-CAPS heading. Lettered items such as `(a)`
stay inside their clause, subsections take their section's heading, and page numbers
at the top or bottom of a page are left out. A document with no headings is split
into paragraphs.

Each clause records `start` and `end`, its character positions in the page texts
joined with a newline, so every clause can be traced back to its exact text.

## Train the clause model

```bash
python -m corneoscope.classify.train
```

It trains clause model v1 on [CUAD](https://www.atticusprojectai.org/cuad), 510
contracts labeled by lawyers, to label paragraphs with 12 clause types such as Governing
Law, Anti-Assignment and Cap On Liability. The first run downloads CUAD (106 MB) to
`data/cuad/`. Training takes under a minute and saves the model and its scores to
`models/`. Neither folder is committed.

On 85 held-out contracts the model scores 0.611 macro F1, 19.1 points above keyword
rules (0.420). The [model card](docs/model-card.md) has the score for each clause type
and the [dataset card](docs/dataset-card.md) has how the data is built and split.

## Extraction schema

```json
{
  "schema_name": "invoice",
  "schema_version": "1.0",
  "fields": {
    "invoice_number": {"type": "string", "required": true},
    "total_amount": {"type": "decimal"},
    "currency": {"type": "enum", "values": ["USD", "EUR", "INR"]}
  }
}
```

`schema_name` is optional and `schema_version` defaults to `"1.0"`; both are
returned with the result. `fields` holds 1 to 50 fields, and each field takes:

| Key | Required | Rule |
| --- | --- | --- |
| `type` | Yes | `string`, `integer`, `decimal`, `date`, `boolean` or `enum` |
| `required` | No | `true` or `false` (default) |
| `description` | No | Up to 500 characters, to say what the field means |
| `values` | Only for `enum` | 1 to 50 allowed values; not allowed on other types |

Field names use lowercase letters, digits and underscores, start with a letter, and
are at most 64 characters. Unknown keys are rejected, so a typo such as `requird`
returns `invalid_schema` instead of being ignored.

Each field result has:

| Key | Meaning |
| --- | --- |
| `key` | The field name from the schema |
| `value` | The extracted value, or `null`; dates and decimals are strings |
| `raw_value` | The exact text the value came from, or `null` |
| `status` | `found`, `missing`, `ambiguous`, `unsupported` or `error` |
| `review_required` | `true` when a person should check the value |
| `evidence` | Where the value was found: page, text and position |
| `confidence` | Always `null` until it can be calibrated on labeled data |
| `warnings` | Problems found while extracting this field |

## Errors

Every error response has the same shape, and every response, success or error,
carries an `X-Request-ID` header with the same ID:

```json
{
  "error": {
    "code": "not_found",
    "message": "Not Found",
    "request_id": "req_0d5670b7f6ca4020883991463feba29e"
  }
}
```

| HTTP | Code | When |
| --- | --- | --- |
| 400 | `invalid_request` | The request failed validation; `details` lists each problem |
| 400 | `invalid_schema` | The `schema` part is not valid; `details` lists each problem |
| 401 | `unauthorized` | Missing or wrong API key |
| 404 | `not_found` | Unknown route |
| 405 | `method_not_allowed` | Wrong HTTP method for the route |
| 413 | `file_too_large` | Upload is over `MAX_UPLOAD_MB` |
| 413 | `too_many_pages` | PDF has more pages than `MAX_PAGES` |
| 415 | `unsupported_media_type` | File content is not a PDF, PNG or JPEG |
| 422 | `unreadable_document` | PDF is damaged or password protected |
| 500 | `internal_error` | Unexpected server error; details are logged, never returned |

Quote the `request_id` when reporting a problem; the server log records the same ID.

## Test and lint

```bash
pytest
ruff check .
ruff format --check .
```

The pre-commit hooks run Ruff and the whitespace checks on every commit. To run
them on all files: `pre-commit run --all-files`.

## License

All rights reserved. See [LICENSE](LICENSE).
