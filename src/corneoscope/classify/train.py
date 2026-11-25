"""Train clause model v1 on CUAD and score it against the keyword baseline.

python -m corneoscope.classify.train
"""

import argparse
import json
import time
from dataclasses import asdict
from datetime import date
from pathlib import Path

import sklearn

from corneoscope.classify import keywords
from corneoscope.classify.cuad import DATA_DIR, Example, download, load_examples, split
from corneoscope.classify.labels import LABELS
from corneoscope.classify.metrics import LabelScore, macro_f1, score
from corneoscope.classify.model import ClauseModel

MODELS_DIR = Path("models")
MODEL_NAME = "clause-model-v1"
C_VALUES = (1.0, 4.0, 16.0)
ERROR_SAMPLES = 5
SAMPLE_CHARS = 300


def texts(examples: list[Example]) -> list[str]:
    return [example.text for example in examples]


def truth(examples: list[Example]) -> list[frozenset[str]]:
    return [example.labels for example in examples]


def summary(parts: dict[str, list[Example]]) -> dict:
    return {
        name: {
            "contracts": len({example.contract for example in examples}),
            "paragraphs": len(examples),
            "labels": {
                label: sum(label in example.labels for example in examples)
                for label in LABELS
            },
        }
        for name, examples in parts.items()
    }


def error_samples(examples: list[Example], predicted: list[frozenset[str]]) -> dict:
    samples = {}
    for label in LABELS:
        missed = [
            example.text[:SAMPLE_CHARS]
            for example, guess in zip(examples, predicted, strict=True)
            if label in example.labels and label not in guess
        ]
        wrong = [
            example.text[:SAMPLE_CHARS]
            for example, guess in zip(examples, predicted, strict=True)
            if label not in example.labels and label in guess
        ]
        samples[label] = {
            "missed": missed[:ERROR_SAMPLES],
            "wrongly_flagged": wrong[:ERROR_SAMPLES],
        }
    return samples


def print_table(model: list[LabelScore], baseline: list[LabelScore]) -> None:
    print(
        f"{'Label':30} {'Support':>7} {'Keywords F1':>11} {'P':>6} {'R':>6} {'F1':>6}"
    )
    for ours, theirs in zip(model, baseline, strict=True):
        print(
            f"{ours.label:30} {ours.support:7} {theirs.f1:11.3f} "
            f"{ours.precision:6.3f} {ours.recall:6.3f} {ours.f1:6.3f}"
        )
    print(
        f"{'Macro F1':30} {'':7} {macro_f1(baseline):11.3f} {'':13} {macro_f1(model):6.3f}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m corneoscope.classify.train",
        description="Train the clause model on CUAD and evaluate it on held-out contracts.",
    )
    parser.add_argument("--data", type=Path, default=DATA_DIR, help="CUAD folder")
    parser.add_argument("--out", type=Path, default=MODELS_DIR, help="output folder")
    args = parser.parse_args(argv)

    started = time.perf_counter()
    parts = split(load_examples(download(args.data)))
    train, validation, test = parts["train"], parts["validation"], parts["test"]
    for name, info in summary(parts).items():
        print(f"{name}: {info['contracts']} contracts, {info['paragraphs']} paragraphs")

    best: tuple[float, ClauseModel] | None = None
    for c in C_VALUES:
        model = ClauseModel(c).fit(texts(train), truth(train))
        model.tune_thresholds(texts(validation), truth(validation))
        result = macro_f1(score(truth(validation), model.predict(texts(validation))))
        print(f"C={c:g}: validation macro F1 {result:.3f}")
        if best is None or result > best[0]:
            best = (result, model)
    validation_f1, model = best

    # The test split is scored once, after every choice was made on validation.
    predicted = model.predict(texts(test))
    model_scores = score(truth(test), predicted)
    baseline_scores = score(truth(test), [keywords.predict(t) for t in texts(test)])
    print_table(model_scores, baseline_scores)

    args.out.mkdir(parents=True, exist_ok=True)
    model.save(args.out / f"{MODEL_NAME}.joblib")
    report = {
        "model": MODEL_NAME,
        "trained": date.today().isoformat(),
        "scikit_learn": sklearn.__version__,
        "c": model.c,
        "thresholds": dict(zip(LABELS, model.thresholds.tolist(), strict=True)),
        "split": summary(parts),
        "validation_macro_f1": validation_f1,
        "test": {
            "model_macro_f1": macro_f1(model_scores),
            "keywords_macro_f1": macro_f1(baseline_scores),
            "model": [asdict(item) for item in model_scores],
            "keywords": [asdict(item) for item in baseline_scores],
        },
        "errors": error_samples(test, predicted),
        "seconds": round(time.perf_counter() - started, 1),
    }
    report_path = args.out / f"{MODEL_NAME}.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"saved {args.out / MODEL_NAME}.joblib and {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
