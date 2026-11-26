from collections.abc import Sequence
from dataclasses import dataclass

from corneoscope.classify.labels import LABELS


@dataclass(frozen=True)
class LabelScore:
    label: str
    precision: float
    recall: float
    f1: float
    support: int


def ratio(part: int, whole: int) -> float:
    # A label never predicted (or never present) scores 0, not a division error.
    return part / whole if whole else 0.0


def score(
    truth: Sequence[frozenset[str]], predicted: Sequence[frozenset[str]]
) -> list[LabelScore]:
    scores = []
    for label in LABELS:
        hits = sum(
            label in t and label in p for t, p in zip(truth, predicted, strict=True)
        )
        actual = sum(label in t for t in truth)
        guessed = sum(label in p for p in predicted)
        precision, recall = ratio(hits, guessed), ratio(hits, actual)
        f1 = ratio(2 * precision * recall, precision + recall) if hits else 0.0
        scores.append(LabelScore(label, precision, recall, f1, actual))
    return scores


def macro_f1(scores: list[LabelScore]) -> float:
    """Every label counts the same, so rare clause types weigh as much as common ones."""
    return sum(item.f1 for item in scores) / len(scores)
