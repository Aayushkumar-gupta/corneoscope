# Corneoscope

[![CI](https://github.com/Aayushkumar-gupta/corneoscope/actions/workflows/ci.yml/badge.svg)](https://github.com/Aayushkumar-gupta/corneoscope/actions/workflows/ci.yml)
![Python 3.13](https://img.shields.io/badge/python-3.13-blue)
![FastAPI](https://img.shields.io/badge/api-FastAPI-009688)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://pre-commit.com)

A document intelligence API for structured extraction, validation and comparison,
with evidence for every extracted value.

**Status:** early development. The upload endpoint checks files; no extraction is
implemented yet.

## Setup

Requires Python 3.13.

```bash
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .
cp .env.example .env
pre-commit install
```

## Run

```bash
uvicorn corneoscope.main:app --reload
```

API docs are at http://localhost:8000/docs.

## Upload a document

`POST /api/v1/extract` accepts one PDF, PNG or JPEG file up to 15 MB
(`MAX_UPLOAD_MB` in `.env`). The type is read from the file's content, not its name.

```bash
curl -F "file=@invoice.pdf" http://localhost:8000/api/v1/extract
```

```json
{
  "status": "validated",
  "document": {
    "id": "doc_5114269d513347c8a90895570138f67b",
    "filename": "invoice.pdf",
    "media_type": "application/pdf",
    "size_bytes": 48213,
    "sha256": "5aea7a7a5e33d66d021fd52802ceb64ac5b8f377b2be55fddca8607f093ce3ce"
  }
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
| 404 | `not_found` | Unknown route |
| 405 | `method_not_allowed` | Wrong HTTP method for the route |
| 413 | `file_too_large` | Upload is over `MAX_UPLOAD_MB` |
| 415 | `unsupported_media_type` | File content is not a PDF, PNG or JPEG |
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
