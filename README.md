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
pre-commit install
```

## Run

```bash
uvicorn corneoscope.main:app --reload
```

API docs are at http://localhost:8000/docs.

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
