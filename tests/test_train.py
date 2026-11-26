import json

from samples import make_cuad

from corneoscope.classify.labels import LABELS
from corneoscope.classify.train import main


def test_trains_scores_and_saves_the_model(tmp_path, capsys):
    paragraphs = [
        (f"The parties agree on topic{number}.", [label])
        for number, label in enumerate(LABELS)
    ] + [("Notices go to the addresses above.", [])]
    data = make_cuad({f"Contract {n}": paragraphs for n in range(30)})
    (tmp_path / "CUAD_v1.json").write_text(json.dumps(data))
    out = tmp_path / "models"

    assert main(["--data", str(tmp_path), "--out", str(out)]) == 0

    report = json.loads((out / "clause-model-v2.json").read_text())
    assert (out / "clause-model-v2.joblib").exists()
    assert sum(part["contracts"] for part in report["split"].values()) == 30
    assert report["test"]["model_macro_f1"] == 1.0
    assert set(report["thresholds"]) == set(LABELS)
    assert "Macro F1" in capsys.readouterr().out
