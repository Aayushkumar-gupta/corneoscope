# Corneoscope

[![CI](https://github.com/Aayushkumar-gupta/corneoscope/actions/workflows/ci.yml/badge.svg)](https://github.com/Aayushkumar-gupta/corneoscope/actions/workflows/ci.yml)
![Python 3.13](https://img.shields.io/badge/python-3.13-blue)
![FastAPI](https://img.shields.io/badge/api-FastAPI-009688)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://pre-commit.com)

A document intelligence API for structured extraction, validation and comparison,
with evidence for every extracted value.

**Status:** early development. The upload endpoint checks files and reads PDF
text; no fields are extracted yet.

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
| `MAX_PAGES` | `20` | Most pages a PDF may have |
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

`POST /api/v1/extract` accepts one PDF, PNG or JPEG file up to 15 MB
(`MAX_UPLOAD_MB`) and, for PDFs, up to 20 pages (`MAX_PAGES`). The type is read from
the file's content, not its name.

The text of every PDF page is read. Pages with no text layer, such as scans, and all
images get a `no_text_layer` warning, because OCR is not available yet.

```bash
export API_KEY=$(grep '^API_KEY=' .env | cut -d= -f2)
curl -H "Authorization: Bearer $API_KEY" -F "file=@invoice.pdf" \
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
  "warnings": [
    {
      "code": "no_text_layer",
      "message": "Page 2 has no text layer; OCR is not available yet",
      "page": 2
    }
  ]
}
```

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
