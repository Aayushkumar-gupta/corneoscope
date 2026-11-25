import pytest

from corneoscope.classify.labels import LABELS
from corneoscope.classify.metrics import macro_f1, score

LAW = frozenset({"Governing Law"})
NONE = frozenset()


def by_label(scores):
    return {item.label: item for item in scores}


def test_perfect_predictions_score_one_for_present_labels():
    scores = by_label(score([LAW, NONE], [LAW, NONE]))

    assert scores["Governing Law"].f1 == 1.0
    assert scores["Governing Law"].support == 1


def test_precision_recall_and_f1():
    truth = [LAW, LAW, NONE, NONE]
    predicted = [LAW, NONE, LAW, LAW]

    law = by_label(score(truth, predicted))["Governing Law"]

    assert law.precision == pytest.approx(1 / 3)
    assert law.recall == pytest.approx(1 / 2)
    assert law.f1 == pytest.approx(0.4)


def test_a_label_never_predicted_scores_zero():
    law = by_label(score([LAW], [NONE]))["Governing Law"]

    assert (law.precision, law.recall, law.f1) == (0.0, 0.0, 0.0)


def test_macro_f1_weighs_every_label_the_same():
    truth = [LAW, frozenset({"Insurance"})]
    predicted = [LAW, NONE]

    assert macro_f1(score(truth, predicted)) == pytest.approx(1 / len(LABELS))
