import pytest
from fastapi.testclient import TestClient
from samples import make_pdf

from corneoscope.api.analyze import get_model
from corneoscope.classify.labels import LABELS
from corneoscope.classify.model import ClauseModel
from corneoscope.core.config import settings
from corneoscope.main import app
from corneoscope.pipeline.analyze import (
    LONG_CLAUSE_CHARS,
    analyze_pages,
    label_clause,
    load_model,
)
from corneoscope.schemas.document import PageText

client = TestClient(
    app, headers={"Authorization": f"Bearer {settings.API_KEY.get_secret_value()}"}
)

CONTRACT = make_pdf(
    [
        "1. Scope\nThe parties agree on topic0 in full.\n"
        "2. Notices\nThe parties agree that notices go out by post.",
        "3. Fees\nThe parties agree on topic2 and the fee is",
        "paid on topic2 terms each month.",
    ]
)


@pytest.fixture(scope="module")
def model():
    """Each label gets its own made-up word; plain paragraphs get none."""
    texts, labels = [], []
    for number, label in enumerate(LABELS):
        for variant in range(4):
            texts.append(f"the parties agree on topic{number} in case {variant}")
            labels.append(frozenset({label}))
    for variant in range(12):
        texts.append(f"the parties agree that notices go out in case {variant}")
        labels.append(frozenset())
    return ClauseModel().fit(texts, labels)


@pytest.fixture
def with_model(model):
    app.dependency_overrides[get_model] = lambda: model
    yield
    app.dependency_overrides.clear()


def page(number: int, text: str) -> PageText:
    return PageText(number=number, width=612, height=792, text=text, blocks=[])


def analyze(content: bytes, filename: str = "contract.pdf"):
    return client.post("/api/v1/analyze", files={"file": (filename, content)})


def test_a_score_at_or_above_its_threshold_gives_the_label():
    scores = [0.0] * len(LABELS)
    scores[0], scores[1] = 0.9, 0.95
    thresholds = [0.5] * len(LABELS)

    labels, warnings = label_clause(scores, thresholds, page=1)

    assert [item.label for item in labels] == [LABELS[1], LABELS[0]]
    assert labels[0].score == 0.95
    assert labels[0].threshold == 0.5
    assert warnings == []


@pytest.mark.parametrize("score", [0.45, 0.55])
def test_a_score_near_its_threshold_needs_review(score):
    scores = [0.0] * len(LABELS)
    scores[3] = score

    labels, warnings = label_clause(scores, [0.5] * len(LABELS), page=4)

    assert [item.label for item in labels] == ([LABELS[3]] if score >= 0.5 else [])
    assert [(w.code, w.page) for w in warnings] == [("low_confidence", 4)]
    assert LABELS[3] in warnings[0].message


def test_analyzes_a_contract(with_model):
    response = analyze(CONTRACT)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "analyzed"
    assert body["model"] == settings.MODEL_PATH.stem
    assert body["document"]["pages"] == 3
    assert [c["number"] for c in body["clauses"]] == ["1", "2", "3"]
    labels = [[item["label"] for item in c["labels"]] for c in body["clauses"]]
    assert labels == [[LABELS[0]], [], [LABELS[2]]]
    assert body["warnings"] == []


def test_every_clause_cites_its_text_on_each_page(with_model):
    body = analyze(CONTRACT).json()

    fees = body["clauses"][2]
    assert (fees["page_start"], fees["page_end"]) == (2, 3)
    assert [(e["page"], e["text"]) for e in fees["evidence"]] == [
        (2, "3. Fees\nThe parties agree on topic2 and the fee is"),
        (3, "paid on topic2 terms each month."),
    ]
    assert {e["method"] for e in fees["evidence"]} == {"text_layer"}
    assert {e["document_id"] for e in fees["evidence"]} == {body["document"]["id"]}


def test_a_clause_on_a_page_that_needs_review_is_flagged(model):
    pages = [
        page(1, "1. Scope\nThe parties agree on topic0."),
        page(2, "2. Fees\n" + "\ufffd" * 40),
    ]

    clauses, warnings = analyze_pages(pages, model, "doc_1")

    assert [(w.code, w.page) for w in warnings] == [("low_text_quality", 2)]
    scope, fees = clauses
    assert not scope.review_required
    assert fees.review_required
    assert ("page_needs_review", 2) in [(w.code, w.page) for w in fees.warnings]


def test_a_very_long_clause_is_flagged(model):
    text = "1. Scope\n" + "The parties agree on many things. " * 150

    clauses, _ = analyze_pages([page(1, text)], model, "doc_1")

    assert len(clauses[0].text) > LONG_CLAUSE_CHARS
    assert clauses[0].review_required
    assert "long_clause" in [w.code for w in clauses[0].warnings]


def test_pages_without_text_give_no_clauses_and_a_warning(model):
    clauses, warnings = analyze_pages([page(1, "")], model, "doc_1")

    assert clauses == []
    assert [w.code for w in warnings] == ["no_text_layer"]


def test_analyzes_a_100_page_contract(with_model):
    pages = [
        f"{n}. Section {n}\nThe parties agree on topic{n % 12}." for n in range(100)
    ]

    response = analyze(make_pdf(pages))

    assert response.status_code == 200
    assert response.json()["document"]["pages"] == 100


def test_images_are_rejected(with_model):
    response = analyze(b"\x89PNG\r\n\x1a\n" + b"0" * 20, "scan.png")

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"


def test_needs_an_api_key(with_model):
    response = TestClient(app).post(
        "/api/v1/analyze", files={"file": ("contract.pdf", CONTRACT)}
    )

    assert response.status_code == 401


def test_a_missing_model_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MODEL_PATH", tmp_path / "missing.joblib")

    response = analyze(CONTRACT)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_not_available"


def test_the_model_is_loaded_once_from_its_file(model, tmp_path, monkeypatch):
    path = tmp_path / "clause-model-v1.joblib"
    model.save(path)
    monkeypatch.setattr(settings, "MODEL_PATH", path)

    try:
        assert get_model() is get_model()
        assert get_model().thresholds.tolist() == model.thresholds.tolist()
    finally:
        load_model.cache_clear()
