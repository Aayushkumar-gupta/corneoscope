# Corneoscope

A document intelligence API for structured extraction, validation and comparison,
with evidence for every extracted value.

**Status:** project setup. Only the health endpoint exists; no document processing
is implemented yet.

## Setup

Requires Python 3.13.

```bash
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .
cp .env.example .env
```

## Run

```bash
uvicorn corneoscope.main:app --reload
```

API docs are at http://localhost:8000/docs.

## Test

```bash
pytest
```

## License

All rights reserved. See [LICENSE](LICENSE).
