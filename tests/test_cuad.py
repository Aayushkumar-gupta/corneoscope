import hashlib
import io
import json
import zipfile

import pytest
from samples import make_cuad

from corneoscope.classify import cuad
from corneoscope.classify.cuad import contract_examples, load_examples, split, split_of


def examples_of(paragraphs):
    contract = make_cuad({"Acme": paragraphs})["data"][0]["paragraphs"][0]
    return contract_examples("Acme", contract["context"], contract["qas"])


def test_each_paragraph_is_an_example_with_its_labels():
    examples = examples_of(
        [
            ("This Agreement is governed by Delaware law.", ["Governing Law"]),
            ("Beta may audit\n   the records.", ["Audit Rights"]),
            ("Notices go to the addresses above.", []),
        ]
    )

    assert [(e.text, set(e.labels)) for e in examples] == [
        ("This Agreement is governed by Delaware law.", {"Governing Law"}),
        ("Beta may audit the records.", {"Audit Rights"}),
        ("Notices go to the addresses above.", set()),
    ]
    assert {e.contract for e in examples} == {"Acme"}


def test_labels_outside_the_label_set_are_ignored():
    examples = examples_of([("Acme Corp and Beta LLC", ["Parties"])])

    assert examples[0].labels == frozenset()


def test_a_span_over_two_paragraphs_labels_both():
    data = make_cuad({"Acme": [("First part.", []), ("Second part.", [])]})
    contract = data["data"][0]["paragraphs"][0]
    contract["qas"] = [
        {
            "question": 'Highlight the parts related to "Insurance" that should be',
            "answers": [{"text": contract["context"], "answer_start": 0}],
        }
    ]

    examples = contract_examples("Acme", contract["context"], contract["qas"])

    assert [set(e.labels) for e in examples] == [{"Insurance"}, {"Insurance"}]


@pytest.mark.parametrize(
    ("title", "side"),
    [
        ("Contract 0", "train"),
        ("Contract 1", "train"),
        ("Contract 2", "validation"),
        ("Contract 3", "validation"),
        ("Contract 4", "test"),
        ("Contract 5", "test"),
    ],
)
def test_split_is_the_same_on_every_machine(title, side):
    assert split_of(title) == side


def test_split_shares_are_70_15_15():
    shares = dict.fromkeys(("train", "validation", "test"), 0)
    for n in range(2000):
        shares[split_of(f"Contract {n}")] += 1

    assert 0.65 < shares["train"] / 2000 < 0.75
    assert 0.11 < shares["validation"] / 2000 < 0.19
    assert 0.11 < shares["test"] / 2000 < 0.19


def test_paragraphs_of_one_contract_stay_in_one_split(tmp_path):
    path = tmp_path / "CUAD_v1.json"
    paragraphs = [(f"Paragraph {n}.", []) for n in range(5)]
    path.write_text(json.dumps(make_cuad({f"C{n}": paragraphs for n in range(40)})))

    parts = split(load_examples(path))

    contracts = [{e.contract for e in part} for part in parts.values()]
    assert sum(len(names) for names in contracts) == 40
    assert not contracts[0] & contracts[1]
    assert not contracts[0] & contracts[2]
    assert not contracts[1] & contracts[2]


def zipped_cuad() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr(cuad.JSON_MEMBER, json.dumps(make_cuad({})))
    return buffer.getvalue()


def test_download_checks_and_unpacks_the_archive(tmp_path, monkeypatch):
    archive = zipped_cuad()
    monkeypatch.setattr(cuad, "SHA256", hashlib.sha256(archive).hexdigest())
    monkeypatch.setattr(cuad, "fetch", lambda url, path: path.write_bytes(archive))

    path = cuad.download(tmp_path)

    assert path == tmp_path / "CUAD_v1.json"
    assert json.loads(path.read_text())["data"] == []


def test_download_rejects_an_archive_with_the_wrong_checksum(tmp_path, monkeypatch):
    monkeypatch.setattr(cuad, "fetch", lambda url, path: path.write_bytes(b"junk"))

    with pytest.raises(RuntimeError, match="checksum"):
        cuad.download(tmp_path)

    assert not (tmp_path / "CUAD_v1.zip").exists()
    assert not (tmp_path / "CUAD_v1.json").exists()


def test_download_skips_the_network_when_the_data_is_there(tmp_path, monkeypatch):
    (tmp_path / "CUAD_v1.json").write_text("{}")
    monkeypatch.setattr(cuad, "fetch", lambda url, path: pytest.fail("fetched"))

    assert cuad.download(tmp_path) == tmp_path / "CUAD_v1.json"
